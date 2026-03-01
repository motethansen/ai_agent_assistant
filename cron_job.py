import os
import subprocess
import datetime
import main

def run_sync():
    """
    Headless sync for cron jobs.
    """
    print(f"--- Cron Sync Started at {datetime.datetime.now()} ---")
    
    # 1. Determine paths
    obsidian_path = main.get_config_value("WORKSPACE_DIR", ".")
    calendar_id = main.get_config_value("CALENDAR_ID", "primary")
    
    # 2. Sync Apple Reminders if on macOS
    import platform
    if platform.system() == "Darwin":
        print("Syncing Apple Reminders...")
        try:
            # We use subprocess to run the extraction script
            subprocess.run(["python3", "debug_reminders.py"], check=True)
        except Exception as e:
            print(f"Error syncing Apple Reminders: {e}")

    # 3. Get Unified Backlog
    print("Fetching unified backlog...")
    tasks = main.get_unified_tasks(obsidian_path)
    if not tasks:
        print("No tasks found. Skipping.")
        return

    # 4. Get Calendar Context
    import calendar_manager
    import ai_orchestration
    
    service = calendar_manager.get_calendar_service()
    if not service:
        print("Error: Calendar service not available.")
        return
        
    busy_slots = calendar_manager.get_busy_slots(service, calendar_id=calendar_id)
    
    # 5. AI Orchestration
    print("Consulting AI scheduler...")
    logseq_path = main.get_config_value("LOGSEQ_DIR", None)
    schedule = ai_orchestration.generate_schedule(
        tasks, 
        busy_slots, 
        workspace_dir=obsidian_path, 
        logseq_dir=logseq_path
    )
    
    if schedule:
        # 6. Sync to Google Calendar
        calendar_manager.create_events(service, schedule, calendar_id=calendar_id)
        
        # 7. Write back to Markdown (Obsidian)
        if os.path.exists(obsidian_path):
            if os.path.isdir(obsidian_path):
                # If it's a directory, we need to know which file to update.
                # Usually it's today's daily note. 
                # For now, let's use daily_note.md as a default if it exists.
                target_file = os.path.join(obsidian_path, "daily_note.md")
                if os.path.exists(target_file):
                    main.update_markdown_plan(target_file, schedule)
            else:
                main.update_markdown_plan(obsidian_path, schedule)
        
        print("--- Cron Sync Complete ---")
    else:
        print("Failed to generate schedule.")

    # 8. Run Update and Health Checks
    print("Running system update and health checks...")
    try:
        import update_manager
        update_manager.run_all_checks()
    except Exception as e:
        print(f"Error running health checks: {e}")

if __name__ == "__main__":
    run_sync()
