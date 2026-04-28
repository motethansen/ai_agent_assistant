"""
Calendar integration — ICS read/write with optional Google Calendar API.

The ICS file is always the source of truth and the export fallback.
Google Calendar API is optional (GOOGLE_CAL_ENABLED=true in .config).
"""

import datetime
import uuid
from pathlib import Path
from typing import Any

from icalendar import Calendar, Event
import config


def _ics_path() -> Path:
    return Path(config.paths.local_calendar())


def _load_cal() -> Calendar:
    path = _ics_path()
    if not path.exists():
        cal = Calendar()
        cal.add("version", "2.0")
        cal.add("prodid", "-//AI Agent Assistant//EN")
        return cal
    return Calendar.from_ical(path.read_bytes())


def _save_cal(cal: Calendar) -> None:
    path = _ics_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cal.to_ical())


def _event_to_dict(component) -> dict:
    start = component.get("dtstart")
    end = component.get("dtend")
    start_val = start.dt if start else None
    end_val = end.dt if end else None
    return {
        "uid": str(component.get("uid", "")),
        "summary": str(component.get("summary", "Busy")),
        "start": start_val,
        "end": end_val,
        "description": str(component.get("description", "")),
        "all_day": isinstance(start_val, datetime.date) and not isinstance(start_val, datetime.datetime),
    }


# ── CalendarReader ────────────────────────────────────────────────────────────

class CalendarReader:
    """Read events from the local ICS calendar."""

    def get_events(
        self,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
        days_ahead: int = 7,
    ) -> list[dict]:
        """Return events in the given date range. Defaults to today + days_ahead."""
        today = datetime.date.today()
        start_date = start_date or today
        end_date = end_date or (today + datetime.timedelta(days=days_ahead))

        cal = _load_cal()
        events = []
        for component in cal.walk():
            if component.name != "VEVENT":
                continue
            ev = _event_to_dict(component)
            ev_start = ev["start"]
            if ev_start is None:
                continue
            ev_date = ev_start.date() if isinstance(ev_start, datetime.datetime) else ev_start
            if start_date <= ev_date <= end_date:
                events.append(ev)

        events.sort(key=lambda e: e["start"] or datetime.datetime.min)
        return events

    def get_today_events(self) -> list[dict]:
        return self.get_events(days_ahead=0)

    def get_busy_slots(self, date: datetime.date) -> list[tuple]:
        """Return list of (start_time, end_time) busy tuples for a given date."""
        events = self.get_events(start_date=date, end_date=date)
        slots = []
        for e in events:
            s, en = e["start"], e["end"]
            if isinstance(s, datetime.datetime) and isinstance(en, datetime.datetime):
                slots.append((s.time(), en.time()))
        return slots


# ── CalendarWriter ────────────────────────────────────────────────────────────

class CalendarWriter:
    """Write events to the local ICS calendar and optionally push to Google Calendar."""

    def add_event(
        self,
        summary: str,
        start: datetime.datetime | datetime.date,
        end: datetime.datetime | datetime.date,
        description: str = "",
        uid: str | None = None,
    ) -> str:
        """Add an event. Returns the UID."""
        uid = uid or str(uuid.uuid4())
        cal = _load_cal()

        event = Event()
        event.add("uid", uid)
        event.add("summary", summary)
        event.add("dtstart", start)
        event.add("dtend", end)
        event.add("dtstamp", datetime.datetime.now())
        if description:
            event.add("description", description)
        cal.add_component(event)
        _save_cal(cal)

        if config.calendar.google_enabled():
            _push_to_google(summary, start, end, description, uid)

        return uid

    def remove_event(self, uid: str | None = None, summary: str | None = None) -> int:
        """Remove matching events. Returns count removed."""
        if uid is None and summary is None:
            raise ValueError("uid or summary required")
        cal = _load_cal()
        to_remove = []
        for component in cal.walk():
            if component.name != "VEVENT":
                continue
            if uid and str(component.get("uid", "")).lower() == uid.lower():
                to_remove.append(component)
            elif summary and summary.lower() in str(component.get("summary", "")).lower():
                to_remove.append(component)

        for component in to_remove:
            cal.subcomponents.remove(component)
        _save_cal(cal)
        return len(to_remove)

    def update_event(self, uid: str, **fields) -> bool:
        """Update fields on an existing event by UID. Returns True if found."""
        cal = _load_cal()
        for component in cal.walk():
            if component.name != "VEVENT":
                continue
            if str(component.get("uid", "")).lower() == uid.lower():
                for key, val in fields.items():
                    component.add(key, val)
                _save_cal(cal)
                return True
        return False

    def export_ics(self, dest_path: str | None = None) -> Path:
        """Copy the ICS file to dest_path (or output/ dir) for calendar app import."""
        src = _ics_path()
        if not src.exists():
            return src
        if dest_path:
            dst = Path(dest_path)
        else:
            dst = Path(config.paths.output()) / "ai_agent_calendar.ics"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        return dst

    def sync_from_obsidian(self, tasks: list[dict]) -> dict:
        """
        Sync #gcal-tagged Obsidian tasks with due dates into the ICS calendar.
        Returns {added, skipped}.
        """
        stats = {"added": 0, "skipped": 0}
        existing_events = CalendarReader().get_events(days_ahead=365)
        existing_summaries = {e["summary"].lower() for e in existing_events}

        for task in tasks:
            if not task.get("gcal") or not task.get("due_date"):
                stats["skipped"] += 1
                continue
            summary = task.get("text", "Task")
            if summary.lower() in existing_summaries:
                stats["skipped"] += 1
                continue

            due = task["due_date"]
            if task.get("due_time"):
                try:
                    h, m = task["due_time"].split(":")
                    start_dt = datetime.datetime.combine(due, datetime.time(int(h), int(m)))
                    end_dt = start_dt + datetime.timedelta(hours=1)
                except ValueError:
                    start_dt = due
                    end_dt = due
            else:
                start_dt = due
                end_dt = due

            self.add_event(summary, start_dt, end_dt)
            existing_summaries.add(summary.lower())
            stats["added"] += 1

        return stats


# ── Optional Google Calendar push ─────────────────────────────────────────────

def _push_to_google(summary, start, end, description, uid) -> None:
    """Push a single event to Google Calendar via the API."""
    creds_file = config.calendar.google_credentials_file()
    if not creds_file or not Path(creds_file).exists():
        return
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(creds_file)
        service = build("calendar", "v3", credentials=creds)

        def _dt_str(dt):
            if isinstance(dt, datetime.datetime):
                return {"dateTime": dt.isoformat(), "timeZone": "UTC"}
            return {"date": dt.isoformat()}

        body = {
            "summary": summary,
            "description": description,
            "start": _dt_str(start),
            "end": _dt_str(end),
            "iCalUID": uid,
        }
        service.events().insert(calendarId="primary", body=body).execute()
    except Exception:
        pass  # Google Cal is optional — never block on failure
