"""
Task Reschedule Agent

Finds overdue tasks in LogSeq journals and Obsidian markdown files and
moves them to a specified target date.

LogSeq tasks:   lines marked LATER/TODO in journal files dated before today
Obsidian tasks: `- [ ]` lines with a 📅 YYYY-MM-DD date before today

Target date accepts natural language:
  "end of next week"   → next Friday
  "start of next week" → next Monday
  "next monday"        → next Monday
  "next friday"        → next Friday
  "tomorrow"           → tomorrow
  "today"              → today
  "2026-04-17"         → literal ISO date

Usage:
  python task_reschedule_agent.py "end of next week"
  python task_reschedule_agent.py "next monday" --dry-run
  python task_reschedule_agent.py "2026-04-17" --logseq-only
  python task_reschedule_agent.py "friday"      --obsidian-only
  python task_reschedule_agent.py "end of next week" --filter "report"

Importable API:
  from task_reschedule_agent import run
  run("end of next week", dry_run=False)
"""

import os
import re
import datetime
import argparse

from config_utils import get_config_value
from logseq_agent import LogSeqAgent


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def parse_target_date(text: str) -> datetime.date:
    """
    Parse a natural language or ISO date string into a datetime.date.
    Raises ValueError if the string cannot be parsed.
    """
    text = text.strip().lower()
    today = datetime.date.today()
    weekday_today = today.weekday()  # 0=Mon … 6=Sun

    # Literal ISO date
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', text)
    if m:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # today / tomorrow / yesterday
    if text == "today":
        return today
    if text == "tomorrow":
        return today + datetime.timedelta(days=1)
    if text == "yesterday":
        return today - datetime.timedelta(days=1)

    # end of next week → next Friday
    if re.search(r'end\s+of\s+next\s+week', text):
        days_ahead = (4 - weekday_today) % 7  # Friday = 4
        if days_ahead == 0:
            days_ahead = 7
        days_ahead += 7  # push to *next* week
        return today + datetime.timedelta(days=days_ahead)

    # start of next week → next Monday
    if re.search(r'start\s+of\s+next\s+week', text):
        days_ahead = (0 - weekday_today) % 7  # Monday = 0
        if days_ahead == 0:
            days_ahead = 7
        days_ahead += 7
        return today + datetime.timedelta(days=days_ahead)

    # end of this week → this Friday
    if re.search(r'end\s+of\s+(this\s+)?week', text):
        days_ahead = (4 - weekday_today) % 7
        if days_ahead == 0:
            days_ahead = 7  # already Friday → use next Friday
        return today + datetime.timedelta(days=days_ahead)

    # next week (no qualifier) → next Monday
    if text in ("next week", "next week"):
        days_ahead = (0 - weekday_today) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + datetime.timedelta(days=days_ahead + 7)

    # next <weekday> or just <weekday>
    for name, num in WEEKDAYS.items():
        if re.search(rf'\b{name}\b', text):
            days_ahead = (num - weekday_today) % 7
            if days_ahead == 0:
                days_ahead = 7  # same weekday → next occurrence
            if "next" in text:
                # "next friday" when today is already in the same week as friday
                # add an extra 7 if not already further ahead
                if days_ahead < 7:
                    days_ahead += 7
            return today + datetime.timedelta(days=days_ahead)

    # in N days
    m = re.match(r'in\s+(\d+)\s+days?', text)
    if m:
        return today + datetime.timedelta(days=int(m.group(1)))

    raise ValueError(f"Cannot parse target date: '{text}'")


# ---------------------------------------------------------------------------
# LogSeq — find and move overdue tasks
# ---------------------------------------------------------------------------

def find_overdue_logseq_tasks(logseq_dir: str) -> list:
    """
    Scan journal files older than today for any LATER/TODO tasks.
    Returns list of dicts:
      { task, source_file (abs path), date_key, line_index (0-based), raw_line }
    """
    journals_dir = os.path.join(logseq_dir, "journals")
    if not os.path.isdir(journals_dir):
        return []

    today_key = datetime.date.today().strftime("%Y_%m_%d")
    overdue = []

    for fname in os.listdir(journals_dir):
        if not re.match(r'\d{4}_\d{2}_\d{2}\.md$', fname):
            continue
        date_key = fname[:-3]
        if date_key >= today_key:
            continue  # today or future — skip

        path = os.path.join(journals_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            continue

        for idx, raw in enumerate(lines):
            if re.match(r'^\s*-\s+(LATER|TODO)\s+', raw):
                task_text = re.sub(r'^\s*-\s+(LATER|TODO)\s+', '', raw).rstrip()
                overdue.append({
                    "task": task_text,
                    "source_file": path,
                    "date_key": date_key,
                    "line_index": idx,
                    "raw_line": raw,
                    "source": "logseq",
                })

    return overdue


def _remove_line_from_file(path: str, line_index: int):
    """Remove the line at line_index (0-based) from a file."""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if 0 <= line_index < len(lines):
        lines.pop(line_index)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def move_logseq_task(task: dict, target_date: datetime.date, dry_run=False) -> bool:
    """
    Remove task from its source journal file and append it to target date's journal.
    Returns True on success.
    """
    logseq_dir = os.path.dirname(os.path.dirname(task["source_file"]))
    date_key = target_date.strftime("%Y_%m_%d")
    target_path = os.path.join(logseq_dir, "journals", f"{date_key}.md")

    label = "[DRY-RUN] " if dry_run else ""
    print(f"  {label}LogSeq: move '{task['task'][:60]}' "
          f"({task['date_key']} → {date_key})")

    if dry_run:
        return True

    # Remove from source
    _remove_line_from_file(task["source_file"], task["line_index"])

    # Append to target
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "a", encoding="utf-8") as f:
        # Preserve original marker (LATER or TODO)
        marker_m = re.match(r'^\s*-\s+(LATER|TODO)\s+', task["raw_line"])
        marker = marker_m.group(1) if marker_m else "LATER"
        f.write(f"\n- {marker} {task['task']}\n")

    return True


# ---------------------------------------------------------------------------
# Obsidian — find and move overdue tasks
# ---------------------------------------------------------------------------

_OBSIDIAN_TASK_RE = re.compile(r'^(\s*-\s+\[ \]\s+)(.*)')
_DUE_DATE_RE  = re.compile(r'📅\s*(\d{4}-\d{2}-\d{2})')
_SCHED_DATE_RE = re.compile(r'⏳\s*(\d{4}-\d{2}-\d{2})')

_PRIORITY_MAP = {
    "🔺": ("highest", 0),
    "⏫": ("high",    1),
    "🔼": ("medium",  2),
    "🔽": ("low",     3),
    "⏬": ("lowest",  4),
}

DEFAULT_EXCLUDE_DIRS = {
    "950 Templates", "900 Archive", "990 Attachments", "910 PDF_PNG",
    "Clippings", "export", "whiteboards", "assets",
    ".obsidian", ".stfolder", ".claude",
}


def _extract_priority(raw: str) -> tuple[str | None, int]:
    for emoji, (label, weight) in _PRIORITY_MAP.items():
        if emoji in raw:
            return label, weight
    return None, 99


def find_overdue_obsidian_tasks(workspace_dir: str) -> list:
    """
    Scan Obsidian vault for incomplete tasks whose 📅 due date OR ⏳ scheduled
    date is before today. Priority metadata is included for display/sorting.

    Returns list of dicts:
      { task, clean_task, source_file, rel_path, line_index, raw_line,
        due_date, scheduled_date, priority, priority_weight, overdue_field }
    """
    if not workspace_dir or not os.path.isdir(workspace_dir):
        return []

    raw_exclude = get_config_value("OBSIDIAN_EXCLUDE_DIRS", "")
    exclude_dirs = (
        {d.strip() for d in raw_exclude.split(",") if d.strip()}
        if raw_exclude else DEFAULT_EXCLUDE_DIRS
    )

    today = datetime.date.today()
    overdue = []

    for root, dirs, files in os.walk(workspace_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            if not fname.endswith(".md"):
                continue
            abs_path = os.path.join(root, fname)
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except OSError:
                continue

            for idx, raw in enumerate(lines):
                if not _OBSIDIAN_TASK_RE.match(raw):
                    continue

                def _d(m):
                    if not m:
                        return None
                    try:
                        return datetime.date.fromisoformat(m.group(1))
                    except ValueError:
                        return None

                due_date  = _d(_DUE_DATE_RE.search(raw))
                sched_date = _d(_SCHED_DATE_RE.search(raw))
                priority, priority_weight = _extract_priority(raw)

                # Determine which field makes this task overdue
                overdue_field = None
                if due_date and due_date < today:
                    overdue_field = "due"
                elif sched_date and sched_date < today and not due_date:
                    overdue_field = "scheduled"

                if not overdue_field:
                    continue

                task_text = _OBSIDIAN_TASK_RE.match(raw).group(2).rstrip()
                # Clean version: strip date markers + priority emojis
                clean = task_text
                for pat in (_DUE_DATE_RE, _SCHED_DATE_RE):
                    clean = pat.sub("", clean)
                for emoji in _PRIORITY_MAP:
                    clean = clean.replace(emoji, "")
                clean = re.sub(r'\s{2,}', ' ', clean).strip()

                rel_path = os.path.relpath(abs_path, workspace_dir)
                overdue.append({
                    "task": task_text,
                    "clean_task": clean,
                    "source_file": abs_path,
                    "rel_path": rel_path,
                    "line_index": idx,
                    "raw_line": raw,
                    "due_date": due_date,
                    "scheduled_date": sched_date,
                    "priority": priority,
                    "priority_weight": priority_weight,
                    "overdue_field": overdue_field,
                    "source": "obsidian",
                })

    # Sort: highest priority first, then earliest date first
    overdue.sort(key=lambda t: (t["priority_weight"], t["due_date"] or datetime.date.max))
    return overdue


def move_obsidian_task(task: dict, target_date: datetime.date, dry_run=False) -> bool:
    """
    Update the 📅 or ⏳ date (whichever made it overdue) in an Obsidian task line.
    If moving by due date, updates 📅. If moving by scheduled date, updates ⏳.
    Returns True on success.
    """
    new_date_str = target_date.strftime("%Y-%m-%d")
    label = "[DRY-RUN] " if dry_run else ""
    old_date = task.get("due_date") or task.get("scheduled_date")
    pri_str = f" [{task['priority']}]" if task.get("priority") else ""
    print(f"  {label}Obsidian{pri_str}: '{task['clean_task'][:55]}' "
          f"({old_date} → {new_date_str})  [{task['rel_path']}:{task['line_index']+1}]")

    if dry_run:
        return True

    try:
        with open(task["source_file"], "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return False

    idx = task["line_index"]
    if idx >= len(lines):
        return False

    # Replace the relevant date marker
    if task["overdue_field"] == "due":
        lines[idx] = _DUE_DATE_RE.sub(f"📅 {new_date_str}", lines[idx])
    else:
        lines[idx] = _SCHED_DATE_RE.sub(f"⏳ {new_date_str}", lines[idx])

    try:
        with open(task["source_file"], "w", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError:
        return False

    return True


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(
    target: str,
    dry_run: bool = False,
    logseq: bool = True,
    obsidian: bool = True,
    filter_text: str = None,
) -> dict:
    """
    Find overdue tasks and move them to the target date.

    Args:
        target:      Natural language or ISO date string for the target date.
        dry_run:     If True, print what would happen but don't modify files.
        logseq:      Whether to process LogSeq journal tasks.
        obsidian:    Whether to process Obsidian tasks with 📅 dates.
        filter_text: If set, only move tasks whose text contains this string.

    Returns:
        dict with keys: target_date, logseq_moved, obsidian_moved, logseq_skipped, obsidian_skipped
    """
    # Parse target date
    try:
        target_date = parse_target_date(target)
    except ValueError as e:
        print(f"[RescheduleAgent] ERROR: {e}")
        return {}

    today = datetime.date.today()
    print(f"\n[RescheduleAgent] Target date: {target_date} (today is {today})")
    if dry_run:
        print("[RescheduleAgent] DRY-RUN mode — no files will be modified.")

    logseq_moved = logseq_skipped = 0
    obsidian_moved = obsidian_skipped = 0

    # -- LogSeq --
    if logseq:
        logseq_dir = get_config_value("LOGSEQ_DIR", "")
        if logseq_dir and os.path.isdir(logseq_dir):
            lq_tasks = find_overdue_logseq_tasks(logseq_dir)
            if filter_text:
                lq_tasks = [t for t in lq_tasks if filter_text.lower() in t["task"].lower()]
            print(f"\n[LogSeq] Found {len(lq_tasks)} overdue task(s).")
            for t in lq_tasks:
                ok = move_logseq_task(t, target_date, dry_run=dry_run)
                if ok:
                    logseq_moved += 1
                else:
                    logseq_skipped += 1
        else:
            print("[LogSeq] LOGSEQ_DIR not configured — skipping.")

    # -- Obsidian --
    if obsidian:
        workspace_dir = get_config_value("WORKSPACE_DIR", "")
        if workspace_dir and os.path.isdir(workspace_dir):
            ob_tasks = find_overdue_obsidian_tasks(workspace_dir)
            if filter_text:
                ob_tasks = [t for t in ob_tasks if filter_text.lower() in t["task"].lower()]
            print(f"\n[Obsidian] Found {len(ob_tasks)} overdue task(s).")
            for t in ob_tasks:
                ok = move_obsidian_task(t, target_date, dry_run=dry_run)
                if ok:
                    obsidian_moved += 1
                else:
                    obsidian_skipped += 1
        else:
            print("[Obsidian] WORKSPACE_DIR not configured — skipping.")

    total = logseq_moved + obsidian_moved
    action = "Would move" if dry_run else "Moved"
    print(f"\n[RescheduleAgent] {action} {total} task(s) to {target_date} "
          f"(LogSeq: {logseq_moved}, Obsidian: {obsidian_moved}).")

    return {
        "target_date": str(target_date),
        "logseq_moved": logseq_moved,
        "obsidian_moved": obsidian_moved,
        "logseq_skipped": logseq_skipped,
        "obsidian_skipped": obsidian_skipped,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Move overdue tasks to a new date.",
        epilog="""
Examples:
  python task_reschedule_agent.py "end of next week"
  python task_reschedule_agent.py "next monday" --dry-run
  python task_reschedule_agent.py "2026-04-17" --logseq-only
  python task_reschedule_agent.py "friday" --obsidian-only
  python task_reschedule_agent.py "end of next week" --filter "report"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("target", help='Target date, e.g. "end of next week", "next monday", "2026-04-17"')
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying files")
    parser.add_argument("--logseq-only", action="store_true", help="Only process LogSeq journals")
    parser.add_argument("--obsidian-only", action="store_true", help="Only process Obsidian tasks")
    parser.add_argument("--filter", metavar="TEXT", help="Only move tasks whose text contains this string")

    args = parser.parse_args()

    logseq_flag = not args.obsidian_only
    obsidian_flag = not args.logseq_only

    result = run(
        target=args.target,
        dry_run=args.dry_run,
        logseq=logseq_flag,
        obsidian=obsidian_flag,
        filter_text=args.filter,
    )
