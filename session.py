import os
import time
import calendar_manager
import ai_orchestration
from watchdog.events import PatternMatchingEventHandler
from config_utils import get_config_value, is_google_calendar_enabled
from calendar_agent import CalendarAgent
from planning_agent import PlanningAgent
from task_utils import get_unified_tasks


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
    if not is_google_calendar_enabled():
        print("  Google Calendar: disabled (ENABLE_GOOGLE_CALENDAR=false in .config)")
    else:
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

        # 2. Get Calendar context (only if Google Calendar is enabled)
        busy_slots = []
        service = None
        calendar_id = None
        if is_google_calendar_enabled():
            calendar_id = get_config_value("CALENDAR_ID", "primary")
            service = calendar_manager.get_calendar_service()
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
            if is_google_calendar_enabled() and service:
                planning_agent = PlanningAgent(service, calendar_id)
                planning_agent.execute_plan(schedule, event.src_path)
            else:
                print("(Google Calendar disabled — schedule generated but not booked)")
            print("--- Sync Complete ---\n")
        else:
            print("Failed to generate schedule from AI.")
