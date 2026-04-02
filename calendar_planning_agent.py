"""
Calendar Planning Agent  (Gemini-powered)

Responsibilities:
  1. Fetch Google Calendar events for the next 7 days.
  2. Load pending tasks from:
       - datainput/reminders.json  (Apple Reminders)
       - LogSeq LATER tasks        (via logseq_later_agent)
  3. Send everything to Gemini and ask for a concrete weekly/daily plan.
  4. Save the suggestions to datainput/calendar_suggestions.md
     (and optionally append to the Obsidian planner).

Config keys used:
  GEMINI_API_KEY        — required
  GEMINI_MODEL          — default: gemini-2.0-flash
  CALENDAR_ID           — default: primary
  WORKSPACE_DIR         — Obsidian vault root
  OBSIDIAN_PLANNER_FILE — planner note (default: Planner.md)
  LOGSEQ_DIR            — for LATER task context
  DEEP_WORK_START/END   — user's focus window (default: 09:00 / 12:00)
  CHRONOTYPE            — morning_owl | night_owl | balanced
"""

import os
import json
import datetime
from config_utils import get_config_value, is_google_calendar_enabled
import calendar_manager
import ai_orchestration

DATAINPUT_DIR     = os.path.join(os.path.dirname(__file__), "datainput")
REMINDERS_FILE    = os.path.join(DATAINPUT_DIR, "reminders.json")
SUGGESTIONS_FILE  = os.path.join(DATAINPUT_DIR, "calendar_suggestions.md")


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------

def _get_week_events(days=7):
    """
    Return all calendar events from today through today+days.
    Returns list of {summary, start, end, date} dicts.
    """
    if not is_google_calendar_enabled():
        print("[CalendarPlanningAgent] Google Calendar disabled (ENABLE_GOOGLE_CALENDAR=false). Skipping calendar fetch.")
        return []
    service = calendar_manager.get_calendar_service()
    if not service:
        print("[CalendarPlanningAgent] Google Calendar not available.")
        return []

    calendar_id = get_config_value("CALENDAR_ID", "primary")
    now  = datetime.datetime.now()
    events = []

    for offset in range(days):
        day = now + datetime.timedelta(days=offset)
        date_str = day.strftime("%Y-%m-%d")
        slots = calendar_manager.get_busy_slots(service, calendar_ids=[calendar_id],
                                                date_str=date_str)
        for s in slots:
            events.append({
                "date":    date_str,
                "summary": s.get("summary", "Busy"),
                "start":   s.get("start", ""),
                "end":     s.get("end", ""),
            })

    print(f"[CalendarPlanningAgent] Fetched {len(events)} events for next {days} days.")
    return events


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

def _load_reminders():
    if not os.path.exists(REMINDERS_FILE):
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _load_logseq_tasks():
    try:
        from logseq_later_agent import scan_all_later_tasks
        return scan_all_later_tasks(days=30)
    except Exception as e:
        print(f"[CalendarPlanningAgent] Could not load LogSeq tasks: {e}")
        return []


# ---------------------------------------------------------------------------
# Gemini planning
# ---------------------------------------------------------------------------

def _build_prompt(events, reminders, logseq_tasks):
    today      = datetime.date.today()
    week_end   = today + datetime.timedelta(days=6)
    dw_start   = get_config_value("DEEP_WORK_START", "09:00")
    dw_end     = get_config_value("DEEP_WORK_END",   "12:00")
    chronotype = get_config_value("CHRONOTYPE",      "morning_owl")

    # Format calendar events
    if events:
        cal_lines = []
        for e in events:
            cal_lines.append(f"  - {e['date']} {e['start'][11:16]}-{e['end'][11:16]}: {e['summary']}")
        cal_block = "\n".join(cal_lines)
    else:
        cal_block = "  (no events scheduled)"

    # Format pending tasks — combine reminders + logseq
    task_lines = []
    for r in reminders[:30]:
        due  = r.get("due_date", "no due date")
        notes = r.get("notes", "").strip()
        line = f"  - [Reminder] {r['task']}"
        if due:
            line += f" (due: {due})"
        if notes:
            line += f" — {notes[:80]}"
        task_lines.append(line)

    for t in logseq_tasks[:30]:
        props = t.get("properties", {})
        line  = f"  - [LogSeq/{t.get('source','?')}] {t['task']}"
        if "deadline" in props:
            line += f" (deadline: {props['deadline']})"
        task_lines.append(line)

    tasks_block = "\n".join(task_lines) if task_lines else "  (no pending tasks)"

    return f"""You are a professional personal productivity planner.

Today is {today.isoformat()} ({today.strftime('%A')}).
Planning horizon: {today.isoformat()} → {week_end.isoformat()}

User profile:
  - Chronotype: {chronotype}
  - Deep work window: {dw_start} – {dw_end}

EXISTING CALENDAR COMMITMENTS (next 7 days):
{cal_block}

PENDING TASKS (from Apple Reminders + LogSeq LATER):
{tasks_block}

Please produce a concrete day-by-day plan for the week. For each task:
  1. Assign it to a specific day (and suggest a time slot if possible).
  2. Respect existing calendar commitments — do not double-book.
  3. Schedule deep/focus work during the user's deep work window.
  4. Flag any tasks that are overdue or have a past due date.
  5. Note tasks that could be delegated or dropped if the week is full.

Output format — use this markdown structure:
### Day-by-Day Plan

#### {today.strftime('%A %d %B')}
- HH:MM – HH:MM | Task name | [category]
...

#### (next day)
...

### Overdue / Needs Attention
- ...

### Could defer / delegate
- ...
"""


def generate_plan(days=7, write_to_obsidian=False):
    """
    Run the full calendar planning pipeline using Gemini.
    Returns the suggestion text.
    """
    if not get_config_value("ENABLE_GEMINI", "false").lower() == "true":
        print("[CalendarPlanningAgent] Gemini is not enabled. Set ENABLE_GEMINI=true in .config")
        return None

    events        = _get_week_events(days=days)
    reminders     = _load_reminders()
    logseq_tasks  = _load_logseq_tasks()

    prompt = _build_prompt(events, reminders, logseq_tasks)
    system = (
        "You are an expert personal productivity planner. "
        "Be specific, actionable, and realistic. "
        "Use the provided data exactly — do not invent tasks or events."
    )

    print("[CalendarPlanningAgent] Sending to Gemini for planning suggestions...")
    suggestions, model = ai_orchestration.generate_with("gemini", prompt, system=system)
    print(f"[CalendarPlanningAgent] Received plan from {model}.")

    if not suggestions or suggestions.startswith("LLM error"):
        print(f"[CalendarPlanningAgent] Gemini error: {suggestions}")
        return None

    # Save suggestions file
    os.makedirs(DATAINPUT_DIR, exist_ok=True)
    today_str = datetime.date.today().isoformat()
    header    = f"# Calendar Plan — {today_str}\n_Generated by CalendarPlanningAgent via {model}_\n\n"
    with open(SUGGESTIONS_FILE, "w", encoding="utf-8") as f:
        f.write(header + suggestions + "\n")
    print(f"[CalendarPlanningAgent] Suggestions saved to {SUGGESTIONS_FILE}")

    # Optional: append to Obsidian planner
    if write_to_obsidian:
        _append_plan_to_obsidian(suggestions, today_str)

    return suggestions


def _append_plan_to_obsidian(suggestions, date_str):
    vault = get_config_value("WORKSPACE_DIR", None)
    if not vault:
        return
    rel     = get_config_value("OBSIDIAN_PLANNER_FILE", "Planner.md")
    planner = os.path.join(vault, rel)

    block_header = "## AI Calendar Plan"
    block = f"\n{block_header} ({date_str})\n{suggestions}\n"

    if os.path.exists(planner):
        with open(planner, "r", encoding="utf-8") as f:
            content = f.read()
        # Replace existing block if present
        if block_header in content:
            start = content.index(block_header)
            rest  = content[start + len(block_header):]
            nxt   = rest.find("\n## ")
            end   = start + len(block_header) + (nxt if nxt != -1 else len(rest))
            content = content[:start] + block.lstrip("\n") + content[end:]
        else:
            content = content.rstrip() + "\n" + block
    else:
        content = block

    with open(planner, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[CalendarPlanningAgent] Plan appended to Obsidian planner at {planner}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(write_to_obsidian=False):
    return generate_plan(write_to_obsidian=write_to_obsidian)


if __name__ == "__main__":
    result = run(write_to_obsidian=False)
    if result:
        print("\n" + "="*60)
        print(result)
