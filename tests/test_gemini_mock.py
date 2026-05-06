"""
Gemini API mock tests — all tests run fully offline, no real API calls.

Tests cover: chat, stream, is_available, history building, model selection,
and router integration using a mocked Gemini backend.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mock_client(response_text: str = "Mocked response") -> MagicMock:
    mock_response = MagicMock()
    mock_response.text = response_text

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


def _make_mock_stream_client(chunks: list[str]) -> MagicMock:
    mock_chunks = []
    for text in chunks:
        c = MagicMock()
        c.text = text
        mock_chunks.append(c)

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = iter(mock_chunks)
    return mock_client


# ── is_available ──────────────────────────────────────────────────────────────

class TestGeminiAvailability:
    def setup_method(self):
        # Reset cached _available between tests
        import llm.gemini as gem
        gem._available = None
        gem._client = None

    def test_available_when_api_key_set(self):
        import llm.gemini as gem
        with patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_api_key.return_value = "AIza-test-key"
            result = gem.is_available()
        assert result is True

    def test_unavailable_when_no_api_key(self):
        import llm.gemini as gem
        with patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_api_key.return_value = ""
            result = gem.is_available()
        assert result is False

    def test_cached_result_is_not_recomputed(self):
        import llm.gemini as gem
        # Prime the cache
        gem._available = True
        with patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_api_key.return_value = ""  # would return False if re-evaluated
            result = gem.is_available()
        # Must return cached True, not re-read the key
        assert result is True


# ── chat ─────────────────────────────────────────────────────────────────────

class TestGeminiChat:
    def setup_method(self):
        import llm.gemini as gem
        gem._available = None
        gem._client = None

    def test_chat_returns_stripped_text(self):
        import llm.gemini as gem
        mock_client = _make_mock_client("  Hello world  ")

        with patch("llm.gemini._get_client", return_value=mock_client), \
             patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_flash_model.return_value = "gemini-2.0-flash"
            mock_cfg.llm.gemini_pro_model.return_value = "gemini-2.5-flash-preview-04-17"

            result = gem.chat("Say hello")

        assert result == "Hello world"

    def test_chat_uses_flash_model_by_default(self):
        import llm.gemini as gem
        mock_client = _make_mock_client("ok")

        with patch("llm.gemini._get_client", return_value=mock_client), \
             patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_flash_model.return_value = "gemini-2.0-flash"
            mock_cfg.llm.gemini_pro_model.return_value = "gemini-2.5-flash-preview-04-17"

            gem.chat("Test prompt")

        _, kwargs = mock_client.models.generate_content.call_args
        assert kwargs.get("model") == "gemini-2.0-flash"

    def test_chat_uses_pro_model_when_specified(self):
        import llm.gemini as gem
        mock_client = _make_mock_client("ok")

        with patch("llm.gemini._get_client", return_value=mock_client), \
             patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_flash_model.return_value = "gemini-2.0-flash"
            mock_cfg.llm.gemini_pro_model.return_value = "gemini-2.5-flash-preview-04-17"

            gem.chat("Plan my week", model="pro")

        _, kwargs = mock_client.models.generate_content.call_args
        assert kwargs.get("model") == "gemini-2.5-flash-preview-04-17"

    def test_chat_with_system_prompt_passes_config(self):
        import llm.gemini as gem
        from google.genai import types  # real types (installed)
        mock_client = _make_mock_client("result")

        with patch("llm.gemini._get_client", return_value=mock_client), \
             patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_flash_model.return_value = "gemini-2.0-flash"
            mock_cfg.llm.gemini_pro_model.return_value = "gemini-2.5-flash"

            gem.chat("Hello", system="You are a helpful assistant.")

        _, kwargs = mock_client.models.generate_content.call_args
        assert kwargs.get("config") is not None

    def test_chat_without_system_passes_no_config(self):
        import llm.gemini as gem
        mock_client = _make_mock_client("result")

        with patch("llm.gemini._get_client", return_value=mock_client), \
             patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_flash_model.return_value = "gemini-2.0-flash"
            mock_cfg.llm.gemini_pro_model.return_value = "gemini-2.5-flash"

            gem.chat("Hello")

        _, kwargs = mock_client.models.generate_content.call_args
        assert kwargs.get("config") is None

    def test_chat_prompt_passed_directly_without_history(self):
        import llm.gemini as gem
        mock_client = _make_mock_client("ok")

        with patch("llm.gemini._get_client", return_value=mock_client), \
             patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_flash_model.return_value = "gemini-2.0-flash"
            mock_cfg.llm.gemini_pro_model.return_value = "gemini-2.5-flash"

            gem.chat("My prompt")

        _, kwargs = mock_client.models.generate_content.call_args
        # Without history, contents is the raw prompt string
        assert kwargs.get("contents") == "My prompt"

    def test_chat_with_history_builds_content_list(self):
        import llm.gemini as gem
        from google.genai import types
        mock_client = _make_mock_client("follow-up answer")

        history = [
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
        ]

        with patch("llm.gemini._get_client", return_value=mock_client), \
             patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_flash_model.return_value = "gemini-2.0-flash"
            mock_cfg.llm.gemini_pro_model.return_value = "gemini-2.5-flash"

            gem.chat("And 3+3?", history=history)

        _, kwargs = mock_client.models.generate_content.call_args
        contents = kwargs.get("contents")
        # With history, contents is a list of Content objects
        assert isinstance(contents, list)
        assert len(contents) == 3  # 2 history + 1 new user turn


# ── stream ────────────────────────────────────────────────────────────────────

class TestGeminiStream:
    def setup_method(self):
        import llm.gemini as gem
        gem._available = None
        gem._client = None

    def test_stream_yields_chunks(self):
        import llm.gemini as gem
        mock_client = _make_mock_stream_client(["Hello ", "world", "!"])

        with patch("llm.gemini._get_client", return_value=mock_client), \
             patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_flash_model.return_value = "gemini-2.0-flash"
            mock_cfg.llm.gemini_pro_model.return_value = "gemini-2.5-flash"

            chunks = list(gem.stream("Stream this"))

        assert chunks == ["Hello ", "world", "!"]

    def test_stream_skips_none_text_chunks(self):
        import llm.gemini as gem

        c1 = MagicMock()
        c1.text = "real chunk"
        c2 = MagicMock()
        c2.text = None  # some API responses have None text on final chunk

        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = iter([c1, c2])

        with patch("llm.gemini._get_client", return_value=mock_client), \
             patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_flash_model.return_value = "gemini-2.0-flash"
            mock_cfg.llm.gemini_pro_model.return_value = "gemini-2.5-flash"

            chunks = list(gem.stream("Test"))

        assert chunks == ["real chunk"]

    def test_stream_concatenated_matches_expected_output(self):
        import llm.gemini as gem
        words = ["The ", "quick ", "brown ", "fox"]
        mock_client = _make_mock_stream_client(words)

        with patch("llm.gemini._get_client", return_value=mock_client), \
             patch("llm.gemini.config") as mock_cfg:
            mock_cfg.llm.gemini_flash_model.return_value = "gemini-2.0-flash"
            mock_cfg.llm.gemini_pro_model.return_value = "gemini-2.5-flash"

            result = "".join(gem.stream("Sentence"))

        assert result == "The quick brown fox"


# ── Router integration with mocked Gemini ────────────────────────────────────

class TestRouterWithGeminiMock:
    def setup_method(self):
        import llm.gemini as gem
        gem._available = None
        gem._client = None

    def test_router_ask_returns_gemini_response(self):
        from llm.router import ask
        mock_client = _make_mock_client("Planned your day!")

        with patch("llm.gemini._get_client", return_value=mock_client), \
             patch("llm.gemini.is_available", return_value=True), \
             patch("llm.gemini.config") as mock_cfg, \
             patch("llm.router.config") as mock_router_cfg:

            mock_cfg.llm.gemini_flash_model.return_value = "gemini-2.0-flash"
            mock_cfg.llm.gemini_pro_model.return_value = "gemini-2.5-flash"
            mock_router_cfg.llm.routing_chat.return_value = "gemini-flash"
            mock_router_cfg.llm.routing_planning.return_value = "gemini-pro"
            mock_router_cfg.llm.routing_notes.return_value = "gemini-flash"
            mock_router_cfg.llm.routing_quick.return_value = "groq"
            mock_router_cfg.llm.routing_offline.return_value = "ollama"
            mock_router_cfg.llm.routing_reasoning.return_value = "deepseek"

            result = ask("Plan my day", task="chat")

        assert result == "Planned your day!"

    def test_router_falls_back_when_gemini_unavailable(self):
        from llm.router import ask

        mock_groq_mod = MagicMock()
        mock_groq_mod.is_available.return_value = True
        mock_groq_mod.chat.return_value = "Groq fallback response"

        with patch("llm.gemini.is_available", return_value=False), \
             patch("llm.router.config") as mock_router_cfg, \
             patch("llm.router._import_provider") as mock_import:

            mock_router_cfg.llm.routing_chat.return_value = "gemini-flash"
            mock_router_cfg.llm.routing_planning.return_value = "gemini-pro"
            mock_router_cfg.llm.routing_notes.return_value = "gemini-flash"
            mock_router_cfg.llm.routing_quick.return_value = "groq"
            mock_router_cfg.llm.routing_offline.return_value = "ollama"
            mock_router_cfg.llm.routing_reasoning.return_value = "deepseek"

            def fake_import(name):
                if name in ("gemini-flash", "gemini-pro"):
                    mod = MagicMock()
                    mod.is_available.return_value = False
                    return mod
                if name == "groq":
                    return mock_groq_mod
                mod = MagicMock()
                mod.is_available.return_value = False
                return mod

            mock_import.side_effect = fake_import

            result = ask("Summarise backlog", task="chat")

        assert result == "Groq fallback response"

    def test_router_stream_with_gemini_mock(self):
        from llm.router import stream
        mock_client = _make_mock_stream_client(["Here ", "is ", "your ", "plan."])

        with patch("llm.gemini._get_client", return_value=mock_client), \
             patch("llm.gemini.is_available", return_value=True), \
             patch("llm.gemini.config") as mock_cfg, \
             patch("llm.router.config") as mock_router_cfg:

            mock_cfg.llm.gemini_flash_model.return_value = "gemini-2.0-flash"
            mock_cfg.llm.gemini_pro_model.return_value = "gemini-2.5-flash"
            mock_router_cfg.llm.routing_chat.return_value = "gemini-flash"
            mock_router_cfg.llm.routing_planning.return_value = "gemini-pro"
            mock_router_cfg.llm.routing_notes.return_value = "gemini-flash"
            mock_router_cfg.llm.routing_quick.return_value = "groq"
            mock_router_cfg.llm.routing_offline.return_value = "ollama"
            mock_router_cfg.llm.routing_reasoning.return_value = "deepseek"

            result = "".join(stream("Plan my week", task="planning"))

        assert result == "Here is your plan."


# ── Planning agent integration ────────────────────────────────────────────────

class TestPlanningAgentMock:
    def test_run_today_returns_plan_string(self):
        from agents.planning_agent import run

        mock_tasks = [
            {"text": "Write tests", "due_date": None, "priority": "high", "priority_weight": 1},
            {"text": "Review PR", "due_date": None, "priority": None, "priority_weight": 99},
        ]
        mock_events = [
            {
                "summary": "Team sync",
                "start": __import__("datetime").datetime(2026, 5, 6, 10, 0),
                "end": __import__("datetime").datetime(2026, 5, 6, 10, 30),
            }
        ]

        with patch("agents.planning_agent.ObsidianVault") as MockVault, \
             patch("agents.planning_agent._load_calendar_events", return_value=mock_events), \
             patch("agents.planning_agent.router") as mock_router:

            mock_vault = MagicMock()
            mock_vault.get_tasks.return_value = mock_tasks
            MockVault.return_value = mock_vault
            mock_router.ask.return_value = "## Today's Plan\n\n- 09:00 Write tests\n- 11:00 Review PR"

            plan = run(mode="today")

        assert isinstance(plan, str)
        assert len(plan) > 0
        mock_vault.write_section.assert_called_once()

    def test_build_planning_prompt_buckets_tasks_correctly(self):
        import datetime
        from agents.planning_agent import _build_planning_prompt

        today = datetime.date.today()
        tasks = [
            {"text": "Overdue task", "due_date": today - datetime.timedelta(days=2),
             "priority": None, "priority_weight": 99},
            {"text": "Due today task", "due_date": today,
             "priority": "high", "priority_weight": 1},
            {"text": "Future task", "due_date": today + datetime.timedelta(days=3),
             "priority": None, "priority_weight": 99},
            {"text": "Backlog task", "due_date": None,
             "priority": None, "priority_weight": 99},
        ]

        with patch("agents.planning_agent.config") as mock_cfg:
            mock_cfg.planning.deep_work_start.return_value = "09:00"
            mock_cfg.planning.deep_work_end.return_value = "12:00"
            mock_cfg.planning.focus_categories.return_value = ["dev", "admin"]
            mock_cfg.planning.chronotype.return_value = "morning"

            prompt = _build_planning_prompt(tasks, [], "today", today)

        assert "Overdue task" in prompt
        assert "Due today task" in prompt
        assert "Backlog task" in prompt

    def test_build_week_prompt_includes_week_range(self):
        import datetime
        from agents.planning_agent import _build_planning_prompt

        today = datetime.date(2026, 5, 6)

        with patch("agents.planning_agent.config") as mock_cfg:
            mock_cfg.planning.deep_work_start.return_value = "09:00"
            mock_cfg.planning.deep_work_end.return_value = "12:00"
            mock_cfg.planning.focus_categories.return_value = ["dev"]
            mock_cfg.planning.chronotype.return_value = "morning"

            prompt = _build_planning_prompt([], [], "week", today)

        assert "May 06" in prompt or "May 6" in prompt
        assert "May 13" in prompt
