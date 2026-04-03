"""
terminal_views.py — /today and /week Rich terminal views.

Renders today's calendar events and tasks (/today) or a 7-day summary (/week)
using Rich tables.  Calendar data is read from the YAML cache written by
CalendarAgent; tasks come from Obsidian, LogSeq and Apple Reminders.
"""
import os
import re
import time
import datetime

import yaml
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

CALENDAR_CACHE = "datainput/googlecalendar.yml"
CACHE_MAX_AGE_HOURS = 6
ICS_FILE = "datainput/local_calendar.ics"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_calendar_cache():
    """Refresh YAML cache if missing or older than CACHE_MAX_AGE_HOURS."""
    needs_refresh = False

    if not os.path.exists(CALENDAR_CACHE):
        needs_refresh = True
    else:
        age_seconds = time.time() - os.path.getmtime(CALENDAR_CACHE)
        if age_seconds > CACHE_MAX_AGE_HOURS * 3600:
            needs_refresh = True

    if needs_refresh:
        try:
            from calendar_agent import CalendarAgent
            agent = CalendarAgent()
            agent.fetch_and_store_calendar()
        except Exception as e:
            console.print(f"[yellow]Warning: could not refresh calendar cache: {e}[/yellow]")


def _load_calendar_events():
    """
    Load events from local ICS calendar (primary) or YAML cache (fallback).
    Returns list of dicts: {summary, start, end, description}.
    """
    # Primary: local ICS
    try:
        from local_calendar_agent import list_events
        today = datetime.date.today()
        far = today + datetime.timedelta(days=14)
        events = list_events(start_date=today, end_date=far)
        return [{"summary": e["summary"],
                 "start":   e["start"],
                 "end":     e["end"],
                 "description": e.get("description", "")} for e in events]
    except Exception:
        pass

    # Fallback: existing YAML cache (Google Calendar)
    if not os.path.exists(CALENDAR_CACHE):
        return []
    try:
        with open(CALENDAR_CACHE, "r") as f:
            data = yaml.safe_load(f) or {}
        return data.get("busy_slots", data.get("events", [])) or []
    except Exception:
        return []


def _load_unified_tasks():
    """
    Load tasks from Obsidian + LogSeq + Apple Reminders.

    Returns a list of dicts with at minimum:
        task      (str)
        due_date  (str YYYY-MM-DD or None)
        source    (str)
    """
    tasks = []

    # --- Obsidian ---
    try:
        from config_utils import get_config_value
        from obsidian_agent import ObsidianAgent

        workspace_dir = get_config_value("WORKSPACE_DIR", None)
        if workspace_dir and os.path.isdir(workspace_dir):
            agent = ObsidianAgent(workspace_dir=workspace_dir)
            raw = agent.get_tasks(todo=True, done=False)
            for t in raw:
                text = t.get("text", "")
                clean_text = re.sub(r"^\s*-\s+\[[ xX]\]\s+", "", text).strip()
                due_date = None

                # Extract 📅 YYYY-MM-DD
                dm = re.search(r"📅\s*(\d{4}-\d{2}-\d{2})", clean_text)
                if dm:
                    due_date = dm.group(1)
                    clean_text = clean_text.replace(f"📅 {due_date}", "").replace(f"📅{due_date}", "").strip()

                # Also support ^YYYY-MM-DD
                if not due_date:
                    dm2 = re.search(r"\^(\d{4}-\d{2}-\d{2})", clean_text)
                    if dm2:
                        due_date = dm2.group(1)
                        clean_text = clean_text.replace(f"^{due_date}", "").strip()

                # Strip trailing #category tags for display
                clean_text = re.sub(r"\s+#[\w./-]+", "", clean_text).strip()

                tasks.append({
                    "task": clean_text,
                    "due_date": due_date,
                    "source": "Obsidian",
                })
    except Exception as e:
        console.print(f"[yellow]Warning: could not load Obsidian tasks: {e}[/yellow]")

    # --- LogSeq ---
    try:
        from config_utils import get_config_value
        from logseq_agent import LogSeqAgent

        logseq_dir = get_config_value("LOGSEQ_DIR", None)
        if logseq_dir and os.path.exists(logseq_dir):
            ls = LogSeqAgent(logseq_dir)
            ls_tasks = ls.get_recent_tasks(days=14) + ls.get_all_page_tasks()
            for t in ls_tasks:
                due_date = t["properties"].get("deadline") or t["properties"].get("scheduled")
                tasks.append({
                    "task": t["task"],
                    "due_date": due_date,
                    "source": "LogSeq",
                })
    except Exception as e:
        console.print(f"[yellow]Warning: could not load LogSeq tasks: {e}[/yellow]")

    # --- Apple Reminders ---
    try:
        from reminders_manager import get_apple_reminders
        from config_utils import get_config_value

        list_name = get_config_value("APPLE_REMINDERS_LIST", "Reminders")
        apple = get_apple_reminders(list_name)
        for t in apple:
            tasks.append({
                "task": t.get("task", ""),
                "due_date": t.get("due_date"),
                "source": "Reminders",
            })
    except Exception as e:
        console.print(f"[yellow]Warning: could not load Apple Reminders: {e}[/yellow]")

    return tasks


def _parse_event_time(iso_str):
    """
    Return a datetime object from an ISO-8601 string or None if unparseable.
    Strips trailing Z and drops sub-second precision to keep fromisoformat happy
    on Python < 3.11.
    """
    if not iso_str:
        return None
    try:
        s = str(iso_str).replace("Z", "").split(".")[0]
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None


def _format_hhmm(dt):
    """Format a datetime as HH:MM, or return '—' for None."""
    if dt is None:
        return "—"
    return dt.strftime("%H:%M")


def _source_label(source: str) -> str:
    """Short display label for a task source."""
    if source.startswith("obsidian"):
        return "Obsidian"
    if source.startswith("logseq"):
        return "LogSeq"
    if source in ("Obsidian", "LogSeq", "Reminders"):
        return source
    return source


# ---------------------------------------------------------------------------
# Public view handlers
# ---------------------------------------------------------------------------

def handle_today_view():
    """
    Render today's calendar events and tasks as a Rich table.

    - Only tasks WITH a due_date equal to today (or overdue) are shown.
    - Overdue tasks are highlighted in red.
    - Events are sorted by start time, followed by tasks.
    """
    today = datetime.date.today()
    today_str = today.isoformat()
    day_name = today.strftime("%A %-d %B %Y")

    console.print()
    console.print(f"[bold cyan]Today — {day_name}[/bold cyan]")
    console.print("━" * 52)

    events = _load_calendar_events()
    all_tasks = _load_unified_tasks()

    # --- Filter events to today ---
    today_events = []
    for ev in events:
        dt = _parse_event_time(ev.get("start"))
        if dt and dt.date() == today:
            today_events.append(ev)

    # Sort by start time
    today_events.sort(key=lambda e: _parse_event_time(e.get("start")) or datetime.datetime.min)

    # --- Filter tasks to today or overdue (must have a due_date) ---
    today_tasks = []
    overdue_tasks = []
    for t in all_tasks:
        due = t.get("due_date")
        if not due:
            continue
        try:
            due_date = datetime.date.fromisoformat(str(due)[:10])
        except ValueError:
            continue
        if due_date == today:
            today_tasks.append(t)
        elif due_date < today:
            overdue_tasks.append(t)

    if not today_events and not today_tasks and not overdue_tasks:
        console.print("[dim]No events or tasks due today.[/dim]")
        console.print()
        return

    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold",
        pad_edge=False,
    )
    table.add_column("Time", width=7, style="dim")
    table.add_column("Type", width=12)
    table.add_column("Description", min_width=28)
    table.add_column("Source", width=12)

    # Events first
    for ev in today_events:
        start_dt = _parse_event_time(ev.get("start"))
        time_str = _format_hhmm(start_dt)
        summary = ev.get("summary", "(no title)")
        table.add_row(time_str, "[blue]📅 Event[/blue]", summary, "Google Cal")

    # Tasks due today
    for t in today_tasks:
        table.add_row("—", "[green]✅ Task[/green]", t["task"], _source_label(t["source"]))

    # Overdue tasks
    for t in overdue_tasks:
        due = t.get("due_date", "")
        desc = f"[red]{t['task']} (due {due})[/red]"
        table.add_row("—", "[red]⚠️  OVERDUE[/red]", desc, _source_label(t["source"]))

    console.print(table)
    console.print()


def handle_week_view():
    """
    Render a compact 7-day summary (today through today+6) as a Rich table.

    Counts events and tasks-with-due-dates per calendar day.
    Only tasks that have a due_date within the 7-day window are counted.
    """
    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=6)

    console.print()
    console.print(
        f"[bold cyan]Week view — "
        f"{today.strftime('%-d %b')} → {end_date.strftime('%-d %b %Y')}[/bold cyan]"
    )
    console.print("━" * 48)

    events = _load_calendar_events()
    all_tasks = _load_unified_tasks()

    # Build per-day buckets
    days = [today + datetime.timedelta(days=i) for i in range(7)]
    event_counts = {d: 0 for d in days}
    task_counts = {d: 0 for d in days}

    for ev in events:
        dt = _parse_event_time(ev.get("start"))
        if dt and dt.date() in event_counts:
            event_counts[dt.date()] += 1

    for t in all_tasks:
        due = t.get("due_date")
        if not due:
            continue
        try:
            due_date = datetime.date.fromisoformat(str(due)[:10])
        except ValueError:
            continue
        if due_date in task_counts:
            task_counts[due_date] += 1

    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold",
        pad_edge=False,
    )
    table.add_column("Date", width=12)
    table.add_column("Events", width=14)
    table.add_column("Tasks Due", min_width=20)

    for day in days:
        date_label = day.strftime("%a %-d %b")
        ev_count = event_counts[day]
        ta_count = task_counts[day]

        ev_str = f"{ev_count} event{'s' if ev_count != 1 else ''}" if ev_count else "[dim]—[/dim]"
        ta_str = f"{ta_count} task{'s' if ta_count != 1 else ''}" if ta_count else "[dim]—[/dim]"

        if day == today:
            date_label = f"[bold]{date_label}[/bold]"

        table.add_row(date_label, ev_str, ta_str)

    console.print(table)
    console.print()
