import pytest
from unittest.mock import patch, MagicMock

from n8n_client import trigger_task_sync
from cli_commands import handle_universal_sync

def test_trigger_task_sync_payload_shape():
    """Verify that trigger_task_sync sends the correct payload keys to n8n."""
    with patch("n8n_client.trigger") as mock_trigger:
        mock_trigger.return_value = True
        tasks = [{"title": "Test Task", "source": "obsidian", "due": None}]
        events = []
        
        result = trigger_task_sync(tasks, events)
        
        assert result is True
        mock_trigger.assert_called_once()
        args, _ = mock_trigger.call_args
        assert args[0] == "task-sync"
        payload = args[1]
        assert "tasks" in payload
        assert "calendar_events" in payload
        assert "synced_at" in payload
        assert payload["tasks"] == tasks

def test_trigger_task_sync_returns_false_on_n8n_down():
    """Verify that trigger_task_sync returns False when n8n trigger fails."""
    with patch("n8n_client.trigger") as mock_trigger:
        mock_trigger.return_value = False
        result = trigger_task_sync([], [])
        assert result is False

def test_handle_universal_sync_warns_when_n8n_down():
    """Verify that handle_universal_sync handles n8n being down without raising."""
    with patch("n8n_client.is_n8n_running") as mock_running:
        mock_running.return_value = False
        # Should print a message and return, not raise
        try:
            handle_universal_sync()
        except Exception as e:
            pytest.fail(f"handle_universal_sync raised an exception: {e}")

def test_handle_universal_sync_calls_trigger_task_sync():
    """Verify that handle_universal_sync correctly gathers tasks and calls trigger."""
    with patch("n8n_client.is_n8n_running") as mock_running, \
         patch("task_utils.get_unified_tasks") as mock_get_tasks, \
         patch("n8n_client.trigger_task_sync") as mock_trigger_sync, \
         patch("config_utils.get_config_value") as mock_get_config:
        
        mock_running.return_value = True
        mock_get_tasks.return_value = [{"text": "My task", "source": "obsidian"}]
        mock_trigger_sync.return_value = True
        mock_get_config.return_value = "/tmp/workspace"
        
        # We don't need to patch builtins.__import__. 
        # If local_calendar_agent is missing, it will raise ImportError naturally and be caught.
        handle_universal_sync()
        
        mock_trigger_sync.assert_called_once()
        args, _ = mock_trigger_sync.call_args
        tasks_sent = args[0]
        assert len(tasks_sent) == 1
        assert tasks_sent[0]["title"] == "My task"
