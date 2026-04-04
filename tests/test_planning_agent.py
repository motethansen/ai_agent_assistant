import pytest
import os
from unittest.mock import patch, MagicMock
from planning_agent import PlanningAgent

@patch('planning_agent.add_event')
@patch('planning_agent.update_markdown_plan')
def test_execute_plan(mock_update_md, mock_add_event, tmp_path):
    agent = PlanningAgent()
    
    test_schedule = [{"task": "Test Task", "start": "2026-03-01T10:00:00Z", "end": "2026-03-01T11:00:00Z"}]
    test_obsidian_path = tmp_path / "daily_note.md"
    test_obsidian_path.write_text("## Today's Plan")
    
    success = agent.execute_plan(test_schedule, str(test_obsidian_path))
    
    assert success is True
    assert mock_add_event.called
    mock_update_md.assert_called_once_with(str(test_obsidian_path), test_schedule)

def test_execute_plan_no_schedule():
    agent = PlanningAgent(None, "primary")
    assert agent.execute_plan([], "path.md") is False
