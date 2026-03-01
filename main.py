import time
import os
import re
import datetime
import json
import traceback
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import calendar_manager
import ai_orchestration
import gmail_agent
from book_agent import BookAgent
from travel_agent import TravelAgent
from observer import parse_markdown_tasks, parse_logseq_tasks
from reminders_manager import get_apple_reminders

from config_utils import get_config_value

def get_unified_tasks(obsidian_path):
    """
    Merges tasks from Obsidian, LogSeq, and Apple Reminders.
    """
    # 1. Parse Obsidian tasks
    obsidian_tasks = parse_markdown_tasks(obsidian_path)
    
    # 2. Parse LogSeq tasks if directory is provided
    logseq_tasks = []
    logseq_dir = get_config_value("LOGSEQ_DIR", None)
    if logseq_dir:
        # Scan journals and pages for pending tasks
        for sub_dir in ["journals", "pages"]:
            target_dir = os.path.join(logseq_dir, sub_dir)
            if os.path.exists(target_dir):
                for filename in os.listdir(target_dir):
                    if filename.endswith(".md"):
                        path = os.path.join(target_dir, filename)
                        tasks = parse_logseq_tasks(path)
                        logseq_tasks.extend(tasks)
        print(f"Extracted {len(logseq_tasks)} total tasks from LogSeq (journals + pages).")

    # 3. Get Apple Reminders
    reminders_list = get_config_value("APPLE_REMINDERS_LIST", "Reminders")
    apple_tasks = get_apple_reminders(reminders_list)
    
    # 4. Combine
    unified_backlog = obsidian_tasks + logseq_tasks + apple_tasks
    return unified_backlog


def update_markdown_plan(file_path, schedule):
    """
    Overwrites the '## Today's Plan' section with the AI-generated schedule.
    """
    if not schedule:
        return

    try:
        # Sort schedule by start time
        schedule = sorted(schedule, key=lambda x: x['start'])

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

def sync_calendar_to_markdown(obsidian_path):
    """
    Pulls 'AI: ' events from Google Calendar and updates the markdown file.
    (Two-Way Sync: Calendar -> Markdown)
    """
    print(f"🔄 Pulling latest AI events from Google Calendar to {os.path.basename(obsidian_path)}...")
    
    calendar_id = get_config_value("CALENDAR_ID", "primary")
    service = calendar_manager.get_calendar_service()
    if not service:
        print("❌ Could not connect to Google Calendar.")
        return

    managed_events = calendar_manager.get_managed_events(service, calendar_id=calendar_id)
    if managed_events:
        update_markdown_plan(obsidian_path, managed_events)
        print(f"✅ Successfully synced {len(managed_events)} events from Calendar to Markdown.")
    else:
        print("ℹ️ No AI-managed events found in today's calendar.")

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
        # Fetch busy slots from BOTH primary and AI calendar
        busy_slots = calendar_manager.get_busy_slots(service, calendar_ids=["primary", calendar_id])
        
        # 3. AI Orchestration
        print("Consulting the AI scheduler...")
        logseq_path = get_config_value("LOGSEQ_DIR", None)
        obsidian_path = get_config_value("WORKSPACE_DIR", ".")
        schedule = ai_orchestration.generate_schedule(
            tasks, 
            busy_slots, 
            workspace_dir=obsidian_path, 
            logseq_dir=logseq_path
        )
        
        if schedule:
            # 4. Sync back to Google Calendar
            calendar_manager.create_events(service, schedule, calendar_id=calendar_id)
            
            # 5. Write back to Markdown
            update_markdown_plan(event.src_path, schedule)
            print("--- Sync Complete ---\n")
        else:
            print("Failed to generate schedule from AI.")

import argparse

def display_stats():
    """
    Display statistics about models, configuration, and usage.
    """
    print("\n📊 === AI Agent Assistant Statistics ===")
    
    # Configuration Status
    print("\n🔧 Configuration:")
    workspace = get_config_value("WORKSPACE_DIR", ".")
    logseq = get_config_value("LOGSEQ_DIR", None)
    calendar_id = get_config_value("CALENDAR_ID", "primary")
    print(f"  Workspace: {os.path.abspath(workspace)}")
    print(f"  LogSeq: {os.path.abspath(logseq) if logseq else 'Not configured'}")
    print(f"  Calendar ID: {calendar_id}")
    
    # API Key Status
    print("\n🔑 API Configuration:")
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        print(f"  Gemini API Key: {'✓ Configured' if api_key else '✗ Missing'}")
        print(f"  Key Length: {len(api_key)} characters")
    else:
        print("  Gemini API Key: ✗ Missing")
    
    # Check Ollama availability
    try:
        import requests
        ollama_response = requests.get("http://localhost:11434/api/version", timeout=2)
        if ollama_response.status_code == 200:
            print("  Ollama: ✓ Available (http://localhost:11434)")
        else:
            print("  Ollama: ✗ Not responding")
    except:
        print("  Ollama: ✗ Not available")
    
    # Available Models
    print("\n🤖 Available Gemini Models:")
    if api_key:
        try:
            import google.genai as genai
            client = genai.Client(api_key=api_key)
            models = list(client.models.list())
            for model in models[:5]:  # Show first 5 models
                print(f"  • {model.name}")
            if len(models) > 5:
                print(f"  ... and {len(models) - 5} more models")
        except Exception as e:
            print(f"  Error listing models: {e}")
    else:
        print("  Cannot list models without API key")
    
    # Calendar Status
    print("\n📅 Calendar Integration:")
    if os.path.exists('credentials.json'):
        print("  credentials.json: ✓ Present")
    else:
        print("  credentials.json: ✗ Missing")
    
    if os.path.exists('token.json'):
        print("  token.json: ✓ Authenticated")
    else:
        print("  token.json: ✗ Not authenticated")
    
    try:
        service = calendar_manager.get_calendar_service()
        if service:
            managed_events = calendar_manager.get_managed_events(service, calendar_id=calendar_id)
            print(f"  Today's AI-managed events: {len(managed_events) if managed_events else 0}")
        else:
            print("  Calendar service: ✗ Cannot connect")
    except Exception as e:
        print(f"  Calendar service: ✗ Error: {e}")
    
    # File System Status
    print("\n📁 File System:")
    if os.path.exists(workspace):
        md_files = [f for f in os.listdir(workspace) if f.endswith('.md')]
        print(f"  Markdown files: {len(md_files)}")
    else:
        print(f"  Workspace directory not found")
    
    print("\n" + "="*45 + "\n")

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
    busy_slots = calendar_manager.get_busy_slots(service, calendar_ids=["primary", calendar_id])
    
    print("AI is processing your backlog for today...")
    logseq_path = get_config_value("LOGSEQ_DIR", None)
    result = ai_orchestration.generate_schedule(
        tasks, 
        busy_slots, 
        morning_mode=True, 
        workspace_dir=obsidian_path, 
        logseq_dir=logseq_path
    )
    
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
from file_system_agent import FileSystemAgent

def execute_actions(actions):
    """
    Shows proposed AI actions to the user and executes them upon confirmation.
    """
    if not actions:
        return

    workspace = get_config_value("WORKSPACE_DIR", ".")
    if "your/markdown/notes" in workspace:
        print("⚠️ WARNING: 'WORKSPACE_DIR' in .config appears to be a placeholder.")
        print(f"Current path: {os.path.abspath(workspace)}")
    
    fs_agent = FileSystemAgent(workspace)

    
    print("\n⚡ AI is proposing the following actions:")
    for i, action in enumerate(actions, 1):
        print(f"  {i}. {action['type'].upper()}: {action['path']} (Reason: {action.get('reason', 'None')})")
    
    confirm = input("\nExecute these actions? (y/n): ").strip().lower()
    if confirm == 'y':
        for action in actions:
            try:
                if action['type'] == "create_folder":
                    msg = fs_agent.create_folder(action['path'])
                    print(f"✅ {msg}")
                elif action['type'] == "write_file":
                    msg = fs_agent.write_file(action['path'], action.get('content', ''))
                    print(f"✅ {msg}")
                elif action['type'] == "read_book":
                    agent = BookAgent()
                    content = agent.read_book_content(action['path'])
                    print(f"📖 Extract from {os.path.basename(action['path'])}:\n{content}")
                elif action['type'] == "index_book":
                    agent = BookAgent()
                    msg = agent.index_book(action['path'])
                    print(f"✅ {msg}")
                elif action['type'] == "search_books":
                    agent = BookAgent()
                    results = agent.search_books(action['query'])
                    print(results)
                elif action['type'] == "plan_travel":
                    agent = TravelAgent()
                    result = agent.plan_travel(action['query'])
                    print(f"\n✈️ TRAVEL PLAN FOUND:\n{result}")
            except Exception as e:
                print(f"❌ Error executing {action['type']}: {e}")
    else:
        print("🚫 Actions cancelled.")

def print_banner():

    """Prints the AI Agent Assistant banner."""
    banner = """
    #######################################
    #                                     #
    #        🤖 AI AGENT ASSISTANT        #
    #                                     #
    #######################################
    """
    print(banner)

def handle_chat_mode(obsidian_path):
    """
    Starts an interactive CLI chat loop with slash commands.
    """
    print_banner()
    print("🤖 AI Agent Assistant: Interactive Chat Mode")
    print("Type /commands to see available slash commands or type your question.")
    
    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            
            if not user_input:
                continue
                
            if user_input.startswith("/"):
                command_full = user_input[1:].lower().strip()
                parts = command_full.split()
                if not parts:
                    print("⚠️ Invalid command. Type /commands for help.")
                    continue
                command = parts[0]
                
                if command == "exit" or command == "quit":
                    print("Goodbye!")
                    break
                elif command == "commands" or command == "help":
                    print("\nAvailable Commands:")
                    print("  /sync     - Manually trigger task sync from Obsidian and Reminders")
                    print("  /pull     - Sync Calendar -> Markdown (Two-Way Sync)")
                    print("  /backlog  - Display the current unified backlog (grouped by category)")
                    print("  /stats    - Display focus analytics for today")
                    print("  /plan     - Trigger a morning planning session")
                    print("  /review   - Trigger an evening review session")
                    print("  /ui       - Launch the Streamlit web interface")
                    print("  /models   - Show current status of LLM models")
                    print("  /model    - Enable/disable models (e.g., /model disable gemini)")
                    print("  /gmail    - List snoozed and filtered emails from Gmail")
                    print("  /gmail-filter - Manage Gmail search filters (e.g., /gmail-filter add 'from:boss')")
                    print("  /docs     - Show project documentation")
                    print("  /create-agent - Scaffold a new custom agent")
                    print("  /list-agents  - Show available custom agents")
                    print("  /exit     - Quit the chat mode")
                elif command == "sync":
                    print("Syncing reminders to local storage...")
                    subprocess.run(["python3", "debug_reminders.py"])
                    print("Manually triggering task sync...")
                    tasks = get_unified_tasks(obsidian_path)
                    calendar_id = get_config_value("CALENDAR_ID", "primary")
                    service = calendar_manager.get_calendar_service()
                    if not service:
                        print("❌ Calendar service not available. Check credentials.")
                        continue
                    busy_slots = calendar_manager.get_busy_slots(service, calendar_ids=["primary", calendar_id])
                    logseq_path = get_config_value("LOGSEQ_DIR", None)
                    schedule = ai_orchestration.generate_schedule(
                        tasks, 
                        busy_slots, 
                        workspace_dir=obsidian_path, 
                        logseq_dir=logseq_path
                    )
                    if schedule:
                        calendar_manager.create_events(service, schedule, calendar_id=calendar_id)
                        update_markdown_plan(obsidian_path, schedule)
                        print("Sync complete.")
                    else:
                        print("Failed to generate schedule.")
                elif command == "pull":
                    sync_calendar_to_markdown(obsidian_path)
                elif command == "stats":
                    print("\n📊 --- Today's Focus Stats ---")
                    service = calendar_manager.get_calendar_service()
                    calendar_id = get_config_value("CALENDAR_ID", "primary")
                    if service:
                        managed = calendar_manager.get_managed_events(service, calendar_id=calendar_id)
                        if managed:
                            cat_hours = {}
                            total_mins = 0
                            for m in managed:
                                start = datetime.datetime.fromisoformat(m['start'].replace('Z', ''))
                                end = datetime.datetime.fromisoformat(m['end'].replace('Z', ''))
                                mins = (end - start).total_seconds() / 60
                                total_mins += mins
                                cat = m.get('category', 'General')
                                cat_hours[cat] = cat_hours.get(cat, 0) + mins
                            
                            for cat, mins in cat_hours.items():
                                print(f"  - {cat:20}: {mins/60:4.1f} hours")
                            print(f"  TOTAL PLANNED FOCUS: {total_mins/60:4.1f} hours")
                        else:
                            print("No AI-managed events found for today.")
                    else:
                        print("Could not connect to Google Calendar.")
                elif command == "backlog":
                    tasks = get_unified_tasks(obsidian_path)
                    print(f"\n--- Unified Backlog ({len(tasks)} tasks) ---")
                    # Group by category
                    cats = {}
                    for t in tasks:
                        cat = t.get("category", "Uncategorized")
                        if cat not in cats: cats[cat] = []
                        cats[cat].append(t)
                    
                    for cat, task_list in cats.items():
                        print(f"\n[{cat.upper()}]")
                        for t in task_list:
                            source_icon = "📝" if t['source'] == "Obsidian" else "🪵" if t['source'] == "Logseq" else "🍎"
                            due = f" (Due: {t['due_date']})" if t.get('due_date') else ""
                            print(f"  {source_icon} {t['task']}{due}")
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
                elif command == "models":
                    print(f"\nModel Activation Status:")
                    for m, enabled in ai_orchestration.MODELS_ENABLED.items():
                        status = "✅ ENABLED" if enabled else "❌ DISABLED"
                        print(f"  - {m:10}: {status}")
                elif command == "model":
                    if len(parts) >= 3:
                        action, target = parts[1].lower(), parts[2].lower()
                        if target in ai_orchestration.MODELS_ENABLED:
                            if action == "enable":
                                ai_orchestration.MODELS_ENABLED[target] = True
                                print(f"✅ Model '{target}' enabled.")
                            elif action == "disable":
                                ai_orchestration.MODELS_ENABLED[target] = False
                                print(f"❌ Model '{target}' disabled.")
                            else:
                                print(f"Unknown action: {action}. Use enable/disable.")
                        else:
                            print(f"Unknown model: {target}. Available: {', '.join(ai_orchestration.MODELS_ENABLED.keys())}")
                    else:
                        print("Usage: /model <enable/disable> <model_name>")
                elif command == "create-agent":
                    if len(parts) >= 2:
                        agent_name = parts[1].lower().replace("-", "_")
                        agent_path = f"custom_agents/{agent_name}.py"
                        if os.path.exists(agent_path):
                            print(f"⚠️ Agent '{agent_name}' already exists.")
                        else:
                            with open(agent_path, "w") as f:
                                f.write(f'\"\"\"\nAgent: {agent_name}\nCreated dynamically by AI Agent Assistant\n\"\"\"\n\ndef run(context):\n    \"\"\"Main entry point for the {agent_name} agent.\"\"\"\n    print(f"[{agent_name}] Running with context: {{len(context)}} tasks")\n    # Add your logic here\n    return f"Agent {agent_name} executed successfully."\n')
                            print(f"✅ Agent '{agent_name}' scaffolded at {agent_path}.")
                    else:
                        print("Usage: /create-agent <name>")
                elif command == "push-agent":
                    if len(parts) >= 3:
                        agent_name, repo_url = parts[1].lower(), parts[2]
                        agent_dir = f"custom_agents/{agent_name}_repo"
                        os.makedirs(agent_dir, exist_ok=True)
                        # Move the file into its own repo folder
                        os.rename(f"custom_agents/{agent_name}.py", f"{agent_dir}/agent.py")
                        # Init git and push
                        subprocess.run(["git", "init"], cwd=agent_dir)
                        subprocess.run(["git", "add", "."], cwd=agent_dir)
                        subprocess.run(["git", "commit", "-m", "Initial commit for custom agent"], cwd=agent_dir)
                        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=agent_dir)
                        print(f"🚀 Agent '{agent_name}' prepared for push to {repo_url}.")
                        print(f"Run 'cd {agent_dir} && git push -u origin main' to complete.")
                    else:
                        print("Usage: /push-agent <name> <repo_url>")
                elif command == "list-agents":
                    agents = [f[:-3] for f in os.listdir("custom_agents") if f.endswith(".py") and f != "__init__.py"]
                    print(f"Available Agents: {', '.join(agents) if agents else 'None'}")
                elif command == "gmail":
                    print("Checking Gmail for snoozed and filtered emails...")
                    service = gmail_agent.get_gmail_service()
                    if service:
                        snoozed = gmail_agent.get_snoozed_emails(service)
                        print(f"\n--- Snoozed Emails ({len(snoozed)}) ---")
                        for e in snoozed:
                            print(f"  💤 {e['subject']} (From: {e['from']})")
                        
                        filters = gmail_agent.load_filters()
                        if filters:
                            filtered = gmail_agent.get_filtered_emails(service, filters)
                            print(f"\n--- Filtered Emails ({len(filtered)}) ---")
                            for e in filtered:
                                print(f"  🔍 [{e['filter']}] {e['subject']} (From: {e['from']})")
                        else:
                            print("\nNo filters set. Use /gmail-filter add <query> to add one.")
                    else:
                        print("❌ Could not connect to Gmail. Check 'credentials.json' and 'token.json'.")
                elif command == "gmail-filter":
                    if len(parts) >= 2:
                        sub_cmd = parts[1].lower()
                        if sub_cmd == "add" and len(parts) >= 3:
                            query = " ".join(parts[2:])
                            if gmail_agent.add_filter(query):
                                print(f"✅ Filter added: '{query}'")
                            else:
                                print(f"ℹ️ Filter already exists: '{query}'")
                        elif sub_cmd == "remove" and len(parts) >= 3:
                            query = " ".join(parts[2:])
                            if gmail_agent.remove_filter(query):
                                print(f"✅ Filter removed: '{query}'")
                            else:
                                print(f"❌ Filter not found: '{query}'")
                        elif sub_cmd == "list":
                            filters = gmail_agent.load_filters()
                            print("\n--- Gmail Search Filters ---")
                            for i, f in enumerate(filters, 1):
                                print(f"  {i}. {f}")
                        else:
                            print("Usage: /gmail-filter <add/remove/list> [query]")
                    else:
                        print("Usage: /gmail-filter <add/remove/list> [query]")
                else:
                    print(f"Unknown command: /{command}. Type /commands for help.")

            else:
                # AI Chat integration
                print("AI is thinking...")
                try:
                    # Get context
                    tasks = get_unified_tasks(obsidian_path)
                    calendar_id = get_config_value("CALENDAR_ID", "primary")
                    service = calendar_manager.get_calendar_service()
                    
                    # Check if we failed at service level (e.g. invalid scope)
                    if not service:
                        print("⚠️ AI: I cannot access your calendar. Please check 'token.json' and 'credentials.json'.")
                        continue

                    busy_slots = calendar_manager.get_busy_slots(service, calendar_ids=["primary", calendar_id])
                    
                    # Get Gmail context
                    gmail_service = gmail_agent.get_gmail_service()
                    snoozed_emails = []
                    filtered_emails = []
                    if gmail_service:
                        snoozed_emails = gmail_agent.get_snoozed_emails(gmail_service)
                        filters = gmail_agent.load_filters()
                        if filters:
                            filtered_emails = gmail_agent.get_filtered_emails(gmail_service, filters)

                    # Get Books context
                    book_agent = BookAgent()
                    books_summary = book_agent.get_summary()

                    context_payload = {
                        "backlog": tasks,
                        "calendar_busy_slots": busy_slots,
                        "gmail_snoozed": snoozed_emails,
                        "gmail_filtered": filtered_emails,
                        "books_library": books_summary,
                        "current_time": datetime.datetime.now().astimezone().isoformat()
                    }
                    
                    prompt = f"User Question: '{user_input}'. Context: {json.dumps(context_payload)}. Provide a helpful answer."
                    
                    # Determine model to use
                    model_to_use = ai_orchestration.get_routing("chat")
                    
                    if model_to_use == "ollama":
                        print(" (Routing to local Ollama...)")
                        response_text = ai_orchestration.ollama_generate(prompt)
                        print(f"🤖 AI (Ollama): {response_text}")
                    else:
                        client = ai_orchestration.genai.Client(api_key=ai_orchestration.api_key)
                        response = client.models.generate_content(
                            model='gemini-flash-latest',
                            contents=prompt
                        )
                        
                        # Try to parse actions if the AI returned JSON
                        try:
                            text_content = response.text.strip()
                            
                            # Find the first { and last } to extract JSON from conversational text
                            start_idx = text_content.find('{')
                            end_idx = text_content.rfind('}')
                            
                            if start_idx != -1 and end_idx != -1:
                                json_str = text_content[start_idx:end_idx+1]
                                data = json.loads(json_str)
                                
                                if isinstance(data, dict):
                                    if "response" in data:
                                        print(f"🤖 AI: {data['response']}")
                                    if "actions" in data:
                                        execute_actions(data["actions"])
                                    continue # Successfully handled JSON
                            
                            # Fallback if no JSON found or parsing failed
                            print(f"🤖 AI: {response.text}")
                        except Exception as e:
                            # Fallback to plain text if not JSON
                            print(f"🤖 AI (Gemini): {response.text}")

                except Exception as e:
                    error_str = str(e).lower()
                    if "429" in error_str or "resource_exhausted" in error_str:
                        print("⚠️ AI: I've hit my API rate limit or daily quota. Please try again in a moment.")
                    elif "503" in error_str or "unavailable" in error_str:
                        print("⚠️ AI: The Gemini service is currently overloaded (503 Service Unavailable). This is usually temporary. Please try again in a few seconds.")
                    elif "invalid_scope" in error_str:
                        print("⚠️ AI: I encountered an 'invalid_scope' error. This usually happens after a security update.")
                        print("💡 FIX: Please run 'rm token.json' and restart the chat to re-authenticate with Google.")
                    else:
                        print(f"⚠️ AI: I encountered an error: {e}")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
            traceback.print_exc()




if __name__ == "__main__":
    # Load HF_TOKEN into environment if present globally at startup
    get_config_value("HF_TOKEN", None)
    
    parser = argparse.ArgumentParser(description="AI Agent Assistant: Local Markdown-Calendar-AI Bridge")
    parser.add_argument("--docs", action="store_true", help="Display project documentation in terminal")
    parser.add_argument("--stats", action="store_true", help="Display statistics about models, configuration, and usage")
    parser.add_argument("--morning", action="store_true", help="Start morning planning mode")
    parser.add_argument("--evening", action="store_true", help="Start evening review mode")
    parser.add_argument("--chat", action="store_true", help="Start interactive chat mode")
    parser.add_argument("--file", type=str, help="Specific markdown file to process", default="daily_note.md")
    args = parser.parse_args()

    if args.docs:
        display_docs()
    elif args.stats:
        display_stats()
    elif args.morning:
        handle_morning_planning(args.file)
    elif args.evening:
        handle_evening_review(args.file)
    elif args.chat:
        handle_chat_mode(args.file)
    else:
        obsidian_path = get_config_value("WORKSPACE_DIR", ".")
        logseq_path = get_config_value("LOGSEQ_DIR", None)
        
        event_handler = TaskSyncHandler()
        observer = Observer()
        
        # Watch Obsidian
        if os.path.exists(obsidian_path):
            observer.schedule(event_handler, obsidian_path, recursive=True)
            print(f"Monitoring Obsidian vault: {os.path.abspath(obsidian_path)}")
        else:
            observer.schedule(event_handler, ".", recursive=False)
            print(f"Monitoring current directory: {os.path.abspath('.')}")

        # Watch LogSeq Journals
        if logseq_path:
            journals_path = os.path.join(logseq_path, "journals")
            if os.path.exists(journals_path):
                observer.schedule(event_handler, journals_path, recursive=False)
                print(f"Monitoring LogSeq journals: {os.path.abspath(journals_path)}")

        print(f"🚀 AI Agent Assistant is active and monitoring for changes...")
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

