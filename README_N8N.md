# n8n Integration Guide

This guide explains how to use the included n8n workflow templates with AI Agent Assistant.

## Prerequisites

- Docker and Docker Compose installed
- AI Agent Assistant running (see main `README.md`)

---

## 1. Starting n8n

Start n8n and the agent API together:

```bash
docker compose up n8n api
```

Or start the full stack:

```bash
docker compose up
```

---

## 2. Accessing the n8n UI

Open your browser at:

```
http://localhost:5679
```

> The port is controlled by `N8N_PORT` in your `.env` file (default: `5679`).

---

## 3. Importing a Workflow

1. In the n8n UI, go to **Workflows** in the left sidebar.
2. Click **Add Workflow** → **Import from File**.
3. Select one of the JSON files from `n8n-workflows/`:
   - `morning-planning.json` — weekday 08:00 daily plan
   - `add-task.json` — inbound webhook to add LogSeq tasks
   - `backlog-digest.json` — Friday 17:00 backlog summary
4. Click **Import**.

---

## 4. Configuring the Agent API URL

The workflows use `http://api:5678` as the agent API base URL. This works when both n8n and the API are running inside the same Docker network.

**If running the API directly on your host** (outside Docker), replace `http://api:5678` with `http://localhost:5678` in each HTTP Request node.

To edit: open the workflow → click the HTTP Request node → update the URL field.

---

## 5. Activating a Workflow

Each workflow is imported in an **inactive** state. To activate:

1. Open the workflow in the n8n editor.
2. Toggle the **Active** switch in the top-right corner.

Cron-based workflows (`morning-planning`, `backlog-digest`) only run automatically when active.

---

## 6. Testing a Workflow

To run a workflow manually without waiting for the schedule:

1. Open the workflow in the editor.
2. Click **Execute Workflow** (▶ button).
3. Inspect the output of each node in the execution panel.

---

## 7. Example: Add a Task via curl

Once the `add-task` workflow is active, you can POST directly to the agent API:

```bash
curl -X POST http://localhost:5678/webhook/add-task \
  -H "Content-Type: application/json" \
  -d '{"description": "Review project notes"}'
```

Or trigger it through the n8n webhook (replace `<your-webhook-url>` with the URL shown in the Webhook node):

```bash
curl -X POST http://localhost:5679/webhook/n8n-trigger/add-task \
  -H "Content-Type: application/json" \
  -d '{"task": "Review project notes"}'
```

---

## Workflow Overview

| File | Trigger | What it does |
|------|---------|--------------|
| `morning-planning.json` | Weekdays 08:00 | Calls `/webhook/plan`, formats today's schedule |
| `add-task.json` | Inbound HTTP POST | Accepts `{"task": "..."}`, proxies to `/webhook/add-task` |
| `backlog-digest.json` | Fridays 17:00 | Fetches `/webhook/backlog`, formats task list |

---

## Extending Workflows

The output nodes in each workflow are intentionally left as `Set` nodes (a no-op placeholder). To send digests or plans somewhere useful, add a downstream node:

- **Slack**: use `n8n-nodes-base.slack` → send a message
- **Email**: use `n8n-nodes-base.emailSend`
- **Webhook**: forward to any other service

Connect the new node to the last existing node in the workflow.

---

## Universal Task Sync

The `universal_task_sync.json` workflow provides a conflict-resolved sync between your local Markdown tasks and a calendar.

### 1. Import
Follow the instructions in section 3 to import `n8n-workflows/universal_task_sync.json`.

### 2. Conflict Rules
The workflow implements three main rules in the **Classify Tasks** node:
- **Local task + Calendar event match**: Skip (already synced).
- **Local task only**: Create a new calendar event (Node 3).
- **Calendar event only**: Add a new local task (Node 4).

### 3. Network Configuration
- **host.docker.internal**: This is the standard Docker DNS name to reach the host machine from inside an n8n container. 
- **Linux Users**: If `host.docker.internal` is not resolved, use the host IP (usually `172.17.0.1`) or add `--add-host=host-gateway:host-gateway` to your Docker run/compose command.

### 4. Google Calendar Dependency
The **Create Calendar Events** node is currently a placeholder. It is designed to call the local ICS API (Sprint-05 dependency) when it becomes available.

### 5. Testing
Run the following command in the AI Agent Assistant CLI to trigger the sync manually:
```bash
/sync-universal
```
You can then watch the live execution in the n8n UI.
