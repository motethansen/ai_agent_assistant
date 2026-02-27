import time
import os
import re
import datetime
import json
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import calendar_manager
import ai_orchestration
from observer import parse_markdown_tasks
from reminders_manager import get_apple_reminders

def get_config_value(key, default):
    """Retrieves a value from .config if it exists."""
    if os.path.exists(".config"):
        with open(".config", "r") as f:
            for line in f:
                if f"{key}=" in line:
                    return line.split("=")[1].strip()
    return default

def get_unified_tasks(obsidian_path):
    """
    Merges tasks from Obsidian and Apple Reminders.
    """
    # 1. Parse Obsidian tasks
    obsidian_tasks = parse_markdown_tasks(obsidian_path)
    
    # 2. Get Apple Reminders
    reminders_list = get_config_value("APPLE_REMINDERS_LIST", "Reminders")
    apple_tasks = get_apple_reminders(reminders_list)
    
    # 3. Combine
    unified_backlog = obsidian_tasks + apple_tasks
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

        plan_text = "## Today's Plan\n"
        for item in schedule:
            # Clean up the ISO time for better readability
            start_time = item['start'].split('T')[1][:5]
            end_time = item['end'].split('T')[1][:5]
            plan_text += f"- **{start_time} - {end_time}**: {item['task']}\n"
        
        # Replace the section using regex
        pattern = r"## Today's Plan.*?(?=\n##|$)"
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
        
        print(f"\n--- Change Detected in {os.path.basename(event.src_path)} ---")
        
        # 1. Get Unified Backlog
        tasks = get_unified_tasks(event.src_path)
        if not tasks:
            print("No tasks found in current backlog. Skipping sync.")
            return
        
        # 2. Get Calendar context
        calendar_id = get_config_value("CALENDAR_ID", "primary")
        service = calendar_manager.get_calendar_service()
        busy_slots = calendar_manager.get_busy_slots(service, calendar_id=calendar_id)
        
        # 3. AI Orchestration
        print("Consulting the AI scheduler...")
        schedule = ai_orchestration.generate_schedule(tasks, busy_slots)
        
        if schedule:
            # 4. Sync back to Google Calendar
            calendar_manager.create_events(service, schedule, calendar_id=calendar_id)
            
            # 5. Write back to Markdown
            update_markdown_plan(event.src_path, schedule)
            print("--- Sync Complete ---\n")
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

    print("\n--- Documentation ---")
    for doc_file in os.listdir(docs_dir):
        if doc_file.endswith(".md"):
            print(f"\n[ {doc_file} ]")
            with open(os.path.join(docs_dir, doc_file), 'r') as f:
                print(f.read())
    print("---------------------\n")

def handle_morning_planning(obsidian_path):
    """
    Runs an interactive morning planning session.
    """
    print("🌅 --- Morning Planning Session ---")
    tasks = get_unified_tasks(obsidian_path)
    calendar_id = get_config_value("CALENDAR_ID", "primary")
    service = calendar_manager.get_calendar_service()
    busy_slots = calendar_manager.get_busy_slots(service, calendar_id=calendar_id)
    
    print("AI is processing your backlog for today...")
    result = ai_orchestration.generate_schedule(tasks, busy_slots, morning_mode=True)
    
    if result:
        # Suggestions for new categories
        if result.get("suggestions"):
            print("\n--- Task Suggestions ---")
            for sug in result["suggestions"]:
                print(f"Suggestion: '{sug['task']}' -> Category: {sug['suggested_category']} (Reason: {sug['reason']})")
        
        # Proposed schedule
        schedule = result.get("schedule", [])
        if schedule:
            print("\n--- Proposed Daily Schedule ---")
            for item in schedule:
                print(f"[{item['start'].split('T')[1][:5]}] {item['task']} ({item.get('category', 'Uncategorized')})")
            
            confirm = input("\nAdd these items to your calendar? (y/n/skip): ").strip().lower()
            if confirm == 'y':
                calendar_manager.create_events(service, schedule, calendar_id=calendar_id)
                update_markdown_plan(obsidian_path, schedule)
            else:
                print("Skipped calendar sync.")
    else:
        print("Failed to generate schedule suggestion.")

def handle_evening_review(obsidian_path):
    """
    Runs an interactive evening review session.
    """
    print("🌙 --- Evening Review Session ---")
    tasks = get_unified_tasks(obsidian_path)
    # Check for completions
    print("Checking which tasks from today's plan were completed...")
    for t in tasks:
        # We'll just ask for status for now as part of the loop
        if t.get("source") == "Obsidian" and t.get("due_date") == datetime.datetime.now().strftime("%Y-%m-%d"):
             status = input(f"Did you complete: '{t['task']}'? (y/n): ").strip().lower()
             if status == 'y':
                 print(f"Great work on {t['task']}!")
    
    print("\nBacklog summary for tomorrow:")

    # Future logic for moving incomplete tasks to the next day

import subprocess

def handle_chat_mode(obsidian_path):
    """
    Starts an interactive CLI chat loop with slash commands.
    """
    print("\n🤖 AI Agent Assistant: Interactive Chat Mode")
    print("Type /commands to see available slash commands or type your question.")
    
    while True:
        user_input = input("\n👤 You: ").strip()
        
        if not user_input:
            continue
            
        if user_input.startswith("/"):
            command = user_input[1:].lower()
            
            if command == "exit" or command == "quit":
                print("Goodbye!")
                break
            elif command == "commands" or command == "help":
                print("\nAvailable Commands:")
                print("  /sync     - Manually trigger task sync from Obsidian and Reminders")
                print("  /backlog  - Display the current unified backlog")
                print("  /plan     - Trigger a morning planning session")
                print("  /review   - Trigger an evening review session")
                print("  /ui       - Launch the Streamlit web interface")
                print("  /docs     - Show project documentation")
                print("  /exit     - Quit the chat mode")
            elif command == "sync":
                print("Manually triggering sync...")
                tasks = get_unified_tasks(obsidian_path)
                calendar_id = get_config_value("CALENDAR_ID", "primary")
                service = calendar_manager.get_calendar_service()
                busy_slots = calendar_manager.get_busy_slots(service, calendar_id=calendar_id)
                schedule = ai_orchestration.generate_schedule(tasks, busy_slots)
                if schedule:
                    calendar_manager.create_events(service, schedule, calendar_id=calendar_id)
                    update_markdown_plan(obsidian_path, schedule)
                    print("Sync complete.")
                else:
                    print("Failed to generate schedule.")
            elif command == "backlog":
                tasks = get_unified_tasks(obsidian_path)
                print("\n--- Current Backlog ---")
                for i, t in enumerate(tasks, 1):
                    cat = t.get("category", "Uncategorized")
                    due = f" (Due: {t['due_date']})" if t.get('due_date') else ""
                    print(f"{i}. [{cat}] {t['task']}{due}")
            elif command == "plan":
                handle_morning_planning(obsidian_path)
            elif command == "review":
                handle_evening_review(obsidian_path)
            elif command == "ui":
                print("Launching Streamlit UI in the background...")
                subprocess.Popen([".venv/bin/streamlit", "run", "app.py"])
                print("Web interface is opening in your browser.")
            elif command == "docs":
                display_docs()
            else:
                print(f"Unknown command: /{command}. Type /commands for help.")
        else:
            # AI Chat integration
            print("AI is thinking...")
            try:
                # Get both backlog and calendar context for better answers
                tasks = get_unified_tasks(obsidian_path)
                calendar_id = get_config_value("CALENDAR_ID", "primary")
                service = calendar_manager.get_calendar_service()
                busy_slots = calendar_manager.get_busy_slots(service, calendar_id=calendar_id)
                
                context_payload = {
                    "backlog": tasks,
                    "calendar_busy_slots": busy_slots,
                    "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                
                prompt = f"The user is asking: '{user_input}'. Based on their state: {json.dumps(context_payload)}, provide a helpful and concise answer."
                
                client = ai_orchestration.genai.Client(api_key=ai_orchestration.api_key)
                # Using the stable model configured in ai_orchestration
                response = client.models.generate_content(
                    model='gemini-flash-latest',
                    contents=prompt
                )
                print(f"🤖 AI: {response.text}")
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    print("⚠️ AI: I've hit my API rate limit or daily quota. Please try again in a moment or check your Gemini API plan.")
                else:
                    print(f"⚠️ AI: I encountered an error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Agent Assistant: Local Markdown-Calendar-AI Bridge")
    parser.add_argument("--docs", action="store_true", help="Display project documentation in terminal")
    parser.add_argument("--morning", action="store_true", help="Start morning planning mode")
    parser.add_argument("--evening", action="store_true", help="Start evening review mode")
    parser.add_argument("--chat", action="store_true", help="Start interactive chat mode")
    parser.add_argument("--file", type=str, help="Specific markdown file to process", default="daily_note.md")
    args = parser.parse_args()

    if args.docs:
        display_docs()
    elif args.morning:
        handle_morning_planning(args.file)
    elif args.evening:
        handle_evening_review(args.file)
    elif args.chat:
        handle_chat_mode(args.file)
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

