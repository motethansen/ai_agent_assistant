import os
import datetime
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel

from config_utils import get_config_value
from logseq_agent import LogSeqAgent

app = FastAPI(title="AI Agent Assistant Webhook API")


# ── Request models ─────────────────────────────────────────────────────────────

class AddTaskRequest(BaseModel):
    description: str
    date: Optional[str] = None  # YYYY-MM-DD, defaults to today


class PlanRequest(BaseModel):
    pass


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_logseq_agent():
    logseq_dir = get_config_value("LOGSEQ_DIR", None)
    if not logseq_dir:
        return None, None
    return LogSeqAgent(logseq_dir), logseq_dir


# ── Endpoints ──────────────────────────────────────────────────────────────────

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

if __name__ == "__main__":
    import uvicorn
    port = int(get_config_value("WEBHOOK_PORT", "5678"))
    uvicorn.run(app, host="0.0.0.0", port=port)
