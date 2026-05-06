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
    """Parse one vault file and add its triples to graph g."""
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

    # Wikilinks
    for linked_title in _WIKILINK_RE.findall(text):
        linked = URIRef(_note_uri(linked_title.strip()))
        g.add((note, KN.linksTo, linked))

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


def _declare_ontology(g, KN, RDF, OWL, RDFS, XSD) -> None:
    g.bind("kn", KN)
    g.bind("owl", OWL)
    g.bind("xsd", XSD)
    for cls in (KN.Note, KN.Task, KN.Tag):
        g.add((cls, RDF.type, OWL.Class))
    for prop in (KN.path, KN.title, KN.modified, KN.text, KN.file,
                 KN.dueDate, KN.priority, KN.name, KN.isDone):
        g.add((prop, RDF.type, OWL.DatatypeProperty))
    for prop in (KN.hasTag, KN.linksTo, KN.hasTask):
        g.add((prop, RDF.type, OWL.ObjectProperty))


# ── Public API ────────────────────────────────────────────────────────────────

def run(full_rebuild: bool = False) -> dict:
    """
    Incremental update of the knowledge graph.
    Only re-indexes files whose mtime has changed.
    Returns {indexed, skipped, removed}.
    """
    from rdflib import Graph, Namespace
    from rdflib.namespace import RDF, OWL, RDFS, XSD

    KN = Namespace(KN_BASE)

    vault_dir = Path(config.paths.obsidian())
    if not vault_dir.is_dir():
        return {"error": "Vault directory not found", "indexed": 0, "skipped": 0, "removed": 0}

    g = Graph() if full_rebuild else _load_graph()
    mtimes = {} if full_rebuild else _load_mtimes()

    _declare_ontology(g, KN, RDF, OWL, RDFS, XSD)

    stats = {"indexed": 0, "skipped": 0, "removed": 0}
    new_mtimes: dict = {}
    current_paths: set = set()

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
        return {"triples": 0, "notes": 0, "tasks": 0, "tags": 0}

    from rdflib import Namespace
    from rdflib.namespace import RDF
    KN = Namespace(KN_BASE)
    g = _load_graph()

    return {
        "triples": len(g),
        "notes":   sum(1 for _ in g.subjects(RDF.type, KN.Note)),
        "tasks":   sum(1 for _ in g.subjects(RDF.type, KN.Task)),
        "tags":    sum(1 for _ in g.subjects(RDF.type, KN.Tag)),
    }


if __name__ == "__main__":
    import sys
    full = "--rebuild" in sys.argv
    print("Running knowledge graph update" + (" (full rebuild)" if full else " (incremental)") + "...")
    result = run(full_rebuild=full)
    print(f"Done — {result['indexed']} indexed, {result['skipped']} skipped, {result['removed']} removed")
    s = graph_stats()
    print(f"Graph: {s['triples']} triples · {s['notes']} notes · {s['tasks']} tasks · {s['tags']} tags")
