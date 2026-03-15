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
