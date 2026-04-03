import datetime
from unittest.mock import patch

from icalendar import Calendar, Event

import local_calendar_agent


def _future_dt(days_ahead=1, hour=10):
    d = datetime.date.today() + datetime.timedelta(days=days_ahead)
    return datetime.datetime.combine(d, datetime.time(hour, 0))


def _write_external_ics(path, summary="Imported event", uid="external-uid-1"):
    cal = Calendar()
    cal.add("version", "2.0")
    cal.add("prodid", "-//AI Agent Assistant Tests//EN")
    event = Event()
    event.add("uid", uid)
    event.add("summary", summary)
    event.add("dtstart", _future_dt(2, 9))
    event.add("dtend", _future_dt(2, 10))
    event.add("dtstamp", datetime.datetime.now())
    cal.add_component(event)
    path.write_bytes(cal.to_ical())


def test_export_creates_file(tmp_path):
    ics_path = str(tmp_path / "local_calendar.ics")
    out_path = tmp_path / "out.ics"
    with patch.object(local_calendar_agent, "LOCAL_CALENDAR_FILE", ics_path):
        local_calendar_agent.add_event("Export me", _future_dt(1, 9), _future_dt(1, 10))
        local_calendar_agent.export_calendar(str(out_path))

    assert out_path.exists()


def test_export_raises_when_no_ics(tmp_path):
    ics_path = str(tmp_path / "missing.ics")
    with patch.object(local_calendar_agent, "LOCAL_CALENDAR_FILE", ics_path):
        try:
            local_calendar_agent.export_calendar(str(tmp_path / "out.ics"))
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError:
            pass


def test_import_adds_new_events(tmp_path):
    ics_path = str(tmp_path / "local_calendar.ics")
    external_path = tmp_path / "incoming.ics"
    _write_external_ics(external_path)

    with patch.object(local_calendar_agent, "LOCAL_CALENDAR_FILE", ics_path):
        imported, skipped = local_calendar_agent.import_calendar(str(external_path))
        events = local_calendar_agent.list_events(
            start_date=datetime.date(2000, 1, 1),
            end_date=datetime.date(2099, 12, 31),
        )

    assert (imported, skipped) == (1, 0)
    assert len(events) == 1


def test_import_skips_duplicates(tmp_path):
    ics_path = str(tmp_path / "local_calendar.ics")
    export_path = tmp_path / "exported.ics"
    with patch.object(local_calendar_agent, "LOCAL_CALENDAR_FILE", ics_path):
        local_calendar_agent.add_event("Duplicate event", _future_dt(3, 9), _future_dt(3, 10))
        local_calendar_agent.export_calendar(str(export_path))
        imported, skipped = local_calendar_agent.import_calendar(str(export_path))

    assert (imported, skipped) == (0, 1)
