import os
import time
import argparse
from watchdog.observers import Observer
from config_utils import get_config_value
from calendar_agent import start_background_calendar_sync
from task_utils import get_unified_tasks
from cli_commands import (
    handle_morning_planning,
    handle_planning_session,
    handle_evening_review,
    handle_chat_mode,
)
from session import display_stats, display_docs, TaskSyncHandler


def print_banner():
    """Prints the AI Agent Assistant banner."""
    try:
        import chat_ui
        chat_ui.print_banner()
    except ImportError:
        print("\n  AI AGENT ASSISTANT\n")


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
    parser.add_argument("--today", action="store_true", help="Show today's tasks and calendar events, then exit")
    args = parser.parse_args()

    if args.today:
        from terminal_views import handle_today_view
        handle_today_view()
    elif args.docs:
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
