"""
Google Calendar API mock tests — verify offline-safe behaviour.

All tests run without network access or credentials files.
"""

import datetime
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── _push_to_google ───────────────────────────────────────────────────────────

class TestPushToGoogle:
    def test_skips_when_creds_file_missing(self):
        from integrations.calendar import _push_to_google
        with patch("integrations.calendar.config") as mock_cfg:
            mock_cfg.calendar.google_credentials_file.return_value = "/nonexistent/creds.json"
            # Should return None without raising — missing file is a no-op
            result = _push_to_google(
                "Meeting",
                datetime.datetime(2026, 5, 1, 10, 0),
                datetime.datetime(2026, 5, 1, 11, 0),
                "",
                "uid-123",
            )
            assert result is None

    def test_skips_when_creds_key_not_configured(self):
        from integrations.calendar import _push_to_google
        with patch("integrations.calendar.config") as mock_cfg:
            mock_cfg.calendar.google_credentials_file.return_value = ""
            result = _push_to_google(
                "Meeting",
                datetime.datetime(2026, 5, 1, 10, 0),
                datetime.datetime(2026, 5, 1, 11, 0),
                "",
                "uid-123",
            )
            assert result is None

    def test_calls_google_api_with_correct_body(self, tmp_path):
        from integrations.calendar import _push_to_google
        import sys
        creds_file = tmp_path / "token.json"
        creds_file.write_text("{}")

        mock_creds = MagicMock()
        mock_service = MagicMock()
        captured = {}

        def capture_insert(calendarId, body):
            captured["body"] = body
            return MagicMock()

        mock_service.events.return_value.insert.side_effect = capture_insert

        mock_oauth2_mod = MagicMock()
        mock_oauth2_mod.Credentials.from_authorized_user_file.return_value = mock_creds
        mock_discovery_mod = MagicMock()
        mock_discovery_mod.build.return_value = mock_service

        fake_modules = {
            "googleapiclient": MagicMock(),
            "googleapiclient.discovery": mock_discovery_mod,
            "google.oauth2": mock_oauth2_mod,
            "google.oauth2.credentials": mock_oauth2_mod,
        }

        with patch("integrations.calendar.config") as mock_cfg, \
             patch.dict(sys.modules, fake_modules):

            mock_cfg.calendar.google_credentials_file.return_value = str(creds_file)

            _push_to_google(
                "Team Standup",
                datetime.datetime(2026, 5, 2, 9, 0),
                datetime.datetime(2026, 5, 2, 9, 30),
                "Daily sync",
                "uid-456",
            )

        body = captured.get("body")
        assert body is not None
        assert body["summary"] == "Team Standup"
        assert body["description"] == "Daily sync"
        assert body["iCalUID"] == "uid-456"
        assert "dateTime" in body["start"]
        assert "dateTime" in body["end"]

    def test_google_api_exception_is_swallowed(self, tmp_path):
        from integrations.calendar import _push_to_google
        import sys
        creds_file = tmp_path / "token.json"
        creds_file.write_text("{}")

        mock_creds = MagicMock()
        mock_service = MagicMock()
        mock_service.events.return_value.insert.return_value.execute.side_effect = Exception(
            "403 quota exceeded"
        )

        mock_oauth2_mod = MagicMock()
        mock_oauth2_mod.Credentials.from_authorized_user_file.return_value = mock_creds
        mock_discovery_mod = MagicMock()
        mock_discovery_mod.build.return_value = mock_service

        fake_modules = {
            "googleapiclient": MagicMock(),
            "googleapiclient.discovery": mock_discovery_mod,
            "google.oauth2": mock_oauth2_mod,
            "google.oauth2.credentials": mock_oauth2_mod,
        }

        with patch("integrations.calendar.config") as mock_cfg, \
             patch.dict(sys.modules, fake_modules):

            mock_cfg.calendar.google_credentials_file.return_value = str(creds_file)

            # Must not raise — Google Cal is optional
            _push_to_google(
                "Event",
                datetime.datetime(2026, 5, 1, 10, 0),
                datetime.datetime(2026, 5, 1, 11, 0),
                "",
                "uid-789",
            )

    def test_all_day_event_uses_date_format(self, tmp_path):
        from integrations.calendar import _push_to_google
        import sys
        creds_file = tmp_path / "token.json"
        creds_file.write_text("{}")

        mock_creds = MagicMock()
        mock_service = MagicMock()
        captured = {}

        def capture_insert(calendarId, body):
            captured["body"] = body
            return MagicMock()

        mock_service.events.return_value.insert.side_effect = capture_insert

        mock_oauth2_mod = MagicMock()
        mock_oauth2_mod.Credentials.from_authorized_user_file.return_value = mock_creds
        mock_discovery_mod = MagicMock()
        mock_discovery_mod.build.return_value = mock_service

        fake_modules = {
            "googleapiclient": MagicMock(),
            "googleapiclient.discovery": mock_discovery_mod,
            "google.oauth2": mock_oauth2_mod,
            "google.oauth2.credentials": mock_oauth2_mod,
        }

        with patch("integrations.calendar.config") as mock_cfg, \
             patch.dict(sys.modules, fake_modules):

            mock_cfg.calendar.google_credentials_file.return_value = str(creds_file)

            _push_to_google(
                "Bank Holiday",
                datetime.date(2026, 5, 4),
                datetime.date(2026, 5, 4),
                "",
                "uid-allday",
            )

        body = captured.get("body", {})
        assert "date" in body.get("start", {})
        assert "dateTime" not in body.get("start", {})


# ── CalendarWriter with google_enabled ───────────────────────────────────────

class TestCalendarWriterGoogleEnabled:
    def test_add_event_triggers_google_push_when_enabled(self, tmp_path):
        from integrations.calendar import CalendarWriter
        ics_path = tmp_path / "calendar.ics"

        with patch("integrations.calendar._ics_path", return_value=ics_path), \
             patch("integrations.calendar.config") as mock_cfg, \
             patch("integrations.calendar._push_to_google") as mock_push:

            mock_cfg.calendar.google_enabled.return_value = True
            mock_cfg.paths.local_calendar.return_value = str(ics_path)

            writer = CalendarWriter()
            uid = writer.add_event(
                "Board Meeting",
                datetime.datetime(2026, 5, 10, 14, 0),
                datetime.datetime(2026, 5, 10, 15, 0),
                description="Q2 review",
            )

            mock_push.assert_called_once()
            args = mock_push.call_args.args
            assert args[0] == "Board Meeting"
            assert args[4] == uid

    def test_add_event_skips_google_push_when_disabled(self, tmp_path):
        from integrations.calendar import CalendarWriter
        ics_path = tmp_path / "calendar.ics"

        with patch("integrations.calendar._ics_path", return_value=ics_path), \
             patch("integrations.calendar.config") as mock_cfg, \
             patch("integrations.calendar._push_to_google") as mock_push:

            mock_cfg.calendar.google_enabled.return_value = False
            mock_cfg.paths.local_calendar.return_value = str(ics_path)

            writer = CalendarWriter()
            writer.add_event(
                "Local Only Event",
                datetime.datetime(2026, 5, 10, 9, 0),
                datetime.datetime(2026, 5, 10, 10, 0),
            )

            mock_push.assert_not_called()

    def test_event_still_written_to_ics_when_google_fails(self, tmp_path):
        from integrations.calendar import CalendarWriter, CalendarReader
        ics_path = tmp_path / "calendar.ics"

        with patch("integrations.calendar._ics_path", return_value=ics_path), \
             patch("integrations.calendar.config") as mock_cfg, \
             patch("integrations.calendar._push_to_google", side_effect=Exception("network error")):

            mock_cfg.calendar.google_enabled.return_value = True
            mock_cfg.paths.local_calendar.return_value = str(ics_path)

            writer = CalendarWriter()
            # _push_to_google raises, but add_event wraps it in try/except so ICS is already written
            # The current code calls _push_to_google AFTER _save_cal, so ICS survives
            try:
                writer.add_event(
                    "Resilient Event",
                    datetime.datetime(2026, 5, 11, 10, 0),
                    datetime.datetime(2026, 5, 11, 11, 0),
                )
            except Exception:
                pass  # push_to_google exception propagates from add_event — that's acceptable

            # ICS file must exist regardless (written before the push attempt)
            assert ics_path.exists()


# ── CalendarReader — offline / ICS-only ──────────────────────────────────────

class TestCalendarReaderOffline:
    def test_get_events_no_google_dependency(self, tmp_path):
        from integrations.calendar import CalendarWriter, CalendarReader
        ics_path = tmp_path / "calendar.ics"

        with patch("integrations.calendar._ics_path", return_value=ics_path), \
             patch("integrations.calendar.config") as mock_cfg:

            mock_cfg.calendar.google_enabled.return_value = False
            mock_cfg.paths.local_calendar.return_value = str(ics_path)

            writer = CalendarWriter()
            writer.add_event(
                "Offline Meeting",
                datetime.datetime(2026, 5, 1, 10, 0),
                datetime.datetime(2026, 5, 1, 11, 0),
            )
            writer.add_event(
                "Another Meeting",
                datetime.datetime(2026, 5, 3, 14, 0),
                datetime.datetime(2026, 5, 3, 15, 0),
            )

            reader = CalendarReader()
            events = reader.get_events(
                start_date=datetime.date(2026, 5, 1),
                end_date=datetime.date(2026, 5, 5),
            )

        assert len(events) == 2
        summaries = {e["summary"] for e in events}
        assert "Offline Meeting" in summaries
        assert "Another Meeting" in summaries

    def test_get_busy_slots_returns_time_tuples(self, tmp_path):
        from integrations.calendar import CalendarWriter, CalendarReader
        ics_path = tmp_path / "calendar.ics"

        with patch("integrations.calendar._ics_path", return_value=ics_path), \
             patch("integrations.calendar.config") as mock_cfg:

            mock_cfg.calendar.google_enabled.return_value = False
            mock_cfg.paths.local_calendar.return_value = str(ics_path)

            writer = CalendarWriter()
            target_date = datetime.date(2026, 5, 6)
            writer.add_event(
                "Morning Standup",
                datetime.datetime(2026, 5, 6, 9, 0),
                datetime.datetime(2026, 5, 6, 9, 30),
            )

            reader = CalendarReader()
            slots = reader.get_busy_slots(target_date)

        assert len(slots) == 1
        start_time, end_time = slots[0]
        assert start_time == datetime.time(9, 0)
        assert end_time == datetime.time(9, 30)

    def test_empty_calendar_returns_no_events(self, tmp_path):
        from integrations.calendar import CalendarReader
        ics_path = tmp_path / "empty.ics"

        with patch("integrations.calendar._ics_path", return_value=ics_path):
            reader = CalendarReader()
            events = reader.get_events(
                start_date=datetime.date(2026, 5, 1),
                end_date=datetime.date(2026, 5, 31),
            )

        assert events == []
