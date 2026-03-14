# Dev Agent Task Prompt — T01-07

> Self-contained — you have no other context. Read everything here carefully before acting.
> PREREQUISITE: T01-06 must be complete (api_server.py must exist and the endpoints must be documented).

---

## Identity & Role

You are a senior software developer working on **AI Agent Assistant** — a personal CLI agent that uses local LLMs (Ollama) to manage tasks from LogSeq and Obsidian and interact with Google Calendar.

You are creating **n8n workflow JSON templates** that users can import into n8n to get event-driven agent automations working immediately — no workflow building required.

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Workflow engine | n8n (self-hosted via Docker) |
| Agent API | FastAPI running on `http://localhost:5678` (or `http://api:5678` inside Docker) |
| Workflow format | n8n workflow JSON (importable via n8n UI: Workflows → Import) |

---

## API Endpoints Available (from T01-06)

All endpoints are on `http://localhost:${WEBHOOK_PORT:-5678}`:

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `POST` | `/webhook/add-task` | `{"description": "...", "date": "YYYY-MM-DD"}` | `{"status": "ok", "message": "...", "file": "..."}` |
| `GET` | `/webhook/backlog` | — | `{"status": "ok", "count": N, "tasks": [...]}` |
| `POST` | `/webhook/plan` | `{}` | `{"status": "ok", "message": "...", "schedule": [...]}` |
| `GET` | `/health` | — | `{"status": "ok", "ollama": bool, "logseq_dir": "..."}` |

---

## Your Task

**Task ID**: T01-07
**Title**: Create n8n workflow JSON templates and README_N8N.md
**Sprint**: Sprint-01
**Backlog item**: BLI-024

### Description

Create three ready-to-import n8n workflow JSON files covering the most useful event-driven automations, plus a README explaining how to get started with n8n alongside this project.

### Files to create

**`n8n-workflows/morning-planning.json`**

Trigger: Cron node — every weekday at 08:00
Steps:
1. Cron trigger (weekdays 08:00)
2. HTTP Request node → `POST http://api:5678/webhook/plan` (body: `{}`)
3. IF node — check `response.body.status == "ok"`
4. Set node — format the schedule as readable text: `"Today's plan:\n- [time] task (category)"`
5. (Optional) Respond to Webhook or log to n8n execution log

**`n8n-workflows/add-task.json`**

Trigger: n8n Webhook node (manual POST trigger from any external source)
Steps:
1. Webhook trigger — listens for `POST /n8n-trigger/add-task` with body `{"task": "..."}`
2. HTTP Request node → `POST http://api:5678/webhook/add-task` with `{"description": "{{$json.task}}"}`
3. Respond to Webhook — return the result from the agent API

Use case: Any tool (another n8n workflow, a phone shortcut, a browser extension) can POST to the n8n webhook URL to add a LogSeq task.

**`n8n-workflows/backlog-digest.json`**

Trigger: Cron node — every Friday at 17:00
Steps:
1. Cron trigger (Friday 17:00)
2. HTTP Request node → `GET http://api:5678/webhook/backlog`
3. Code node — format the task list:
   ```javascript
   const tasks = $input.first().json.tasks || [];
   const lines = tasks.map(t => `- [${t.category}] ${t.task} (${t.source})`);
   return [{ json: { digest: lines.join('\n'), count: tasks.length } }];
   ```
4. (Optional) Send to any output node (Slack, email, console log)

### Workflow JSON format

Each file must be valid n8n workflow JSON that can be imported directly. Use n8n's standard workflow schema:

```json
{
  "name": "Workflow Name",
  "nodes": [...],
  "connections": {...},
  "active": false,
  "settings": {},
  "tags": []
}
```

Key n8n node types to use:
- `n8n-nodes-base.scheduleTrigger` — for cron jobs
- `n8n-nodes-base.webhook` — for inbound HTTP triggers
- `n8n-nodes-base.httpRequest` — to call the agent API
- `n8n-nodes-base.if` — conditional branching
- `n8n-nodes-base.set` — set/transform data
- `n8n-nodes-base.code` — JavaScript transformation

### `README_N8N.md`

Create a concise setup guide covering:

1. **Starting n8n** — `docker compose up n8n api` or `docker compose up`
2. **Accessing n8n UI** — `http://localhost:5679` (or configured `N8N_PORT`)
3. **Importing a workflow** — Workflows → Add Workflow → Import from File → select JSON
4. **Configuring the webhook URL** — explain that `http://api:5678` works inside Docker; use `http://localhost:5678` if running the API directly
5. **Activating workflows** — toggle Active switch in n8n
6. **Testing** — use n8n's Execute Workflow button to run manually
7. **Example: Add a task from curl**:
   ```bash
   curl -X POST http://localhost:5678/webhook/add-task \
     -H "Content-Type: application/json" \
     -d '{"description": "Review project notes"}'
   ```

### Acceptance Criteria
- [ ] `n8n-workflows/morning-planning.json` — valid n8n workflow JSON, importable without errors
- [ ] `n8n-workflows/add-task.json` — valid n8n workflow JSON with inbound webhook trigger
- [ ] `n8n-workflows/backlog-digest.json` — valid n8n workflow JSON with cron + formatting
- [ ] All three workflows use `http://api:5678` as the agent API base URL (works in Docker)
- [ ] `README_N8N.md` covers: start n8n, import workflow, configure URL, activate, test
- [ ] README includes the curl example for manual task addition

### Out of Scope
- Do NOT build Slack/email notification nodes — leave output nodes as placeholders
- Do NOT create more than 3 workflows — keep it focused
- Do NOT modify `api_server.py` — that is T01-06's scope

---

## Output Format

### 1. Summary

### 2. New Files

#### `n8n-workflows/morning-planning.json` [NEW]
```json
[complete workflow JSON]
```

#### `n8n-workflows/add-task.json` [NEW]
```json
[complete workflow JSON]
```

#### `n8n-workflows/backlog-digest.json` [NEW]
```json
[complete workflow JSON]
```

#### `README_N8N.md` [NEW]
```markdown
[complete file content]
```

### 3. Dependencies Added
None (n8n runs in Docker, no Python packages needed)

### 4. Integration Notes
[Anything sprint-02 tasks should know about extending the n8n integration]

### 5. Known Limitations
