"""
google_tasks_agent.py — Google Tasks ↔ Obsidian two-way sync via n8n.

Google Tasks auth moved to n8n (ADR-010).
Task sync triggers n8n workflows instead of calling Google Tasks API directly.

Pull: triggers "google-tasks-pull" n8n workflow
Push: scans Obsidian planner for - [x] done tasks;
      triggers "google-tasks-push" with completed task titles.

Config keys:
    ENABLE_GOOGLE_TASKS   — false by default; skip all calls if not true
    WORKSPACE_DIR         — Obsidian vault path
    OBSIDIAN_PLANNER_FILE — planner filename (default: 010 Planning/Planner.md)

Entry points:
    run(sync_back=False)  — trigger pull; optionally trigger push
"""

import os
import re
import logging
from config_utils import get_config_value
import n8n_client

# GATE: ENABLE_GOOGLE_TASKS=false must short-circuit
def _is_enabled():
    return get_config_value("ENABLE_GOOGLE_TASKS", "false").lower() == "true"

def sync_to_obsidian() -> bool:
    """
    Trigger n8n workflow to pull incomplete tasks from Google Tasks.
    """
    if not _is_enabled():
        return False
    
    print("[GoogleTasksAgent] Triggering n8n pull workflow...")
    return n8n_client.trigger("google-tasks-pull", {})

def sync_completions_to_google() -> bool:
    """
    Scan Obsidian planner for - [x] done tasks.
    Trigger n8n workflow to mark them complete in Google Tasks.
    """
    if not _is_enabled():
        return False

    workspace = get_config_value("WORKSPACE_DIR", "")
    planner_file = get_config_value("OBSIDIAN_PLANNER_FILE", "010 Planning/Planner.md")
    planner_path = os.path.join(workspace, planner_file)
    
    if not os.path.exists(planner_path):
        print(f"[GoogleTasksAgent] Planner not found: {planner_path}")
        return False

    done_titles = []
    with open(planner_path, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^\s*-\s+\[x\]\s+(.*)", line, re.IGNORECASE)
            if m:
                done_titles.append(m.group(1).strip())

    if not done_titles:
        return True

    print(f"[GoogleTasksAgent] Triggering n8n push workflow for {len(done_titles)} tasks...")
    return n8n_client.trigger("google-tasks-push", {"completions": done_titles})

def run(sync_back=False):
    """
    Run the full Google Tasks agent pipeline via n8n triggers.
    """
    if not _is_enabled():
        return None
        
    pulled_ok = sync_to_obsidian()
    pushed_ok = False
    if sync_back:
        pushed_ok = sync_completions_to_google()
        
    return {"pulled": pulled_ok, "pushed": pushed_ok}

if __name__ == "__main__":
    res = run(sync_back=True)
    if res:
        print(f"Sync triggers: Pull={res['pulled']}, Push={res['pushed']}")
    else:
        print("Google Tasks Agent is disabled.")
