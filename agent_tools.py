"""
Agent Action Tools for LLM Tool-Calling

Exposes the project's agents as LangChain @tool functions so the LLM can
decide when to execute them. Each tool:
  1. Tries to route through n8n (so executions appear in n8n's audit log).
  2. Falls back to direct Python execution if n8n is unreachable.

Exported:
  ACTION_TOOLS  — list of all tools, ready to pass to AgentExecutor
  ACTION_KEYWORDS — strings that suggest the user wants an action, not just chat
"""

import json
import logging

logger = logging.getLogger(__name__)

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(func):
        """Fallback no-op decorator when LangChain is not installed."""
        return func


import requests
from config_utils import get_config_value

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_api(endpoint: str, method: str = "POST", params: dict = None) -> dict | None:
    """Try the local API server first; then try n8n as fallback."""
    port = get_config_value("WEBHOOK_PORT", "5000")
    base_url = f"http://localhost:{port}"
    
    try:
        if method == "GET":
            resp = requests.get(f"{base_url}/{endpoint.lstrip('/')}", params=params, timeout=10)
        else:
            resp = requests.post(f"{base_url}/{endpoint.lstrip('/')}", json=params, timeout=15)
        
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug("API server unreachable at %s: %s", endpoint, e)

    # Fallback to n8n if relevant (some agents have n8n equivalents)
    if endpoint.startswith("webhook/agent/"):
        flow = endpoint.replace("webhook/agent/", "")
        try:
            from n8n_client import trigger_agent
            return trigger_agent(flow, params or {})
        except Exception:
            pass
    return None


@tool
def read_obsidian_file(path: str) -> str:
    """
    Read the content of a file from the Obsidian vault.
    Provide a path relative to the vault root (e.g. '010 Planning/Planner.md').
    """
    result = _call_api("vault/read", method="GET", params={"path": path})
    if result and result.get("status") == "ok":
        return result.get("content", "")
    return f"Error reading file: {result.get('message') if result else 'Server unavailable'}"


@tool
def write_obsidian_file(path: str, content: str, overwrite: bool = False) -> str:
    """
    Create or update a file in the Obsidian vault.
    Provide a path relative to the vault root and the full content string.
    """
    result = _call_api("vault/write", method="POST", params={"path": path, "content": content, "overwrite": overwrite})
    if result and result.get("status") == "ok":
        return result.get("message", "Success")
    return f"Error writing file: {result.get('message') if result else 'Server unavailable'}"


@tool
def reschedule_overdue_tasks(target_date: str) -> str:
    """
    Move all overdue tasks to a new date.

    Works across LogSeq journal files and Obsidian tasks with a 📅 due date.
    target_date accepts natural language or ISO format, e.g.:
      "end of next week", "next monday", "friday", "2026-04-17"
    Returns a summary of how many tasks were moved.
    """
    result = _call_api("webhook/agent/reschedule", {"target": target_date})
    if result and result.get("status") == "ok":
        moved = result.get("logseq_moved", 0) + result.get("obsidian_moved", 0)
        return (
            f"Moved {moved} overdue task(s) to {result.get('target_date')}. "
            f"(LogSeq: {result.get('logseq_moved', 0)}, "
            f"Obsidian: {result.get('obsidian_moved', 0)})"
        )

    # Direct fallback
    try:
        import task_reschedule_agent
        r = task_reschedule_agent.run(target_date)
        if r:
            moved = r.get("logseq_moved", 0) + r.get("obsidian_moved", 0)
            return f"Moved {moved} overdue task(s) to {r.get('target_date')}."
        return "Could not parse target date."
    except Exception as e:
        return f"Error rescheduling tasks: {e}"


@tool
def sync_logseq_tasks() -> str:
    """
    Sync all LATER/TODO tasks from LogSeq journal files into the Obsidian planner.

    Scans the last N days of LogSeq journals and all LogSeq pages,
    deduplicates, and appends a '## LogSeq LATER Tasks' block to the planner.
    """
    result = _call_api("webhook/agent/sync-logseq")
    if result and result.get("status") == "ok":
        return result.get("message", "LogSeq tasks synced to Obsidian.")

    try:
        from logseq_later_agent import run as logseq_run
        logseq_run(write_to_obsidian=True)
        return "LogSeq tasks synced to Obsidian planner."
    except Exception as e:
        return f"Error syncing LogSeq tasks: {e}"


@tool
def sync_reminders() -> str:
    """
    Sync Apple Reminders into the Obsidian planner.

    Reads datainput/reminders.json, deduplicates against already-synced
    reminders, and appends new items under '## Reminders' in the planner.
    """
    result = _call_api("webhook/agent/sync-reminders")
    if result and result.get("status") == "ok":
        return result.get("message", "Reminders synced to Obsidian.")

    try:
        import datainput_agent
        datainput_agent.run(organise=False)
        return "Reminders synced to Obsidian planner."
    except Exception as e:
        return f"Error syncing reminders: {e}"


@tool
def organize_planner() -> str:
    """
    Organise the Obsidian planner using AI.

    Surfaces overdue tasks, groups items by project category, and rewrites
    the planner with a structured layout. Uses the configured LLM.
    """
    result = _call_api("webhook/agent/organize")
    if result and result.get("status") == "ok":
        return result.get("message", "Planner organised.")

    try:
        import datainput_agent
        datainput_agent.run(organise=True)
        return "Planner organised and categorised."
    except Exception as e:
        return f"Error organising planner: {e}"


@tool
def run_morning_pipeline() -> str:
    """
    Run the full morning sync pipeline.

    Executes three steps in order:
      1. Sync Apple Reminders → Obsidian planner
      2. Sync LogSeq LATER tasks → Obsidian planner
      3. Generate an AI weekly plan via the calendar planning agent
    Returns a summary of each step's result.
    """
    result = _call_api("webhook/agent/morning-sync")
    if result and result.get("status") == "ok":
        steps = result.get("steps", {})
        summary = ", ".join(f"{k}: {v}" for k, v in steps.items())
        plan_preview = result.get("plan", "")[:120]
        return f"Morning pipeline complete. Steps: {summary}. Plan preview: {plan_preview}"

    # Direct fallback — run each step inline
    steps = {}
    try:
        import datainput_agent
        datainput_agent.run(organise=False)
        steps["reminders"] = "ok"
    except Exception as e:
        steps["reminders"] = f"error: {e}"

    try:
        from logseq_later_agent import run as logseq_run
        logseq_run(write_to_obsidian=True)
        steps["logseq"] = "ok"
    except Exception as e:
        steps["logseq"] = f"error: {e}"

    plan_preview = ""
    try:
        import calendar_planning_agent
        plan_text = calendar_planning_agent.generate_plan(days=7, write_to_obsidian=True)
        steps["plan"] = "ok" if plan_text else "no output"
        plan_preview = (plan_text or "")[:120]
    except Exception as e:
        steps["plan"] = f"error: {e}"

    summary = ", ".join(f"{k}: {v}" for k, v in steps.items())
    return f"Morning pipeline complete. Steps: {summary}. Plan preview: {plan_preview}"


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

ACTION_TOOLS = [
    read_obsidian_file,
    write_obsidian_file,
    reschedule_overdue_tasks,
    sync_logseq_tasks,
    sync_reminders,
    organize_planner,
    run_morning_pipeline,
]

# Keywords that suggest the user wants to *execute* an agent, not just chat.
# Used by ai_orchestration.run_agent_query_stream to route to the tool-calling agent.
ACTION_KEYWORDS = [
    "reschedule", "move overdue", "move tasks", "shift tasks", "push tasks",
    "overdue tasks", "overdue to", "move my tasks",
    "sync logseq", "sync tasks", "sync reminders", "sync notes",
    "organize planner", "organise planner", "reorganise planner", "reorganize planner",
    "morning pipeline", "morning sync", "run all agents", "run agents",
    "run morning", "full sync",
]
