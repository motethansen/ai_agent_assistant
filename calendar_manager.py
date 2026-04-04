"""
Legacy module — Google Calendar auth moved to n8n (ADR-010).
Use local_calendar_agent.py for calendar operations.
"""
import os
import yaml
from local_calendar_agent import import_calendar

def get_busy_slots_from_yaml(yml_path="datainput/googlecalendar.yml"):
    """Reads the busy slots from the YAML file (cached from Google/n8n)."""
    if not os.path.exists(yml_path):
        return []
    with open(yml_path, 'r', encoding='utf-8') as f:
        try:
            data = yaml.safe_load(f)
            return data.get("busy_slots", [])
        except Exception as e:
            print(f"Error reading YAML {yml_path}: {e}")
            return []

def import_ics_from_google_export(path):
    """Import an ICS file (exported from Google) into the local calendar."""
    return import_calendar(path)
