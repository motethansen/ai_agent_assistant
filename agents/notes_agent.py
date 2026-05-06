"""
Notes agent — organises Obsidian notes into better folders and suggests wikilinks.

NEVER rewrites note content. Only:
  1. Moves notes into better folders (PARA-lite structure)
  2. Appends wikilink suggestions at the bottom of notes

Always dry-runs first — caller must confirm before changes are applied.

Usage:
    result = run()              # analyse, return proposed changes
    apply(result['changes'])    # apply confirmed changes
"""

import json
import re
from pathlib import Path

from integrations.obsidian import ObsidianVault
import config
from llm import router

_SYSTEM_PROMPT = """You are a personal knowledge management assistant.
You help organise notes using the PARA method (Projects, Areas, Resources, Archive).
You suggest connections between notes using Obsidian wikilinks [[Note Title]].
Never rewrite or summarise note content — only suggest moves and links.
Always respond with valid JSON."""

_VAULT_FOLDERS = ["Projects", "Areas", "Resources", "Archive", "Inbox", "Daily"]

_ANALYSIS_PROMPT = """Analyse these Obsidian notes and suggest:
1. Which notes to move to better folders (PARA: Projects / Areas / Resources / Archive)
2. Wikilinks to add between related notes

Notes:
{notes_summary}

Respond ONLY with JSON in this exact format:
{{
  "moves": [
    {{"path": "current/path.md", "suggested_folder": "Resources/Dev", "reason": "reference material"}}
  ],
  "links": [
    {{"path": "note.md", "suggested_links": ["Related Note A", "Related Note B"], "reason": "both cover X"}}
  ]
}}

Rules:
- Only suggest moves if the note is clearly in the wrong folder
- Only suggest links if there is a real content relationship
- Use existing folder names: {folders}
- Keep moves and links lists short (top 10 each max)
- Do not suggest moving Daily notes or notes already in the right place"""


def _summarise_notes(notes: list[dict], max_notes: int = 80) -> str:
    """Format notes for LLM context — most recently modified first."""
    sorted_notes = sorted(notes, key=lambda n: n.get("mtime", 0), reverse=True)
    if len(sorted_notes) > max_notes:
        from ui.views import console
        console.print(
            f"[dim]Note: {len(sorted_notes)} notes found — analysing the {max_notes} "
            f"most recently modified. Use /organise <subfolder> to target a specific area.[/dim]"
        )
    lines = []
    for n in sorted_notes[:max_notes]:
        title = n["title"]
        folder = str(Path(n["path"]).parent)
        preview = " | ".join(n["first_lines"][:2])[:120]
        tags = " ".join(f"#{t}" for t in n["tags"][:3])
        lines.append(f'- [{folder}/{title}] {preview} {tags}'.strip())
    return "\n".join(lines)


def _parse_llm_response(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    # Strip markdown code fence if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON object from mixed text
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return {"moves": [], "links": []}


def run(subdir: str | None = None) -> dict:
    """
    Analyse notes and return proposed changes (dry run — nothing written yet).

    Returns:
        {
          "moves": [{path, suggested_folder, reason}],
          "links": [{path, suggested_links, reason}],
          "note_count": int,
        }
    """
    vault = ObsidianVault()
    notes = vault.list_notes(subdir=subdir)

    # Skip Daily notes and already-organised notes
    notes = [
        n for n in notes
        if not n["path"].startswith("Daily/")
        and not n["path"].startswith(".obsidian/")
    ]

    if not notes:
        return {"moves": [], "links": [], "note_count": 0}

    summary = _summarise_notes(notes)
    prompt = _ANALYSIS_PROMPT.format(
        notes_summary=summary,
        folders=", ".join(_VAULT_FOLDERS),
    )

    raw = router.ask(prompt, task="notes", system=_SYSTEM_PROMPT)
    result = _parse_llm_response(raw)

    # Validate that suggested paths exist in vault
    note_paths = {n["path"] for n in notes}
    result["moves"] = [
        m for m in result.get("moves", [])
        if m.get("path") in note_paths
    ]
    result["links"] = [
        lk for lk in result.get("links", [])
        if lk.get("path") in note_paths
    ]
    result["note_count"] = len(notes)
    return result


def apply(changes: dict) -> dict:
    """
    Apply confirmed changes from run().
    Returns {moves_done, links_added, errors}.
    """
    vault = ObsidianVault()
    stats = {"moves_done": 0, "links_added": 0, "errors": []}

    for move in changes.get("moves", []):
        src = move.get("path", "")
        folder = move.get("suggested_folder", "")
        if not src or not folder:
            continue
        filename = Path(src).name
        dest = f"{folder}/{filename}"
        try:
            if vault.move_file(src, dest):
                stats["moves_done"] += 1
            else:
                stats["errors"].append(f"Could not move {src} (file not found)")
        except Exception as e:
            stats["errors"].append(f"Move error {src}: {e}")

    for link_suggestion in changes.get("links", []):
        path = link_suggestion.get("path", "")
        links = link_suggestion.get("suggested_links", [])
        if not path or not links:
            continue
        try:
            wikilinks = "  ".join(f"[[{l}]]" for l in links)
            vault.append_to_file(path, f"\n\nRelated: {wikilinks}\n")
            stats["links_added"] += 1
        except Exception as e:
            stats["errors"].append(f"Link error {path}: {e}")

    return stats


def run_links_only(subdir: str | None = None) -> dict:
    """Run analysis for wikilinks only — no folder moves suggested."""
    result = run(subdir=subdir)
    result["moves"] = []
    return result
