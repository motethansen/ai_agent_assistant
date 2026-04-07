"""
DataInput Agent

Responsibilities:
  1. Read datainput/reminders.json produced by debug_reminders.py (Apple Reminders export).
  2. Detect reminders not yet added to the Obsidian planner file.
  3. Append new tasks under a "## Reminders" section in the planner.
  4. Run the organiser: ask the LLM to re-group and sort the full planner content,
     then write the organised version back to the file.

Config keys used:
  WORKSPACE_DIR          — Obsidian vault root
  OBSIDIAN_PLANNER_FILE  — relative path inside vault (default: Planner.md)
"""

import os
import json
import datetime
import re
from config_utils import get_config_value
import ai_orchestration

DATAINPUT_DIR   = os.path.join(os.path.dirname(__file__), "datainput")
REMINDERS_FILE  = os.path.join(DATAINPUT_DIR, "reminders.json")
SYNCED_FILE     = os.path.join(DATAINPUT_DIR, "synced_reminders.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _planner_path():
    vault = get_config_value("WORKSPACE_DIR", ".")
    rel   = get_config_value("OBSIDIAN_PLANNER_FILE", "Planner.md")
    return os.path.join(vault, rel)


def _load_reminders():
    if not os.path.exists(REMINDERS_FILE):
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[DataInputAgent] Could not read reminders.json: {e}")
        return []


def _load_synced():
    if not os.path.exists(SYNCED_FILE):
        return set()
    try:
        with open(SYNCED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_synced(synced_set):
    os.makedirs(DATAINPUT_DIR, exist_ok=True)
    with open(SYNCED_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(synced_set), f, indent=2)


def _task_key(reminder):
    """Stable identifier for a reminder."""
    return f"{reminder['task']}|{reminder.get('due_date', '')}"


def _format_due(due_str):
    """Convert 'Wednesday, 8 April 2026 at 11:00:00' → '2026-04-08'."""
    if not due_str:
        return None
    try:
        dt = datetime.datetime.strptime(due_str, "%A, %d %B %Y at %H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def _read_planner(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_planner(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Step 1 — Sync new reminders into planner
# ---------------------------------------------------------------------------

def sync_reminders_to_planner():
    """
    Add any unsynced reminders to the planner file.
    Returns list of newly added task dicts.
    """
    reminders = _load_reminders()
    synced    = _load_synced()
    planner   = _planner_path()

    new_tasks = [r for r in reminders if _task_key(r) not in synced]
    if not new_tasks:
        print("[DataInputAgent] No new reminders to sync.")
        return []

    print(f"[DataInputAgent] Adding {len(new_tasks)} new reminders to planner.")

    content = _read_planner(planner)

    # Ensure a "## Reminders" section exists
    if "## Reminders" not in content:
        content = content.rstrip() + "\n\n## Reminders\n"

    # Build lines to append
    lines_to_add = []
    for r in new_tasks:
        task_text = r["task"].strip()
        due       = _format_due(r.get("due_date"))
        notes     = r.get("notes", "").strip()

        line = f"- [ ] {task_text}"
        if due:
            line += f" 📅 {due}"
        if notes:
            # Notes go as a sub-bullet
            lines_to_add.append(line)
            lines_to_add.append(f"  - {notes}")
        else:
            lines_to_add.append(line)

    # Insert after the "## Reminders" heading
    insert_marker = "## Reminders"
    idx = content.find(insert_marker)
    insert_pos = idx + len(insert_marker)
    # Skip past any existing newline right after the heading
    while insert_pos < len(content) and content[insert_pos] == "\n":
        insert_pos += 1

    block = "\n".join(lines_to_add) + "\n"
    content = content[:insert_pos] + block + content[insert_pos:]

    _write_planner(planner, content)

    # Mark as synced
    for r in new_tasks:
        synced.add(_task_key(r))
    _save_synced(synced)

    print(f"[DataInputAgent] Planner updated at {planner}")
    return new_tasks


# ---------------------------------------------------------------------------
# Step 2 — Pre-scan for overdue tasks (Python-side, reliable date comparison)
# ---------------------------------------------------------------------------

def _find_overdue_tasks(content):
    """
    Scan planner markdown for incomplete tasks with a 📅 YYYY-MM-DD date
    that is strictly before today. Returns list of (task_line, due_date_str).
    """
    today = datetime.date.today()
    overdue = []
    date_pattern = re.compile(r'📅\s*(\d{4}-\d{2}-\d{2})')
    for line in content.splitlines():
        # Only open tasks: - [ ] ...
        if not re.match(r'\s*-\s*\[ \]', line):
            continue
        m = date_pattern.search(line)
        if not m:
            continue
        try:
            due = datetime.date.fromisoformat(m.group(1))
            if due < today:
                overdue.append((line.strip(), m.group(1)))
        except ValueError:
            continue
    return overdue


# ---------------------------------------------------------------------------
# Step 3 — Organise the planner with LLM
# ---------------------------------------------------------------------------

def organise_planner():
    """
    Read the full planner file, pre-detect overdue tasks, then send to LLM
    with explicit category and overdue instructions. Writes result back.
    Returns the organised content string.
    """
    planner = _planner_path()
    content = _read_planner(planner)
    if not content.strip():
        print("[DataInputAgent] Planner is empty — nothing to organise.")
        return ""

    today = datetime.date.today().isoformat()

    # Pre-detect overdue tasks in Python (reliable, doesn't depend on LLM date parsing)
    overdue = _find_overdue_tasks(content)
    overdue_block = ""
    if overdue:
        overdue_lines = "\n".join(f"  - {line} (was due {due})" for line, due in overdue)
        overdue_block = (
            f"\nIMPORTANT — the following {len(overdue)} task(s) are OVERDUE "
            f"(due date is before {today}). They MUST appear under a "
            f"'## 🚨 Overdue' section at the very top of the output:\n{overdue_lines}\n"
        )

    # Read user's focus categories from config
    raw_cats = get_config_value("FOCUS_CATEGORIES", "")
    categories = [c.strip() for c in raw_cats.split(",") if c.strip()] if raw_cats else []
    if categories:
        cat_instruction = (
            f"\nOrganise tasks under these category headings where possible "
            f"(use ## headers): {', '.join(categories)}. "
            f"Tasks that don't fit any category go under '## Other'."
        )
    else:
        cat_instruction = (
            "\nGroup tasks by project or theme using ## headers."
        )

    system = (
        "You are a personal productivity assistant. "
        "Your job is to reorganise a markdown task planner into clean, prioritised sections. "
        "Rules:\n"
        "  1. Preserve ALL task text exactly — do not alter, merge, or remove any task.\n"
        "  2. If there are overdue tasks, place them in a '## 🚨 Overdue' section at the very top.\n"
        "  3. Within each section, sort by due date (earliest first), then by apparent urgency.\n"
        "  4. Use ## markdown headers for each section.\n"
        "  5. Return ONLY the reorganised markdown — no explanations, no commentary."
    )

    prompt = (
        f"Today is {today}.\n"
        f"{overdue_block}"
        f"{cat_instruction}\n\n"
        f"Please reorganise this planner:\n\n"
        f"---\n{content}\n---"
    )

    print(f"[DataInputAgent] Asking LLM to organise planner "
          f"({len(overdue)} overdue, {len(categories)} categories)...")
    organised, model = ai_orchestration.generate(prompt, system=system, task_type="parsing")
    print(f"[DataInputAgent] Organised by {model}.")

    # Guard: don't overwrite with an error message or empty result
    if not organised or organised.startswith("LLM error") or len(organised) < 50:
        print("[DataInputAgent] LLM returned unusable output — planner unchanged.")
        return content

    _write_planner(planner, organised.strip() + "\n")
    print(f"[DataInputAgent] Planner reorganised and saved.")
    return organised


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(organise=True):
    """
    Run the full DataInput agent pipeline.
    Returns dict with keys: new_tasks, organised (bool).
    """
    new_tasks = sync_reminders_to_planner()
    organised = False
    if organise:
        organise_planner()
        organised = True
    return {"new_tasks": new_tasks, "organised": organised}


if __name__ == "__main__":
    result = run()
    print(f"\nSummary: {len(result['new_tasks'])} new tasks added, organised={result['organised']}")
