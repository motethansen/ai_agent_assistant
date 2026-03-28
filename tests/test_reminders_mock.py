import pytest
from task_utils import get_unified_tasks
from unittest.mock import patch, MagicMock

def test_unified_backlog_merges_sources(tmp_path):
    """
    Test that the unified backlog contains both Obsidian and Apple Reminders tasks.
    """
    # 1. Setup mock Obsidian file
    d = tmp_path / "obsidian"
    d.mkdir()
    p = d / "daily.md"
    p.write_text("""## Tasks
- [ ] #winedragons Review wireframes ^2026-02-26""")
    
    # 2. Mock Apple Reminders retrieval
    mock_reminders = [
        {"task": "Buy milk", "source": "Apple Reminders", "category": "Personal"}
    ]
    
    def _fake_config(key, default=None):
        return {"WORKSPACE_DIR": str(d), "LOGSEQ_DIR": None, "APPLE_REMINDERS_LIST": "Reminders"}.get(key, default)

    with patch("task_utils.get_apple_reminders", return_value=mock_reminders), \
         patch("task_utils.get_config_value", side_effect=_fake_config):
        backlog = get_unified_tasks(str(d))

        # Verify both sources are merged
        task_names = [t["task"] for t in backlog]
        assert any("Review wireframes" in name for name in task_names)
        assert any("Buy milk" in name for name in task_names)

def test_unified_backlog_categories(tmp_path):
    """
    Verify categories are correctly assigned in the unified backlog.
    """
    d = tmp_path / "obsidian"
    d.mkdir()
    p = d / "daily.md"
    p.write_text("""## Tasks
- [ ] #Ref.team.Degree.planning Update curriculum""")
    
    def _fake_config2(key, default=None):
        return {"WORKSPACE_DIR": str(d), "LOGSEQ_DIR": None, "APPLE_REMINDERS_LIST": "Reminders"}.get(key, default)

    with patch("task_utils.get_apple_reminders", return_value=[]), \
         patch("task_utils.get_config_value", side_effect=_fake_config2):
        backlog = get_unified_tasks(str(d))
        assert backlog[0]["category"] == "Ref.team.Degree.planning"
