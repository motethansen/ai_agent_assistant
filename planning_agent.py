import os
import datetime
from observer import update_markdown_plan
from local_calendar_agent import add_event

class PlanningAgent:
    """
    Takes confirmed tasks, submits them to the local calendar,
    and updates the task list in Obsidian.
    """
    def __init__(self, service=None, calendar_id=None):
        # ADR-010: service and calendar_id are legacy/ignored
        self.service = service
        self.calendar_id = calendar_id

    def execute_plan(self, schedule, obsidian_path):
        """
        Submits confirmed tasks to local calendar and updates Obsidian.
        """
        if not schedule:
            print("PlanningAgent: No schedule provided.")
            return False

        print(f"PlanningAgent: Booking {len(schedule)} events to local calendar...")
        # 1. Submit to Local Calendar
        for item in schedule:
            try:
                # Basic parsing of the ISO start/end if they are strings
                # local_calendar_agent.add_event expects datetime objects
                start_str = item['start']
                end_str = item['end']
                
                # Handle Z or +/- offsets
                start_dt = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                end_dt = datetime.datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                
                add_event(item['task'], start_dt, end_dt)
            except Exception as e:
                print(f"PlanningAgent: Error adding event '{item['task']}': {e}")
        
        # 2. Update Obsidian task list
        if obsidian_path and os.path.exists(obsidian_path):
            print(f"PlanningAgent: Updating Obsidian file at {obsidian_path}...")
            update_markdown_plan(obsidian_path, schedule)
        else:
            print(f"PlanningAgent: Note - Obsidian path {obsidian_path} not found.")

        print("PlanningAgent: Execution complete.")
        return True
