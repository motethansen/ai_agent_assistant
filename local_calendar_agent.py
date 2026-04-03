"""
local_calendar_agent.py — Local ICS calendar engine (RFC 5545).

Reads and writes datainput/local_calendar.ics using the icalendar library.
No Google credentials required. The .ics file is the source of truth and
can be imported by Google Calendar, Apple Calendar, or Outlook at any time.

Public API:
    add_event(summary, start_dt, end_dt, description=None) -> str  (uid)
    remove_event(uid=None, summary=None) -> int  (events removed)
    list_events(start_date=None, end_date=None) -> list[dict]
    get_today_events() -> list[dict]
"""
import datetime
import os
import uuid

from icalendar import Calendar, Event
from config_utils import get_config_value

LOCAL_CALENDAR_FILE = get_config_value("LOCAL_CALENDAR_FILE", "datainput/local_calendar.ics")


def _load_cal():
    """Read the ICS file and return a Calendar. Creates it with headers if missing."""
    path = LOCAL_CALENDAR_FILE
    if not os.path.exists(path):
        cal = Calendar()
        cal.add("version", "2.0")
        cal.add("prodid", "-//AI Agent Assistant//EN")
        return cal
    with open(path, "rb") as f:
        return Calendar.from_ical(f.read())


def _save_cal(cal):
    """Write the Calendar object back to the ICS file."""
    path = LOCAL_CALENDAR_FILE
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(cal.to_ical())


def add_event(summary, start_dt, end_dt, description=None):
    """Append a VEVENT to the ICS file. Returns the event UID string."""
    cal = _load_cal()
    event = Event()
    uid = str(uuid.uuid4())
    event.add("uid", uid)
    event.add("summary", summary)
    event.add("dtstart", start_dt)
    event.add("dtend", end_dt)
    event.add("dtstamp", datetime.datetime.now())
    if description:
        event.add("description", description)
    cal.add_component(event)
    _save_cal(cal)
    return uid


def remove_event(uid=None, summary=None):
    """Remove matching VEVENTs. Returns count of events removed.

    uid: exact match (case-insensitive) on UID
    summary: case-insensitive substring match on SUMMARY
    Raises ValueError if neither arg given.
    """
    if uid is None and summary is None:
        raise ValueError("Either uid or summary must be provided")

    cal = _load_cal()
    to_remove = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        if uid is not None:
            event_uid = str(component.get("uid", "")).lower()
            if event_uid == uid.lower():
                to_remove.append(component)
        else:
            event_summary = str(component.get("summary", "")).lower()
            if summary.lower() in event_summary:
                to_remove.append(component)

    for component in to_remove:
        cal.subcomponents.remove(component)

    _save_cal(cal)
    return len(to_remove)


def list_events(start_date=None, end_date=None):
    """Return events whose DTSTART falls within [start_date, end_date].

    Both default to today and today+7days if not provided.
    Returns list of dicts: {uid, summary, start, end, description}
    where start/end are ISO format strings, sorted ascending.
    Handles both date-naive and date-aware DTSTART values.
    """
    today = datetime.date.today()
    if start_date is None:
        start_date = today
    if end_date is None:
        end_date = today + datetime.timedelta(days=7)

    cal = _load_cal()
    results = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        dtstart_prop = component.get("dtstart")
        if dtstart_prop is None:
            continue
        dtstart_val = dtstart_prop.dt if hasattr(dtstart_prop, "dt") else dtstart_prop

        # Normalize to date for range comparison — strip timezone if present
        if isinstance(dtstart_val, datetime.datetime):
            event_date = dtstart_val.date()
        elif isinstance(dtstart_val, datetime.date):
            event_date = dtstart_val
        else:
            continue

        if not (start_date <= event_date <= end_date):
            continue

        dtend_prop = component.get("dtend")
        if dtend_prop is not None:
            dtend_val = dtend_prop.dt if hasattr(dtend_prop, "dt") else dtend_prop
            end_iso = dtend_val.isoformat() if dtend_val is not None else None
        else:
            end_iso = None

        desc_prop = component.get("description")
        description = str(desc_prop) if desc_prop is not None else None

        results.append({
            "uid": str(component.get("uid", "")),
            "summary": str(component.get("summary", "")),
            "start": dtstart_val.isoformat(),
            "end": end_iso,
            "description": description,
        })

    results.sort(key=lambda x: x["start"])
    return results


def get_today_events():
    """Return only today's events."""
    today = datetime.date.today()
    return list_events(start_date=today, end_date=today)


def _ics_path():
    """Return the configured ICS file path."""
    return LOCAL_CALENDAR_FILE


def export_calendar(dest_path=None) -> str:
    """Copy local_calendar.ics to dest_path (default: ~/calendar_export.ics).
    Returns the destination path. Raises if source does not exist."""
    import shutil
    src = _ics_path()
    if not os.path.exists(src):
        raise FileNotFoundError(f"No local calendar found at {src}")
    dest = os.path.expanduser(dest_path or "~/calendar_export.ics")
    shutil.copy2(src, dest)
    return dest


def import_calendar(src_path: str) -> tuple[int, int]:
    """Merge events from an external .ics file into the local calendar.
    Deduplicates by UID — existing UIDs are skipped.
    Returns (imported_count, skipped_count). Handles malformed files gracefully."""
    import logging
    from icalendar import Calendar

    local = _load_cal()
    existing_uids = {
        str(c.get("UID", "")).lower()
        for c in local.walk()
        if c.name == "VEVENT"
    }
    imported = skipped = 0
    try:
        with open(os.path.expanduser(src_path), "rb") as f:
            external = Calendar.from_ical(f.read())
    except Exception as e:
        logging.getLogger(__name__).warning("import_calendar: could not parse %s: %s", src_path, e)
        return 0, 0
    for component in external.walk():
        if component.name != "VEVENT":
            continue
        uid = str(component.get("UID", "")).lower()
        if uid and uid in existing_uids:
            skipped += 1
            continue
        local.add_component(component)
        imported += 1
    _save_cal(local)
    return imported, skipped
