"""
HTTP API for ai_agent_assistant — lets distributed agents query Obsidian/planning data
over Tailscale (or localhost) without needing a local copy of the assistant.

Start: python main.py --api [PORT]   (default port 7890)

Auth: set ASSISTANT_API_KEY in .config; workers must send it as x-api-key header.
If ASSISTANT_API_KEY is empty, the API is open (localhost-only is fine for testing).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.responses import JSONResponse

API_KEY = config.get("ASSISTANT_API_KEY", "")

app = FastAPI(title="AI Agent Assistant API", version="1.0.0")


def _check_auth(x_api_key: str) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid x-api-key")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "ai_agent_assistant"}


# ── Obsidian: tasks ───────────────────────────────────────────────────────────

@app.get("/tasks")
def get_tasks(
    include_done: bool = False,
    subdirs: str = Query(default="", description="Comma-separated vault subdirectories to scan"),
    x_api_key: str = Header(default=""),
):
    """Return open Obsidian tasks. Optionally filter by subdirectory."""
    _check_auth(x_api_key)
    from integrations.obsidian import ObsidianVault
    vault = ObsidianVault()
    subdir_list = [s.strip() for s in subdirs.split(",") if s.strip()] if subdirs else None
    tasks = vault.get_tasks(include_done=include_done, subdirs=subdir_list)
    # Serialize date objects so FastAPI can JSON-encode them
    for t in tasks:
        for key in ("due_date", "scheduled_date"):
            if t.get(key) is not None:
                t[key] = str(t[key])
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/tasks")
def add_task(
    body: dict,
    x_api_key: str = Header(default=""),
):
    """Add a task to the vault inbox. Body: {"text": "...", "due_date": "YYYY-MM-DD"?}."""
    _check_auth(x_api_key)
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    due = (body.get("due_date") or "").strip()
    task_line = f"- [ ] {text}" + (f" 📅 {due}" if due else "")

    from integrations.obsidian import ObsidianVault
    vault = ObsidianVault()
    section = vault.read_section("inbox") or ""
    vault.write_section("inbox", (section.rstrip() + "\n" + task_line).strip())
    return {"added": task_line}


@app.post("/tasks/done")
def mark_task_done(
    body: dict,
    x_api_key: str = Header(default=""),
):
    """Mark the first task matching the text as done. Body: {"text_match": "..."}."""
    _check_auth(x_api_key)
    match = (body.get("text_match") or "").strip()
    if not match:
        raise HTTPException(status_code=422, detail="text_match is required")
    from integrations.obsidian import ObsidianVault
    ok = ObsidianVault().mark_task_done(match)
    if not ok:
        raise HTTPException(status_code=404, detail=f"no open task matched: {match}")
    return {"done": match}


# ── Calendar ──────────────────────────────────────────────────────────────────

@app.get("/calendar")
def get_calendar(
    min_free_minutes: int = Query(default=120, description="Minimum size of the 'next free slot'"),
    work_start: str = Query(default="08:00"),
    work_end: str = Query(default="20:00"),
    x_api_key: str = Header(default=""),
):
    """Today's events + the next free slot >= min_free_minutes within working hours.

    Reads the assistant's local ICS calendar (synced from Obsidian #gcal tags).
    """
    _check_auth(x_api_key)
    import datetime
    from integrations.calendar import CalendarReader

    reader = CalendarReader()
    today = datetime.date.today()

    events = []
    for e in reader.get_today_events():
        s, en = e.get("start"), e.get("end")
        events.append({
            "summary": e.get("summary", ""),
            "start": str(s) if s is not None else None,
            "end": str(en) if en is not None else None,
            "all_day": e.get("all_day", False),
        })

    def _parse_hm(s: str) -> datetime.time:
        h, m = (s.split(":") + ["0"])[:2]
        return datetime.time(int(h), int(m))

    ws, we = _parse_hm(work_start), _parse_hm(work_end)
    busy = sorted(reader.get_busy_slots(today))

    # Build free windows = working hours minus busy slots.
    free: list[tuple] = []
    cursor = ws
    for bs, be in busy:
        if bs > cursor:
            free.append((cursor, min(bs, we)))
        if be > cursor:
            cursor = be
        if cursor >= we:
            break
    if cursor < we:
        free.append((cursor, we))

    def _mins(a: datetime.time, b: datetime.time) -> int:
        return int((datetime.datetime.combine(today, b) - datetime.datetime.combine(today, a)).total_seconds() // 60)

    now = datetime.datetime.now().time()
    next_free = None
    for fs, fe in free:
        start = max(fs, now) if fe > now else None
        if start is None:
            continue
        if _mins(start, fe) >= min_free_minutes:
            next_free = {"start": start.strftime("%H:%M"), "end": fe.strftime("%H:%M"),
                         "minutes": _mins(start, fe)}
            break

    return {
        "date": str(today),
        "events": events,
        "event_count": len(events),
        "next_free_slot": next_free,
        "free_slots": [{"start": a.strftime("%H:%M"), "end": b.strftime("%H:%M")} for a, b in free],
    }


# ── Obsidian: notes ───────────────────────────────────────────────────────────

@app.get("/notes")
def list_notes(
    subdir: str = Query(default="", description="Vault subdirectory to list (empty = all)"),
    x_api_key: str = Header(default=""),
):
    """Return note index (path, title, tags, size — no content)."""
    _check_auth(x_api_key)
    from integrations.obsidian import ObsidianVault
    vault = ObsidianVault()
    notes = vault.list_notes(subdir=subdir or None)
    index = [
        {"path": n["path"], "title": n["title"], "tags": n["tags"], "size": n["size"]}
        for n in notes
    ]
    return {"notes": index, "count": len(index)}


@app.get("/note")
def read_note(
    path: str = Query(..., description="Relative path within the Obsidian vault"),
    x_api_key: str = Header(default=""),
):
    """Return the full content of a specific note."""
    _check_auth(x_api_key)
    from integrations.obsidian import ObsidianVault
    vault = ObsidianVault()
    content = vault.read_file(path)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Note not found: {path}")
    return {"path": path, "content": content}


# ── Obsidian: dashboard ───────────────────────────────────────────────────────

@app.get("/dashboard")
def read_dashboard(
    section: str = Query(default="", description="Named section (e.g. today-plan). Empty returns all standard sections."),
    x_api_key: str = Header(default=""),
):
    """Read named sections from Dashboard.md."""
    _check_auth(x_api_key)
    from integrations.obsidian import ObsidianVault
    vault = ObsidianVault()
    if section:
        content = vault.read_section(section)
        return {"section": section, "content": content}
    sections = {}
    for sec in ("today-plan", "week-plan", "backlog", "focus"):
        sections[sec] = vault.read_section(sec)
    return {"sections": sections}


# ── Planning: generate plan ───────────────────────────────────────────────────

@app.post("/plan")
def generate_plan(
    mode: str = Query(default="today", description="today or week"),
    x_api_key: str = Header(default=""),
):
    """Generate a fresh daily or weekly plan using the planning agent and LLM."""
    _check_auth(x_api_key)
    if mode not in ("today", "week"):
        raise HTTPException(status_code=400, detail="mode must be 'today' or 'week'")
    from agents.planning_agent import run
    plan = run(mode=mode)
    return {"mode": mode, "plan": plan}


# ── Status ────────────────────────────────────────────────────────────────────

@app.get("/status")
def status(x_api_key: str = Header(default="")):
    """Return the assistant's configuration summary."""
    _check_auth(x_api_key)
    return config.summary()


# ── LLM info ─────────────────────────────────────────────────────────────────

@app.get("/llm")
def llm_info(x_api_key: str = Header(default="")):
    """Return which LLM providers are configured and available."""
    _check_auth(x_api_key)
    from llm.router import all_providers
    return {"providers": all_providers()}
