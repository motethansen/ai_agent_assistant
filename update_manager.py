import os
import re
import subprocess
import json
import datetime
import time
import requests
from config_utils import get_config_value

def check_git_updates():
    """Checks if there are updates available in the git repository."""
    if not os.path.exists(".git"):
        return {"status": "error", "message": "Not a git repository"}
    
    try:
        subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=10)
        local_hash = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        remote_hash = subprocess.check_output(["git", "rev-parse", "@{u}"]).decode().strip()
        
        if local_hash != remote_hash:
            return {"status": "update_available", "message": "New updates available"}
        else:
            return {"status": "up_to_date", "message": "System is up to date"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def check_ollama_health():
    """Checks if Ollama server is reachable."""
    host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
    try:
        response = requests.get(f"{host}/api/tags", timeout=3)
        if response.status_code == 200:
            return {"status": "ok", "message": "Ollama is running"}
        else:
            return {"status": "error", "message": f"Ollama returned {response.status_code}"}
    except Exception:
        return {"status": "error", "message": "Ollama is not reachable"}

def check_venv_health():
    """Checks if the virtual environment is healthy (basic check)."""
    if not os.path.exists(".venv"):
        return {"status": "error", "message": ".venv missing"}
    return {"status": "ok", "message": "Environment looks good"}

def check_gemini():
    """GEMINI_API_KEY present in .config and non-empty."""
    key = get_config_value("GEMINI_API_KEY", "")
    if key:
        return {"status": "ok", "message": "Key present"}
    return {"status": "warning", "message": "GEMINI_API_KEY not set in .config"}


def check_lm_studio():
    """LM Studio local server reachable at http://localhost:1234. Skipped if ENABLE_LM_STUDIO=false."""
    enabled = get_config_value("ENABLE_LM_STUDIO", "false").lower() == "true"
    if not enabled:
        return {"status": "disabled", "message": "LM Studio disabled (ENABLE_LM_STUDIO=false)"}
    try:
        response = requests.get("http://localhost:1234/v1/models", timeout=3)
        if response.status_code == 200:
            data = response.json()
            models = [m.get("id", "") for m in data.get("data", [])]
            active = get_config_value("LM_STUDIO_MODEL", models[0] if models else "unknown")
            return {
                "status": "ok",
                "message": f"LM Studio running, active model: {active}",
                "active_model": active,
                "available_models": models,
            }
        return {"status": "error", "message": f"LM Studio returned {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"LM Studio is not reachable: {e}"}


def check_local_calendar():
    """Local ICS calendar file exists and is readable."""
    ics_path = get_config_value("LOCAL_CALENDAR_FILE", "datainput/local_calendar.ics")
    if not os.path.exists(ics_path):
        return {"status": "missing", "message": f"No local calendar at {ics_path} — run /add-event to create it"}
    try:
        age_hours = (time.time() - os.path.getmtime(ics_path)) / 3600
        size = os.path.getsize(ics_path)
        return {"status": "ok", "message": f"ICS file: {size} bytes, last modified {age_hours:.1f}h ago"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_google_calendar():
    """Local ICS calendar check (Google Calendar replaced by local ICS)."""
    return check_local_calendar()


def check_logseq_dir():
    """LOGSEQ_DIR from config exists and is a directory."""
    logseq_dir = get_config_value("LOGSEQ_DIR", "")
    if not logseq_dir:
        return {"status": "error", "message": "LOGSEQ_DIR not set in .config"}
    if os.path.isdir(logseq_dir):
        return {"status": "ok", "message": logseq_dir}
    return {"status": "error", "message": f"Directory not found: {logseq_dir}"}


def check_obsidian_vault():
    """WORKSPACE_DIR from config exists and is a directory."""
    workspace_dir = get_config_value("WORKSPACE_DIR", "")
    if not workspace_dir:
        return {"status": "error", "message": "WORKSPACE_DIR not set in .config"}
    if os.path.isdir(workspace_dir):
        return {"status": "ok", "message": workspace_dir}
    return {"status": "error", "message": f"Directory not found: {workspace_dir}"}


def check_cron_last_run():
    """Parse last timestamp from logs/cron_sync.log. warning if >25h ago, error if log missing."""
    log_path = os.path.join("logs", "cron_sync.log")
    if not os.path.exists(log_path):
        return {"status": "error", "message": "logs/cron_sync.log missing"}
    # Match lines like: "Cron Sync Started at 2026-03-20 11:00:01"
    # or "[2026-03-20 11:01:31] Cron Sync Complete."
    ts_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')
    last_ts = None
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = ts_pattern.search(line)
                if m:
                    try:
                        ts = datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                        if last_ts is None or ts > last_ts:
                            last_ts = ts
                    except ValueError:
                        pass
    except Exception as e:
        return {"status": "error", "message": f"Could not read log: {e}"}
    if last_ts is None:
        return {"status": "warning", "message": "No timestamps found in cron_sync.log"}
    age_hours = (datetime.datetime.now() - last_ts).total_seconds() / 3600
    if age_hours > 25:
        return {"status": "warning", "message": f"Last run {age_hours:.1f}h ago", "age_hours": round(age_hours, 2)}
    age_mins = int(age_hours * 60)
    if age_mins < 60:
        return {"status": "ok", "message": f"{age_mins} min ago", "age_hours": round(age_hours, 2)}
    return {"status": "ok", "message": f"{age_hours:.1f}h ago", "age_hours": round(age_hours, 2)}


def check_reminders_sync():
    """Age of datainput/reminders.json in hours. warning if >48h, error if missing."""
    path = os.path.join("datainput", "reminders.json")
    if not os.path.exists(path):
        return {"status": "error", "message": "datainput/reminders.json missing"}
    age_hours = (datetime.datetime.now().timestamp() - os.path.getmtime(path)) / 3600
    if age_hours > 48:
        return {"status": "warning", "message": f"Last synced {age_hours:.0f}h ago", "age_hours": round(age_hours, 2)}
    return {"status": "ok", "message": f"Last synced {age_hours:.1f}h ago", "age_hours": round(age_hours, 2)}


def check_google_tasks():
    """Google Tasks sync status — disabled check if ENABLE_GOOGLE_TASKS=false."""
    enabled = get_config_value("ENABLE_GOOGLE_TASKS", "false").lower() == "true"
    if not enabled:
        return {"status": "disabled", "message": "ENABLE_GOOGLE_TASKS=false"}
    synced_file = "datainput/synced_google_tasks.json"
    if not os.path.exists(synced_file):
        return {"status": "not_run", "message": "synced_google_tasks.json not found — run /google-tasks"}
    age_hours = (time.time() - os.path.getmtime(synced_file)) / 3600
    try:
        with open(synced_file) as f:
            data = json.load(f)
        count = len(data)
        return {"status": "ok", "message": f"{count} tasks tracked, last sync {age_hours:.1f}h ago"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def run_all_checks():
    # Attempt to start services if they are down
    if os.path.exists("scripts/manage_services.sh"):
        subprocess.run(["bash", "scripts/manage_services.sh", "check"], capture_output=True)

    status = {
        "last_check": datetime.datetime.now().isoformat(),
        "git": check_git_updates(),
        "ollama": check_ollama_health(),
        "lm_studio": check_lm_studio(),
        "venv": check_venv_health(),
        "gemini": check_gemini(),
        "local_calendar": check_local_calendar(),
        "logseq_dir": check_logseq_dir(),
        "obsidian_vault": check_obsidian_vault(),
        "cron_last_run": check_cron_last_run(),
        "reminders_sync": check_reminders_sync(),
        "google_tasks": check_google_tasks(),
    }

    os.makedirs("logs", exist_ok=True)
    with open("logs/system_status.json", "w") as f:
        json.dump(status, f, indent=4)

    return status

if __name__ == "__main__":
    print(json.dumps(run_all_checks(), indent=4))
