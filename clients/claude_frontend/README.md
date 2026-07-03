# Claude Agent SDK Terminal Frontend

A Claude AI-powered terminal interface for the `ai_agent_assistant` HTTP API. Provides interactive chat and one-shot task suggestions using the Claude Agent SDK.

## Features

- **Interactive Chat Loop** (`frontend.py`): Multi-turn conversation with Claude, asking about tasks, generating plans, and managing your day
- **One-Shot Suggestions** (`suggest.py`): Fetch today's tasks and overdue items, ask Claude for top 3 focus areas
- **MCP Tools**: Custom tools that wrap the assistant API endpoints:
  - `get_tasks(filter)` — Fetch tasks (today, overdue, week, all)
  - `get_dashboard(section)` — View dashboard sections
  - `generate_plan(mode)` — Create daily/weekly plans
  - `add_task(text, due_date)` — Add new tasks
  - `mark_done(text_match)` — Mark tasks complete
  - `get_status()` — Check assistant configuration

## Setup

### Prerequisites

- Python 3.10+
- `claude` CLI installed and authenticated (`claude auth`)
- `ai_agent_assistant` API running locally or on Tailscale

### Installation

```bash
cd /Users/michaelhansen/Projects/github/ai_agent_assistant/clients/claude_frontend
pip install -r requirements.txt
```

### Configuration

Set environment variables or edit `.config` in the parent project:

```bash
# Optional — default is localhost
export ASSISTANT_API_URL="http://localhost:7890"

# API key (read from .config if not set)
export ASSISTANT_API_KEY="your-key-here"
```

To find the API key, check `ai_agent_assistant/.config`:
```bash
grep ASSISTANT_API_KEY ../../.config
```

### On Mac Mini (Remote)

The assistant API already runs as launchd service `com.mh.aiassistant.api` on
port 7890 — no need to start it manually.

**⚠️ Keychain caveat (verified 2026-07-03):** the `claude` CLI stores its
credentials in the macOS Keychain, which is only unlocked in a GUI login
session. Over plain `ssh` the CLI reports *"Not logged in"* even though the
Mac is authenticated. Run the frontend one of these ways:

1. **Local/Screen Sharing terminal on the Mini** (Keychain unlocked):
   ```bash
   cd /Users/michaelhansen/Projects/github/ai_agent_assistant/clients/claude_frontend
   ../../venv/bin/python frontend.py
   ```

2. **Via the distributed-infra queue** (worker runs under launchd in the GUI
   session, so Claude is authenticated) — from the MacBook:
   ```bash
   # payload key is "script", pin to mac-mini
   da run mac-mini 'export PATH=/usr/local/bin:$PATH && cd ~/Projects/github/ai_agent_assistant/clients/claude_frontend && ASSISTANT_API_URL=http://localhost:7890 ../../venv/bin/python suggest.py'
   ```

3. **Scheduled/launchd** (morning brief, WhatsApp bridge integration) — same
   GUI-session rule applies; anything spawned by launchd user agents works.

## Usage

### Interactive Mode

```bash
python frontend.py
```

Starts a multi-turn chat session. Example conversation:

```
Welcome to Claude Agent SDK — AI Assistant Frontend
API: http://localhost:7890

You: What's on my plate today? Give me a quick summary and top 3 focus areas.

Claude: I'll check your tasks for today...
  [Claude fetches tasks using get_tasks tool]

Today's tasks (3 total):
  ○ Finish report draft [high] (due 2026-07-03)
  ○ Code review for PR #42 [medium] (due 2026-07-03)
  ○ Team standup prep [low] (due 2026-07-03)

**Top 3 Focus Areas:**
1. **Finish report draft** (high priority, ~90 min)
2. **Code review** (medium, 30-45 min)
3. **Standup prep** (low, 15 min)

**Schedule suggestion:**
- 09:00–10:30  Deep work on report
- 10:30–11:15  Code review + lunch
- 14:00–14:30  Standup prep

You: Can you help me reschedule the report to tomorrow?
  [Continue conversation...]
```

Commands:
- `/help` — Show available commands
- `/tasks` — Show today's tasks
- `/dashboard` — Show dashboard sections
- `/plan` — Generate a daily plan
- `/exit` or `/quit` — Exit the chat

### One-Shot Mode (Suggestions)

```bash
python suggest.py
```

Outputs markdown to stdout (suitable for piping):

```markdown
**Top 3 Focus Areas:**
1. Finish report draft — estimated 90 min, high impact
2. Code review — 30-45 min, quick win
3. Standup prep — 15 min, easy

**Quick Suggestions:**
- Start with deep work on the report (most complex task)
- Block 09:00–10:30 for uninterrupted focus
- Use code review as a mid-morning break activity

**Energy Check:**
- Morning: High energy → tackle report
- After lunch: Medium energy → code review
- End of day: Low energy → prep + admin
```

Pipe to file or WhatsApp:
```bash
python suggest.py > /tmp/focus.md
python suggest.py | xargs -I {} echo "Daily focus: {}"
```

## API Endpoints Used

The frontend wraps these endpoints from `api/server.py`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Check API status |
| `/tasks` | GET | Fetch tasks (with optional filters) |
| `/dashboard` | GET | Read dashboard sections |
| `/calendar` | GET | Get today's calendar + next free slot |
| `/plan` | POST | Generate plan (mode: today or week) |
| `/status` | GET | Configuration summary |

### Request Headers
```
x-api-key: <ASSISTANT_API_KEY>
```

### Example API Calls

**Fetch today's tasks:**
```bash
curl -H "x-api-key: $(grep ASSISTANT_API_KEY ../../.config | cut -d= -f2)" \
  http://localhost:7890/tasks
```

**Generate daily plan:**
```bash
curl -X POST \
  -H "x-api-key: $(grep ASSISTANT_API_KEY ../../.config | cut -d= -f2)" \
  http://localhost:7890/plan?mode=today
```

## Architecture

### MCP Tools

Each tool is decorated with `@tool()` from the Claude SDK and runs async:

```python
@tool(name="get_tasks", description="...", input_schema={"filter": str})
async def get_tasks(args: dict) -> dict:
    """Tool implementation"""
    filter_type = args["filter"]
    result = await _api_request("/tasks")
    # Process and return
    return {"content": [...]}
```

Tools are registered with `create_sdk_mcp_server()` and passed to `ClaudeSDKClient` via `ClaudeAgentOptions.mcp_servers`.

### Error Handling

- API unreachable → graceful error message, continue
- Task not found → return empty result
- Invalid filter → default to all tasks
- SDK connection errors → exit with message

### Async Flow

- `frontend.py` uses `ClaudeSDKClient` with `async with client.connect(prompt)` and `client.stream_messages()`
- `suggest.py` uses `query()` for simple one-shot queries
- All HTTP calls are async via `httpx.AsyncClient`

## Caveats & Known Issues

1. **API Key in .config**: The client falls back to parsing `../../.config` if `ASSISTANT_API_KEY` env var is not set. This is read-only and non-destructive.

2. **Task Modification**: The HTTP API doesn't expose `PATCH` or `PUT` endpoints for adding/updating tasks. The tools provide guidance pointing to CLI commands (`/add-task`, `/done`), or can be extended later.

3. **No Streaming Calendar**: The calendar endpoint returns a full response, not streamed. For large calendars, consider pagination (future enhancement).

4. **CLI Authentication**: `claude` CLI must be logged in (`claude auth` once). The SDK uses the system `claude` command, so auth tokens are managed by the CLI.

5. **Session State**: `ClaudeSDKClient` maintains conversation state within a single async context. Reconnecting will start a new conversation.

## Future Enhancements

- [ ] Add task modification endpoints (PUT/PATCH to `/tasks/{id}`)
- [ ] Stream large calendar responses
- [ ] Support for calendar sync (Google Calendar, Apple Calendar)
- [ ] Kanban board integration (read/write to trello/linear)
- [ ] Daily digest via cron (run `suggest.py` hourly)
- [ ] WhatsApp bridge (pipe `suggest.py` output via Twilio/Waha)
- [ ] Web UI (FastHTML or Next.js wrapper around SDK)

## Troubleshooting

### "Cannot connect to API at http://localhost:7890"

Ensure the assistant is running:
```bash
cd ../../
python main.py --api
```

### "Invalid x-api-key"

Check that `ASSISTANT_API_KEY` in `.config` is non-empty and matches:
```bash
export ASSISTANT_API_KEY=$(grep ASSISTANT_API_KEY ../../.config | cut -d= -f2)
```

### "claude: command not found"

Install or authenticate the Claude CLI:
```bash
# Install
pip install --upgrade anthropic

# Authenticate
claude auth
```

### SDK Import Errors

Ensure dependencies are installed in the right environment:
```bash
pip install -r requirements.txt
python -c "from claude_agent_sdk import ClaudeSDKClient; print('OK')"
```

## License

Same as parent project (`ai_agent_assistant`).
