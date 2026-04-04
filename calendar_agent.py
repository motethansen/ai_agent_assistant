"""
Calendar Agent — Reads cached calendar data from YAML.
Live Google Calendar sync is now handled by n8n (ADR-010).
"""
import os
import yaml
from config_utils import get_config_value
import datetime

class CalendarAgent:
    def __init__(self, data_dir="datainput"):
        self.data_dir = data_dir
        self.yml_path = os.path.join(self.data_dir, "googlecalendar.yml")
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def get_busy_slots_from_yml(self):
        """Reads the busy slots from the YAML file (cached from Google/n8n)."""
        if not os.path.exists(self.yml_path):
            # ADR-010: No longer auto-fetching from Google API
            return []
        
        with open(self.yml_path, 'r', encoding='utf-8') as f:
            try:
                data = yaml.safe_load(f)
                return data.get("busy_slots", [])
            except Exception as e:
                print(f"CalendarAgent: Error reading YAML: {e}")
                return []

if __name__ == "__main__":
    agent = CalendarAgent()
    print(agent.get_busy_slots_from_yml())
