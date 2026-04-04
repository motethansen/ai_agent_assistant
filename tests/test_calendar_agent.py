import pytest
import os
import yaml
from unittest.mock import patch, MagicMock
from calendar_agent import CalendarAgent

def test_calendar_agent_init(tmp_path):
    # Test with a temporary data directory
    data_dir = tmp_path / "datainput"
    agent = CalendarAgent(data_dir=str(data_dir))
    assert os.path.exists(data_dir)
    assert agent.yml_path == os.path.join(str(data_dir), "googlecalendar.yml")

def test_get_busy_slots_from_yml(tmp_path):
    data_dir = tmp_path / "datainput"
    os.makedirs(data_dir)
    yml_path = data_dir / "googlecalendar.yml"
    
    test_data = {
        "last_updated": "2026-03-01T12:00:00",
        "busy_slots": [{"summary": "Stored Event"}]
    }
    
    with open(yml_path, 'w') as f:
        yaml.dump(test_data, f)
        
    agent = CalendarAgent(data_dir=str(data_dir))
    slots = agent.get_busy_slots_from_yml()
    assert len(slots) == 1
    assert slots[0]["summary"] == "Stored Event"
