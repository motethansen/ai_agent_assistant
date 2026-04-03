"""
google_tasks_agent.py — Google Tasks ↔ Obsidian two-way sync.

Pull: fetches incomplete tasks from Google Tasks list → appends to Obsidian
      planner under ## Google Tasks; deduplicates via datainput/synced_google_tasks.json
Push: scans Obsidian planner for - [x] done tasks matching synced tasks;
      marks them complete in Google Tasks; removes from tracking JSON.

Config keys:
    ENABLE_GOOGLE_TASKS   — false by default; skip all API calls if not true
    GOOGLE_TASKS_LIST     — @default (maps to "My Tasks"); or a list name
    WORKSPACE_DIR         — Obsidian vault path
    OBSIDIAN_PLANNER_FILE — planner filename (default: Planner.md)

Entry points:
    run(sync_back=False)  — pull tasks; if sync_back=True also push completions
"""

import os
import json
import datetime
import re
import logging
from config_utils import get_config_value

# GATE: ENABLE_GOOGLE_TASKS=false must short-circuit before any import of googleapiclient
# to avoid hard dependency when not configured
def _is_enabled():
    return get_config_value("ENABLE_GOOGLE_TASKS", "false").lower() == "true"

# Constants
DATAINPUT_DIR = os.path.join(os.path.dirname(__file__), "datainput")
SYNCED_FILE   = os.path.join(DATAINPUT_DIR, "synced_google_tasks.json")

# Scopes
# Note: existing token.json must be deleted and re-auth run to add this scope.
SCOPES = ['https://www.googleapis.com/auth/tasks']

def _get_service():
    """Builds Google Tasks API service using OAuth2."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google.auth.exceptions import RefreshError
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError:
        print("[GoogleTasksAgent] Missing google-api-python-client or google-auth-oauthlib.")
        return None

    creds = None
    # Use existing token.json if it exists
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                print("⚠️ Token has been expired or revoked. Re-authenticating...")
                creds = None
        
        if not creds or not creds.valid:
            if not os.path.exists('credentials.json'):
                print("[GoogleTasksAgent] 'credentials.json' not found.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

    try:
        service = build('tasks', 'v1', credentials=creds)
        return service
    except Exception as e:
        print(f"[GoogleTasksAgent] Error building service: {e}")
        return None

def get_task_lists():
    """Returns list of {id, title} dicts from the API."""
    service = _get_service()
    if not service:
        return []
    try:
        results = service.tasklists().list().execute()
        items = results.get('items', [])
        return [{"id": item['id'], "title": item['title']} for item in items]
    except Exception as e:
        print(f"[GoogleTasksAgent] Error fetching task lists: {e}")
        return []

def _resolve_list_id(list_name):
    """Maps GOOGLE_TASKS_LIST config value to a list_id."""
    lists = get_task_lists()
    if not lists:
        return None
    
    if not list_name or list_name == "@default":
        return lists[0]['id']
    
    for l in lists:
        if l['title'] == list_name:
            return l['id']
            
    return lists[0]['id']

def fetch_tasks(list_id):
    """Returns all non-completed tasks as [{id, title, due, notes}]."""
    service = _get_service()
    if not service or not list_id:
        return []
    try:
        results = service.tasks().list(tasklist=list_id, showCompleted=False).execute()
        items = results.get('items', [])
        return [
            {
                "id": item['id'],
                "title": item['title'],
                "due": item.get('due'),
                "notes": item.get('notes')
            }
            for item in items
        ]
    except Exception as e:
        print(f"[GoogleTasksAgent] Error fetching tasks: {e}")
        return []

def _load_synced():
    if not os.path.exists(SYNCED_FILE):
        return {}
    try:
        with open(SYNCED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_synced(synced):
    os.makedirs(DATAINPUT_DIR, exist_ok=True)
    with open(SYNCED_FILE, "w", encoding="utf-8") as f:
        json.dump(synced, f, indent=2)

def _planner_path():
    vault = get_config_value("WORKSPACE_DIR", ".")
    rel   = get_config_value("OBSIDIAN_PLANNER_FILE", "Planner.md")
    return os.path.join(vault, rel)

def sync_to_obsidian() -> int:
    """
    Add any unsynced Google Tasks to the planner file.
    Returns count of new tasks synced.
    """
    synced = _load_synced()
    list_name = get_config_value("GOOGLE_TASKS_LIST", "@default")
    list_id = _resolve_list_id(list_name)
    tasks = fetch_tasks(list_id)
    
    new_tasks = [t for t in tasks if t['id'] not in synced]
    if not new_tasks:
        return 0
    
    path = _planner_path()
    content = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
    # Ensure a "## Google Tasks" section exists
    if "## Google Tasks" not in content:
        content = content.rstrip() + "\n\n## Google Tasks\n"
        
    lines_to_add = []
    for t in new_tasks:
        line = f"- [ ] {t['title'].strip()}"
        if t['due']:
            due_date = t['due'].split('T')[0]
            line += f" 📅 {due_date}"
        lines_to_add.append(line)
        if t['notes']:
            lines_to_add.append(f"  - 📝 {t['notes'].strip()}")
            
    insert_marker = "## Google Tasks"
    idx = content.find(insert_marker)
    insert_pos = idx + len(insert_marker)
    while insert_pos < len(content) and content[insert_pos] == "\n":
        insert_pos += 1
        
    block = "\n".join(lines_to_add) + "\n"
    content = content[:insert_pos] + block + content[insert_pos:]
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        
    synced_date = datetime.datetime.now().isoformat()
    for t in new_tasks:
        synced[t['id']] = {
            "title": t['title'],
            "synced_date": synced_date
        }
    _save_synced(synced)
    
    return len(new_tasks)

def sync_completions_to_google() -> int:
    """
    Scan Obsidian planner for - [x] done tasks that match a synced Google Task.
    For each match: mark complete in Google Tasks, remove from tracking JSON.
    Returns count of tasks pushed. Logs errors per task but never raises.
    """
    enabled = get_config_value("ENABLE_GOOGLE_TASKS", "false").lower() == "true"
    if not enabled:
        return 0

    synced = _load_synced()
    if not synced:
        return 0

    workspace = get_config_value("WORKSPACE_DIR", "")
    planner_file = get_config_value("OBSIDIAN_PLANNER_FILE", "Planner.md")
    planner_path = os.path.join(workspace, planner_file)
    if not os.path.exists(planner_path):
        return 0

    with open(planner_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    done_titles = set()
    for line in lines:
        m = re.match(r"^\s*-\s+\[x\]\s+(.*)", line, re.IGNORECASE)
        if m:
            done_titles.add(m.group(1).strip().lower())

    try:
        service = _get_service()
        list_id = _resolve_list_id(get_config_value("GOOGLE_TASKS_LIST", "@default"))
    except Exception as e:
        logging.getLogger(__name__).error("sync_completions_to_google: auth failed: %s", e)
        return 0

    if not service or not list_id:
        return 0

    pushed = 0
    to_remove = []

    for task_id, info in synced.items():
        title_norm = info.get("title", "").strip().lower()
        if title_norm in done_titles:
            try:
                service.tasks().update(
                    tasklist=list_id,
                    task=task_id,
                    body={"id": task_id, "status": "completed"}
                ).execute()
                to_remove.append(task_id)
                pushed += 1
            except Exception as e:
                logging.getLogger(__name__).error(
                    "sync_completions_to_google: failed to update task %s: %s", task_id, e
                )

    for task_id in to_remove:
        del synced[task_id]
    _save_synced(synced)

    return pushed

def run(sync_back=False):
    """
    Run the full Google Tasks agent pipeline.
    Returns dict with pulled and pushed counts.
    """
    if not _is_enabled():
        return None
        
    pulled = sync_to_obsidian()
    pushed = 0
    if sync_back:
        pushed = sync_completions_to_google()
        
    return {"pulled": pulled, "pushed": pushed}

if __name__ == "__main__":
    res = run(sync_back=True)
    if res:
        print(f"Summary: Pulled {res['pulled']}, Pushed {res['pushed']}")
    else:
        print("Google Tasks Agent is disabled.")
