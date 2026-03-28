"""
Tests for calendar_planning_agent.py

Mocks all external calls (Gemini, calendar, file I/O where needed).
Uses tmp_path for output file assertions.
"""
import os
import pytest
from unittest.mock import patch, MagicMock, call

import calendar_planning_agent


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_plan_saved_to_output_file_when_gemini_enabled(tmp_path):
    """
    When ENABLE_GEMINI=true and Gemini returns a plan, the plan is written
    to the SUGGESTIONS_FILE and returned by generate_plan().
    """
    suggestions_file = tmp_path / "calendar_suggestions.md"

    fake_plan = "### Day-by-Day Plan\n#### Friday 27 March\n- 09:00 – 10:00 | Write tests | dev\n"

    def _fake_config(key, default=None):
        return {
            "ENABLE_GEMINI": "true",
            "GEMINI_MODEL": "gemini-2.0-flash",
            "CALENDAR_ID": "primary",
            "DEEP_WORK_START": "09:00",
            "DEEP_WORK_END": "12:00",
            "CHRONOTYPE": "morning_owl",
        }.get(key, default)

    with patch("calendar_planning_agent.get_config_value", side_effect=_fake_config), \
         patch("calendar_planning_agent._get_week_events", return_value=[]), \
         patch("calendar_planning_agent._load_reminders", return_value=[]), \
         patch("calendar_planning_agent._load_logseq_tasks", return_value=[]), \
         patch("ai_orchestration.generate_with", return_value=(fake_plan, "gemini-2.0-flash")) as mock_gen, \
         patch.object(calendar_planning_agent, "SUGGESTIONS_FILE", str(suggestions_file)), \
         patch.object(calendar_planning_agent, "DATAINPUT_DIR", str(tmp_path)):

        result = calendar_planning_agent.generate_plan(days=7, write_to_obsidian=False)

    assert result == fake_plan
    mock_gen.assert_called_once()

    assert suggestions_file.exists(), "Suggestions file should have been created"
    content = suggestions_file.read_text(encoding="utf-8")
    assert fake_plan in content


def test_run_returns_none_when_gemini_disabled():
    """
    When ENABLE_GEMINI=false, generate_plan() returns None immediately
    without calling the LLM.
    """
    with patch("calendar_planning_agent.get_config_value", return_value="false"), \
         patch("ai_orchestration.generate_with") as mock_gen:

        result = calendar_planning_agent.run(write_to_obsidian=False)

    assert result is None
    mock_gen.assert_not_called()
