"""
Sync agent — pulls tasks and notes from LogSeq into Obsidian.

Runs automatically every 30 min via cron_job.py.
Uses a hash file to track what has already been synced (no duplicates).
"""

import datetime
import hashlib
import json
from pathlib import Path

from integrations.logseq import LogSeqReader
from integrations.obsidian import ObsidianVault
import config

_HASH_FILE = Path(__file__).parent.parent / "output" / ".synced_hashes.json"


def _load_hashes() -> set[str]:
    try:
        return set(json.loads(_HASH_FILE.read_text()))
    except (OSError, json.JSONDecodeError):
        return set()


def _save_hashes(hashes: set[str]) -> None:
    _HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    _HASH_FILE.write_text(json.dumps(sorted(hashes), indent=2))


def _task_hash(task: dict) -> str:
    key = f"{task['task']}|{task['source']}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def run() -> dict:
    """
    Pull new LogSeq tasks and notes into Obsidian.
    Returns a summary dict: {tasks_added, notes_added, skipped}.
    """
    logseq = LogSeqReader()
    vault = ObsidianVault()
    synced = _load_hashes()
    today = datetime.date.today()

    stats = {"tasks_added": 0, "notes_added": 0, "skipped": 0}

    # ── Tasks ────────────────────────────────────────────────────────────────
    days = config.sync.logseq_journal_days()
    tasks = logseq.get_recent_tasks(days=days)
    page_tasks = logseq.get_all_page_tasks()
    all_tasks = tasks + page_tasks

    new_task_lines = []
    new_hashes = set()
    for t in all_tasks:
        h = _task_hash(t)
        if h in synced:
            stats["skipped"] += 1
            continue
        line = f"- [ ] {t['task']}"
        if t.get("description"):
            line += f"  _{t['description']}_"
        line += f"  _(from {t['source']})_"
        new_task_lines.append(line)
        new_hashes.add(h)
        stats["tasks_added"] += 1

    if new_task_lines:
        section_content = "\n".join(new_task_lines)
        # Prepend new tasks to existing inbox section
        existing = vault.read_section("inbox")
        combined = (section_content + "\n\n" + existing).strip() if existing else section_content
        vault.write_section("inbox", combined)

    # ── Notes (journal entries) ───────────────────────────────────────────────
    note_entries = logseq.get_recent_notes(days=days)
    new_note_lines = []
    for entry in note_entries:
        h = hashlib.sha1(entry["source"].encode()).hexdigest()[:12]
        if h in synced:
            continue
        new_note_lines.append(f"\n### {entry['date']}")
        for ln in entry["lines"]:
            new_note_lines.append(f"- {ln}")
        new_hashes.add(h)
        stats["notes_added"] += 1

    if new_note_lines:
        # Write raw notes dump to Inbox/<date>-logseq.md
        inbox_rel = f"Inbox/{today.isoformat()}-logseq.md"
        existing_dump = vault.read_file(inbox_rel) or ""
        dump_content = existing_dump + "\n".join(new_note_lines) + "\n"
        vault.write_file(inbox_rel, dump_content)

    # Persist hashes
    _save_hashes(synced | new_hashes)

    return stats


def reset_hashes() -> None:
    """Clear sync state — next run will re-sync everything. Use with caution."""
    if _HASH_FILE.exists():
        _HASH_FILE.unlink()


if __name__ == "__main__":
    result = run()
    print(f"Sync complete: {result['tasks_added']} tasks, {result['notes_added']} note entries, {result['skipped']} skipped")
