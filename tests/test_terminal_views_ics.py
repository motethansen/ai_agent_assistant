import pytest
import os
from unittest.mock import patch
import terminal_views


def test_load_calendar_events_uses_ics_when_available():
    """_load_calendar_events() returns ICS events when local_calendar_agent works."""
    fake_events = [
        {
            "uid": "1",
            "summary": "Standup",
            "start": "2026-04-03T09:00:00",
            "end": "2026-04-03T09:30:00",
            "description": "",
        }
    ]
    with patch("local_calendar_agent.list_events", return_value=fake_events):
        result = terminal_views._load_calendar_events()

    assert len(result) == 1
    assert result[0]["summary"] == "Standup"


def test_load_calendar_events_falls_back_to_yaml(tmp_path):
    """_load_calendar_events() falls back to YAML cache when ICS import fails."""
    import yaml

    yaml_file = tmp_path / "googlecalendar.yml"
    yaml_file.write_text(
        yaml.dump({"busy_slots": [{"summary": "YAML event", "start": "2026-04-03T10:00:00", "end": "2026-04-03T11:00:00"}]})
    )

    with patch("local_calendar_agent.list_events", side_effect=Exception("no ICS")), \
         patch.object(terminal_views, "CALENDAR_CACHE", str(yaml_file)):
        result = terminal_views._load_calendar_events()

    assert len(result) == 1
    assert result[0]["summary"] == "YAML event"


def test_load_calendar_events_returns_empty_on_both_fail(tmp_path):
    """_load_calendar_events() returns [] when both ICS and YAML are unavailable."""
    nonexistent = str(tmp_path / "does_not_exist.yml")

    with patch("local_calendar_agent.list_events", side_effect=Exception("no ICS")), \
         patch.object(terminal_views, "CALENDAR_CACHE", nonexistent):
        result = terminal_views._load_calendar_events()

    assert result == []
