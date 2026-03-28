#!/usr/bin/env python3
"""
scripts/remind.py — Schedule a one-off reminder with three delivery channels.

Usage:
    python scripts/remind.py "Task text" "HH:MM"

Delivery channels (each fails gracefully; nothing fatal):
    A) macOS notification via `at` + `osascript`  (macOS only)
    B) Log entry in logs/reminders.log             (always)
    C) n8n webhook if N8N_WEBHOOK_URL is configured
"""
import os
import sys
import datetime
import platform
import subprocess

# Allow importing project modules when run as a standalone script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _log_reminder(task: str, remind_time: str, now_str: str, log_path: str) -> bool:
    """Append a line to logs/reminders.log.  Returns True on success."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
        today = datetime.date.today().isoformat()
        line = f"{today} {remind_time} | SCHEDULED | {task} | set at {now_str}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
        return True
    except Exception as e:
        print(f"   [warn] Could not write to {log_path}: {e}")
        return False


def _schedule_macos_notification(task: str, remind_time: str) -> bool:
    """
    Schedule a macOS notification using `at` + `osascript`.

    Requires the `at` daemon to be enabled:
        sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.atrun.plist

    Returns True if the `at` command accepted the job.
    """
    if platform.system() != "Darwin":
        return False
    try:
        # Escape single quotes in task text so the osascript string is safe
        safe_task = task.replace("'", "\\'")
        osa_cmd = f"osascript -e 'display notification \"{safe_task}\" with title \"Reminder\"'"
        at_input = f"{osa_cmd}\n"
        result = subprocess.run(
            f"echo '{osa_cmd}' | at {remind_time}",
            shell=True,
            capture_output=True,
            text=True,
        )
        # `at` exits 0 on success; non-zero or stderr containing "error" means failure
        if result.returncode != 0 or ("error" in result.stderr.lower() and "warning" not in result.stderr.lower()):
            return False
        return True
    except Exception:
        return False


def _send_n8n_webhook(task: str, remind_time: str, now_str: str) -> bool:
    """Send a webhook event to n8n if N8N_WEBHOOK_URL is set.  Returns True on success."""
    try:
        from config_utils import get_config_value
        webhook_url = get_config_value("N8N_WEBHOOK_URL", None)
        if not webhook_url:
            return False
        from n8n_client import trigger
        return trigger("reminder-set", {
            "task": task,
            "remind_at": remind_time,
            "set_at": now_str,
        })
    except Exception:
        return False


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/remind.py \"Task text\" \"HH:MM\"")
        sys.exit(1)

    task = sys.argv[1].strip()
    remind_time = sys.argv[2].strip()

    # Basic validation of time format
    try:
        datetime.datetime.strptime(remind_time, "%H:%M")
    except ValueError:
        print(f"Error: time must be in HH:MM format, got: {remind_time!r}")
        sys.exit(1)

    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M")

    log_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "logs", "reminders.log"
    )

    print(f"Reminder set: \"{task}\" at {remind_time}")

    # Channel B — log (always runs first so there is always a record)
    logged = _log_reminder(task, remind_time, now_str, log_path)
    if logged:
        print(f"   Logged to logs/reminders.log")

    # Channel C — n8n webhook
    sent_n8n = _send_n8n_webhook(task, remind_time, now_str)
    if sent_n8n:
        print(f"   Sent to n8n")

    # Channel A — macOS notification
    notified = _schedule_macos_notification(task, remind_time)
    if notified:
        print(f"   macOS notification scheduled")


if __name__ == "__main__":
    main()
