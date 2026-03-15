import time
import os
import re
import sys
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
from observer import parse_markdown_tasks, parse_logseq_tasks, update_markdown_plan
from reminders_manager import get_apple_reminders
from config_utils import get_config_value
from monitoring_agent import MonitoringAgent
from calendar_agent import CalendarAgent, start_background_calendar_sync
from planning_agent import PlanningAgent
from obsidian_agent import ObsidianAgent

def _update_config_key(config_path, key, value):
    """Update or append a KEY=value line in the .config file."""
    lines = []
    found = False
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            lines = f.readlines()
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}=") or line.startswith(f"# {key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}\n")
    with open(config_path, "w") as f:
        f.writelines(new_lines)


def get_unified_tasks(obsidian_path):
    """
    Merges tasks from Obsidian, LogSeq, and Apple Reminders.
    """
    # 1. Parse Obsidian tasks via direct file parsing (no Obsidian app needed)
    obsidian_tasks = []

    workspace_dir = get_config_value("WORKSPACE_DIR", None)
    if not workspace_dir:
        print("ℹ️  WORKSPACE_DIR not set — skipping Obsidian tasks")
    elif not os.path.isdir(workspace_dir):
        print(f"⚠️  WORKSPACE_DIR is set but does not exist: {workspace_dir}")
    else:
        try:
            agent = ObsidianAgent(workspace_dir=workspace_dir)
            raw_obs_tasks = agent.get_tasks(todo=True, done=False)

            for t in raw_obs_tasks:
                text = t.get("text", "")
                clean_text = re.sub(r"^\s*-\s+\[[ xX]\]\s+", "", text).strip()
                rel_file = t.get("file", "")
                line_num = t.get("line", "")

                task_data = {
                    "task": clean_text,
                    "category": "Uncategorized",
                    "due_date": None,
                    "source": f"obsidian:{rel_file}:{line_num}",
                    "file": rel_file,
                    "line": line_num,
                }

                # Extract #category
                cat_match = re.search(r"#([\w./-]+)", task_data["task"])
                if cat_match:
                    task_data["category"] = cat_match.group(1)
                    task_data["task"] = task_data["task"].replace(f"#{task_data['category']}", "").strip()

                # Extract 📅 YYYY-MM-DD
                date_match = re.search(r"📅\s*(\d{4}-\d{2}-\d{2})", task_data["task"])
                if date_match:
                    task_data["due_date"] = date_match.group(1)
                    task_data["task"] = task_data["task"].replace(f"📅 {task_data['due_date']}", "").strip()
                    task_data["task"] = task_data["task"].replace(f"📅{task_data['due_date']}", "").strip()

                # Also support ^YYYY-MM-DD
                if not task_data["due_date"]:
                    date_match = re.search(r"\^(\d{4}-\d{2}-\d{2})", task_data["task"])
                    if date_match:
                        task_data["due_date"] = date_match.group(1)
                        task_data["task"] = task_data["task"].replace(f"^{task_data['due_date']}", "").strip()

                obsidian_tasks.append(task_data)

            if obsidian_tasks:
                print(f"Extracted {len(obsidian_tasks)} tasks from Obsidian vault.")
        except Exception as e:
            print(f"⚠️ ObsidianAgent error: {e}")
    
    # 2. Parse LogSeq tasks if directory is provided
    logseq_tasks = []
    logseq_dir = get_config_value("LOGSEQ_DIR", None)
    if not logseq_dir:
        print("ℹ️  LOGSEQ_DIR not set — skipping LogSeq tasks. Set it in .env")
    elif not os.path.exists(logseq_dir):
        print(f"⚠️  LOGSEQ_DIR is set but does not exist: {logseq_dir}")
    else:
        from logseq_agent import LogSeqAgent
        ls_agent = LogSeqAgent(logseq_dir)
        ls_tasks = ls_agent.get_recent_tasks(days=14) + ls_agent.get_all_page_tasks()
        for t in ls_tasks:
            logseq_tasks.append({
                "task": t["task"],
                "category": t["properties"].get("category", "Personal"),
                "source": t["source"],
            })
        if logseq_tasks:
            print(f"Extracted {len(logseq_tasks)} total tasks from LogSeq (journals + pages).")

    # 3. Get Apple Reminders
    reminders_list = get_config_value("APPLE_REMINDERS_LIST", "Reminders")
    apple_tasks = get_apple_reminders(reminders_list)
    
    # 4. Combine
    unified_backlog = obsidian_tasks + logseq_tasks + apple_tasks
    return unified_backlog


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
        # Fetch busy slots from YAML cache
        calendar_agent = CalendarAgent()
        busy_slots = calendar_agent.get_busy_slots_from_yml()
        
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
            # 4. Sync back to Google Calendar and Obsidian via Planning Agent
            planning_agent = PlanningAgent(service, calendar_id)
            planning_agent.execute_plan(schedule, event.src_path)
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
    calendar_agent = CalendarAgent()
    busy_slots = calendar_agent.get_busy_slots_from_yml()
    
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
                planning_agent = PlanningAgent(service, calendar_id)
                planning_agent.execute_plan(schedule, obsidian_path)
            else:
                print("Skipped calendar sync.")
    else:
        print("Failed to generate schedule suggestion.")

def handle_planning_session(obsidian_path, dry_run=False):
    """
    Interactive planning session: fetch tasks + 7-day calendar, propose schedule,
    confirm per-task, then book confirmed items to Google Calendar.
    Safe to run non-interactively (cron, systemd): prints schedule to stdout and exits.
    """
    is_interactive = sys.stdin.isatty()

    # 1. Check credentials
    if not os.path.exists("token.json"):
        print("⚠️  Google Calendar not connected. Run the assistant once interactively to authenticate.")
        print("    Missing: token.json")
        return

    # 2. Get tasks
    tasks = get_unified_tasks(obsidian_path)
    if not tasks:
        if is_interactive:
            print("ℹ️  No tasks found in backlog.")
        return

    # 3. Connect to calendar
    service = calendar_manager.get_calendar_service()
    if not service:
        print("⚠️  Could not connect to Google Calendar.")
        return

    # 4. Fetch busy slots for next 7 days
    busy_slots = []
    for i in range(7):
        day = (datetime.datetime.now() + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        busy_slots.extend(calendar_manager.get_busy_slots(service, date_str=day))

    # 5. Generate schedule via LLM
    logseq_path = get_config_value("LOGSEQ_DIR", None)
    print("AI is generating your schedule...")
    result = ai_orchestration.generate_schedule(
        tasks, busy_slots, morning_mode=True,
        workspace_dir=obsidian_path, logseq_dir=logseq_path
    )
    if not result or not result.get("schedule"):
        print("ℹ️  No schedule proposed.")
        return

    if dry_run:
        print("\n--- Proposed Schedule (dry-run, nothing will be booked) ---")
        for item in result["schedule"]:
            date_part = item["start"].split("T")[0] if "T" in item["start"] else item["start"]
            time_part = item["start"].split("T")[1][:5] if "T" in item["start"] else ""
            print(f"  [{date_part} {time_part}] {item['task']}")
        print("\nDry run — no events created.")
        return

    if not is_interactive:
        print("📋 Proposed schedule (non-interactive mode — no calendar writes):")
        for item in result["schedule"]:
            print(f"  [{item['start']}] {item['task']}")
        print(f"\nℹ️  Run interactively to confirm and book: python main.py --plan")
        return

    # 6. Per-task confirmation
    confirmed = []
    for item in result["schedule"]:
        date_part = item["start"].split("T")[0] if "T" in item["start"] else item["start"]
        time_part = item["start"].split("T")[1][:5] if "T" in item["start"] else ""
        print(f"\nSchedule '{item['task']}' on {date_part} at {time_part}? [y/n/s(kip all)]: ", end="", flush=True)
        try:
            choice = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if choice == "y":
            confirmed.append(item)
        elif choice == "s":
            break

    # 7. Book confirmed items
    if confirmed:
        calendar_id = get_config_value("CALENDAR_ID", "primary")
        calendar_manager.create_events(service, confirmed, calendar_id=calendar_id)
        print(f"\n✅ Booked {len(confirmed)} event(s) to Google Calendar.")
    else:
        print("No events booked.")


def handle_evening_review(obsidian_path):
    """Scans completed tasks from today, generates LLM summary, optionally saves to LogSeq."""
    print("🌙 Evening Review")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_logseq = datetime.datetime.now().strftime("%Y_%m_%d")
    done_tasks = []

    # 1. Scan Obsidian for - [x] lines in any .md file modified today
    workspace = get_config_value("WORKSPACE_DIR", None)
    if workspace and os.path.isdir(workspace):
        for root, _, files in os.walk(workspace):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, errors="ignore") as fh:
                    for line in fh:
                        if re.match(r"\s*- \[x\]", line):
                            task = re.sub(r"\s*- \[x\]\s*", "", line).strip()
                            if task:
                                done_tasks.append(f"[Obsidian] {task}")

    # 2. Scan LogSeq journal for DONE lines from today
    logseq_dir = get_config_value("LOGSEQ_DIR", None)
    if logseq_dir:
        jpath = os.path.join(logseq_dir, "journals", f"{today_logseq}.md")
        if os.path.exists(jpath):
            with open(jpath, errors="ignore") as fh:
                for line in fh:
                    if re.match(r"\s*- DONE", line):
                        task = re.sub(r"\s*- DONE\s*", "", line).strip()
                        if task:
                            done_tasks.append(f"[LogSeq] {task}")

    if not done_tasks:
        print("No tasks completed today.")
        return

    print(f"\n✅ {len(done_tasks)} tasks completed today:")
    for t in done_tasks:
        print(f"  • {t}")

    # 3. Generate LLM summary
    prompt = (
        f"Today is {today}. The user completed the following tasks:\n\n"
        + "\n".join(f"- {t}" for t in done_tasks)
        + "\n\nWrite a brief, encouraging 2-3 sentence daily summary. "
        "Mention the key themes of what was accomplished. Be concise and positive."
    )
    print("\n💬 Generating summary...")
    summary = ai_orchestration.ollama_generate(prompt)
    if summary:
        print(f"\n{summary}")

    # 4. Optionally append to LogSeq journal
    if logseq_dir and summary:
        try:
            save = input("\nAppend summary to today's LogSeq journal? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            save = "n"
        if save == "y":
            jpath = os.path.join(logseq_dir, "journals", f"{today_logseq}.md")
            os.makedirs(os.path.dirname(jpath), exist_ok=True)
            with open(jpath, "a", encoding="utf-8") as f:
                f.write(f"\n## Evening Review — {today}\n\n{summary}\n")
            print(f"✅ Saved to {jpath}")

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
                elif action['type'] == "read_file":
                    content = fs_agent.read_file(action['path'])
                    print(f"📄 Read content from {action['path']} ({len(content)} chars)")
                    # This might need to be fed back to the AI in a real scenario
                    # For now, let's just show it.
                    print(f"\n--- CONTENT FROM {action['path']} ---\n{content[:500]}...\n")
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
    try:
        import chat_ui
        chat_ui.print_banner()
    except ImportError:
        print("\n  AI AGENT ASSISTANT\n")

def sync_logseq_to_obsidian():
    """
    One-way sync: reads all open LATER/TODO tasks from LogSeq journals and pages,
    then appends new (non-duplicate) tasks to the configured Obsidian target file.
    Returns (synced_count, skipped_count, target_path) or None on config error.
    """
    logseq_dir = get_config_value("LOGSEQ_DIR", None)
    workspace_dir = get_config_value("WORKSPACE_DIR", None)

    missing = []
    if not logseq_dir or "path/to" in logseq_dir:
        missing.append("LOGSEQ_DIR")
    if not workspace_dir or "path/to" in workspace_dir:
        missing.append("WORKSPACE_DIR")
    if missing:
        print(f"❌ Required config key(s) not set: {', '.join(missing)}")
        print("   Set them with: /settings set <KEY> <value>")
        return None

    from logseq_agent import LogSeqAgent
    ls = LogSeqAgent(logseq_dir)

    journal_tasks = ls.get_recent_tasks(days=30)
    page_tasks = ls.get_all_page_tasks()
    all_tasks = journal_tasks + page_tasks

    sync_target = get_config_value("SYNC_TARGET_PAGE", "Inbox.md")
    target_path = os.path.join(workspace_dir, sync_target)

    # Read existing content (create parent dirs if needed)
    if os.path.exists(target_path):
        with open(target_path, "r", encoding="utf-8") as f:
            current_content = f.read()
    else:
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        current_content = ""

    new_lines = []
    skipped = 0
    for task in all_tasks:
        task_text = task.get("task", "").strip()
        if not task_text:
            continue
        # Duplicate detection: skip if task text already appears anywhere in file
        if task_text in current_content:
            skipped += 1
            continue
        source = task.get("source", "")
        new_lines.append(f"- [ ] {task_text} #logseq <!-- source: {source} -->")

    if new_lines:
        separator = "\n" if current_content and not current_content.endswith("\n") else ""
        updated = current_content + separator + "\n".join(new_lines) + "\n"
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(updated)

    synced = len(new_lines)
    target_name = os.path.basename(target_path)
    print(f"✅ Synced {synced} tasks, skipped {skipped} duplicates → {target_name}")
    return synced, skipped, target_path


def handle_chat_mode(obsidian_file):
    """
    Starts an interactive CLI chat loop with slash commands and Rich UI.
    """
    import chat_ui

    obsidian_path = get_config_value("WORKSPACE_DIR", ".")
    logseq_path = get_config_value("LOGSEQ_DIR", None)

    chat_ui.print_banner()

    # Config path status
    workspace_status = "✅ set" if obsidian_path and obsidian_path != "." else "⚠️  not set (defaulting to .)"
    logseq_status = "✅ set" if logseq_path else "⚠️  not set"
    print(f"WORKSPACE_DIR: {obsidian_path}  [{workspace_status}]")
    print(f"LOGSEQ_DIR:    {logseq_path or '(none)'}  [{logseq_status}]")

    # Ollama startup check
    if ai_orchestration.is_ollama_running():
        models = ai_orchestration.list_ollama_models()
        if models:
            print(f"✅ Ollama running — models: {', '.join(models)}")
        else:
            print("⚠️  Ollama running but no models found. Run: ollama pull llama3")
    else:
        print("⚠️  Ollama is not running. Start it with: ollama serve")

    history = chat_ui.load_history()

    # Auto-sync LogSeq → Obsidian on startup if configured
    if get_config_value("AUTO_SYNC_LOGSEQ", "false").lower() == "true":
        chat_ui.render_info("AUTO_SYNC_LOGSEQ enabled — syncing LogSeq tasks on startup...")
        sync_logseq_to_obsidian()

    # Use prompt_toolkit for better input if available
    try:
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.history import FileHistory
        input_history = FileHistory(os.path.expanduser("~/.ai_agent_input_history"))
        def get_input():
            return pt_prompt("You: ", history=input_history).strip()
    except ImportError:
        def get_input():
            return input("\nYou: ").strip()

    while True:
        try:
            user_input = get_input()

            if not user_input:
                continue

            if user_input.startswith("/"):
                command_full = user_input[1:].strip()
                parts = command_full.split()
                if not parts:
                    chat_ui.render_warning("Invalid command. Type /commands for help.")
                    continue
                command = parts[0].lower()

                if command in ("exit", "quit"):
                    chat_ui.render_info("Goodbye!")
                    break
                elif command in ("commands", "help"):
                    chat_ui.render_command_help()
                elif command == "history":
                    chat_ui.render_history_summary(history)
                elif command == "clear-history":
                    history = []
                    chat_ui.save_history(history)
                    chat_ui.render_success("Conversation history cleared.")
                elif command == "index":
                    chat_ui.render_info("Re-indexing all notes and books...")
                    from rag_agent import RAGAgent
                    rag_agent = RAGAgent(obsidian_path, logseq_path)
                    rag_agent.index_vault()
                    from book_agent import BookAgent
                    book_agent = BookAgent()
                    books = book_agent.scan_books()
                    for b in books:
                        print(book_agent.index_book(b['full_path']))
                    chat_ui.render_success("Indexing complete.")
                elif command == "sync":
                    chat_ui.render_info("Syncing reminders to local storage...")
                    subprocess.run(["python3", "debug_reminders.py"])
                    chat_ui.render_info("Manually triggering task sync...")
                    tasks = get_unified_tasks(obsidian_path)
                    calendar_id = get_config_value("CALENDAR_ID", "primary")
                    service = calendar_manager.get_calendar_service()
                    if not service:
                        chat_ui.render_error("Calendar service not available. Check credentials.")
                        continue
                    calendar_agent = CalendarAgent()
                    busy_slots = calendar_agent.get_busy_slots_from_yml()
                    logseq_path = get_config_value("LOGSEQ_DIR", None)
                    schedule = ai_orchestration.generate_schedule(
                        tasks, busy_slots,
                        workspace_dir=obsidian_path, logseq_dir=logseq_path
                    )
                    confirm_sync = input("Sync to calendar? (y/n): ").strip().lower()
                    if confirm_sync == 'y':
                        planning_agent = PlanningAgent(service, calendar_id)
                        planning_agent.execute_plan(schedule, obsidian_path)
                        chat_ui.render_success("Scheduled!")
                    else:
                        chat_ui.render_info("Sync cancelled.")
                elif command == "pull":
                    sync_calendar_to_markdown(obsidian_path)
                elif command == "stats":
                    print("\n--- Today's Focus Stats ---")
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
                            chat_ui.render_info("No AI-managed events found for today.")
                    else:
                        chat_ui.render_error("Could not connect to Google Calendar.")
                elif command == "backlog":
                    tasks = get_unified_tasks(obsidian_path)
                    chat_ui.render_backlog(tasks)
                elif command == "plan":
                    handle_planning_session(obsidian_path)
                elif command == "review":
                    handle_evening_review(obsidian_path)
                elif command == "ui":
                    chat_ui.render_info("Launching Streamlit UI in the background...")
                    subprocess.Popen([".venv/bin/streamlit", "run", "app.py"])
                    chat_ui.render_success("Web interface is opening in your browser.")
                elif command == "docs":
                    display_docs()
                elif command == "services":
                    ollama_up = ai_orchestration.is_ollama_running()
                    chat_ui.render_services(ollama_up)
                elif command == "models":
                    ollama_models = ai_orchestration.list_ollama_models()
                    if not ollama_models:
                        chat_ui.render_warning("No Ollama models found. Run: ollama pull llama3")
                    else:
                        current_model = get_config_value("OLLAMA_MODEL", "llama3")
                        print("\n🤖 Installed Ollama Models:")
                        for i, m in enumerate(ollama_models, 1):
                            marker = " (current)" if m == current_model or m.split(":")[0] == current_model else ""
                            print(f"  {i}. {m}{marker}")
                        try:
                            selection = input("\nSelect a model number (or press Enter to keep current): ").strip()
                            if selection:
                                idx = int(selection) - 1
                                if 0 <= idx < len(ollama_models):
                                    selected_model = ollama_models[idx]
                                    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".config")
                                    _update_config_key(config_path, "OLLAMA_MODEL", selected_model)
                                    chat_ui.render_success(f"Switched to {selected_model}. Effective immediately.")
                                else:
                                    chat_ui.render_warning("Invalid selection.")
                        except (ValueError, KeyboardInterrupt):
                            chat_ui.render_info("Selection cancelled.")
                elif command == "model":
                    if len(parts) >= 3:
                        action, target = parts[1].lower(), parts[2].lower()
                        if target in ai_orchestration.MODELS_ENABLED:
                            if action == "enable":
                                ai_orchestration.MODELS_ENABLED[target] = True
                                chat_ui.render_success(f"Model '{target}' enabled.")
                            elif action == "disable":
                                ai_orchestration.MODELS_ENABLED[target] = False
                                chat_ui.render_info(f"Model '{target}' disabled.")
                            else:
                                chat_ui.render_warning(f"Unknown action: {action}. Use enable/disable.")
                        else:
                            chat_ui.render_warning(f"Unknown model: {target}. Available: {', '.join(ai_orchestration.MODELS_ENABLED.keys())}")
                    else:
                        chat_ui.render_info("Usage: /model <enable/disable> <model_name>")
                elif command == "routing":
                    ollama_models = ai_orchestration.list_ollama_models()
                    if not ollama_models:
                        chat_ui.render_warning("No Ollama models found. Run: ollama pull <model>")
                    else:
                        task_types = ["chat", "scheduling", "parsing"]
                        print("\n--- Current Routing ---")
                        for i, tt in enumerate(task_types, 1):
                            current = get_config_value(f"ROUTING_{tt.upper()}", "ollama")
                            print(f"  {i}. {tt:<12} → {current}")
                        print("\n--- Installed Ollama Models ---")
                        for j, m in enumerate(ollama_models, 1):
                            print(f"  {j}. {m}")
                        try:
                            route_choice = input("\nChange routing for which task type? (1=chat 2=scheduling 3=parsing, Enter=skip): ").strip()
                            if route_choice.isdigit() and 1 <= int(route_choice) <= 3:
                                tt = task_types[int(route_choice) - 1]
                                model_choice = input(f"Select model number for {tt}: ").strip()
                                if model_choice.isdigit() and 1 <= int(model_choice) <= len(ollama_models):
                                    selected = ollama_models[int(model_choice) - 1]
                                    _update_config_key(config_path, f"ROUTING_{tt.upper()}", selected)
                                    chat_ui.render_success(f"Routing for {tt} → {selected}. Effective immediately.")
                                else:
                                    chat_ui.render_warning("Invalid model selection.")
                        except (EOFError, KeyboardInterrupt):
                            pass
                elif command == "create-agent":
                    if len(parts) >= 2:
                        agent_name = parts[1].lower().replace("-", "_")
                        agent_path = f"custom_agents/{agent_name}.py"
                        if os.path.exists(agent_path):
                            chat_ui.render_warning(f"Agent '{agent_name}' already exists.")
                        else:
                            with open(agent_path, "w") as f:
                                f.write(f'\"\"\"\nAgent: {agent_name}\nCreated dynamically by AI Agent Assistant\n\"\"\"\n\ndef run(context):\n    \"\"\"Main entry point for the {agent_name} agent.\"\"\"\n    print(f"[{agent_name}] Running with context: {{len(context)}} tasks")\n    # Add your logic here\n    return f"Agent {agent_name} executed successfully."\n')
                            chat_ui.render_success(f"Agent '{agent_name}' scaffolded at {agent_path}.")
                    else:
                        chat_ui.render_info("Usage: /create-agent <name>")
                elif command == "push-agent":
                    if len(parts) >= 3:
                        agent_name, repo_url = parts[1].lower(), parts[2]
                        agent_dir = f"custom_agents/{agent_name}_repo"
                        os.makedirs(agent_dir, exist_ok=True)
                        os.rename(f"custom_agents/{agent_name}.py", f"{agent_dir}/agent.py")
                        subprocess.run(["git", "init"], cwd=agent_dir)
                        subprocess.run(["git", "add", "."], cwd=agent_dir)
                        subprocess.run(["git", "commit", "-m", "Initial commit for custom agent"], cwd=agent_dir)
                        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=agent_dir)
                        chat_ui.render_success(f"Agent '{agent_name}' prepared for push to {repo_url}.")
                        chat_ui.render_info(f"Run 'cd {agent_dir} && git push -u origin main' to complete.")
                    else:
                        chat_ui.render_info("Usage: /push-agent <name> <repo_url>")
                elif command == "list-agents":
                    agents = [f[:-3] for f in os.listdir("custom_agents") if f.endswith(".py") and f != "__init__.py"]
                    chat_ui.render_info(f"Available Agents: {', '.join(agents) if agents else 'None'}")
                elif command == "organize":
                    chat_ui.render_info("AI is analyzing your backlog for organization...")
                    tasks = get_unified_tasks(obsidian_path)
                    if not tasks:
                        chat_ui.render_info("No tasks found in backlog.")
                        continue
                    results = ai_orchestration.suggest_task_organization(tasks)
                    if results and "suggestions" in results:
                        for sug in results["suggestions"]:
                            print(f"  - {sug['task']} -> {sug['suggested_category']} ({sug['target_date']}): {sug['reason']}")
                        confirm = input("\nApply these suggestions to your markdown plan? (y/n): ").strip().lower()
                        if confirm == 'y':
                            update_markdown_plan(obsidian_path, results["suggestions"])
                            chat_ui.render_success("Suggestions applied to markdown.")
                    else:
                        chat_ui.render_error("Failed to get suggestions from AI.")
                elif command == "cmd":
                    if len(parts) >= 2:
                        user_cmd = " ".join(parts[1:])
                        chat_ui.render_info(f"Executing command on backlog: '{user_cmd}'")
                        tasks = get_unified_tasks(obsidian_path)
                        results = ai_orchestration.process_tasks_with_command(tasks, user_cmd)
                        if results and "suggestions" in results:
                            for sug in results["suggestions"]:
                                print(f"  - {sug['task']} -> {sug['suggested_category']} ({sug['target_date']})")
                            confirm = input("\nApply changes? (y/n): ").strip().lower()
                            if confirm == 'y':
                                update_markdown_plan(obsidian_path, results["suggestions"])
                                chat_ui.render_success("Changes applied.")
                        else:
                            chat_ui.render_info("No changes suggested by AI.")
                    else:
                        chat_ui.render_info("Usage: /cmd <instruction for backlog>")
                elif command == "develop":
                    if len(parts) >= 2:
                        prompt = " ".join(parts[1:])
                        chat_ui.render_info(f"AI is developing code for: '{prompt}'...")
                        code_prompt = f"Develop a complete, working script or code snippet for: {prompt}. Return only the code and a brief explanation."
                        code_response, model_used = ai_orchestration.run_agent_query(code_prompt)
                        chat_ui.render_response(code_response, model_used)
                        save = input("Save this code to a file? (y/n): ").strip().lower()
                        if save == 'y':
                            filename = input("Enter filename (e.g. script.py): ").strip()
                            with open(filename, "w") as f:
                                f.write(code_response)
                            chat_ui.render_success(f"Saved to {filename}")
                    else:
                        chat_ui.render_info("Usage: /develop <what to build>")
                elif command == "define-agent":
                    if len(parts) >= 3:
                        agent_name = parts[1].lower().replace("-", "_")
                        linked_llm = parts[2].lower()
                        if linked_llm not in ai_orchestration.MODELS_ENABLED:
                            chat_ui.render_warning(f"'{linked_llm}' is not a recognized model. Using default.")
                        agent_path = f"custom_agents/{agent_name}.py"
                        with open(agent_path, "w") as f:
                            f.write(f'\"\"\"\nAgent: {agent_name}\nLinked LLM: {linked_llm}\nCreated dynamically by AI Agent Assistant\n\"\"\"\n\nimport ai_orchestration\n\ndef run(context):\n    \"\"\"Main entry point for the {agent_name} agent using {linked_llm}.\"\"\"\n    prompt = f"As the {agent_name} specialist, process this context: {{context}}"\n    if "{linked_llm}" == "ollama":\n        return ai_orchestration.ollama_generate(prompt)\n    else:\n        result, _ = ai_orchestration.run_agent_query(prompt)\n        return result\n')
                        chat_ui.render_success(f"Agent '{agent_name}' defined and linked to '{linked_llm}' at {agent_path}.")
                    else:
                        chat_ui.render_info("Usage: /define-agent <name> <llm_type>")
                elif command == "gmail":
                    chat_ui.render_info("Checking Gmail for snoozed and filtered emails...")
                    service = gmail_agent.get_gmail_service()
                    if service:
                        snoozed = gmail_agent.get_snoozed_emails(service)
                        print(f"\n--- Snoozed Emails ({len(snoozed)}) ---")
                        for e in snoozed:
                            print(f"  {e['subject']} (From: {e['from']})")
                        filters = gmail_agent.load_filters()
                        if filters:
                            filtered = gmail_agent.get_filtered_emails(service, filters)
                            print(f"\n--- Filtered Emails ({len(filtered)}) ---")
                            for e in filtered:
                                print(f"  [{e['filter']}] {e['subject']} (From: {e['from']})")
                        else:
                            chat_ui.render_info("No filters set. Use /gmail-filter add <query> to add one.")
                    else:
                        chat_ui.render_error("Could not connect to Gmail. Check 'credentials.json' and 'token.json'.")
                elif command == "gmail-filter":
                    if len(parts) >= 2:
                        sub_cmd = parts[1].lower()
                        if sub_cmd == "add" and len(parts) >= 3:
                            query = " ".join(parts[2:])
                            if gmail_agent.add_filter(query):
                                chat_ui.render_success(f"Filter added: '{query}'")
                            else:
                                chat_ui.render_info(f"Filter already exists: '{query}'")
                        elif sub_cmd == "remove" and len(parts) >= 3:
                            query = " ".join(parts[2:])
                            if gmail_agent.remove_filter(query):
                                chat_ui.render_success(f"Filter removed: '{query}'")
                            else:
                                chat_ui.render_error(f"Filter not found: '{query}'")
                        elif sub_cmd == "list":
                            filters = gmail_agent.load_filters()
                            print("\n--- Gmail Search Filters ---")
                            for i, f in enumerate(filters, 1):
                                print(f"  {i}. {f}")
                        else:
                            chat_ui.render_info("Usage: /gmail-filter <add/remove/list> [query]")
                    else:
                        chat_ui.render_info("Usage: /gmail-filter <add/remove/list> [query]")
                elif command == "add-task":
                    args_str = " ".join(parts[1:])
                    if not args_str:
                        chat_ui.render_warning("Usage: /add-task <task description>")
                    else:
                        logseq_dir = get_config_value("LOGSEQ_DIR", None)
                        if not logseq_dir:
                            chat_ui.render_error("LOGSEQ_DIR not set in .env")
                        else:
                            from logseq_agent import LogSeqAgent
                            ls = LogSeqAgent(logseq_dir)
                            path = ls.add_task(args_str)
                            chat_ui.render_success(f"Added to LogSeq: {args_str}")
                            chat_ui.render_info(f"  → {path}")
                elif command == "done":
                    args_str = " ".join(parts[1:])
                    if not args_str:
                        chat_ui.render_warning("Usage: /done <task text or partial match>")
                    else:
                        marked = False
                        logseq_dir = get_config_value("LOGSEQ_DIR", None)
                        if logseq_dir:
                            from logseq_agent import LogSeqAgent
                            ls = LogSeqAgent(logseq_dir)
                            if ls.mark_done(args_str):
                                chat_ui.render_success(f"Marked DONE in LogSeq: {args_str}")
                                marked = True
                        if not marked:
                            workspace_dir = get_config_value("WORKSPACE_DIR", None)
                            if workspace_dir:
                                obs = ObsidianAgent(workspace_dir=workspace_dir)
                                if obs.mark_done(args_str):
                                    chat_ui.render_success(f"Marked DONE in Obsidian: {args_str}")
                                    marked = True
                        if not marked:
                            chat_ui.render_warning(f"No matching task found for: {args_str}")
                elif command == "settings":
                    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".config")
                    if len(parts) >= 3 and parts[1].lower() == "set":
                        key = parts[2].upper()
                        value = parts[3] if len(parts) >= 4 else ""
                        if not value:
                            chat_ui.render_warning("Usage: /settings set <KEY> <value>")
                        else:
                            _update_config_key(config_path, key, value)
                            chat_ui.render_success(f"Updated {key} in .config")
                            # Reload relevant in-memory values
                            if key in ("OLLAMA_MODEL", "OLLAMA_HOST", "LLM_PRIORITY",
                                       "ROUTING_CHAT", "ROUTING_SCHEDULING"):
                                chat_ui.render_info("Restart the chat for routing changes to take effect.")
                    else:
                        chat_ui.render_settings(config_path)
                elif command == "sync-logseq":
                    chat_ui.render_info("Syncing LogSeq tasks → Obsidian...")
                    sync_logseq_to_obsidian()
                else:
                    chat_ui.render_warning(f"Unknown command: /{command}. Type /commands for help.")

            else:
                # Streaming AI response with Rich rendering
                history = chat_ui.add_to_history("user", user_input, history)

                try:
                    stream, model_used = ai_orchestration.run_agent_query_stream(user_input, history)
                    full_response = chat_ui.render_streaming(stream, model_used)
                    history = chat_ui.add_to_history("assistant", full_response, history)
                    chat_ui.save_history(history)
                except Exception as e:
                    chat_ui.render_error(str(e))
                    traceback.print_exc()

        except KeyboardInterrupt:
            chat_ui.render_info("\nGoodbye!")
            break
        except EOFError:
            chat_ui.render_info("\nGoodbye!")
            break
        except Exception as e:
            chat_ui.render_error(f"An unexpected error occurred: {e}")
            traceback.print_exc()




if __name__ == "__main__":
    # Load HF_TOKEN into environment if present globally at startup
    get_config_value("HF_TOKEN", None)
    
    parser = argparse.ArgumentParser(description="AI Agent Assistant: Local Markdown-Calendar-AI Bridge")
    parser.add_argument("--docs", action="store_true", help="Display project documentation in terminal")
    parser.add_argument("--stats", action="store_true", help="Display statistics about models, configuration, and usage")
    parser.add_argument("--morning", action="store_true", help="Start morning planning mode")
    parser.add_argument("--plan", action="store_true", help="Run interactive planning session against Google Calendar")
    parser.add_argument("--dry-run", action="store_true", help="Show proposed schedule without booking (use with --plan)")
    parser.add_argument("--evening", action="store_true", help="Start evening review mode")
    parser.add_argument("--chat", action="store_true", help="Start interactive chat mode")
    parser.add_argument("--backlog", action="store_true", help="Print unified task backlog (Obsidian + LogSeq + Reminders) and exit")
    parser.add_argument("--no-web", action="store_true", help="Suppress any Streamlit/web UI references (CLI-only mode)")
    parser.add_argument("--file", type=str, help="Specific markdown file to process", default="daily_note.md")
    args = parser.parse_args()

    if args.docs:
        display_docs()
    elif args.stats:
        display_stats()
    elif args.backlog:
        import chat_ui
        obsidian_path = get_config_value("WORKSPACE_DIR", ".")
        tasks = get_unified_tasks(obsidian_path)
        chat_ui.render_backlog(tasks)
    elif args.morning:
        handle_morning_planning(args.file)
    elif args.plan:
        obsidian_path = get_config_value("WORKSPACE_DIR", ".")
        handle_planning_session(obsidian_path, dry_run=args.dry_run)
    elif args.evening:
        handle_evening_review(args.file)
    elif args.chat:
        start_background_calendar_sync()
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
        # Start calendar background sync
        start_background_calendar_sync()
        
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

