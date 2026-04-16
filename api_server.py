import os
import datetime
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel

from config_utils import get_config_value
from logseq_agent import LogSeqAgent
from obsidian_agent import ObsidianAgent

app = FastAPI(title="AI Agent Assistant Webhook API")


# ── Request models ─────────────────────────────────────────────────────────────

class AddTaskRequest(BaseModel):
    description: str
    date: Optional[str] = None  # YYYY-MM-DD, defaults to today


class PlanRequest(BaseModel):
    pass


class FileOpRequest(BaseModel):
    path: str
    content: Optional[str] = None
    overwrite: bool = False


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_logseq_agent():
    logseq_dir = get_config_value("LOGSEQ_DIR", None)
    if not logseq_dir:
        return None, None
    return LogSeqAgent(logseq_dir), logseq_dir

def _get_obsidian_agent():
    workspace_dir = get_config_value("WORKSPACE_DIR", ".")
    return ObsidianAgent(workspace_dir=workspace_dir)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/vault/read")
def read_vault_file(path: str):
    agent = _get_obsidian_agent()
    content = agent.read_file(path)
    if content is None:
        return {"status": "error", "message": f"File not found: {path}"}
    return {"status": "ok", "content": content}


@app.post("/vault/write")
def write_vault_file(body: FileOpRequest):
    agent = _get_obsidian_agent()
    # Simple check for path traversal could be added here
    if body.content is None:
        return {"status": "error", "message": "No content provided"}
    
    success = agent.create_file(body.path, body.content, overwrite=body.overwrite)
    if not success:
        return {"status": "error", "message": "File already exists and overwrite is false"}
    return {"status": "ok", "message": f"File written to {body.path}"}


@app.get("/vault/tasks")
def get_vault_tasks(todo: bool = True, done: bool = False):
    agent = _get_obsidian_agent()
    tasks = agent.get_tasks(todo=todo, done=done)
    return {"status": "ok", "count": len(tasks), "tasks": tasks}


@app.get("/logseq/tasks")
def get_logseq_tasks(days: int = 7):
    agent, _ = _get_logseq_agent()
    if not agent:
        return {"status": "error", "message": "LogSeq not configured"}
    context = agent.context_for_recent(days=days)
    return {"status": "ok", "context": context}


@app.post("/webhook/add-task")
def add_task(body: AddTaskRequest):
    agent, logseq_dir = _get_logseq_agent()
    if agent is None:
        return {"status": "error", "message": "LOGSEQ_DIR not configured"}

    date_key = None
    if body.date:
        try:
            dt = datetime.datetime.strptime(body.date, "%Y-%m-%d")
            date_key = dt.strftime("%Y_%m_%d")
        except ValueError:
            return {"status": "error", "message": f"Invalid date format: {body.date}. Use YYYY-MM-DD."}

    file_path = agent.add_task(body.description, date_key=date_key)
    return {
        "status": "ok",
        "message": "Added to LogSeq",
        "file": file_path,
    }


@app.get("/webhook/backlog")
def get_backlog():
    from main import get_unified_tasks
    obsidian_path = get_config_value("WORKSPACE_DIR", ".")
    tasks = get_unified_tasks(obsidian_path)
    return {
        "status": "ok",
        "count": len(tasks),
        "tasks": tasks,
    }


@app.post("/webhook/plan")
def run_plan(_: PlanRequest = None):
    import ai_orchestration
    from calendar_agent import CalendarAgent

    obsidian_path = get_config_value("WORKSPACE_DIR", ".")
    logseq_path = get_config_value("LOGSEQ_DIR", None)

    from main import get_unified_tasks
    tasks = get_unified_tasks(obsidian_path)

    calendar_agent = CalendarAgent()
    busy_slots = calendar_agent.get_busy_slots_from_yml()

    result = ai_orchestration.generate_schedule(
        tasks,
        busy_slots,
        morning_mode=True,
        workspace_dir=obsidian_path,
        logseq_dir=logseq_path,
    )

    schedule = result.get("schedule", []) if result else []
    return {
        "status": "ok",
        "message": "Planning triggered",
        "schedule": schedule,
    }


@app.post("/webhook/morning-plan")
def morning_plan():
    """
    Run the full morning planning pipeline and return the generated plan.

    Sequence:
      1. datainput_agent  — sync Apple Reminders → Obsidian planner
      2. logseq_later_agent — sync LogSeq LATER tasks → Obsidian planner
      3. calendar_planning_agent — generate day/week plan via configured LLM (ROUTING_PLANNING)
      4. Return plan text + path to suggestions file
    """
    import calendar_planning_agent

    results = {}

    # Step 1: datainput sync
    try:
        import datainput_agent
        datainput_agent.run(organise=False)
        results["datainput"] = "ok"
    except Exception as e:
        results["datainput"] = f"error: {e}"

    # Step 2: LogSeq LATER sync
    try:
        from logseq_later_agent import run as logseq_run
        logseq_run(write_to_obsidian=True)
        results["logseq_later"] = "ok"
    except Exception as e:
        results["logseq_later"] = f"error: {e}"

    # Step 3: Generate plan via LLM
    try:
        plan_text = calendar_planning_agent.generate_plan(
            days=7, write_to_obsidian=True
        )
        results["plan"] = "ok" if plan_text else "no output"
    except Exception as e:
        results["plan"] = f"error: {e}"
        plan_text = None

    suggestions_path = os.path.join("datainput", "calendar_suggestions.md")
    return {
        "status": "ok",
        "steps": results,
        "plan": plan_text or "",
        "suggestions_file": suggestions_path if os.path.exists(suggestions_path) else None,
    }


@app.get("/health")
def health():
    logseq_dir = get_config_value("LOGSEQ_DIR", None)

    ollama_ok = False
    try:
        import requests as req
        ollama_host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
        resp = req.get(f"{ollama_host}/api/version", timeout=2)
        ollama_ok = resp.status_code == 200
    except Exception:
        pass

    return {
        "status": "ok",
        "ollama": ollama_ok,
        "logseq_dir": logseq_dir,
    }


# ── Entry point ────────────────────────────────────────────────────────────────

# ── Agent execution endpoints (called by n8n agent workflows) ──────────────────

class RescheduleRequest(BaseModel):
    target: str
    dry_run: bool = False
    logseq: bool = True
    obsidian: bool = True
    filter_text: Optional[str] = None


@app.post("/webhook/agent/reschedule")
def agent_reschedule(body: RescheduleRequest):
    """Move overdue tasks to a new date. Called by n8n agent/reschedule workflow."""
    import task_reschedule_agent
    result = task_reschedule_agent.run(
        target=body.target,
        dry_run=body.dry_run,
        logseq=body.logseq,
        obsidian=body.obsidian,
        filter_text=body.filter_text,
    )
    if not result:
        return {"status": "error", "message": "Could not parse target date"}
    return {"status": "ok", **result}


@app.post("/webhook/agent/sync-logseq")
def agent_sync_logseq():
    """Sync LogSeq LATER/TODO tasks into the Obsidian planner."""
    from logseq_later_agent import run as logseq_run
    try:
        logseq_run(write_to_obsidian=True)
        return {"status": "ok", "message": "LogSeq tasks synced to Obsidian"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/webhook/agent/sync-reminders")
def agent_sync_reminders():
    """Sync Apple Reminders into the Obsidian planner (no LLM re-organisation)."""
    try:
        import datainput_agent
        datainput_agent.run(organise=False)
        return {"status": "ok", "message": "Reminders synced to Obsidian"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/webhook/agent/organize")
def agent_organize():
    """Organise the Obsidian planner: surface overdue tasks, categorise by project."""
    try:
        import datainput_agent
        datainput_agent.run(organise=True)
        return {"status": "ok", "message": "Planner organised"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/webhook/agent/morning-sync")
def agent_morning_sync():
    """Run the full morning pipeline: sync reminders + LogSeq + generate AI weekly plan."""
    import calendar_planning_agent

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

    plan_text = None
    try:
        plan_text = calendar_planning_agent.generate_plan(days=7, write_to_obsidian=True)
        steps["plan"] = "ok" if plan_text else "no output"
    except Exception as e:
        steps["plan"] = f"error: {e}"

    suggestions_path = os.path.join("datainput", "calendar_suggestions.md")
    return {
        "status": "ok",
        "steps": steps,
        "plan": plan_text or "",
        "suggestions_file": suggestions_path if os.path.exists(suggestions_path) else None,
    }


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(get_config_value("WEBHOOK_PORT", "5000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
