import pytest
from unittest.mock import patch, MagicMock
import sys
import cron_job
import update_manager


def test_run_google_tasks_agent_skips_when_disabled():
    """run_google_tasks_agent() returns early and never imports google_tasks_agent when disabled."""
    def cfg(key, default):
        if key == "ENABLE_GOOGLE_TASKS":
            return "false"
        return default

    # Remove google_tasks_agent from sys.modules so we can detect if it gets imported
    sys.modules.pop("google_tasks_agent", None)

    with patch("cron_job.get_config_value", side_effect=cfg):
        cron_job.run_google_tasks_agent()

    assert "google_tasks_agent" not in sys.modules


def test_run_google_tasks_agent_calls_run(capsys):
    """run_google_tasks_agent() calls google_tasks_agent.run() when enabled and logs counts."""
    mock_agent = MagicMock()
    mock_agent.run.return_value = {"pulled": 2, "pushed": 1}

    def cfg(key, default):
        if key == "ENABLE_GOOGLE_TASKS":
            return "true"
        return default

    with patch("cron_job.get_config_value", side_effect=cfg), \
         patch.dict(sys.modules, {"google_tasks_agent": mock_agent}):
        cron_job.run_google_tasks_agent()

    mock_agent.run.assert_called_once_with(sync_back=True)
    captured = capsys.readouterr()
    assert "pulled 2" in captured.out


def test_check_google_tasks_disabled():
    """check_google_tasks() returns disabled status without any file access."""
    def cfg(key, default):
        if key == "ENABLE_GOOGLE_TASKS":
            return "false"
        return default

    with patch("update_manager.get_config_value", side_effect=cfg):
        result = update_manager.check_google_tasks()

    assert result["status"] == "disabled"
