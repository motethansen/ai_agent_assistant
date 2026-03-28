"""
Tests for datainput_agent.py

Uses tmp_path for all file I/O — never touches real vault files.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

import datainput_agent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_reminders():
    return [
        {
            "task": "Buy groceries",
            "due_date": "Wednesday, 8 April 2026 at 11:00:00",
            "notes": "",
        },
        {
            "task": "Call dentist",
            "due_date": "",
            "notes": "Ask about teeth cleaning",
        },
    ]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _setup_files(tmp_path, reminders, synced_keys=None, planner_content=""):
    reminders_file = tmp_path / "reminders.json"
    synced_file = tmp_path / "synced_reminders.json"
    planner_file = tmp_path / "Planner.md"

    reminders_file.write_text(json.dumps(reminders), encoding="utf-8")
    synced_file.write_text(json.dumps(sorted(synced_keys or [])), encoding="utf-8")
    planner_file.write_text(planner_content, encoding="utf-8")

    return reminders_file, synced_file, planner_file


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_new_reminders_appended_under_reminders_section(tmp_path, fake_reminders):
    """New reminders are inserted under ## Reminders in the planner."""
    reminders_file, synced_file, planner_file = _setup_files(
        tmp_path, fake_reminders, planner_content="# My Planner\n"
    )

    with patch.object(datainput_agent, "REMINDERS_FILE", str(reminders_file)), \
         patch.object(datainput_agent, "SYNCED_FILE", str(synced_file)), \
         patch.object(datainput_agent, "_planner_path", return_value=str(planner_file)):

        result = datainput_agent.sync_reminders_to_planner()

    assert len(result) == 2

    content = planner_file.read_text(encoding="utf-8")
    assert "## Reminders" in content
    assert "Buy groceries" in content
    assert "Call dentist" in content
    # Task with due date should have a date marker
    assert "2026-04-08" in content

    synced = json.loads(synced_file.read_text(encoding="utf-8"))
    # Both task keys should be persisted
    task_keys = {datainput_agent._task_key(r) for r in fake_reminders}
    assert task_keys.issubset(set(synced))


def test_already_synced_reminders_are_skipped(tmp_path, fake_reminders):
    """Reminders already in synced_reminders.json are not re-added."""
    first_task = fake_reminders[0]
    pre_synced = [datainput_agent._task_key(first_task)]

    reminders_file, synced_file, planner_file = _setup_files(
        tmp_path, fake_reminders,
        synced_keys=pre_synced,
        planner_content="# My Planner\n\n## Reminders\n- [ ] Buy groceries 📅 2026-04-08\n",
    )

    with patch.object(datainput_agent, "REMINDERS_FILE", str(reminders_file)), \
         patch.object(datainput_agent, "SYNCED_FILE", str(synced_file)), \
         patch.object(datainput_agent, "_planner_path", return_value=str(planner_file)):

        result = datainput_agent.sync_reminders_to_planner()

    # Only the second reminder should have been added
    assert len(result) == 1
    assert result[0]["task"] == "Call dentist"

    content = planner_file.read_text(encoding="utf-8")
    # Buy groceries appears exactly once (no duplicate)
    assert content.count("Buy groceries") == 1
    assert "Call dentist" in content


def test_organise_planner_calls_llm_and_writes_result(tmp_path):
    """organise_planner() calls ai_orchestration.generate and writes back the LLM response."""
    planner_file = tmp_path / "Planner.md"
    planner_file.write_text("## Work\n- [ ] Old task\n", encoding="utf-8")

    llm_response = "## Work\n- [ ] Task A — reorganised by AI\n\n## Personal\n- [ ] Call dentist\n"

    with patch.object(datainput_agent, "_planner_path", return_value=str(planner_file)), \
         patch("ai_orchestration.generate", return_value=(llm_response, "ollama")) as mock_gen:

        result = datainput_agent.organise_planner()

    mock_gen.assert_called_once()
    assert "Task A" in result
    written = planner_file.read_text(encoding="utf-8")
    assert "Task A" in written
    assert "Old task" not in written


def test_run_with_organise_false_does_not_call_organise_planner(tmp_path, fake_reminders):
    """run(organise=False) must not call organise_planner()."""
    reminders_file, synced_file, planner_file = _setup_files(
        tmp_path, fake_reminders
    )

    with patch.object(datainput_agent, "REMINDERS_FILE", str(reminders_file)), \
         patch.object(datainput_agent, "SYNCED_FILE", str(synced_file)), \
         patch.object(datainput_agent, "_planner_path", return_value=str(planner_file)), \
         patch.object(datainput_agent, "organise_planner") as mock_organise:

        result = datainput_agent.run(organise=False)

    mock_organise.assert_not_called()
    assert result["organised"] is False
