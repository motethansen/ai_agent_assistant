import os
import yaml
import time
import threading
import calendar_manager
from config_utils import get_config_value
import datetime

class CalendarAgent:
    def __init__(self, data_dir="datainput"):
        self.data_dir = data_dir
        self.yml_path = os.path.join(self.data_dir, "googlecalendar.yml")
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def fetch_and_store_calendar(self):
        """Fetches calendar data from Google API and stores it in a YAML file."""
        calendar_id = get_config_value("CALENDAR_ID", "primary")
        service = calendar_manager.get_calendar_service()
        if not service:
            print("CalendarAgent: No service available.")
            return

        print("CalendarAgent: Fetching calendar data to store in YAML...")
        busy_slots = calendar_manager.get_busy_slots(service, calendar_ids=["primary", calendar_id])
        
        data = {
            "last_updated": datetime.datetime.now().isoformat(),
            "busy_slots": busy_slots
        }

        with open(self.yml_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)
        print(f"CalendarAgent: Saved calendar data to {self.yml_path}")

    def get_busy_slots_from_yml(self):
        """Reads the busy slots from the YAML file. Fetches if not found."""
        if not os.path.exists(self.yml_path):
            print("CalendarAgent: YAML file not found. Attempting to fetch...")
            try:
                self.fetch_and_store_calendar()
            except Exception as e:
                print(f"CalendarAgent: Failed to fetch calendar: {e}")
                return []
        
        if not os.path.exists(self.yml_path):
            print("CalendarAgent: YAML still not found after fetch, returning empty slots.")
            return []
            
        with open(self.yml_path, 'r') as f:
            try:
                data = yaml.safe_load(f)
                return data.get("busy_slots", [])
            except Exception as e:
                print(f"CalendarAgent: Error reading YAML: {e}")
                return []

def start_background_calendar_sync(interval=300):
    """Starts a background thread to periodically fetch calendar data."""
    agent = CalendarAgent()
    def run_sync():
        while True:
            agent.fetch_and_store_calendar()
            time.sleep(interval)
            
    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()
    return thread

if __name__ == "__main__":
    agent = CalendarAgent()
    agent.fetch_and_store_calendar()
    print(agent.get_busy_slots_from_yml())
