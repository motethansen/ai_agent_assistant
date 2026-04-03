import datetime
import pytest
from unittest.mock import patch
import local_calendar_agent


@pytest.fixture(autouse=True)
def patch_ics_path(tmp_path):
    """Redirect all ICS reads/writes to a temp file for every test."""
    ics_path = str(tmp_path / "local_calendar.ics")
    with patch.object(local_calendar_agent, "LOCAL_CALENDAR_FILE", ics_path):
        yield ics_path


def _future_dt(days_ahead=1, hour=10):
    """Return a naive datetime N days from today at the given hour."""
    d = datetime.date.today() + datetime.timedelta(days=days_ahead)
    return datetime.datetime.combine(d, datetime.time(hour, 0))


def test_add_event_creates_ics_file(patch_ics_path):
    """add_event() creates the ICS file and writes the summary to it."""
    import os
    start = _future_dt(1, 9)
    end = _future_dt(1, 10)
    local_calendar_agent.add_event("Daily standup", start, end)

    assert os.path.exists(patch_ics_path)
    with open(patch_ics_path, "rb") as f:
        content = f.read().decode("utf-8", errors="replace")
    assert "Daily standup" in content


def test_add_event_returns_uid():
    """add_event() returns a non-empty UID string."""
    start = _future_dt(1, 9)
    end = _future_dt(1, 10)
    uid = local_calendar_agent.add_event("Sprint review", start, end)
    assert isinstance(uid, str) and len(uid) > 0


def test_list_events_returns_added_event():
    """list_events() includes an event that was just added."""
    start = _future_dt(1, 14)
    end = _future_dt(1, 15)
    local_calendar_agent.add_event("Team lunch", start, end, description="Pizza day")

    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    events = local_calendar_agent.list_events(start_date=tomorrow, end_date=tomorrow)
    assert len(events) == 1
    assert events[0]["summary"] == "Team lunch"


def test_list_events_filters_by_date():
    """list_events() only returns events whose DTSTART falls in the given range."""
    day_near = datetime.date.today() + datetime.timedelta(days=2)
    day_far = datetime.date.today() + datetime.timedelta(days=15)

    near_start = datetime.datetime.combine(day_near, datetime.time(10, 0))
    near_end = datetime.datetime.combine(day_near, datetime.time(11, 0))
    far_start = datetime.datetime.combine(day_far, datetime.time(10, 0))
    far_end = datetime.datetime.combine(day_far, datetime.time(11, 0))

    local_calendar_agent.add_event("Near event", near_start, near_end)
    local_calendar_agent.add_event("Far event", far_start, far_end)

    # Query only the near window
    events = local_calendar_agent.list_events(start_date=day_near, end_date=day_near)
    assert len(events) == 1
    assert events[0]["summary"] == "Near event"


def test_remove_event_by_uid():
    """remove_event(uid=...) removes the matching event and leaves none behind."""
    start = _future_dt(3, 9)
    end = _future_dt(3, 10)
    uid = local_calendar_agent.add_event("To delete", start, end)

    removed = local_calendar_agent.remove_event(uid=uid)
    assert removed == 1

    target = datetime.date.today() + datetime.timedelta(days=3)
    events = local_calendar_agent.list_events(start_date=target, end_date=target)
    assert events == []


def test_remove_event_by_summary():
    """remove_event(summary=...) removes events matching as a case-insensitive substring."""
    start = _future_dt(4, 9)
    end = _future_dt(4, 10)
    local_calendar_agent.add_event("Team standup", start, end)

    removed = local_calendar_agent.remove_event(summary="standup")
    assert removed == 1
