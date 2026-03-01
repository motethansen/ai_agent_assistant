import pytest
import os
from unittest.mock import patch, MagicMock
from planning_agent import PlanningAgent

@patch('calendar_manager.create_events')
@patch('planning_agent.update_markdown_plan')
def test_execute_plan(mock_update_md, mock_create_events, tmp_path):
    mock_service = MagicMock()
    agent = PlanningAgent(mock_service, "test_cal_id")
    
    test_schedule = [{"task": "Test Task", "start": "2026-03-01T10:00:00", "end": "2026-03-01T11:00:00"}]
    test_obsidian_path = tmp_path / "daily_note.md"
    test_obsidian_path.write_text("## Today's Plan")
    
    success = agent.execute_plan(test_schedule, str(test_obsidian_path))
    
    assert success is True
    mock_create_events.assert_called_once_with(mock_service, test_schedule, calendar_id="test_cal_id")
    mock_update_md.assert_called_once_with(str(test_obsidian_path), test_schedule)

def test_execute_plan_no_schedule():
    agent = PlanningAgent(None, "primary")
    assert agent.execute_plan([], "path.md") is False
