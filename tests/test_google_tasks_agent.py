import os
import pytest
from unittest.mock import patch, MagicMock
import google_tasks_agent

@pytest.fixture
def mock_config(tmp_path):
    """Mocks config values and workspace paths."""
    workspace = tmp_path / "obsidian"
    workspace.mkdir()
    planner = workspace / "Planner.md"
    
    with patch("google_tasks_agent.get_config_value") as mock:
        def side_effect(key, default):
            if key == "ENABLE_GOOGLE_TASKS": return "true"
            if key == "WORKSPACE_DIR": return str(workspace)
            if key == "OBSIDIAN_PLANNER_FILE": return "Planner.md"
            return default
        mock.side_effect = side_effect
        yield {
            "workspace": workspace,
            "planner": planner,
            "mock_get_config": mock
        }

def test_run_returns_none_when_disabled():
    """patch get_config_value for ENABLE_GOOGLE_TASKS to return 'false'; call run(); assert result is None"""
    with patch("google_tasks_agent.get_config_value") as mock_get:
        mock_get.return_value = "false"
        assert google_tasks_agent.run() is None

@patch("n8n_client.trigger")
def test_sync_to_obsidian_triggers_n8n(mock_trigger, mock_config):
    """sync_to_obsidian() should call n8n_client.trigger with 'google-tasks-pull'"""
    mock_trigger.return_value = True
    assert google_tasks_agent.sync_to_obsidian() is True
    mock_trigger.assert_called_once_with("google-tasks-pull", {})

@patch("n8n_client.trigger")
def test_sync_completions_triggers_n8n(mock_trigger, mock_config):
    """sync_completions_to_google() scans planner and triggers n8n for each [x] task."""
    mock_config["planner"].write_text("## Google Tasks\n- [ ] Pending\n- [x] Buy milk\n- [X] Call mom\n")
    mock_trigger.return_value = True
    
    assert google_tasks_agent.sync_completions_to_google() is True
    
    # It should send all completed titles in one call (as per my implementation)
    mock_trigger.assert_called_once()
    args, kwargs = mock_trigger.call_args
    assert args[0] == "google-tasks-push"
    assert "Buy milk" in args[1]["completions"]
    assert "Call mom" in args[1]["completions"]

def test_sync_completions_returns_true_no_tasks(mock_config):
    """If no [x] tasks, it should return True (nothing to do) without triggering n8n."""
    mock_config["planner"].write_text("## Google Tasks\n- [ ] Pending\n")
    with patch("n8n_client.trigger") as mock_trigger:
        assert google_tasks_agent.sync_completions_to_google() is True
        mock_trigger.assert_not_called()

@patch("n8n_client.trigger")
def test_run_executes_both(mock_trigger, mock_config):
    """run(sync_back=True) should trigger both pull and push."""
    mock_config["planner"].write_text("## Google Tasks\n- [x] Done\n")
    mock_trigger.return_value = True
    
    res = google_tasks_agent.run(sync_back=True)
    assert res == {"pulled": True, "pushed": True}
    assert mock_trigger.call_count == 2
