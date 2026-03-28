"""
Cron Job Orchestrator

Runs all agents in sequence. Designed to be called by cron every hour,
or triggered via n8n webhook.

Safety features:
  - Lockfile prevents concurrent runs (stale locks auto-expire after MAX_RUN_SECONDS).
  - Global timeout kills the process if it hangs.

Agents run in this order:
  1. DataInput Agent   — sync Apple Reminders → Obsidian planner, then organise
  2. LogSeq LATER Agent — scan journals + pages, write summary to Obsidian
  3. Calendar Planning Agent — Gemini analyses calendar + tasks, saves weekly plan
  4. (Legacy) Google Calendar ↔ Markdown sync via AI scheduler

Usage:
  python cron_job.py             # run all agents
  python cron_job.py --agents datainput logseq  # run specific agents only
"""

import os
import sys
import signal
import datetime
import argparse
import atexit
import subprocess

from config_utils import get_config_value

# ---------------------------------------------------------------------------
# Safety: global timeout and lockfile
# ---------------------------------------------------------------------------

MAX_RUN_SECONDS = 300  # 5 minutes — hard kill if exceeded
LOCKFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cron_job.lock")


def _timeout_handler(signum, frame):
    print(f"\n[TIMEOUT] cron_job.py exceeded {MAX_RUN_SECONDS}s — terminating.")
    _release_lock()
    sys.exit(1)


def _acquire_lock():
    """Create a lockfile with our PID. Abort if another instance is running."""
    if os.path.exists(LOCKFILE):
        try:
            with open(LOCKFILE, "r") as f:
                old_pid = int(f.read().strip())
            # Check if old process is still alive
            os.kill(old_pid, 0)
            # Process exists — check if the lock is stale (older than MAX_RUN_SECONDS)
            lock_age = datetime.datetime.now().timestamp() - os.path.getmtime(LOCKFILE)
            if lock_age > MAX_RUN_SECONDS:
                print(f"[LOCK] Stale lock from PID {old_pid} ({lock_age:.0f}s old) — removing.")
                try:
                    os.kill(old_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            else:
                print(f"[LOCK] Another cron_job.py is running (PID {old_pid}) — aborting.")
                sys.exit(0)
        except (ProcessLookupError, ValueError, OSError):
            # Old process is gone — lock is stale
            pass

    with open(LOCKFILE, "w") as f:
        f.write(str(os.getpid()))


def _release_lock():
    try:
        if os.path.exists(LOCKFILE):
            with open(LOCKFILE, "r") as f:
                pid = int(f.read().strip())
            if pid == os.getpid():
                os.remove(LOCKFILE)
    except Exception:
        pass


# Register cleanup
atexit.register(_release_lock)
signal.signal(signal.SIGALRM, _timeout_handler)


def _ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_datainput_agent():
    print(f"\n[{_ts()}] === DataInput Agent ===")
    try:
        import datainput_agent
        result = datainput_agent.run(organise=True)
        print(f"  New reminders synced: {len(result['new_tasks'])}")
        print(f"  Planner organised:    {result['organised']}")
        return result
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def run_logseq_later_agent():
    print(f"\n[{_ts()}] === LogSeq LATER Agent ===")
    try:
        import logseq_later_agent
        tasks = logseq_later_agent.run(write_to_obsidian=True)
        print(f"  LATER tasks found: {len(tasks)}")
        return tasks
    except Exception as e:
        print(f"  ERROR: {e}")
        return []


def run_calendar_planning_agent():
    print(f"\n[{_ts()}] === Calendar Planning Agent (Gemini) ===")
    gemini_enabled = get_config_value("ENABLE_GEMINI", "false").lower() == "true"
    if not gemini_enabled:
        print("  Skipped — ENABLE_GEMINI=false in .config")
        return None
    try:
        import calendar_planning_agent
        result = calendar_planning_agent.run(write_to_obsidian=False)
        if result:
            print("  Plan generated — see datainput/calendar_suggestions.md")
        return result
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def run_legacy_calendar_sync():
    """
    Original cron logic: generate AI schedule and sync to Google Calendar.
    Kept as optional step — only runs if CALENDAR_SYNC=true in .config.
    """
    if get_config_value("CALENDAR_SYNC", "false").lower() != "true":
        return

    print(f"\n[{_ts()}] === Legacy Calendar Sync ===")
    try:
        import main as app
        import calendar_manager
        import ai_orchestration

        obsidian_path = get_config_value("WORKSPACE_DIR", ".")
        calendar_id   = get_config_value("CALENDAR_ID", "primary")

        tasks = app.get_unified_tasks(obsidian_path)
        if not tasks:
            print("  No tasks found.")
            return

        service = calendar_manager.get_calendar_service()
        if not service:
            print("  Google Calendar service unavailable.")
            return

        busy_slots = calendar_manager.get_busy_slots(service, calendar_ids=[calendar_id])
        logseq_dir = get_config_value("LOGSEQ_DIR", None)

        schedule = ai_orchestration.generate_schedule(
            tasks, busy_slots,
            workspace_dir=obsidian_path,
            logseq_dir=logseq_dir
        )

        if schedule:
            calendar_manager.create_events(service, schedule, calendar_id=calendar_id)
            target_file = os.path.join(obsidian_path, "daily_note.md")
            if os.path.isdir(obsidian_path) and os.path.exists(target_file):
                from observer import update_markdown_plan
                update_markdown_plan(target_file, schedule)
            print("  Calendar sync complete.")
        else:
            print("  Failed to generate schedule.")

    except Exception as e:
        print(f"  ERROR: {e}")


def run_health_checks():
    print(f"\n[{_ts()}] === Health Checks ===")
    try:
        import update_manager
        update_manager.run_all_checks()
    except Exception as e:
        print(f"  ERROR: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

AGENT_MAP = {
    "datainput":   run_datainput_agent,
    "logseq":      run_logseq_later_agent,
    "calendar":    run_calendar_planning_agent,
    "legacy_sync": run_legacy_calendar_sync,
    "health":      run_health_checks,
}

ALL_AGENTS = ["datainput", "logseq", "calendar", "legacy_sync", "health"]


def main():
    # Prevent concurrent runs and enforce hard timeout
    _acquire_lock()
    signal.alarm(MAX_RUN_SECONDS)

    parser = argparse.ArgumentParser(description="AI Agent Assistant — Cron Orchestrator")
    parser.add_argument(
        "--agents", nargs="*",
        help=f"Run specific agents. Choices: {', '.join(AGENT_MAP.keys())}. Default: all."
    )
    args = parser.parse_args()

    agents_to_run = args.agents if args.agents else ALL_AGENTS

    print(f"\n{'='*60}")
    print(f"Cron Sync Started at {_ts()} (PID {os.getpid()}, timeout {MAX_RUN_SECONDS}s)")
    print(f"Agents: {', '.join(agents_to_run)}")
    print(f"{'='*60}")

    results = {}
    for name in agents_to_run:
        fn = AGENT_MAP.get(name)
        if fn:
            results[name] = fn()
        else:
            print(f"  Unknown agent: {name}")

    print(f"\n[{_ts()}] Cron Sync Complete.")

    # Rotate logs — archive entries older than 7 days
    rotate_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "rotate_logs.sh")
    if os.path.exists(rotate_script):
        subprocess.run(["bash", rotate_script], capture_output=True)

    return results


if __name__ == "__main__":
    main()
