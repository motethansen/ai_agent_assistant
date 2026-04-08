import os
import re
import sys
import datetime
import traceback
import subprocess
from config_utils import get_config_value, is_google_calendar_enabled
import calendar_manager
import ai_orchestration
import gmail_agent
from book_agent import BookAgent
from travel_agent import TravelAgent
from observer import update_markdown_plan
from obsidian_agent import ObsidianAgent
from calendar_agent import CalendarAgent
from planning_agent import PlanningAgent
from file_system_agent import FileSystemAgent
from task_utils import get_unified_tasks
import task_reschedule_agent


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


def sync_calendar_to_markdown(obsidian_path):
    """
    Pulls 'AI: ' events from the local calendar and updates the markdown file.
    (Two-Way Sync: Local ICS -> Markdown)
    """
    print(f"🔄 Syncing latest events from local calendar to {os.path.basename(obsidian_path)}...")

    from local_calendar_agent import get_today_events
    events = get_today_events()
    
    if events:
        update_markdown_plan(obsidian_path, events)
        print(f"✅ Successfully synced {len(events)} events from local calendar to Markdown.")
    else:
        print("ℹ️ No events found in today's local calendar.")


def handle_morning_planning(obsidian_path):
    """
    Runs an interactive morning planning session using local calendar data.
    """
    print("🌅 --- Morning Planning Session ---")
    tasks = get_unified_tasks(obsidian_path)

    calendar_agent = CalendarAgent()
    busy_slots = calendar_agent.get_busy_slots_from_yml()
    
    # Also add local ICS events to busy slots
    try:
        from local_calendar_agent import get_today_events
        local_events = get_today_events()
        for le in local_events:
            busy_slots.append({
                "summary": le["summary"],
                "start": le["start"],
                "end": le["end"]
            })
    except Exception:
        pass

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

            confirm = input("\nAdd these items to your local calendar and Markdown? (y/n/skip): ").strip().lower()
            if confirm == 'y':
                planning_agent = PlanningAgent()
                planning_agent.execute_plan(schedule, obsidian_path)
            else:
                print("Skipped scheduling.")
    else:
        print("Failed to generate schedule suggestion.")
    # Fire-and-forget n8n notification — safe if n8n is down
    try:
        import datetime as _dt
        from ai_orchestration import send_to_n8n
        send_to_n8n("morning-plan", {"plan_date": str(_dt.date.today())})
    except Exception:
        pass


def handle_planning_session(obsidian_path, dry_run=False):
    """
    Interactive planning session: fetch tasks + 7-day calendar, propose schedule,
    confirm per-task, then book confirmed items to Google Calendar.
    Safe to run non-interactively (cron, systemd): prints schedule to stdout and exits.
    """
    is_interactive = sys.stdin.isatty()

    # 1. Get tasks
    tasks = get_unified_tasks(obsidian_path)
    if not tasks:
        if is_interactive:
            print("ℹ️  No tasks found in backlog.")
        return

    # 2. Fetch busy slots from YAML cache and local ICS
    busy_slots = []
    calendar_agent = CalendarAgent()
    busy_slots.extend(calendar_agent.get_busy_slots_from_yml())
    
    try:
        from local_calendar_agent import list_events
        today = datetime.date.today()
        local_events = list_events(start_date=today, end_date=today + datetime.timedelta(days=7))
        for le in local_events:
            busy_slots.append({
                "summary": le["summary"],
                "start": le["start"],
                "end": le["end"]
            })
    except Exception:
        pass
        print("ℹ️  Google Calendar disabled — planning without busy-slot data.")

    # 3. Generate schedule via LLM
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

    # 4. Per-task confirmation
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

    # 5. Book confirmed items to local calendar
    if confirmed:
        try:
            from local_calendar_agent import add_event
            import datetime
            for item in confirmed:
                # Basic parsing of the ISO start/end if they are strings
                # local_calendar_agent.add_event expects datetime objects
                start_dt = datetime.datetime.fromisoformat(item['start'].replace('Z', '+00:00'))
                end_dt = datetime.datetime.fromisoformat(item['end'].replace('Z', '+00:00'))
                add_event(item['task'], start_dt, end_dt)
            print(f"\n✅ Booked {len(confirmed)} event(s) to local calendar (datainput/local_calendar.ics).")
            print("    n8n will sync these to Google Calendar if configured.")
        except Exception as e:
            print(f"\n❌ Error booking to local calendar: {e}")
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
    # Fire-and-forget n8n notification — safe if n8n is down
    try:
        from ai_orchestration import send_to_n8n
        send_to_n8n("logseq-synced", {"tasks_synced": synced, "tasks_skipped": skipped})
    except Exception:
        pass
    return synced, skipped, target_path


def handle_universal_sync():
    """Collect local tasks + ICS calendar events and trigger n8n Universal Task Sync."""
    from n8n_client import trigger_task_sync, is_n8n_running
    from config_utils import get_config_value

    if not is_n8n_running():
        print("[yellow]n8n is not running. Start it with: docker compose up -d[/yellow]")
        return

    workspace = get_config_value("WORKSPACE_DIR", "")
    from task_utils import get_unified_tasks
    raw_tasks = get_unified_tasks(workspace)
    tasks = [
        {
            "title": t.get("title", t.get("task", t.get("text", ""))).strip(),
            "source": t.get("source", "local"),
            "due": t.get("due") or t.get("due_date"),
        }
        for t in raw_tasks
        if t.get("title") or t.get("task") or t.get("text")
    ]

    events = []
    try:
        from local_calendar_agent import list_events
        import datetime
        today = datetime.date.today()
        events = list_events(start_date=today, end_date=today + datetime.timedelta(days=7))
    except (ImportError, Exception):
        pass  # ICS agent not yet available — send tasks only

    ok = trigger_task_sync(tasks, events)
    if ok:
        print(f"[green]Universal Task Sync triggered — {len(tasks)} tasks, {len(events)} events sent to n8n[/green]")
    else:
        print("[red]Universal Task Sync failed — check that n8n is running and the task-sync webhook is active[/red]")


def handle_google_tasks():
    """Pull tasks from Google Tasks → Obsidian; push done tasks back."""
    from config_utils import get_config_value
    if get_config_value("ENABLE_GOOGLE_TASKS", "false").lower() != "true":
        print("⚠️   Google Tasks is disabled. Set ENABLE_GOOGLE_TASKS=true in .config")
        return
    try:
        import google_tasks_agent
        result = google_tasks_agent.run(sync_back=True)
        pulled = result.get("pulled", 0) if result else 0
        pushed = result.get("pushed", 0) if result else 0
        print(f"✅ Pulled {pulled} new tasks, marked {pushed} complete in Google Tasks")
    except Exception as e:
        print(f"❌ Google Tasks sync failed: {e}")


def handle_add_event():
    """Interactive prompt to add an event to the local ICS calendar and optionally Apple Calendar."""
    from local_calendar_agent import add_event
    import apple_calendar
    import datetime
    print("Add calendar event")
    summary = input("  Event name: ").strip()
    if not summary:
        print("Cancelled.")
        return
    date_str = input("  Date (YYYY-MM-DD): ").strip()
    start_str = input("  Start time (HH:MM): ").strip()
    end_str   = input("  End time   (HH:MM): ").strip()
    desc      = input("  Description (optional): ").strip() or None
    try:
        date = datetime.date.fromisoformat(date_str)
        start_dt = datetime.datetime.combine(date, datetime.time.fromisoformat(start_str))
        end_dt   = datetime.datetime.combine(date, datetime.time.fromisoformat(end_str))
    except ValueError as e:
        print(f"❌ Invalid date/time: {e}")
        return

    # 1. Always write to local ICS
    try:
        uid = add_event(summary, start_dt, end_dt, description=desc)
        print(f"✅ Added to local calendar (uid: {uid[:8]}…): {summary} on {date_str} {start_str}–{end_str}")
    except Exception as e:
        print(f"❌ Failed to add to local ICS: {e}")
        return

    # 2. Optionally push to Apple Calendar (macOS only)
    if apple_calendar.is_available():
        cal_name = get_config_value("APPLE_CALENDAR_NAME", "Home")
        cals = apple_calendar.list_calendars()
        if cals:
            # Deduplicate while preserving order
            seen = set()
            unique_cals = [c for c in cals if not (c in seen or seen.add(c))]
            print(f"  Available calendars: {', '.join(unique_cals)}")
        push = input(f"  Also add to Apple Calendar '{cal_name}'? (y/n): ").strip().lower()
        if push == "y":
            ok = apple_calendar.add_event(summary, start_dt, end_dt, description=desc)
            if ok:
                print(f"✅ Added to Apple Calendar '{cal_name}'.")
            else:
                print(f"⚠  Apple Calendar push failed — event is still saved in local ICS.")


def handle_remove_event():
    """List upcoming events and prompt user to remove one by index."""
    from local_calendar_agent import list_events, remove_event
    import datetime
    today = datetime.date.today()
    events = list_events(start_date=today, end_date=today + datetime.timedelta(days=30))
    if not events:
        print("No upcoming events in the next 30 days.")
        return
    print("Upcoming events:")
    for i, ev in enumerate(events):
        print(f"  [{i}] {ev['start'][:10]}  {ev['summary']}")
    choice = input("  Enter number to remove (or Enter to cancel): ").strip()
    if not choice:
        print("Cancelled.")
        return
    try:
        ev = events[int(choice)]
        removed = remove_event(uid=ev["uid"])
        print(f"✅ Removed: {ev['summary']}")
    except (ValueError, IndexError) as e:
        print(f"❌ Invalid selection: {e}")


def handle_export_calendar(args=None):
    from local_calendar_agent import export_calendar, list_events
    import datetime
    dest = args[0] if args else None
    try:
        path = export_calendar(dest)
        count = len(list_events(datetime.date(2000, 1, 1), datetime.date(2099, 12, 31)))
        print(f"✅ Exported {count} events to {path}")
    except Exception as e:
        print(f"❌ Export failed: {e}")


def handle_import_calendar(args=None):
    from local_calendar_agent import import_calendar
    if not args:
        src = input("  Path to .ics file: ").strip()
    else:
        src = args[0]
    if not src:
        print("Cancelled.")
        return
    try:
        imported, skipped = import_calendar(src)
        print(f"✅ Imported {imported} new events ({skipped} duplicates skipped)")
    except Exception as e:
        print(f"❌ Import failed: {e}")


def handle_chat_mode(obsidian_file):
    """
    Starts an interactive CLI chat loop with slash commands and Rich UI.
    """
    import chat_ui

    obsidian_path = get_config_value("WORKSPACE_DIR", ".")
    logseq_path = get_config_value("LOGSEQ_DIR", None)

    chat_ui.print_banner()
    chat_ui.print_startup_status()

    history = chat_ui.load_history()

    # Auto-sync LogSeq → Obsidian on startup if configured
    if get_config_value("AUTO_SYNC_LOGSEQ", "false").lower() == "true":
        chat_ui.render_info("AUTO_SYNC_LOGSEQ enabled — syncing LogSeq tasks on startup...")
        sync_logseq_to_obsidian()

    get_input = chat_ui.make_input_fn()

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
                args = parts[1:]

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
                    busy_slots = []
                    service = None
                    if is_google_calendar_enabled():
                        service = calendar_manager.get_calendar_service()
                        if not service:
                            chat_ui.render_error("ENABLE_GOOGLE_CALENDAR=true but calendar service unavailable.")
                            continue
                        calendar_agent = CalendarAgent()
                        busy_slots = calendar_agent.get_busy_slots_from_yml()
                    logseq_path = get_config_value("LOGSEQ_DIR", None)
                    schedule = ai_orchestration.generate_schedule(
                        tasks, busy_slots,
                        workspace_dir=obsidian_path, logseq_dir=logseq_path
                    )
                    if is_google_calendar_enabled() and service:
                        confirm_sync = input("Sync to calendar? (y/n): ").strip().lower()
                        if confirm_sync == 'y':
                            calendar_id = get_config_value("CALENDAR_ID", "primary")
                            planning_agent = PlanningAgent(service, calendar_id)
                            planning_agent.execute_plan(schedule, obsidian_path)
                            chat_ui.render_success("Scheduled!")
                        else:
                            chat_ui.render_info("Sync cancelled.")
                    else:
                        chat_ui.render_info("Schedule generated (Google Calendar disabled — set ENABLE_GOOGLE_CALENDAR=true to book).")
                elif command == "pull":
                    if is_google_calendar_enabled():
                        sync_calendar_to_markdown(obsidian_path)
                    else:
                        chat_ui.render_info("Google Calendar is disabled. Set ENABLE_GOOGLE_CALENDAR=true in .config to pull events.")
                elif command == "stats":
                    print("\n--- Today's Focus Stats ---")
                    if not is_google_calendar_enabled():
                        chat_ui.render_info("Google Calendar is disabled — no stats available. Set ENABLE_GOOGLE_CALENDAR=true in .config.")
                    else:
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
                    from session import display_docs
                    display_docs()
                elif command == "services":
                    from config_utils import get_config_value as _gcv
                    lms_up = ai_orchestration.is_lmstudio_running() if _gcv("ENABLE_LM_STUDIO", "false").lower() == "true" else None
                    ollama_up = ai_orchestration.is_ollama_running() if _gcv("ENABLE_OLLAMA", "true").lower() == "true" else None
                    chat_ui.render_services(lmstudio_status=lms_up, ollama_status=ollama_up)
                elif command == "models":
                    from rich.table import Table
                    from rich.console import Console as _Console
                    _con = _Console()
                    tbl = Table(title="Active LLM Providers", show_header=True, header_style="bold cyan")
                    tbl.add_column("Provider", style="bold")
                    tbl.add_column("Enabled")
                    tbl.add_column("Model")
                    tbl.add_column("Status")

                    # LM Studio
                    lms_enabled = get_config_value("ENABLE_LM_STUDIO", "false").lower() == "true"
                    lms_model = get_config_value("LM_STUDIO_MODEL", "—")
                    if lms_enabled:
                        lms_up = ai_orchestration.is_lmstudio_running()
                        lms_status = "✅ running" if lms_up else "❌ not running"
                    else:
                        lms_status = "—"
                    tbl.add_row("LM Studio", "✅" if lms_enabled else "❌", lms_model if lms_enabled else "—", lms_status)

                    # Ollama
                    ollama_enabled = get_config_value("ENABLE_OLLAMA", "true").lower() == "true"
                    ollama_model = get_config_value("OLLAMA_MODEL", "llama3")
                    if ollama_enabled:
                        ollama_up = ai_orchestration.is_ollama_running()
                        ollama_models = ai_orchestration.list_ollama_models()
                        ollama_status = f"✅ running ({len(ollama_models)} models)" if ollama_up else "❌ not running"
                    else:
                        ollama_status = "—"
                    tbl.add_row("Ollama", "✅" if ollama_enabled else "❌", ollama_model if ollama_enabled else "—", ollama_status)

                    # Gemini
                    gemini_enabled = get_config_value("ENABLE_GEMINI", "false").lower() == "true"
                    gemini_key = get_config_value("GEMINI_API_KEY", "")
                    gemini_ok = bool(gemini_key) and "your_" not in gemini_key
                    tbl.add_row("Gemini", "✅" if gemini_enabled else "❌",
                                get_config_value("GEMINI_MODEL", "gemini-2.0-flash") if gemini_enabled else "—",
                                ("✅ key present" if gemini_ok else "❌ no key") if gemini_enabled else "—")

                    # OpenAI
                    openai_enabled = get_config_value("ENABLE_OPENAI", "false").lower() == "true"
                    tbl.add_row("OpenAI", "✅" if openai_enabled else "❌",
                                get_config_value("OPENAI_MODEL", "gpt-4o") if openai_enabled else "—", "—")

                    priority = get_config_value("LLM_PRIORITY", "lmstudio,ollama,gemini,openai,claude")
                    _con.print(tbl)
                    _con.print(f"[dim]Fallback order: {priority}[/dim]")
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
                elif command == "ask":
                    # /ask <provider> <query...>
                    # e.g. /ask gemini find tasks about academic papers in obsidian
                    known_providers = list(ai_orchestration.MODELS_ENABLED.keys())
                    if len(parts) < 3:
                        chat_ui.render_info(
                            f"Usage: /ask <provider> <query>\n"
                            f"  Providers: {', '.join(known_providers)}\n"
                            f"  Example: /ask gemini find tasks in obsidian about academic papers"
                        )
                    else:
                        provider = parts[1].lower()
                        # Accept aliases: "lm-studio" → "lmstudio", "gpt" → "openai"
                        _aliases = {"lm-studio": "lmstudio", "lm_studio": "lmstudio",
                                    "gpt": "openai", "gpt4": "openai", "gpt-4": "openai",
                                    "anthropic": "claude"}
                        provider = _aliases.get(provider, provider)
                        if provider not in known_providers:
                            chat_ui.render_warning(
                                f"Unknown provider '{provider}'. Available: {', '.join(known_providers)}"
                            )
                        else:
                            query = " ".join(parts[2:])
                            # Pull file context the same way the main chat loop does
                            file_context = ai_orchestration._get_file_context(query)
                            augmented = f"{query}\n\n{file_context}" if file_context else query
                            chat_ui.render_info(f"Sending to {provider}...")
                            response, model_used = ai_orchestration.generate_with(provider, augmented)
                            if response.startswith("LLM error:"):
                                # Parse quota / auth errors into a readable one-liner
                                err = response[len("LLM error:"):].strip()
                                if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
                                    chat_ui.render_warning(
                                        f"{model_used}: rate-limit / quota exceeded. "
                                        f"Try again in a moment, switch provider with /ask lmstudio <query>, "
                                        f"or upgrade your API plan."
                                    )
                                elif "401" in err or "API_KEY" in err or "authentication" in err.lower():
                                    chat_ui.render_warning(f"{model_used}: invalid or missing API key.")
                                else:
                                    # Truncate long error blobs to first line
                                    short = err.splitlines()[0][:200]
                                    chat_ui.render_warning(f"{model_used} error: {short}")
                            else:
                                chat_ui.render_response(response, model_used)
                elif command == "routing":
                    # Build list of available providers/models to route to
                    available_targets = []
                    lms_enabled = get_config_value("ENABLE_LM_STUDIO", "false").lower() == "true"
                    if lms_enabled:
                        lms_model = get_config_value("LM_STUDIO_MODEL", "")
                        available_targets.append(f"lmstudio ({lms_model})" if lms_model else "lmstudio")
                    ollama_models = ai_orchestration.list_ollama_models()
                    for m in ollama_models:
                        available_targets.append(m)
                    for provider in ["gemini", "openai", "claude"]:
                        key = f"ENABLE_{provider.upper()}"
                        if get_config_value(key, "false").lower() == "true":
                            available_targets.append(provider)

                    task_types = ["chat", "scheduling", "parsing", "planning"]
                    print("\n--- Current Routing ---")
                    for i, tt in enumerate(task_types, 1):
                        current = get_config_value(f"ROUTING_{tt.upper()}", "lmstudio")
                        print(f"  {i}. {tt:<12} → {current}")
                    if available_targets:
                        print("\n--- Available Targets ---")
                        for j, t in enumerate(available_targets, 1):
                            print(f"  {j}. {t}")
                        try:
                            route_choice = input(f"\nChange routing for which task type? (1-{len(task_types)}, Enter=skip): ").strip()
                            if route_choice.isdigit() and 1 <= int(route_choice) <= len(task_types):
                                tt = task_types[int(route_choice) - 1]
                                model_choice = input(f"Select target number for {tt} (or type a name): ").strip()
                                if model_choice.isdigit() and 1 <= int(model_choice) <= len(available_targets):
                                    selected = available_targets[int(model_choice) - 1].split(" ")[0]  # strip "(model)" annotation
                                    _update_config_key(config_path, f"ROUTING_{tt.upper()}", selected)
                                    chat_ui.render_success(f"Routing for {tt} → {selected}. Effective immediately.")
                                elif model_choice:
                                    _update_config_key(config_path, f"ROUTING_{tt.upper()}", model_choice)
                                    chat_ui.render_success(f"Routing for {tt} → {model_choice}. Effective immediately.")
                        except (EOFError, KeyboardInterrupt):
                            pass
                    else:
                        chat_ui.render_warning("No enabled providers found. Check ENABLE_LM_STUDIO / ENABLE_OLLAMA / ENABLE_GEMINI in .config")
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
                    import datainput_agent
                    import datetime as _dt
                    chat_ui.render_info("Scanning planner for overdue tasks and reorganising by category...")
                    # Pre-show overdue count before calling LLM
                    planner_content = datainput_agent._read_planner(datainput_agent._planner_path())
                    if not planner_content.strip():
                        chat_ui.render_warning("Planner is empty — nothing to organise.")
                        continue
                    overdue = datainput_agent._find_overdue_tasks(planner_content)
                    if overdue:
                        chat_ui.render_warning(f"{len(overdue)} overdue task(s) found — will be moved to 🚨 Overdue section:")
                        for line, due in overdue[:10]:
                            print(f"    {line[:80]}  (was due {due})")
                        if len(overdue) > 10:
                            print(f"    ... and {len(overdue) - 10} more")
                    else:
                        chat_ui.render_info("No overdue tasks detected.")
                    result = datainput_agent.organise_planner()
                    if result and not result.startswith("LLM error"):
                        chat_ui.render_success("Planner reorganised. Open Obsidian to review.")
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
                elif command == "sync-universal":
                    handle_universal_sync()
                elif command == "status":
                    subprocess.run([sys.executable, "scripts/status.py"])
                elif command == "today":
                    from terminal_views import handle_today_view
                    handle_today_view()
                elif command == "week":
                    from terminal_views import handle_week_view
                    handle_week_view()
                elif command == "plan":
                    from terminal_views import handle_plan_view
                    handle_plan_view(args[0] if args else None)
                elif command == "cal":
                    from terminal_views import handle_cal_view
                    month = args[0] if args else None
                    year = args[1] if len(args) > 1 else None
                    handle_cal_view(month=month, year=year)
                elif command == "cal-day":
                    from terminal_views import handle_cal_day_view
                    if args:
                        handle_cal_day_view(args[0])
                    else:
                        import datetime
                        handle_cal_day_view(datetime.date.today().isoformat())
                elif command == "add-event":
                    handle_add_event()
                elif command == "remove-event":
                    handle_remove_event()
                elif command == "export-calendar":
                    handle_export_calendar(args)
                elif command == "import-calendar":
                    handle_import_calendar(args)
                elif command == "google-tasks":
                    handle_google_tasks()
                elif command == "reschedule":
                    # /reschedule <target date> [--dry-run] [--logseq-only] [--obsidian-only]
                    # e.g. /reschedule end of next week
                    #      /reschedule next monday --dry-run
                    if len(parts) < 2:
                        chat_ui.render_info(
                            "Usage: /reschedule <target date> [--dry-run] [--logseq-only] [--obsidian-only]\n"
                            '  Examples: /reschedule "end of next week"\n'
                            "            /reschedule next monday --dry-run\n"
                            "            /reschedule friday --obsidian-only"
                        )
                    else:
                        flags = {p.lstrip("-").replace("-", "_") for p in parts if p.startswith("--")}
                        date_parts = [p for p in parts[1:] if not p.startswith("--")]
                        target = " ".join(date_parts)
                        dry_run = "dry_run" in flags
                        logseq_only = "logseq_only" in flags
                        obsidian_only = "obsidian_only" in flags
                        result = task_reschedule_agent.run(
                            target=target,
                            dry_run=dry_run,
                            logseq=not obsidian_only,
                            obsidian=not logseq_only,
                        )
                        if result:
                            action = "Would move" if dry_run else "Moved"
                            chat_ui.render_success(
                                f"{action} {result['logseq_moved'] + result['obsidian_moved']} overdue task(s) "
                                f"to {result['target_date']} "
                                f"(LogSeq: {result['logseq_moved']}, Obsidian: {result['obsidian_moved']})"
                            )
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
