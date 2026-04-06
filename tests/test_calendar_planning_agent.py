"""
Tests for calendar_planning_agent.py

Mocks all external calls (LLM, calendar, file I/O where needed).
Uses tmp_path for output file assertions.
"""
import os
import pytest
from unittest.mock import patch, MagicMock, call

import calendar_planning_agent


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_plan_saved_to_output_file(tmp_path):
    """
    generate_plan() writes the plan to SUGGESTIONS_FILE and returns the text.
    ROUTING_PLANNING is unset so the fallback generate() path is used.
    """
    suggestions_file = tmp_path / "calendar_suggestions.md"

    fake_plan = "### Day-by-Day Plan\n#### Monday 06 April\n- 09:00 – 10:00 | Write tests | dev\n"

    def _fake_config(key, default=None):
        return {
            "ROUTING_PLANNING": None,
            "DEEP_WORK_START": "09:00",
            "DEEP_WORK_END": "12:00",
            "CHRONOTYPE": "morning_owl",
        }.get(key, default)

    with patch("calendar_planning_agent.get_config_value", side_effect=_fake_config), \
         patch("calendar_planning_agent._get_week_events", return_value=[]), \
         patch("calendar_planning_agent._load_reminders", return_value=[]), \
         patch("calendar_planning_agent._load_logseq_tasks", return_value=[]), \
         patch("ai_orchestration.generate", return_value=(fake_plan, "ollama/qwen2.5:14b")) as mock_gen, \
         patch.object(calendar_planning_agent, "SUGGESTIONS_FILE", str(suggestions_file)), \
         patch.object(calendar_planning_agent, "DATAINPUT_DIR", str(tmp_path)):

        result = calendar_planning_agent.generate_plan(days=7, write_to_obsidian=False)

    assert result == fake_plan
    mock_gen.assert_called_once()

    assert suggestions_file.exists(), "Suggestions file should have been created"
    content = suggestions_file.read_text(encoding="utf-8")
    assert fake_plan in content


def test_plan_uses_routing_planning_provider(tmp_path):
    """
    When ROUTING_PLANNING is set, generate_plan() calls generate_with(provider, ...).
    """
    suggestions_file = tmp_path / "calendar_suggestions.md"
    fake_plan = "### Day-by-Day Plan\n#### Tuesday\n- 09:00 – 10:00 | Review PRs | dev\n"

    def _fake_config(key, default=None):
        return {
            "ROUTING_PLANNING": "ollama",
            "DEEP_WORK_START": "09:00",
            "DEEP_WORK_END": "12:00",
            "CHRONOTYPE": "morning_owl",
        }.get(key, default)

    with patch("calendar_planning_agent.get_config_value", side_effect=_fake_config), \
         patch("calendar_planning_agent._get_week_events", return_value=[]), \
         patch("calendar_planning_agent._load_reminders", return_value=[]), \
         patch("calendar_planning_agent._load_logseq_tasks", return_value=[]), \
         patch("ai_orchestration.generate_with", return_value=(fake_plan, "ollama/qwen2.5:14b")) as mock_gen, \
         patch.object(calendar_planning_agent, "SUGGESTIONS_FILE", str(suggestions_file)), \
         patch.object(calendar_planning_agent, "DATAINPUT_DIR", str(tmp_path)):

        result = calendar_planning_agent.generate_plan(days=7, write_to_obsidian=False)

    assert result == fake_plan
    mock_gen.assert_called_once()
    assert mock_gen.call_args[0][0] == "ollama"
