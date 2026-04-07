"""
Apple Calendar integration via osascript.

Only works on macOS. All functions are no-ops on other platforms.

Config key:
  APPLE_CALENDAR_NAME — name of the calendar to add events to (default: "Home")
"""

import subprocess
import sys
import datetime
from config_utils import get_config_value


def is_available():
    """True when running on macOS."""
    return sys.platform == "darwin"


def _calendar_name():
    return get_config_value("APPLE_CALENDAR_NAME", "Home")


def add_event(summary: str, start_dt: datetime.datetime, end_dt: datetime.datetime,
              description: str = None) -> bool:
    """
    Add an event to Apple Calendar via osascript.
    Returns True on success, False on failure.
    """
    if not is_available():
        return False

    _ensure_calendar_running()
    cal = _calendar_name()
    desc_line = description or ""

    # AppleScript date format: "Monday, April 7, 2026 at 9:00:00 AM"
    def _as_date(dt: datetime.datetime) -> str:
        return dt.strftime("%-m/%-d/%Y %-I:%M:%S %p")

    script = f"""
tell application "Calendar"
    set startDate to date "{_as_date(start_dt)}"
    set endDate to date "{_as_date(end_dt)}"
    set targetCal to first calendar whose name is "{cal}"
    make new event at end of events of targetCal with properties {{¬
        summary:"{summary.replace('"', "'")}", ¬
        start date:startDate, ¬
        end date:endDate, ¬
        description:"{desc_line.replace('"', "'")}"¬
    }}
end tell
"""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            print(f"[AppleCalendar] osascript error: {result.stderr.strip()}")
            return False
        return True
    except Exception as e:
        print(f"[AppleCalendar] Failed: {e}")
        return False


def _ensure_calendar_running():
    """Launch Calendar.app if not already running and wait for it to be ready."""
    import time
    subprocess.run(["open", "-a", "Calendar"], capture_output=True)
    time.sleep(2)


def list_calendars() -> list[str]:
    """Return names of all calendars in Apple Calendar (launches the app if needed)."""
    if not is_available():
        return []
    _ensure_calendar_running()
    script = 'tell application "Calendar" to return name of every calendar'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return [c.strip() for c in result.stdout.strip().split(",") if c.strip()]
        print(f"[AppleCalendar] list_calendars error: {result.stderr.strip()}")
    except Exception as e:
        print(f"[AppleCalendar] list_calendars failed: {e}")
    return []
