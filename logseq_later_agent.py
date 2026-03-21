"""
LogSeq LATER Agent

Scans LogSeq journals and pages for tasks marked LATER.
The existing logseq_agent.py already handles the line-by-line parsing
(including collecting indented property lines that belong to the same task).
This module adds:
  - unified scanning across journals + pages
  - deduplication by task text
  - optional write of a LATER task summary to Obsidian
  - standalone run() function for cron and n8n use

Config keys used:
  LOGSEQ_DIR              — root of the LogSeq graph
  WORKSPACE_DIR           — Obsidian vault root (for optional summary write)
  OBSIDIAN_PLANNER_FILE   — planner note (default: Planner.md)
  LOGSEQ_JOURNAL_DAYS     — how many recent journal files to scan (default: 30)
"""

import os
import datetime
from config_utils import get_config_value
from logseq_agent import LogSeqAgent


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------

def scan_all_later_tasks(days=None):
    """
    Scan journals (last N days) and all pages for LATER tasks.
    Returns a deduplicated list of task dicts:
        {task, source, properties, date_key (for journal entries)}
    """
    logseq_dir = get_config_value("LOGSEQ_DIR", None)
    if not logseq_dir or not os.path.exists(logseq_dir):
        print("[LogSeqLaterAgent] LOGSEQ_DIR not configured or not found.")
        return []

    if days is None:
        days = int(get_config_value("LOGSEQ_JOURNAL_DAYS", "30"))

    agent = LogSeqAgent(logseq_dir)
    all_tasks = []

    # -- Journals --
    journal_tasks = agent.get_recent_tasks(days=days)
    all_tasks.extend(journal_tasks)

    # -- Pages --
    page_tasks = agent.get_all_page_tasks()
    all_tasks.extend(page_tasks)

    # -- Deduplicate by normalised task text --
    seen = set()
    deduped = []
    for t in all_tasks:
        key = t["task"].strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(t)

    print(f"[LogSeqLaterAgent] Found {len(deduped)} unique LATER tasks "
          f"({len(journal_tasks)} from journals, {len(page_tasks)} from pages).")
    return deduped


# ---------------------------------------------------------------------------
# Optional: write summary to Obsidian
# ---------------------------------------------------------------------------

def write_summary_to_obsidian(tasks):
    """
    Write a LATER task summary block to the Obsidian planner file
    under a '## LogSeq LATER Tasks' section (replaced on each run).
    """
    if not tasks:
        return

    vault = get_config_value("WORKSPACE_DIR", None)
    if not vault:
        return
    rel     = get_config_value("OBSIDIAN_PLANNER_FILE", "Planner.md")
    planner = os.path.join(vault, rel)

    today   = datetime.date.today().isoformat()
    header  = "## LogSeq LATER Tasks"
    footer_marker = "\n## "  # next section starts here

    # Build new block
    lines = [f"{header}", f"_Last synced: {today}_", ""]
    for t in tasks:
        src   = t.get("source", "")
        props = t.get("properties", {})
        line  = f"- [ ] {t['task']}"
        if "deadline" in props:
            line += f" 📅 {props['deadline']}"
        line += f"  _(from {src})_"
        lines.append(line)
    lines.append("")
    new_block = "\n".join(lines)

    # Read existing planner
    if os.path.exists(planner):
        with open(planner, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = ""

    # Replace or append the block
    if header in content:
        start = content.index(header)
        # Find where the next ## section starts after our block
        rest  = content[start + len(header):]
        next_section = rest.find("\n## ")
        if next_section != -1:
            end = start + len(header) + next_section
            content = content[:start] + new_block + content[end:]
        else:
            content = content[:start] + new_block
    else:
        content = content.rstrip() + "\n\n" + new_block

    with open(planner, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[LogSeqLaterAgent] Summary written to {planner}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(write_to_obsidian=True, days=None):
    """
    Run the LogSeq LATER scan.
    Returns list of task dicts.
    """
    tasks = scan_all_later_tasks(days=days)
    if write_to_obsidian and tasks:
        write_summary_to_obsidian(tasks)
    return tasks


if __name__ == "__main__":
    tasks = run(write_to_obsidian=False)
    for t in tasks:
        src = t.get("source", "")
        print(f"  [{src}] {t['task']}")
        if t.get("properties"):
            for k, v in t["properties"].items():
                print(f"      {k}: {v}")
