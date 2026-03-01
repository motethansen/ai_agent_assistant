import os
import calendar_manager
from observer import update_markdown_plan

class PlanningAgent:
    """
    Takes confirmed tasks, submits them to Google Calendar,
    and updates the task list in Obsidian.
    """
    def __init__(self, service, calendar_id):
        self.service = service
        self.calendar_id = calendar_id

    def execute_plan(self, schedule, obsidian_path):
        """
        Submits confirmed tasks to Calendar and updates Obsidian.
        """
        if not schedule:
            print("PlanningAgent: No schedule provided.")
            return False

        print(f"PlanningAgent: Booking {len(schedule)} events to calendar...")
        # 1. Submit to Google Calendar
        calendar_manager.create_events(self.service, schedule, calendar_id=self.calendar_id)
        
        # 2. Update Obsidian task list
        if obsidian_path and os.path.exists(obsidian_path):
            print(f"PlanningAgent: Updating Obsidian file at {obsidian_path}...")
            update_markdown_plan(obsidian_path, schedule)
        else:
            print(f"PlanningAgent: Note - Obsidian path {obsidian_path} not found.")

        print("PlanningAgent: Execution complete.")
        return True
