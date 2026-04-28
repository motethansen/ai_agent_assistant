"""
Planning agent — reads Obsidian tasks + calendar events, generates a daily/weekly plan.

Triggered by:
    /plan           → today's focused schedule
    /week           → 7-day overview
    Morning cron    → writes Dashboard.md "Today's Plan" section
"""

import datetime
from pathlib import Path

from integrations.obsidian import ObsidianVault
import config
from llm import router

_SYSTEM_PROMPT = """You are a personal productivity assistant helping plan a focused workday.
Be concise and practical. Format your output as clean markdown.
Respect the user's deep work window and focus categories.
Never invent tasks — only work with what you are given."""


def _build_planning_prompt(
    tasks: list[dict],
    events: list[dict],
    mode: str,
    date: datetime.date,
) -> str:
    deep_start = config.planning.deep_work_start()
    deep_end = config.planning.deep_work_end()
    focus_cats = ", ".join(config.planning.focus_categories())
    chronotype = config.planning.chronotype()

    # Format tasks
    today = datetime.date.today()
    overdue, due_today, due_soon, backlog = [], [], [], []
    for t in tasks:
        d = t.get("due_date")
        if d:
            if d < today:
                overdue.append(t)
            elif d == today:
                due_today.append(t)
            elif d <= today + datetime.timedelta(days=7):
                due_soon.append(t)
        else:
            backlog.append(t)

    def fmt_tasks(lst):
        if not lst:
            return "  (none)"
        return "\n".join(
            f"  - {t['text']}"
            + (f" [due {t['due_date']}]" if t.get("due_date") else "")
            + (f" [{t['priority']}]" if t.get("priority") else "")
            for t in lst[:20]
        )

    # Format events
    def fmt_events(lst):
        if not lst:
            return "  (no events)"
        return "\n".join(
            f"  - {e.get('start', '?')} – {e.get('end', '?')}: {e.get('summary', 'Busy')}"
            for e in lst
        )

    if mode == "today":
        date_events = [e for e in events if _event_on_date(e, date)]
        return f"""Plan my day for {date.strftime('%A, %B %d %Y')}.

Deep work window: {deep_start} – {deep_end}
Chronotype: {chronotype}
Focus categories: {focus_cats}

Calendar events today:
{fmt_events(date_events)}

Tasks due TODAY:
{fmt_tasks(due_today)}

OVERDUE tasks (reschedule or handle):
{fmt_tasks(overdue[:5])}

High-priority backlog:
{fmt_tasks(sorted(backlog, key=lambda t: t.get('priority_weight', 99))[:10])}

Create a realistic hour-by-hour schedule. Include:
1. A focused time block table (Time | Task | Notes)
2. 2–3 tasks to carry forward if not done today
3. One sentence on what "done" looks like for today

Keep it short and actionable."""

    else:  # week
        week_end = date + datetime.timedelta(days=7)
        week_events = [e for e in events if _event_in_range(e, date, week_end)]
        return f"""Give me a weekly plan from {date.strftime('%B %d')} to {week_end.strftime('%B %d %Y')}.

Deep work window: {deep_start} – {deep_end}
Focus categories: {focus_cats}

Calendar events this week:
{fmt_events(week_events[:20])}

Tasks due this week:
{fmt_tasks(due_today + due_soon)}

OVERDUE (needs rescheduling):
{fmt_tasks(overdue[:5])}

Top backlog items:
{fmt_tasks(sorted(backlog, key=lambda t: t.get('priority_weight', 99))[:10])}

Produce:
1. A day-by-day table (Day | Events | Focus Task | Notes)
2. Top 3 priorities for the week
3. Any tasks to defer or drop

Be realistic — leave buffer time."""


def _event_on_date(event: dict, date: datetime.date) -> bool:
    start = event.get("start")
    if isinstance(start, datetime.datetime):
        return start.date() == date
    if isinstance(start, datetime.date):
        return start == date
    return False


def _event_in_range(event: dict, start: datetime.date, end: datetime.date) -> bool:
    ev_start = event.get("start")
    if isinstance(ev_start, datetime.datetime):
        ev_start = ev_start.date()
    if isinstance(ev_start, datetime.date):
        return start <= ev_start <= end
    return False


def _load_calendar_events(days_ahead: int = 7) -> list[dict]:
    """Load events from local ICS calendar."""
    try:
        from integrations.calendar import CalendarReader
        reader = CalendarReader()
        return reader.get_events(days_ahead=days_ahead)
    except Exception:
        return []


def run(mode: str = "today", date: datetime.date | None = None) -> str:
    """
    Generate a plan. mode='today' or 'week'.
    Returns the plan as a markdown string.
    """
    date = date or datetime.date.today()
    vault = ObsidianVault()

    tasks = vault.get_tasks()
    events = _load_calendar_events(days_ahead=7 if mode == "today" else 14)

    prompt = _build_planning_prompt(tasks, events, mode, date)
    plan = router.ask(prompt, task="planning", system=_SYSTEM_PROMPT)

    # Write to Dashboard
    section = "today-plan" if mode == "today" else "week-plan"
    header = f"_Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
    vault.write_section(section, header + plan)

    return plan


def run_today() -> str:
    return run(mode="today")


def run_week() -> str:
    return run(mode="week")
