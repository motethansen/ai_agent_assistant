# Dev Agent Task Prompt — T01-06

> **ACTION REQUIRED: You are a Claude Code agent with file-editing tools (Read, Edit, Write, Bash).**
> **READ the actual source files in the project, then APPLY all changes directly to disk using your tools.**
> **Do NOT output code as text blocks. Write changes to the actual files.**
> **Project root: /home/michaelhansen/Projects/github/ai_agent_assistant**
>
> Self-contained — you have no other context. Read everything here carefully before acting.
> PREREQUISITE: T01-01 and T01-02 must be complete (no OpenClaw in the codebase).

---

## Identity & Role

You are a senior software developer working on **AI Agent Assistant** — a personal CLI agent that uses local LLMs (Ollama) to manage tasks from LogSeq and Obsidian and interact with Google Calendar.

You are adding a **webhook HTTP API** so that n8n (and any other automation tool) can trigger agent actions via HTTP requests. This is the foundation for event-driven automation.

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| HTTP API | FastAPI + uvicorn |
| Primary LLM | Ollama via `ai_orchestration.py` |
| Task sources | LogSeq (markdown files), Obsidian (markdown files) |
| Config | `.env` file via `config_utils.get_config_value()` |
| Workflow engine | n8n (runs in Docker) |

---

## Repository Structure (relevant parts)

```
ai_agent_assistant/
├── api_server.py              ← NEW — create this file
├── docker-compose.yml         ← NEW — create this file
├── main.py                    ← read-only reference
├── ai_orchestration.py        ← read-only reference
├── logseq_agent.py            ← read-only reference
├── config_utils.py            ← read-only reference
└── config.template            ← add WEBHOOK_PORT, N8N_PORT
```

---

## Relevant Existing Code

### config_utils.py (interface only)
```python
def get_config_value(key: str, default=None) -> str:
    """Reads KEY from .config file or environment. Returns default if not found."""
```

### logseq_agent.py — relevant methods
```python
class LogSeqAgent:
    def __init__(self, logseq_dir: str): ...
    def add_task(self, description: str, date_key: str = None) -> str:
        """Appends a LATER task to a journal file. Returns path written."""
    def get_recent_tasks(self, days: int = 7) -> list:
        """Returns list of {"task": str, "source": str, "properties": dict}"""
    def get_all_page_tasks(self) -> list:
        """Returns all LATER/TODO tasks from pages/"""
```

### main.py — get_unified_tasks() signature
```python
def get_unified_tasks(obsidian_path: str) -> list:
    """Returns merged list of tasks from Obsidian + LogSeq + Reminders.
    Each task: {"task": str, "category": str, "source": str, "due_date": str|None}
    """
```

### main.py — handle_morning_planning() signature
```python
def handle_morning_planning(obsidian_path: str):
    """Runs morning planning: reads backlog, generates schedule, confirms with user."""
```

---

## Your Task

**Task ID**: T01-06
**Title**: Build webhook HTTP API and docker-compose for n8n integration
**Sprint**: Sprint-01
**Backlog item**: BLI-023

### Description

Create `api_server.py` — a FastAPI HTTP server that exposes the assistant's core functions as webhook endpoints. n8n (and other tools) can POST/GET these endpoints to trigger tasks without using the CLI.

Also create `docker-compose.yml` so the user can run both n8n and the API server with a single command.

### Files to create

**`api_server.py`**:

Create a FastAPI app with these endpoints:

```
POST /webhook/add-task
  Body: {"description": "...", "date": "YYYY-MM-DD" (optional)}
  Returns: {"status": "ok", "message": "Added to LogSeq", "file": "/path/to/journal.md"}
  Error if LOGSEQ_DIR not set: {"status": "error", "message": "LOGSEQ_DIR not configured"}

GET /webhook/backlog
  Returns: {"status": "ok", "count": 12, "tasks": [...]}
  Each task: {"task": str, "category": str, "source": str, "due_date": str|null}

POST /webhook/plan
  Body: {} (empty — uses config for paths)
  Returns: {"status": "ok", "message": "Planning triggered", "schedule": [...]}
  Note: runs generate_schedule() synchronously — may take 10-30s with Ollama

GET /health
  Returns: {"status": "ok", "ollama": true|false, "logseq_dir": "/path or null"}
```

Use `get_config_value()` for all path/config reads. Do not hardcode paths.

Run with:
```python
if __name__ == "__main__":
    import uvicorn
    port = int(get_config_value("WEBHOOK_PORT", "5678"))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

**`docker-compose.yml`**:

```yaml
version: "3.8"
services:
  n8n:
    image: n8nio/n8n:latest
    ports:
      - "${N8N_PORT:-5679}:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=false
      - WEBHOOK_URL=http://api:${WEBHOOK_PORT:-5678}
    volumes:
      - n8n_data:/home/node/.n8n
    networks:
      - agent_net
    restart: unless-stopped

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "${WEBHOOK_PORT:-5678}:5678"
    volumes:
      - .:/app
      - ${LOGSEQ_DIR:-/tmp}:/logseq:ro
      - ${WORKSPACE_DIR:-/tmp}:/workspace:ro
    env_file:
      - .config
    networks:
      - agent_net
    restart: unless-stopped

volumes:
  n8n_data:

networks:
  agent_net:
```

**`Dockerfile.api`**:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt fastapi uvicorn
COPY . .
CMD ["python", "api_server.py"]
```

**`config.template`** — add these lines to the General Settings section:

```
# --- n8n & Webhook Settings ---
# WEBHOOK_PORT: Port the FastAPI webhook server listens on (used by n8n to call the agent)
WEBHOOK_PORT=5678
# N8N_PORT: Port to access the n8n UI in your browser
N8N_PORT=5679
```

### Acceptance Criteria
- [ ] `api_server.py` created with `/webhook/add-task`, `/webhook/backlog`, `/webhook/plan`, `/health`
- [ ] All endpoints return JSON with `{"status": "ok"|"error", ...}`
- [ ] `POST /webhook/add-task` with `{"description": "buy milk"}` adds the task to today's LogSeq journal
- [ ] `GET /webhook/backlog` returns the unified task list as JSON
- [ ] `POST /webhook/plan` triggers schedule generation and returns the result
- [ ] `GET /health` reports Ollama status and configured paths
- [ ] `WEBHOOK_PORT` and `N8N_PORT` added to `config.template`
- [ ] `docker-compose.yml` created — `docker compose up` starts both n8n and the API
- [ ] `Dockerfile.api` created for the API container
- [ ] Server starts locally without Docker: `python api_server.py`

### Out of Scope
- Do NOT add authentication to the webhook endpoints (local tool, not internet-facing)
- Do NOT create n8n workflow JSON files — that is T01-07
- Do NOT modify `main.py` or `ai_orchestration.py`
- Do NOT add background task queuing — synchronous responses are fine for now

---

## Completion Report

After applying all changes to the actual files, write a brief report covering:

### 1. Files created/modified
List each file you created or edited.

### 2. Acceptance criteria check
Go through each AC item and confirm ✅ or ❌ with a one-line note.

### 3. Integration notes for T01-07
What T01-07 needs to know about the API endpoints when building n8n workflow JSONs.

### 4. Any issues or deviations
Note anything you couldn't apply and why.
