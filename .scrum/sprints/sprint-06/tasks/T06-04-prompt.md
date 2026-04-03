# T06-04 — Universal Task Sync via n8n Workflow

**Sprint**: 06 | **BLI**: BLI-039 | **Estimate**: L | **LLM Agent**: Gemini
**Wave**: 3 — run in parallel with T06-05 (zero file overlap)
**Depends on**: Sprint-05 BLI-030 (`local_calendar_agent.py` must exist) + n8n running via Docker

---

## Context

Currently, tasks live in Obsidian/LogSeq `.md` files and calendar events live in Google Calendar — with no automated conflict resolution. A task may exist in both systems with different names, duplicated as a calendar event, or missing from one side entirely.

This task builds a Universal Task Sync pipeline:
1. Python CLI collects local tasks + ICS calendar events and POSTs them to n8n
2. n8n applies conflict resolution rules and calls back into the Python API server for any writes
3. The result is a consistent state between local `.md` files and Google Calendar

The n8n workflow is the source of truth for conflict logic — editing the rules does not require touching Python code.

Key files to read before starting:
- `n8n_client.py` — `trigger(path, payload)` and `is_n8n_running()` — this is how Python calls n8n
- `api_server.py` — understand the existing `POST /webhook/add-task` endpoint (n8n calls this for Calendar→LogSeq direction)
- `local_calendar_agent.py` (Sprint-05) — `list_events(start_date, end_date)` returns `[{uid, summary, start, end}]`
- `task_utils.py` — `get_unified_tasks(obsidian_path)` returns unified task list
- `cli_commands.py` — where to add the `/sync-universal` command handler
- `config_utils.py` — `get_config_value(key, default)`

---

## What to Do

### 1. `n8n_client.py` — Add `trigger_task_sync()` helper

Add to `n8n_client.py`:

```python
def trigger_task_sync(tasks: list, events: list) -> bool:
    """
    Send unified task and calendar event payload to n8n Universal Task Sync workflow.

    tasks: list of dicts with at minimum {"title": str, "source": str, "due": str|None}
    events: list of dicts with at minimum {"uid": str, "summary": str, "start": str, "end": str}

    Returns True if n8n accepted the payload, False otherwise.
    """
    payload = {
        "tasks": tasks,
        "calendar_events": events,
        "synced_at": __import__("datetime").datetime.now().isoformat(),
    }
    return trigger("task-sync", payload)
```

### 2. `cli_commands.py` — Add `/sync-universal` command

In the chat command dispatch section, add:

```python
elif command == "sync-universal":
    handle_universal_sync()
```

Add the handler function (can be near the other sync handlers like `sync_logseq_to_obsidian()`):

```python
def handle_universal_sync():
    """Collect local tasks + ICS events and trigger n8n Universal Task Sync."""
    from n8n_client import trigger_task_sync, is_n8n_running
    from config_utils import get_config_value

    if not is_n8n_running():
        print("[yellow]n8n is not running. Start it with: docker compose up -d[/yellow]")
        return

    # Load tasks
    workspace = get_config_value("WORKSPACE_DIR", "")
    from task_utils import get_unified_tasks
    raw_tasks = get_unified_tasks(workspace)
    tasks = [
        {"title": t.get("title", t.get("text", "")), "source": t.get("source", "local"), "due": t.get("due")}
        for t in raw_tasks
    ]

    # Load calendar events from local ICS (Sprint-05 agent)
    events = []
    try:
        from local_calendar_agent import list_events
        import datetime
        today = datetime.date.today()
        week_end = today + datetime.timedelta(days=7)
        events = list_events(start_date=today, end_date=week_end)
    except ImportError:
        print("[yellow]local_calendar_agent not available — sending tasks only[/yellow]")

    ok = trigger_task_sync(tasks, events)
    if ok:
        print(f"[green]Universal Task Sync triggered — {len(tasks)} tasks, {len(events)} events sent to n8n[/green]")
    else:
        print("[red]Universal Task Sync failed — check n8n logs[/red]")
```

Also add to `COMMAND_DESCRIPTIONS` in `chat_ui.py`:
```python
"sync-universal": "Sync local tasks and ICS calendar through n8n conflict resolution",
```

### 3. `n8n-workflows/universal_task_sync.json` — n8n workflow

Create a valid n8n workflow JSON that can be imported via File → Import in the n8n UI. The workflow must contain these nodes:

**Node 1 — Webhook trigger**
- Type: `n8n-nodes-base.webhook`
- Path: `task-sync`
- HTTP Method: POST
- Response mode: `responseNode`

**Node 2 — Parse payload (Function node)**
```javascript
// Extract tasks and events from the incoming payload
const tasks = $json.body.tasks || [];
const events = $json.body.calendar_events || [];

// Build lookup: normalised event summary → event object
const eventMap = {};
for (const ev of events) {
  const key = ev.summary.trim().toLowerCase();
  eventMap[key] = ev;
}

// Classify each task
const toCreate = [];   // local task with no calendar match → create event
const skipped = [];    // local task with calendar match → skip

for (const task of tasks) {
  const key = (task.title || "").trim().toLowerCase();
  if (eventMap[key]) {
    skipped.push({ task, reason: "exists_in_calendar" });
  } else {
    toCreate.push(task);
  }
}

// Calendar-only events (no local task) → create local task
const taskTitles = new Set(tasks.map(t => (t.title || "").trim().toLowerCase()));
const toAddLocally = events.filter(ev => !taskTitles.has(ev.summary.trim().toLowerCase()));

return [{ json: { toCreate, skipped, toAddLocally } }];
```

**Node 3 — Create calendar events (HTTP Request node)**
- Iterates `toCreate` array
- Method: POST to Google Calendar via n8n's Google Calendar node (or HTTP Request to the API)
- Gated: only runs if `toCreate.length > 0`
- If Google Calendar credential not configured, log and skip

**Node 4 — Create local tasks (HTTP Request node)**
- Iterates `toAddLocally` array
- Method: POST to `http://host.docker.internal:5678/webhook/add-task` (the Python API server)
  - Note: uses `host.docker.internal` because n8n runs in Docker and needs to reach the host's `api_server.py`
- Body: `{"description": "{{ $json.summary }}", "source": "calendar"}`

**Node 5 — Response (Respond to Webhook node)**
```javascript
return {
  synced_at: new Date().toISOString(),
  created_events: $node["Parse payload"].json.toCreate.length,
  added_tasks: $node["Parse payload"].json.toAddLocally.length,
  skipped: $node["Parse payload"].json.skipped.length,
};
```

Generate the full `universal_task_sync.json` as valid n8n export format (use n8n's standard JSON schema with `nodes`, `connections`, `settings` keys). The node IDs can be UUIDs.

### 4. `README_N8N.md` — Update with Universal Task Sync section

Add:
- How to import `universal_task_sync.json` into n8n
- How to set up the Google Calendar credential in n8n (n8n UI → Credentials → Google Calendar OAuth2)
- Note: existing `token.json` / `credentials.json` are NOT used by this workflow — n8n manages its own credentials
- The `host.docker.internal` URL for the add-task webhook — verify it works on Linux with `--add-host=host-gateway:host-gateway` in Docker
- Test command: trigger `/sync-universal` from Python CLI and watch n8n execution log

### 5. `tests/test_universal_sync.py` — Write tests

```python
from unittest.mock import patch, MagicMock
import pytest


# Test 1: trigger_task_sync calls trigger("task-sync", ...) with correct payload shape
def test_trigger_task_sync_calls_n8n():
    with patch("n8n_client.trigger") as mock_trigger:
        mock_trigger.return_value = True
        from n8n_client import trigger_task_sync
        result = trigger_task_sync(
            tasks=[{"title": "Write tests", "source": "obsidian", "due": None}],
            events=[{"uid": "abc", "summary": "Team meeting", "start": "2026-04-04T09:00", "end": "2026-04-04T10:00"}]
        )
        assert result is True
        call_args = mock_trigger.call_args
        assert call_args[0][0] == "task-sync"
        payload = call_args[0][1]
        assert "tasks" in payload
        assert "calendar_events" in payload
        assert len(payload["tasks"]) == 1


# Test 2: handle_universal_sync prints warning when n8n is not running
def test_handle_universal_sync_n8n_down(capsys):
    with patch("cli_commands.is_n8n_running", return_value=False):
        from cli_commands import handle_universal_sync
        handle_universal_sync()
        # Should print a warning, not raise
        # (capsys captures Rich output as plain text)


# Test 3: handle_universal_sync calls trigger_task_sync when n8n is up
def test_handle_universal_sync_calls_trigger():
    with patch("cli_commands.is_n8n_running", return_value=True), \
         patch("cli_commands.get_config_value", return_value="/fake/vault"), \
         patch("cli_commands.get_unified_tasks", return_value=[
             {"title": "My task", "source": "obsidian", "due": None}
         ]), \
         patch("cli_commands.trigger_task_sync", return_value=True) as mock_sync:
        from cli_commands import handle_universal_sync
        handle_universal_sync()
        mock_sync.assert_called_once()
        tasks_arg = mock_sync.call_args[0][0]
        assert tasks_arg[0]["title"] == "My task"


# Test 4: handle_universal_sync handles missing local_calendar_agent gracefully
def test_handle_universal_sync_no_ics():
    with patch("cli_commands.is_n8n_running", return_value=True), \
         patch("cli_commands.get_config_value", return_value="/fake/vault"), \
         patch("cli_commands.get_unified_tasks", return_value=[]), \
         patch("cli_commands.trigger_task_sync", return_value=True), \
         patch.dict("sys.modules", {"local_calendar_agent": None}):
        from cli_commands import handle_universal_sync
        # Should not raise — degrades gracefully without ICS agent
        handle_universal_sync()
```

---

## Acceptance Criteria

- [ ] `n8n_client.trigger_task_sync(tasks, events)` exists and returns bool
- [ ] `/sync-universal` CLI command exists and is in `COMMAND_DESCRIPTIONS`
- [ ] `handle_universal_sync()` checks `is_n8n_running()` before proceeding
- [ ] `handle_universal_sync()` degrades gracefully if `local_calendar_agent` is not available
- [ ] `n8n-workflows/universal_task_sync.json` is valid n8n export format (5 nodes: Webhook, Parse, Create Events, Add Tasks, Respond)
- [ ] `README_N8N.md` updated: import steps, Google Calendar credential setup, `host.docker.internal` explanation
- [ ] `tests/test_universal_sync.py` — all 4 tests pass
- [ ] Full test suite still passes: `bash scripts/run_tests.sh`

---

## Notes

- The n8n workflow JSON must use valid n8n node types — reference existing `n8n-workflows/` files for the schema format
- `host.docker.internal` is the standard Docker DNS name to reach the host from inside a container (macOS + Windows); on Linux use `172.17.0.1` or configure `--add-host` — document both
- Do NOT hard-code API credentials in the workflow JSON — use n8n credential references (`{{$credentials.googleCalendarOAuth2Api}}`)
- If `ENABLE_GOOGLE_CALENDAR` is `false`, the Create Calendar Events node should be bypassed — implement this as an IF node before Node 3
- After finishing, run: `bash scripts/run_tests.sh` — all tests must pass before considering this task complete
