# AI Agent Assistant

A local-first personal AI assistant that bridges your Markdown notes (Obsidian + LogSeq), your calendar, and your task lists — all from the terminal, powered by local LLMs.

> **Primary LLM**: LM Studio (local, no cloud required)  
> **Fallback chain**: LM Studio → Gemini → OpenAI → Claude

---

## What It Does

- Reads tasks from **Obsidian** and **LogSeq** (`LATER` / `TODO` markers)
- Syncs **Apple Reminders** into your Obsidian planner
- Shows your schedule as a **unix `cal`-style month grid** in the terminal
- Generates a **day-by-day AI plan** using your calendar and task data
- Triggers the full planning pipeline from **n8n** on a schedule (weekdays 08:00)
- Runs completely **offline** — no cloud accounts required

---

## Quick Start

```bash
git clone https://github.com/yourusername/ai_agent_assistant
cd ai_agent_assistant
cp config.example .config        # fill in WORKSPACE_DIR, LOGSEQ_DIR, model names
./install.sh
./run.sh                         # start the terminal chat
```

---

## Requirements

- macOS or Linux, Python 3.11+
- [LM Studio](https://lmstudio.ai) — load any GGUF/MLX model, enable local server on port 1234
- Obsidian vault and/or LogSeq graph (paths set in `.config`)
- Docker / OrbStack (optional — for n8n workflow automation)

---

## Configuration

All settings live in `.config` (copy from `config.example`). **Never commit `.config`** — it contains your API keys.

| Key | Description | Example |
|-----|-------------|---------|
| `LM_STUDIO_MODEL` | Model loaded in LM Studio | `qwen2.5-coder-7b-instruct-mlx` |
| `ENABLE_LM_STUDIO` | Use LM Studio as primary LLM | `true` |
| `ENABLE_OLLAMA` | Use Ollama (alternative local LLM) | `false` |
| `LLM_PRIORITY` | Fallback chain | `lmstudio,gemini,openai,claude` |
| `ROUTING_CHAT` | LLM for chat | `lmstudio` |
| `ROUTING_SCHEDULING` | LLM for scheduling | `lmstudio` |
| `ROUTING_PARSING` | LLM for task parsing | `lmstudio` |
| `ROUTING_PLANNING` | LLM for daily plan generation | `lmstudio` |
| `WORKSPACE_DIR` | Path to Obsidian vault | `/path/to/vault` |
| `LOGSEQ_DIR` | Path to LogSeq graph | `/path/to/logseq` |
| `OBSIDIAN_PLANNER_FILE` | Planner note (relative to vault) | `Planner.md` |
| `DEEP_WORK_START/END` | Focus window for plan scheduling | `09:00` / `12:00` |
| `CHRONOTYPE` | Used to shape plan suggestions | `morning_owl` |

Update any key live from the chat:
```
/settings set LM_STUDIO_MODEL qwen2.5-coder-7b-instruct-mlx
```

---

## Terminal Chat Commands

Start the chat: `./run.sh` or `python main.py --chat`

### Calendar & Tasks

| Command | Description |
|---------|-------------|
| `/today` | Today's calendar events + tasks due today |
| `/week` | 7-day summary — event and task counts per day |
| `/plan` | All tasks grouped by: Today, This Week, This Month, This Year, Backlog |
| `/plan today` | Filter to today's tasks and overdue only |
| `/plan week` | Tasks due within 7 days |
| `/plan month` | Tasks due within 30 days |
| `/plan year` | Tasks due within 365 days |
| `/plan backlog` | Tasks with no due date |
| `/cal` | Month grid with `*` (events) and `•` (tasks) markers |
| `/cal 5 2026` | Calendar for any month/year |
| `/cal-day 2026-04-10` | Drill into a specific day's events and tasks |

### Planning

| Command | Description |
|---------|-------------|
| `--morning` | Run the full morning planning pipeline (sync + AI plan) |
| `/sync-logseq` | Sync LogSeq `LATER` tasks → Obsidian planner |
| `/sync-universal` | Full task sync through n8n conflict resolution |
| `/google-tasks` | Pull Google Tasks → Obsidian; push completions back |

### Tasks

| Command | Description |
|---------|-------------|
| `/backlog` | Unified task backlog (Obsidian + LogSeq) |
| `/add-task Write tests` | Add a `LATER` task to today's LogSeq journal |
| `/done Write tests` | Mark a task done in LogSeq or Obsidian |
| `/add-event` | Add an event to your local ICS calendar |
| `/remove-event` | Remove an upcoming ICS event |
| `/export-calendar` | Export local calendar to `.ics` file |
| `/import-calendar` | Import events from an `.ics` file |

### LLM & Services

| Command | Description |
|---------|-------------|
| `/models` | Show installed models and enable/disable |
| `/routing` | Show current LLM routing config |
| `/services` | Check and start local AI services |
| `/settings` | View or update config keys and API keys |
| `/status` | Full system health dashboard |

### Research & Utilities

| Command | Description |
|---------|-------------|
| `/cmd prioritize by deadline` | Custom AI command on your backlog |
| `/develop a FastAPI endpoint` | AI code generation |
| `/index` | Re-index notes and books for RAG search |
| `/gmail` | List snoozed and filtered emails |
| `/help` | Full command list |

---

## CLI Flags

```bash
python main.py --chat          # interactive terminal chat
python main.py --morning       # run morning planning pipeline (non-interactive)
python main.py --plan          # interactive planning session with calendar
python main.py --backlog       # print unified task backlog and exit
python main.py --today         # print today view and exit
python main.py --dry-run       # plan without writing to calendar
python main.py --stats         # show focus analytics
```

---

## Agent Pipeline (cron / scheduled)

```bash
python cron_job.py                          # run all agents
python cron_job.py --agents datainput logseq  # run specific agents
```

Agents run in order:
1. **datainput** — Apple Reminders → Obsidian planner
2. **logseq** — LogSeq `LATER` tasks → Obsidian planner block
3. **calendar_planning** — AI-generated day/week plan → `datainput/calendar_suggestions.md`
4. **google_tasks** — Google Tasks ↔ Obsidian two-way sync

---

## n8n Workflow Automation

n8n runs as a Docker container and automates the morning pipeline on a schedule.

```bash
docker compose up -d n8n        # start n8n at http://localhost:5679
python api_server.py            # start the Python webhook server on port 5678
```

Import workflows from `n8n-workflows/`:
- `morning-planning.json` — fires weekdays at 08:00, calls `/webhook/morning-plan`
- `add-task.json` — n8n → add task to LogSeq
- `backlog-digest.json` — n8n → fetch backlog summary
- `universal_task_sync.json` — n8n conflict resolution for tasks
- `google_tasks_sync.json` — Google Tasks pull/push via n8n

The `POST /webhook/morning-plan` endpoint runs the full pipeline:
datainput sync → LogSeq LATER sync → AI plan (LM Studio) → writes `datainput/calendar_suggestions.md`

---

## LLM Routing

```
ROUTING_CHAT=lmstudio          → all chat goes to LM Studio
ROUTING_SCHEDULING=lmstudio    → scheduling decisions via LM Studio
ROUTING_PARSING=lmstudio       → task parsing via LM Studio
ROUTING_PLANNING=lmstudio      → daily plan generation via LM Studio
LLM_PRIORITY=lmstudio,gemini,openai,claude   → fallback order if LM Studio unavailable
```

To switch to Ollama:
```
ENABLE_OLLAMA=true
ENABLE_LM_STUDIO=false
ROUTING_CHAT=ollama
ROUTING_PLANNING=ollama
LLM_PRIORITY=ollama,gemini,openai,claude
```

---

## Google API Setup

Cloud Google services are optional. See `docs/GOOGLE_API_SETUP.md` for setup steps.  
Google Calendar and Tasks credentials are managed via **n8n** — no `token.json` required in Python.

---

## License

MIT
