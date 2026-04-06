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

    # LLM backend status
    print("\n🤖 LLM Backend:")
    try:
        from ai_orchestration import is_lmstudio_running, is_ollama_running, MODELS_ENABLED
        from config_utils import get_config_value
        if MODELS_ENABLED.get("lmstudio"):
            lms_model = get_config_value("LM_STUDIO_MODEL", "")
            status = "✓ Running" if is_lmstudio_running() else "✗ Not responding"
            print(f"  LM Studio ({lms_model}): {status}")
        if MODELS_ENABLED.get("ollama"):
            status = "✓ Running" if is_ollama_running() else "✗ Not responding"
            print(f"  Ollama: {status}")
        routing = get_config_value("ROUTING_CHAT", "lmstudio")
        print(f"  Active routing: {routing}")
    except Exception as e:
        print(f"  Could not check LLM status: {e}")
    else:
        print("  Cannot list models without API key")

    # Calendar Status
    print("\n📅 Calendar Integration:")
    print(f"  Local Calendar (ICS): {'✓ Present' if os.path.exists('datainput/local_calendar.ics') else '✗ Missing'}")
    
    yml_path = 'datainput/googlecalendar.yml'
    if os.path.exists(yml_path):
        import yaml
        with open(yml_path, 'r', encoding='utf-8') as f:
            try:
                data = yaml.safe_load(f)
                last_upd = data.get('last_updated', 'Unknown')
                slots = len(data.get('busy_slots', []))
                print(f"  n8n YAML Cache: ✓ Present (Last updated: {last_upd}, Slots: {slots})")
            except:
                print("  n8n YAML Cache: ✗ Corrupt")
    else:
        print("  n8n YAML Cache: ✗ Missing (Run n8n sync to populate)")

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

        # 2. Get Calendar context (YAML cache + local ICS)
        busy_slots = []
        calendar_agent = CalendarAgent()
        busy_slots.extend(calendar_agent.get_busy_slots_from_yml())
        
        try:
            from local_calendar_agent import get_today_events
            for le in get_today_events():
                busy_slots.append({
                    "summary": le["summary"],
                    "start": le["start"],
                    "end": le["end"]
                })
        except:
            pass

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
            # 4. Sync back to Local Calendar and Obsidian via Planning Agent
            planning_agent = PlanningAgent()
            planning_agent.execute_plan(schedule, event.src_path)
            print("--- Sync Complete ---\n")
        else:
            print("Failed to generate schedule from AI.")
