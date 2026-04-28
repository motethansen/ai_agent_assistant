"""
Core tests for the new agent architecture.
Tests use fixtures and mocks — no API calls, no file system writes to real vault.
"""

import datetime
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Config ────────────────────────────────────────────────────────────────────

class TestConfig:
    def test_get_default(self):
        import config
        assert config.get("MISSING_KEY_XYZ", "fallback") == "fallback"

    def test_get_bool_defaults(self):
        import config
        assert config.get_bool("MISSING_BOOL", False) is False
        assert config.get_bool("MISSING_BOOL", True) is True

    def test_get_list_empty(self):
        import config
        result = config.get_list("MISSING_LIST", ["a", "b"])
        assert result == ["a", "b"]

    def test_validate_returns_list(self):
        import config
        warnings = config.validate()
        assert isinstance(warnings, list)

    def test_summary_has_required_keys(self):
        import config
        s = config.summary()
        for key in ("obsidian", "logseq", "llm_chat", "llm_planning", "sync_interval"):
            assert key in s


# ── LLM Router ────────────────────────────────────────────────────────────────

class TestLLMRouter:
    def test_provider_for_returns_string(self):
        from llm.router import provider_for
        for task in ("chat", "planning", "notes", "quick", "offline"):
            result = provider_for(task)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_fallback_chain_starts_with_primary(self):
        from llm.router import _build_fallback_chain
        chain = _build_fallback_chain("groq")
        assert chain[0] == "groq"

    def test_fallback_chain_no_duplicates(self):
        from llm.router import _build_fallback_chain
        chain = _build_fallback_chain("gemini-flash")
        assert len(chain) == len(set(chain))

    def test_all_providers_returns_list(self):
        from llm.router import all_providers
        providers = all_providers()
        assert isinstance(providers, list)
        assert len(providers) > 0
        for p in providers:
            assert "provider" in p
            assert "available" in p

    def test_ask_raises_on_no_providers(self):
        from llm.router import ask
        with patch("llm.router._import_provider") as mock_import:
            mock_mod = MagicMock()
            mock_mod.is_available.return_value = False
            mock_import.return_value = mock_mod
            with pytest.raises(RuntimeError, match="All LLM providers failed"):
                ask("test prompt", task="chat")


# ── LogSeq Integration ────────────────────────────────────────────────────────

class TestLogSeqReader:
    def test_parse_tasks_basic(self):
        from integrations.logseq import LogSeqReader
        reader = LogSeqReader(logseq_dir="/nonexistent")
        text = "- LATER Buy groceries\n- TODO Write report\n- Just a note"
        tasks = reader.parse_tasks(text, source="test")
        assert len(tasks) == 2
        assert tasks[0]["task"] == "Buy groceries"
        assert tasks[1]["task"] == "Write report"

    def test_parse_tasks_with_properties(self):
        from integrations.logseq import LogSeqReader
        reader = LogSeqReader(logseq_dir="/nonexistent")
        text = "- LATER Research topic\n  :category: dev\n  :url: https://example.com"
        tasks = reader.parse_tasks(text, source="test")
        assert len(tasks) == 1
        assert tasks[0]["properties"]["category"] == "dev"
        assert "https://example.com" in tasks[0]["task"]

    def test_parse_tasks_strips_macros(self):
        from integrations.logseq import LogSeqReader
        reader = LogSeqReader(logseq_dir="/nonexistent")
        text = "- LATER {{renderer plugin, value}} Clean task"
        tasks = reader.parse_tasks(text, source="test")
        assert len(tasks) == 1
        assert "renderer" not in tasks[0]["task"]

    def test_empty_text_returns_no_tasks(self):
        from integrations.logseq import LogSeqReader
        reader = LogSeqReader(logseq_dir="/nonexistent")
        assert reader.parse_tasks("") == []
        assert reader.parse_tasks("Just a regular note") == []

    def test_parse_date_from_text(self):
        from integrations.logseq import parse_date_from_text
        assert parse_date_from_text("2026-03-15") == "2026_03_15"
        assert parse_date_from_text("March 15, 2026") == "2026_03_15"
        assert parse_date_from_text("no date here") is None


# ── Obsidian Integration ──────────────────────────────────────────────────────

class TestObsidianVault:
    def test_parse_task_metadata_basic(self):
        from integrations.obsidian import parse_task_metadata
        result = parse_task_metadata("- [ ] Buy milk 📅 2026-05-01")
        assert result["text"] == "Buy milk"
        assert result["due_date"] == datetime.date(2026, 5, 1)
        assert result["is_done"] is False

    def test_parse_task_metadata_done(self):
        from integrations.obsidian import parse_task_metadata
        result = parse_task_metadata("- [x] Done task")
        assert result["is_done"] is True

    def test_parse_task_metadata_priority(self):
        from integrations.obsidian import parse_task_metadata
        result = parse_task_metadata("- [ ] Urgent task ⏫")
        assert result["priority"] == "high"
        assert result["priority_weight"] == 1

    def test_parse_task_gcal_tag(self):
        from integrations.obsidian import parse_task_metadata
        result = parse_task_metadata("- [ ] Meeting 📅 2026-05-01 #gcal")
        assert result["gcal"] is True

    def test_parse_task_no_match(self):
        from integrations.obsidian import parse_task_metadata
        result = parse_task_metadata("Just a regular line")
        assert result == {}

    def test_write_section_creates_file(self):
        from integrations.obsidian import ObsidianVault
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = ObsidianVault(vault_dir=tmpdir)
            vault.write_section("inbox", "- [ ] Test task", file_rel="Dashboard.md")
            content = (Path(tmpdir) / "Dashboard.md").read_text()
            assert "Test task" in content
            assert "<!-- agent:inbox:start -->" in content
            assert "<!-- agent:inbox:end -->" in content

    def test_write_section_updates_in_place(self):
        from integrations.obsidian import ObsidianVault
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = ObsidianVault(vault_dir=tmpdir)
            vault.write_section("inbox", "old content", file_rel="Dashboard.md")
            vault.write_section("inbox", "new content", file_rel="Dashboard.md")
            content = (Path(tmpdir) / "Dashboard.md").read_text()
            assert "new content" in content
            assert "old content" not in content
            # Markers appear exactly once each
            assert content.count("<!-- agent:inbox:start -->") == 1

    def test_write_section_preserves_other_sections(self):
        from integrations.obsidian import ObsidianVault
        with tempfile.TemporaryDirectory() as tmpdir:
            vault = ObsidianVault(vault_dir=tmpdir)
            vault.write_section("inbox", "inbox content", file_rel="Dashboard.md")
            vault.write_section("today-plan", "plan content", file_rel="Dashboard.md")
            content = (Path(tmpdir) / "Dashboard.md").read_text()
            assert "inbox content" in content
            assert "plan content" in content

    def test_mark_task_done(self):
        from integrations.obsidian import ObsidianVault
        with tempfile.TemporaryDirectory() as tmpdir:
            md = Path(tmpdir) / "tasks.md"
            md.write_text("- [ ] Buy groceries\n- [ ] Write report\n")
            vault = ObsidianVault(vault_dir=tmpdir)
            result = vault.mark_task_done("Buy groceries")
            assert result is True
            updated = md.read_text()
            assert "- [x] Buy groceries" in updated
            assert "- [ ] Write report" in updated

    def test_move_file(self):
        from integrations.obsidian import ObsidianVault
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "note.md"
            src.write_text("# Note")
            vault = ObsidianVault(vault_dir=tmpdir)
            result = vault.move_file("note.md", "Resources/note.md")
            assert result is True
            assert (Path(tmpdir) / "Resources" / "note.md").exists()
            assert not src.exists()


# ── Sync Agent ────────────────────────────────────────────────────────────────

class TestSyncAgent:
    def test_task_hash_stable(self):
        from agents.sync_agent import _task_hash
        task = {"task": "Buy milk", "source": "journal/2026_04_01:5"}
        h1 = _task_hash(task)
        h2 = _task_hash(task)
        assert h1 == h2
        assert len(h1) == 12

    def test_task_hash_differs_by_task(self):
        from agents.sync_agent import _task_hash
        h1 = _task_hash({"task": "Task A", "source": "s"})
        h2 = _task_hash({"task": "Task B", "source": "s"})
        assert h1 != h2

    def test_run_deduplicates(self):
        from agents.sync_agent import run, reset_hashes, _HASH_FILE
        with tempfile.TemporaryDirectory() as tmpdir:
            # Patch the hash file location to temp dir
            test_hash_file = Path(tmpdir) / ".synced_hashes.json"
            mock_logseq_tasks = [
                {"task": "Test task", "source": "journal/2026_04_01:1",
                 "properties": {}, "description": ""},
            ]
            with patch("agents.sync_agent._HASH_FILE", test_hash_file), \
                 patch("agents.sync_agent.LogSeqReader") as MockLS, \
                 patch("agents.sync_agent.ObsidianVault") as MockVault:

                mock_ls = MagicMock()
                mock_ls.get_recent_tasks.return_value = mock_logseq_tasks
                mock_ls.get_all_page_tasks.return_value = []
                mock_ls.get_recent_notes.return_value = []
                MockLS.return_value = mock_ls

                mock_vault = MagicMock()
                mock_vault.read_section.return_value = ""
                MockVault.return_value = mock_vault

                result1 = run()
                assert result1["tasks_added"] == 1
                assert result1["skipped"] == 0

                result2 = run()
                assert result2["tasks_added"] == 0
                assert result2["skipped"] == 1


# ── Calendar Integration ──────────────────────────────────────────────────────

class TestCalendar:
    def test_add_and_remove_event(self):
        from integrations.calendar import CalendarWriter, CalendarReader
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = Path(tmpdir) / "calendar.ics"
            with patch("integrations.calendar._ics_path", return_value=ics_path), \
                 patch("integrations.calendar.config") as mock_cfg:
                mock_cfg.calendar.google_enabled.return_value = False
                mock_cfg.paths.local_calendar.return_value = str(ics_path)
                mock_cfg.paths.output.return_value = tmpdir
                mock_cfg.calendar.gcal_tag.return_value = "gcal"

                writer = CalendarWriter()
                uid = writer.add_event(
                    "Test Meeting",
                    datetime.datetime(2026, 5, 1, 10, 0),
                    datetime.datetime(2026, 5, 1, 11, 0),
                )
                assert isinstance(uid, str)
                assert len(uid) > 0

                removed = writer.remove_event(uid=uid)
                assert removed == 1

    def test_sync_from_obsidian_skips_no_date(self):
        from integrations.calendar import CalendarWriter
        with tempfile.TemporaryDirectory() as tmpdir:
            ics_path = Path(tmpdir) / "calendar.ics"
            with patch("integrations.calendar._ics_path", return_value=ics_path), \
                 patch("integrations.calendar.config") as mock_cfg:
                mock_cfg.calendar.google_enabled.return_value = False
                mock_cfg.paths.local_calendar.return_value = str(ics_path)
                mock_cfg.calendar.gcal_tag.return_value = "gcal"

                writer = CalendarWriter()
                tasks = [
                    {"text": "No date task", "gcal": True, "due_date": None},
                    {"text": "No gcal tag", "gcal": False, "due_date": datetime.date(2026, 5, 1)},
                ]
                stats = writer.sync_from_obsidian(tasks)
                assert stats["added"] == 0
                assert stats["skipped"] == 2


# ── Notes Agent ───────────────────────────────────────────────────────────────

class TestNotesAgent:
    def test_parse_llm_response_valid_json(self):
        from agents.notes_agent import _parse_llm_response
        text = '{"moves": [{"path": "a.md", "suggested_folder": "Resources", "reason": "ref"}], "links": []}'
        result = _parse_llm_response(text)
        assert len(result["moves"]) == 1
        assert result["moves"][0]["path"] == "a.md"

    def test_parse_llm_response_with_code_fence(self):
        from agents.notes_agent import _parse_llm_response
        text = '```json\n{"moves": [], "links": []}\n```'
        result = _parse_llm_response(text)
        assert result["moves"] == []
        assert result["links"] == []

    def test_parse_llm_response_invalid_returns_empty(self):
        from agents.notes_agent import _parse_llm_response
        result = _parse_llm_response("not json at all")
        assert result["moves"] == []
        assert result["links"] == []

    def test_apply_moves_file(self):
        from agents.notes_agent import apply
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "note.md"
            src.write_text("# Note content")
            with patch("agents.notes_agent.ObsidianVault") as MockVault:
                mock_vault = MagicMock()
                mock_vault.move_file.return_value = True
                MockVault.return_value = mock_vault

                changes = {
                    "moves": [{"path": "note.md", "suggested_folder": "Resources"}],
                    "links": [],
                }
                stats = apply(changes)
                assert stats["moves_done"] == 1
                assert stats["links_added"] == 0

    def test_apply_adds_links(self):
        from agents.notes_agent import apply
        with patch("agents.notes_agent.ObsidianVault") as MockVault:
            mock_vault = MagicMock()
            MockVault.return_value = mock_vault

            changes = {
                "moves": [],
                "links": [{"path": "note.md", "suggested_links": ["Related A", "Related B"]}],
            }
            stats = apply(changes)
            assert stats["links_added"] == 1
            mock_vault.append_to_file.assert_called_once()
            call_args = mock_vault.append_to_file.call_args[0]
            assert "[[Related A]]" in call_args[1]
            assert "[[Related B]]" in call_args[1]
