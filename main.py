import time
import os
import re
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import calendar_manager
import ai_orchestration
from observer import parse_markdown_tasks

def update_markdown_plan(file_path, schedule):
    """
    Overwrites the '## Today's Plan' section with the AI-generated schedule.
    """
    if not schedule:
        return

    try:
        with open(file_path, 'r') as f:
            content = f.read()

        plan_text = "## Today's Plan
"
        for item in schedule:
            # Clean up the ISO time for better readability
            start_time = item['start'].split('T')[1][:5]
            end_time = item['end'].split('T')[1][:5]
            plan_text += f"- **{start_time} - {end_time}**: {item['task']}
"
        
        # Replace the section using regex
        pattern = r"## Today's Plan.*?(?=
##|$)"
        new_content = re.sub(pattern, plan_text, content, flags=re.DOTALL)
        
        with open(file_path, 'w') as f:
            f.write(new_content)
        print(f"Updated {os.path.basename(file_path)} with Today's Plan.")
    except Exception as e:
        print(f"Error updating markdown file: {e}")

class TaskSyncHandler(PatternMatchingEventHandler):
    patterns = ["*.md"]

    def on_modified(self, event):
        # Debounce (ignore rapid saves)
        if hasattr(self, 'last_triggered') and time.time() - self.last_triggered < 5:
            return
        self.last_triggered = time.time()
        
        print(f"
--- Change Detected in {os.path.basename(event.src_path)} ---")
        
        # 1. Parse tasks
        tasks = parse_markdown_tasks(event.src_path)
        if not tasks:
            print("No tasks found in '## Tasks' section. Skipping sync.")
            return
        
        # 2. Get Calendar context
        service = calendar_manager.get_calendar_service()
        busy_slots = calendar_manager.get_busy_slots(service)
        
        # 3. AI Orchestration
        print("Consulting the AI scheduler...")
        schedule = ai_orchestration.generate_schedule(tasks, busy_slots)
        
        if schedule:
            # 4. Sync back to Google Calendar
            calendar_manager.create_events(service, schedule)
            
            # 5. Write back to Markdown
            update_markdown_plan(event.src_path, schedule)
            print("--- Sync Complete ---
")
        else:
            print("Failed to generate schedule from AI.")

if __name__ == "__main__":
    path = "."
    event_handler = TaskSyncHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    
    print(f"🚀 AI Agent Assistant is active and monitoring {os.path.abspath(path)}...")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
