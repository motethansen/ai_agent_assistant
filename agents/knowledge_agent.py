"""
Knowledge graph agent — incremental OWL/RDF index of the Obsidian vault.

Runs once daily via cron. Only processes files whose mtime has changed.
Persists to output/knowledge_graph.ttl (human-readable Turtle).
Exposes a SPARQL query interface for other agents.

Usage:
    from agents.knowledge_agent import run, query, stats
    run()                        # incremental update
    run(full_rebuild=True)       # wipe and rebuild from scratch
    results = query(\"\"\"
        PREFIX kn: <http://knowledgebase.local/>
        SELECT ?text ?due WHERE {
            ?t a kn:Task ; kn:text ?text ; kn:isDone false .
            OPTIONAL { ?t kn:dueDate ?due }
        } ORDER BY ?due
    \"\"\")
"""

import datetime
import hashlib
import json
import os
import re
from pathlib import Path

import config
from integrations.obsidian import parse_task_metadata, _TASK_RE, _TAG_RE

# ── Paths ─────────────────────────────────────────────────────────────────────

_GRAPH_FILE  = Path(config.paths.output()) / "knowledge_graph.ttl"
_MTIMES_FILE = Path(config.paths.output()) / ".kg_mtimes.json"

_EXCLUDE_DIRS = {
    ".obsidian", ".stfolder", ".claude", "assets", "Attachments",
    "990 Attachments", "910 PDF_PNG", "Clippings", "whiteboards", "export",
}

KN_BASE = "http://knowledgebase.local/"
_WIKILINK_RE = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')
# File extensions that are never note targets — used to skip ![[image.png]] embeds
_NON_NOTE_EXT = re.compile(
    r'\.(png|jpg|jpeg|gif|svg|pdf|mp4|mp3|webp|ico|bmp|tiff?|zip|docx?|xlsx?|pptx?)$',
    re.IGNORECASE,
)


# ── URI helpers ───────────────────────────────────────────────────────────────

def _note_uri(path: str) -> str:
    return KN_BASE + "note_" + hashlib.sha1(path.encode()).hexdigest()[:10]


def _task_uri(path: str, line: int) -> str:
    return KN_BASE + "task_" + hashlib.sha1(f"{path}:{line}".encode()).hexdigest()[:10]


def _tag_uri(tag: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_/]", "_", tag)
    return KN_BASE + "tag_" + safe


# ── Graph helpers ─────────────────────────────────────────────────────────────

def _load_graph():
    from rdflib import Graph
    g = Graph()
    if _GRAPH_FILE.exists():
        try:
            g.parse(str(_GRAPH_FILE), format="turtle")
        except Exception:
            pass  # corrupt graph — start fresh
    return g


def _save_graph(g) -> None:
    _GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(_GRAPH_FILE), format="turtle")


def _load_mtimes() -> dict:
    try:
        return json.loads(_MTIMES_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_mtimes(mtimes: dict) -> None:
    _MTIMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MTIMES_FILE.write_text(json.dumps(mtimes, indent=2))


def _remove_note_triples(g, KN, rel_path: str) -> None:
    """Remove all triples for a note (and its tasks) from the graph."""
    from rdflib import URIRef, Literal
    note = URIRef(_note_uri(rel_path))
    g.remove((note, None, None))
    g.remove((None, None, note))
    for task in list(g.subjects(KN.file, Literal(rel_path))):
        g.remove((task, None, None))
        g.remove((None, None, task))


def _index_file(g, KN, RDF, XSD, abs_path: Path, rel_path: str) -> None:
    """Parse one vault file and add note/tag/task triples to graph g.
    Wikilink resolution is handled separately in _build_links."""
    from rdflib import URIRef, Literal

    try:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    note = URIRef(_note_uri(rel_path))
    g.add((note, RDF.type, KN.Note))
    g.add((note, KN.path, Literal(rel_path)))
    g.add((note, KN.title, Literal(abs_path.stem)))
    g.add((note, KN.modified, Literal(
        datetime.datetime.fromtimestamp(abs_path.stat().st_mtime).isoformat()
    )))

    # Tags (scan first 4K chars — frontmatter + opening content)
    for tag in set(_TAG_RE.findall(text[:4000])):
        tag_node = URIRef(_tag_uri(tag))
        g.add((note, KN.hasTag, tag_node))
        g.add((tag_node, RDF.type, KN.Tag))
        g.add((tag_node, KN.name, Literal(tag)))

    # Tasks
    for line_num, raw_line in enumerate(text.splitlines(), start=1):
        if not _TASK_RE.match(raw_line):
            continue
        meta = parse_task_metadata(raw_line)
        if not meta:
            continue
        task = URIRef(_task_uri(rel_path, line_num))
        g.add((task, RDF.type, KN.Task))
        g.add((task, KN.text, Literal(meta.get("text", ""))))
        g.add((task, KN.isDone, Literal(meta.get("is_done", False), datatype=XSD.boolean)))
        g.add((task, KN.file, Literal(rel_path)))
        g.add((note, KN.hasTask, task))
        if meta.get("due_date"):
            g.add((task, KN.dueDate, Literal(str(meta["due_date"]))))
        if meta.get("priority"):
            g.add((task, KN.priority, Literal(meta["priority"])))


def _build_links(g, KN, vault_dir: Path, current_paths: set) -> dict:
    """
    Rebuild ALL linksTo triples from scratch using a resolved title→path index.
    Runs on every update (fast — regex only) so link targets are always current.

    Obsidian resolution rules applied:
    - Case-insensitive title match
    - Shortest path wins when multiple notes share a title (Obsidian's disambiguation)
    - Dangling links are kept with a kn:danglingLink flag so broken links are queryable

    Returns {resolved, dangling}.
    """
    from rdflib import URIRef, Literal

    # Remove all stale linksTo triples
    g.remove((None, KN.linksTo, None))
    g.remove((None, KN.danglingLink, None))

    # Build title → shortest-path index (case-insensitive)
    title_index: dict[str, str] = {}
    for path in current_paths:
        title = Path(path).stem.lower()
        if title not in title_index or len(path) < len(title_index[title]):
            title_index[title] = path

    stats = {"resolved": 0, "dangling": 0}

    for rel_path in current_paths:
        abs_path = vault_dir / rel_path
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        source = URIRef(_note_uri(rel_path))
        seen_targets: set = set()  # deduplicate per-file

        for raw_title in _WIKILINK_RE.findall(text):
            title = raw_title.strip()
            # Skip image/file embeds (![[image.png]]) and relative paths
            if title.startswith("./") or title.startswith("../") or _NON_NOTE_EXT.search(title):
                continue
            key = title.lower()
            if key in seen_targets:
                continue
            seen_targets.add(key)

            resolved_path = title_index.get(key)
            if resolved_path:
                target = URIRef(_note_uri(resolved_path))
                stats["resolved"] += 1
            else:
                # Dangling link — record so broken-link queries work
                target = URIRef(KN_BASE + "dangling_" + hashlib.sha1(key.encode()).hexdigest()[:10])
                g.add((target, KN.title, Literal(title)))
                g.add((target, KN.danglingLink, Literal(True)))
                stats["dangling"] += 1

            g.add((source, KN.linksTo, target))

    return stats


def _declare_ontology(g, KN, RDF, OWL, RDFS, XSD) -> None:
    g.bind("kn", KN)
    g.bind("owl", OWL)
    g.bind("xsd", XSD)
    for cls in (KN.Note, KN.Task, KN.Tag):
        g.add((cls, RDF.type, OWL.Class))
    for prop in (KN.path, KN.title, KN.modified, KN.text, KN.file,
                 KN.dueDate, KN.priority, KN.name, KN.isDone, KN.danglingLink):
        g.add((prop, RDF.type, OWL.DatatypeProperty))
    for prop in (KN.hasTag, KN.linksTo, KN.hasTask):
        g.add((prop, RDF.type, OWL.ObjectProperty))


# ── Public API ────────────────────────────────────────────────────────────────

def run(full_rebuild: bool = False) -> dict:
    """
    Incremental update of the knowledge graph.
    Note/tag/task triples: only re-indexed when mtime changes.
    linksTo triples: always rebuilt from scratch (fast regex pass) so
    renamed targets are immediately reflected without a full rebuild.
    Returns {indexed, skipped, removed, links_resolved, links_dangling}.
    """
    from rdflib import Graph, Namespace
    from rdflib.namespace import RDF, OWL, RDFS, XSD

    KN = Namespace(KN_BASE)

    vault_dir = Path(config.paths.obsidian())
    if not vault_dir.is_dir():
        return {"error": "Vault directory not found", "indexed": 0, "skipped": 0,
                "removed": 0, "links_resolved": 0, "links_dangling": 0}

    g = Graph() if full_rebuild else _load_graph()
    mtimes = {} if full_rebuild else _load_mtimes()

    _declare_ontology(g, KN, RDF, OWL, RDFS, XSD)

    stats = {"indexed": 0, "skipped": 0, "removed": 0,
             "links_resolved": 0, "links_dangling": 0}
    new_mtimes: dict = {}
    current_paths: set = set()

    # Phase 1 — re-index changed note/tag/task triples
    for dirpath, dirs, files in os.walk(vault_dir):
        dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            abs_path = Path(dirpath) / fname
            rel_path = str(abs_path.relative_to(vault_dir))
            current_paths.add(rel_path)

            current_mtime = abs_path.stat().st_mtime
            new_mtimes[rel_path] = current_mtime

            if not full_rebuild and mtimes.get(rel_path) == current_mtime:
                stats["skipped"] += 1
                continue

            _remove_note_triples(g, KN, rel_path)
            _index_file(g, KN, RDF, XSD, abs_path, rel_path)
            stats["indexed"] += 1

    # Prune deleted files
    for old_path in set(mtimes.keys()) - current_paths:
        _remove_note_triples(g, KN, old_path)
        stats["removed"] += 1

    # Phase 2 — rebuild ALL linksTo triples with title→path resolution
    link_stats = _build_links(g, KN, vault_dir, current_paths)
    stats["links_resolved"] = link_stats["resolved"]
    stats["links_dangling"] = link_stats["dangling"]

    _save_graph(g)
    _save_mtimes(new_mtimes)
    return stats


def query(sparql_str: str) -> list[dict]:
    """
    Execute a SPARQL SELECT query against the knowledge graph.
    Returns list of row dicts keyed by variable name.

    Example — open tasks sorted by due date:
        query(\"\"\"
            PREFIX kn: <http://knowledgebase.local/>
            SELECT ?text ?due ?priority ?file WHERE {
                ?t a kn:Task ; kn:text ?text ; kn:isDone false ; kn:file ?file .
                OPTIONAL { ?t kn:dueDate ?due }
                OPTIONAL { ?t kn:priority ?priority }
            } ORDER BY ?due
        \"\"\")

    Example — notes with a specific tag:
        query(\"\"\"
            PREFIX kn: <http://knowledgebase.local/>
            SELECT ?path WHERE { ?n a kn:Note ; kn:hasTag ?tag ; kn:path ?path .
                                  ?tag kn:name "dev" }
        \"\"\")
    """
    if not _GRAPH_FILE.exists():
        return []

    from rdflib import Namespace
    g = _load_graph()
    g.bind("kn", Namespace(KN_BASE))

    try:
        result = g.query(sparql_str)
        return [
            {str(var): str(val) if val is not None else "" for var, val in zip(result.vars, row)}
            for row in result
        ]
    except Exception as e:
        return [{"error": str(e)}]


def graph_stats() -> dict:
    """Return counts of nodes/triples in the graph."""
    if not _GRAPH_FILE.exists():
        return {"triples": 0, "notes": 0, "tasks": 0, "tags": 0,
                "links": 0, "dangling_links": 0}

    from rdflib import Namespace, Literal
    from rdflib.namespace import RDF
    KN = Namespace(KN_BASE)
    g = _load_graph()

    return {
        "triples":       len(g),
        "notes":         sum(1 for _ in g.subjects(RDF.type, KN.Note)),
        "tasks":         sum(1 for _ in g.subjects(RDF.type, KN.Task)),
        "tags":          sum(1 for _ in g.subjects(RDF.type, KN.Tag)),
        "links":         sum(1 for _ in g.triples((None, KN.linksTo, None))),
        "dangling_links": sum(1 for _ in g.subjects(KN.danglingLink, Literal(True))),
    }


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Build or update a SPARQL knowledge graph from an Obsidian vault.",
        epilog="""
Examples
--------
  # Use the vault configured in .config (WORKSPACE_DIR):
  python -m agents.knowledge_agent

  # Point at any Obsidian vault directly (no .config needed):
  python -m agents.knowledge_agent --vault ~/Documents/MyVault

  # Full rebuild (wipes existing graph):
  python -m agents.knowledge_agent --rebuild

  # Query the graph interactively after building:
  python - <<'EOF'
  from agents.knowledge_agent import query
  rows = query(\"\"\"
    PREFIX kn: <http://knowledgebase.local/>
    SELECT ?text ?due WHERE {
      ?t a kn:Task ; kn:text ?text ; kn:isDone false .
      OPTIONAL { ?t kn:dueDate ?due }
    } ORDER BY ?due LIMIT 20
  \"\"\")
  for r in rows: print(r)
  EOF
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--rebuild", action="store_true",
                        help="Wipe the existing graph and rebuild from scratch")
    parser.add_argument("--vault", metavar="PATH",
                        help="Path to Obsidian vault (overrides WORKSPACE_DIR in .config)")
    parser.add_argument("--output", metavar="PATH",
                        help="Directory for knowledge_graph.ttl and cache files "
                             "(default: output/ inside the project)")
    args = parser.parse_args()

    # Allow standalone use without a .config file
    if args.vault:
        import os
        os.environ["WORKSPACE_DIR"] = args.vault
        # reload config so the override takes effect
        import importlib
        import config as _cfg
        importlib.reload(_cfg)

    if args.output:
        _GRAPH_FILE  = Path(args.output) / "knowledge_graph.ttl"
        _MTIMES_FILE = Path(args.output) / ".kg_mtimes.json"
        Path(args.output).mkdir(parents=True, exist_ok=True)

    mode = "full rebuild" if args.rebuild else "incremental"
    vault_path = args.vault or config.paths.obsidian()
    print(f"Knowledge graph update ({mode})")
    print(f"Vault : {vault_path}")
    print(f"Output: {_GRAPH_FILE}")
    print()

    result = run(full_rebuild=args.rebuild)
    if result.get("error"):
        print(f"Error: {result['error']}")
        sys.exit(1)

    print(f"Notes  — {result['indexed']} indexed, {result['skipped']} skipped, {result['removed']} removed")
    print(f"Links  — {result['links_resolved']} resolved, {result['links_dangling']} dangling")
    s = graph_stats()
    print(f"Graph  — {s['triples']:,} triples · {s['notes']:,} notes · {s['tasks']:,} tasks · "
          f"{s['tags']:,} tags · {s['links']:,} links ({s['dangling_links']:,} dangling)")
