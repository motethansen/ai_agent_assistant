import os
import json
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
            if key == "GOOGLE_TASKS_LIST": return "@default"
            return default
        mock.side_effect = side_effect
        yield {
            "workspace": workspace,
            "planner": planner,
            "mock_get_config": mock
        }

@pytest.fixture
def mock_synced_file(tmp_path):
    """Mocks the synced tasks JSON file path."""
    synced_file = tmp_path / "synced_google_tasks.json"
    with patch("google_tasks_agent.SYNCED_FILE", str(synced_file)):
        yield synced_file

def test_run_returns_none_when_disabled():
    """patch get_config_value for ENABLE_GOOGLE_TASKS to return 'false'; call run(); assert result is None"""
    with patch("google_tasks_agent.get_config_value") as mock_get:
        mock_get.return_value = "false"
        assert google_tasks_agent.run() is None

def test_fetch_tasks_returns_list():
    """mock the service object; service.tasks().list().execute() returns items; assert fetch_tasks returns cleaned list"""
    mock_service = MagicMock()
    mock_service.tasks().list().execute.return_value = {
        "items": [{"id": "1", "title": "Buy milk", "status": "needsAction"}]
    }
    
    with patch("google_tasks_agent._get_service", return_value=mock_service):
        tasks = google_tasks_agent.fetch_tasks("list1")
        assert tasks == [{"id": "1", "title": "Buy milk", "due": None, "notes": None}]

def test_sync_to_obsidian_appends_new_tasks(mock_config, mock_synced_file):
    """mock _get_service and fetch_tasks to return one task; call sync_to_obsidian(); assert planner contains task"""
    mock_tasks = [{"id": "1", "title": "Buy milk", "due": "2026-04-08T00:00:00.000Z", "notes": "Full cream"}]
    
    with patch("google_tasks_agent._resolve_list_id", return_value="list1"), \
         patch("google_tasks_agent.fetch_tasks", return_value=mock_tasks):
        
        count = google_tasks_agent.sync_to_obsidian()
        assert count == 1
        
        content = mock_config["planner"].read_text()
        assert "## Google Tasks" in content
        assert "- [ ] Buy milk 📅 2026-04-08" in content
        assert "  - 📝 Full cream" in content
        
        # Verify synced file updated
        synced = json.loads(mock_synced_file.read_text())
        assert "1" in synced
        assert synced["1"]["title"] == "Buy milk"

def test_sync_to_obsidian_skips_duplicates(mock_config, mock_synced_file):
    """pre-populate synced file with task id '1'; call sync_to_obsidian() with same task; assert count is 0"""
    mock_synced_file.write_text(json.dumps({"1": {"title": "Buy milk", "synced_date": "2026-01-01"}}))
    mock_tasks = [{"id": "1", "title": "Buy milk", "due": None, "notes": None}]
    
    with patch("google_tasks_agent._resolve_list_id", return_value="list1"), \
         patch("google_tasks_agent.fetch_tasks", return_value=mock_tasks):
        
        count = google_tasks_agent.sync_to_obsidian()
        assert count == 0

def test_sync_completions_pushes_done_tasks(mock_config, mock_synced_file):
    """write planner with '- [x] Buy milk'; pre-populate synced file; mock API call; call sync_completions; assert API called"""
    mock_config["planner"].write_text("## Google Tasks\n- [x] Buy milk\n")
    mock_synced_file.write_text(json.dumps({"1": {"title": "Buy milk", "synced_date": "2026-01-01"}}))
    
    mock_service = MagicMock()
    with patch("google_tasks_agent._get_service", return_value=mock_service), \
         patch("google_tasks_agent._resolve_list_id", return_value="list1"):
        
        count = google_tasks_agent.sync_completions_to_google()
        assert count == 1
        
        # Verify API call
        mock_service.tasks().update.assert_called_with(
            tasklist="list1", 
            task="1", 
            body={"id": "1", "status": "completed"}
        )
        
        # Verify entry removed from synced file
        synced = json.loads(mock_synced_file.read_text())
        assert "1" not in synced


def test_sync_completions_logs_error_and_continues(mock_config, mock_synced_file):
    """per-task API errors are logged and do not raise; successful tasks still complete."""
    mock_config["planner"].write_text(
        "## Google Tasks\n- [x] Buy milk\n- [x] Call mom\n",
        encoding="utf-8",
    )
    mock_synced_file.write_text(json.dumps({
        "1": {"title": "Buy milk", "synced_date": "2026-01-01"},
        "2": {"title": "Call mom", "synced_date": "2026-01-01"},
    }))

    mock_service = MagicMock()
    update_call = mock_service.tasks().update
    update_call.side_effect = [
        Exception("boom"),
        MagicMock(execute=MagicMock(return_value={})),
    ]

    with patch("google_tasks_agent._get_service", return_value=mock_service), \
         patch("google_tasks_agent._resolve_list_id", return_value="list1"), \
         patch("google_tasks_agent.logging.getLogger") as mock_logger:

        count = google_tasks_agent.sync_completions_to_google()

    assert count == 1
    assert update_call.call_count == 2
    mock_logger.return_value.error.assert_called()

    synced = json.loads(mock_synced_file.read_text())
    assert "1" in synced
    assert "2" not in synced
