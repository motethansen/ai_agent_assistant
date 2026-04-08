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
  OBSIDIAN_PLANNER_FILE  — relative path inside vault (default: 010 Planning/Planner.md)
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
    rel   = get_config_value("OBSIDIAN_PLANNER_FILE", "010 Planning/Planner.md")
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
# Step 2 — Pre-scan tasks (Python-side, reliable date + priority analysis)
# ---------------------------------------------------------------------------

# Obsidian Tasks plugin emoji markers
_PRIORITY_MAP = {
    "🔺": ("highest", 0),
    "⏫": ("high",    1),
    "🔼": ("medium",  2),
    "🔽": ("low",     3),
    "⏬": ("lowest",  4),
}
_DUE_PAT       = re.compile(r'📅\s*(\d{4}-\d{2}-\d{2})')
_SCHEDULED_PAT = re.compile(r'⏳\s*(\d{4}-\d{2}-\d{2})')
_START_PAT     = re.compile(r'🛫\s*(\d{4}-\d{2}-\d{2})')


def _parse_task_line(line: str) -> dict | None:
    """
    Parse a single markdown task line.
    Returns None if not an open task (`- [ ]`).
    Returns dict: {line, due, scheduled, start, priority, priority_weight, clean_text}
    """
    if not re.match(r'\s*-\s*\[ \]', line):
        return None

    priority = None
    priority_weight = 99
    for emoji, (label, weight) in _PRIORITY_MAP.items():
        if emoji in line:
            priority = label
            priority_weight = weight
            break

    def _d(m):
        if not m:
            return None
        try:
            return datetime.date.fromisoformat(m.group(1))
        except ValueError:
            return None

    due       = _d(_DUE_PAT.search(line))
    scheduled = _d(_SCHEDULED_PAT.search(line))
    start     = _d(_START_PAT.search(line))

    # Clean text: strip task prefix, emoji markers, and date values
    clean = re.sub(r'^\s*-\s*\[ \]\s*', '', line.strip())
    for pat in (_DUE_PAT, _SCHEDULED_PAT, _START_PAT):
        clean = pat.sub("", clean)
    for emoji in _PRIORITY_MAP:
        clean = clean.replace(emoji, "")
    clean = re.sub(r'\s{2,}', ' ', clean).strip()

    return {
        "line": line.strip(),
        "clean": clean,
        "due": due,
        "scheduled": scheduled,
        "start": start,
        "priority": priority,
        "priority_weight": priority_weight,
    }


def _analyse_tasks(content: str) -> dict:
    """
    Scan planner content and classify open tasks into buckets:
      overdue        — due date < today
      due_soon       — due date within URGENT_DAYS (default 3) days
      unscheduled_hi — high/highest priority but no due date (needs planning)
      scheduled_soon — scheduled date (⏳) within URGENT_DAYS but no due date
    Returns dict of lists, each item is a task dict from _parse_task_line.
    """
    today = datetime.date.today()
    urgent_days = int(get_config_value("URGENT_DAYS", "3"))
    deadline = today + datetime.timedelta(days=urgent_days)

    buckets = {
        "overdue": [],
        "due_soon": [],
        "unscheduled_hi": [],
        "scheduled_soon": [],
    }

    for line in content.splitlines():
        task = _parse_task_line(line)
        if not task:
            continue

        if task["due"] and task["due"] < today:
            buckets["overdue"].append(task)
        elif task["due"] and today <= task["due"] <= deadline:
            buckets["due_soon"].append(task)
        elif task["priority_weight"] <= 1 and not task["due"]:
            # high or highest priority but no due date — needs explicit scheduling
            buckets["unscheduled_hi"].append(task)
        elif task["scheduled"] and task["scheduled"] <= deadline and not task["due"]:
            buckets["scheduled_soon"].append(task)

    return buckets


# ---------------------------------------------------------------------------
# Step 3 — Organise the planner with LLM
# ---------------------------------------------------------------------------

def _format_task_list(tasks: list) -> str:
    lines = []
    for t in tasks:
        due_str = f" (due {t['due']})" if t.get("due") else ""
        sched_str = f" (scheduled {t['scheduled']})" if t.get("scheduled") else ""
        pri_str = f" [{t['priority']}]" if t.get("priority") else ""
        lines.append(f"  - {t['clean']}{pri_str}{due_str}{sched_str}")
    return "\n".join(lines)


def organise_planner():
    """
    Read the full planner file, pre-analyse task urgency/priority, then send
    to LLM with explicit structured instructions. Writes result back.
    Returns the organised content string.
    """
    planner = _planner_path()
    content = _read_planner(planner)
    if not content.strip():
        print("[DataInputAgent] Planner is empty — nothing to organise.")
        return ""

    today = datetime.date.today().isoformat()

    # Python-side analysis — reliable, independent of LLM date parsing
    buckets = _analyse_tasks(content)
    overdue        = buckets["overdue"]
    due_soon       = buckets["due_soon"]
    unscheduled_hi = buckets["unscheduled_hi"]
    scheduled_soon = buckets["scheduled_soon"]

    print(f"[DataInputAgent] Task analysis — overdue: {len(overdue)}, "
          f"due soon: {len(due_soon)}, high-priority unscheduled: {len(unscheduled_hi)}, "
          f"scheduled soon: {len(scheduled_soon)}")

    # Build the urgency context block for the LLM
    urgency_parts = []

    if overdue:
        urgency_parts.append(
            f"OVERDUE ({len(overdue)} tasks — due date has already passed):\n"
            + _format_task_list(overdue)
        )

    if due_soon:
        urgency_parts.append(
            f"DUE SOON ({len(due_soon)} tasks — due within the next few days):\n"
            + _format_task_list(due_soon)
        )

    if unscheduled_hi:
        urgency_parts.append(
            f"NEEDS IMMEDIATE PLANNING ({len(unscheduled_hi)} high/highest-priority tasks with NO due date set):\n"
            + _format_task_list(unscheduled_hi)
        )

    if scheduled_soon:
        urgency_parts.append(
            f"SCHEDULED SOON but no due date ({len(scheduled_soon)} tasks — scheduled date approaching):\n"
            + _format_task_list(scheduled_soon)
        )

    urgency_block = ""
    if urgency_parts:
        urgency_block = (
            "\n\nIMPORTANT — Python pre-scan identified the following tasks needing attention "
            f"(today is {today}). Use this to guide placement and the review section:\n\n"
            + "\n\n".join(urgency_parts)
            + "\n"
        )

    # Read user's focus categories from config
    raw_cats = get_config_value("FOCUS_CATEGORIES", "")
    categories = [c.strip() for c in raw_cats.split(",") if c.strip()] if raw_cats else []
    if categories:
        cat_instruction = (
            f"Organise tasks under these category headings where possible "
            f"(use ## headers): {', '.join(categories)}. "
            f"Tasks that don't fit any category go under '## Other'."
        )
    else:
        cat_instruction = "Group tasks by project or theme using ## headers."

    system = (
        "You are a personal productivity assistant. "
        "Reorganise a markdown task planner into clean, prioritised sections. "
        "Rules:\n"
        "  1. Preserve ALL task text and emoji markers EXACTLY — never alter, merge, or remove any task or its 📅⏳🛫🔺⏫🔼🔽⏬ markers.\n"
        "  2. Section order (top to bottom):\n"
        "       a. '## 🚨 Overdue' — tasks whose 📅 date is before today (omit section if none).\n"
        "       b. '## ⚠️ Needs Review' — tasks that need urgent planning attention:\n"
        "             • High/highest priority (⏫🔺) with no due date set\n"
        "             • Due within the next 3 days\n"
        "             • Scheduled soon (⏳) with no due date\n"
        "          Include a brief plain-English note after each task explaining WHY it needs review.\n"
        "          Omit this section if nothing qualifies.\n"
        "       c. Category sections — one ## heading per project/theme.\n"
        "       d. '## Other' — tasks that don't fit any category.\n"
        "  3. Within each category section, sort tasks: highest priority first (🔺⏫🔼🔽⏬), "
        "     then by 📅 due date ascending, then alphabetically.\n"
        "  4. Tasks with no date and no priority go last within their section.\n"
        "  5. Return ONLY the reorganised markdown — no explanations, no preamble, no code fences."
    )

    prompt = (
        f"Today is {today}.\n"
        f"{urgency_block}\n"
        f"{cat_instruction}\n\n"
        f"Please reorganise this planner:\n\n"
        f"---\n{content}\n---"
    )

    print(f"[DataInputAgent] Asking LLM to organise planner...")
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
