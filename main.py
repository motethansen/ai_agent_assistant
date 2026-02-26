import time
import os
import re
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import calendar_manager
import ai_orchestration
from observer import parse_markdown_tasks
from reminders_manager import get_apple_reminders

def get_unified_tasks(obsidian_path):
    """
    Merges tasks from Obsidian and Apple Reminders.
    """
    # 1. Parse Obsidian tasks
    obsidian_tasks = parse_markdown_tasks(obsidian_path)
    
    # 2. Get Apple Reminders
    # Pull the list name from the .config file if available
    reminders_list = "Reminders"
    if os.path.exists(".config"):
        with open(".config", "r") as f:
            for line in f:
                if "APPLE_REMINDERS_LIST=" in line:
                    reminders_list = line.split("=")[1].strip()
    
    apple_tasks = get_apple_reminders(reminders_list)
    
    # 3. Combine
    unified_backlog = obsidian_tasks + apple_tasks
    print(f"Unified Backlog: {len(unified_backlog)} tasks ({len(obsidian_tasks)} Obsidian, {len(apple_tasks)} Apple Reminders)")
    return unified_backlog

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
        
        # 1. Get Unified Backlog
        tasks = get_unified_tasks(event.src_path)
        if not tasks:
            print("No tasks found in current backlog. Skipping sync.")
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

import argparse

def display_docs():
    """
    Renders documentation files in the terminal.
    """
    docs_dir = "docs"
    if not os.path.exists(docs_dir):
        print("No documentation found in 'docs/' directory.")
        return

    print("
--- Documentation ---")
    for doc_file in os.listdir(docs_dir):
        if doc_file.endswith(".md"):
            print(f"
[ {doc_file} ]")
            with open(os.path.join(docs_dir, doc_file), 'r') as f:
                print(f.read())
    print("---------------------
")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Agent Assistant: Local Markdown-Calendar-AI Bridge")
    parser.add_argument("--docs", action="store_true", help="Display project documentation in terminal")
    args = parser.parse_args()

    if args.docs:
        display_docs()
    else:
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

