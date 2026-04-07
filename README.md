# AI Agent Assistant

A local-first personal AI assistant that bridges your Markdown notes (Obsidian + LogSeq), your calendar, and your task lists — all from the terminal, powered by local LLMs.

> **Primary LLM**: LM Studio (local, no cloud required)
> **Fallback chain**: LM Studio → Groq → Gemini → OpenAI → Claude

---

## What It Does

- Reads tasks from **Obsidian** and **LogSeq** (`LATER` / `TODO` markers)
- Syncs **Apple Reminders** into your Obsidian planner
- Shows your schedule as a **unix `cal`-style month grid** in the terminal
- Generates a **day-by-day AI plan** using your calendar and task data
- Pushes events to **Apple Calendar** directly from the terminal
- **Detects and surfaces overdue tasks**, categorised by your focus areas
- Triggers the full planning pipeline from **n8n** on a schedule (weekdays 08:00)
- Runs completely **offline** — no cloud accounts required by default

---

## Dependencies: What You Need Before Installing

These must be installed and running before `./install.sh` will fully succeed.

### Required

| Dependency | Why | Install |
|---|---|---|
| **Python 3.11+** | Runtime | `brew install python@3.12` (macOS) / `apt install python3.12` (Linux) |
| **Git** | Clone and updates | `brew install git` / `apt install git` |

### Local LLM — choose one (or both)

| Dependency | Why | Install |
|---|---|---|
| **LM Studio** _(recommended)_ | Primary local LLM inference — no internet required after model download. Provides a model management GUI. | [lmstudio.ai](https://lmstudio.ai) — download the macOS or Linux app, open it, load a model, and enable the local server (port 1234) |
| **Ollama** _(alternative)_ | Headless local LLM — better for Linux servers without a GUI | `curl -fsSL https://ollama.com/install.sh \| sh` then `ollama pull qwen2.5:14b` |

> You need at least one local LLM **or** a cloud API key (Gemini/OpenAI). LM Studio is the default.

### Notes & Vault Tools — you need the folders, not the apps

| Dependency | Why | Notes |
|---|---|---|
| **Obsidian vault** | Task planner and note target — agents read/write `.md` files directly | The Obsidian app does not need to be running. Set `WORKSPACE_DIR` in `.config`. |
| **LogSeq graph** | Source of `LATER`/`TODO` tasks | The LogSeq app does not need to be running. Set `LOGSEQ_DIR` in `.config`. |

### Optional — Cloud API Keys

Only needed if LM Studio / Ollama are unavailable or you want cloud fallback.

| Key | Provider | Free tier | Get your key |
|---|---|---|---|
| `GROQ_API_KEY` | Groq | Yes — generous free tier, very fast inference | [console.groq.com](https://console.groq.com) |
| `GEMINI_API_KEY` | Google AI Studio | Yes — rate-limited. `gemini-1.5-flash` has a more generous free quota than `gemini-2.0-flash`. | [aistudio.google.com](https://aistudio.google.com) |
| `OPENAI_API_KEY` | OpenAI | No | [platform.openai.com](https://platform.openai.com) |
| `CLAUDE_API_KEY` | Anthropic | No | [console.anthropic.com](https://console.anthropic.com) |

> **Adding more LLMs:** Groq hosts many open-source models (Llama, Qwen, Kimi K2, and more). See the full list at [console.groq.com/docs/models](https://console.groq.com/docs/models) and set `GROQ_MODEL` in `.config` to any active model ID.

> If you exceed your Gemini free-tier quota, the CLI will display a clear rate-limit warning and suggest switching to LM Studio for that query.

### Optional — Workflow Automation

| Dependency | Why | Install |
|---|---|---|
| **Docker** or **OrbStack** | Runs n8n for scheduled automation and n8n-based Google connector | [orbstack.dev](https://orbstack.dev) (macOS, recommended) / [docs.docker.com](https://docs.docker.com/desktop/) |
| **n8n** | Scheduled morning planning, Universal Task Sync, Google Calendar/Tasks connector | `docker compose up -d n8n` — runs automatically once Docker is available |

### Optional — Apple Integrations (macOS only)

| Dependency | Why | Notes |
|---|---|---|
| **Apple Calendar** | Push events from `/add-event` directly into Apple Calendar | Must have granted Calendar access to Terminal in System Settings → Privacy → Automation |
| **Apple Reminders** export | Sync Reminders into Obsidian planner | Run `python debug_reminders.py` to export to `datainput/reminders.json` via AppleScript |

### Optional — NanoClaw (containerised agents)

| Dependency | Why | Notes |
|---|---|---|
| **Docker** | Run ObsidianAgent and LogSeqAgent in isolated containers | Set `NANOCLAW_ENABLED=true` in `.config` after `docker compose build` |

---

## Quick Start

```bash
git clone https://github.com/yourusername/ai_agent_assistant
cd ai_agent_assistant
cp config.example .config        # edit: set WORKSPACE_DIR, LOGSEQ_DIR, LM_STUDIO_MODEL
./install.sh
./run.sh                         # start the terminal chat
```

On first run, `install.sh` will:
1. Check for Python 3.11+
2. Create `.venv` and install Python dependencies
3. Start LM Studio or Ollama (whichever is enabled)
4. Start n8n if Docker is available
5. Prompt for API keys if not already set
6. Set up a cron job for hourly background sync

To upgrade an existing installation:
```bash
./install.sh upgrade
```

---

## Configuration

All settings live in `.config` (copy from `config.example`). **Never commit `.config`** — it contains your API keys.

| Key | Description | Example |
|---|---|---|
| `LM_STUDIO_MODEL` | Model loaded in LM Studio | `qwen2.5-coder-7b-instruct-mlx` |
| `ENABLE_LM_STUDIO` | Use LM Studio as primary LLM | `true` |
| `ENABLE_OLLAMA` | Use Ollama (alternative local LLM) | `false` |
| `ENABLE_GROQ` | Use Groq cloud inference (free tier) | `false` |
| `GROQ_API_KEY` | Groq API key — get one at [console.groq.com](https://console.groq.com) | `gsk_...` |
| `GROQ_MODEL` | Groq model ID — see [console.groq.com/docs/models](https://console.groq.com/docs/models) | `llama-3.3-70b-versatile` |
| `LLM_PRIORITY` | Fallback chain | `lmstudio,groq,gemini,openai,claude` |
| `ROUTING_CHAT` | LLM for chat | `lmstudio` |
| `ROUTING_SCHEDULING` | LLM for scheduling | `lmstudio` |
| `ROUTING_PARSING` | LLM for task parsing | `lmstudio` |
| `ROUTING_PLANNING` | LLM for daily plan generation | `lmstudio` |
| `WORKSPACE_DIR` | Path to Obsidian vault | `/path/to/vault` |
| `LOGSEQ_DIR` | Path to LogSeq graph | `/path/to/logseq` |
| `OBSIDIAN_PLANNER_FILE` | Planner note (relative to vault) | `Planner.md` |
| `APPLE_CALENDAR_NAME` | Apple Calendar to push events to | `Home` |
| `FOCUS_CATEGORIES` | Categories for task organisation | `dev,writing,learning Thai` |
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
|---|---|
| `/today` | Today's calendar events + tasks due today |
| `/week` | 7-day summary — event and task counts per day |
| `/plan` | All tasks grouped by: Today, This Week, This Month, This Year, Backlog |
| `/plan today` | Filter to today's tasks and overdue only |
| `/cal` | Month grid with `*` (events) and `•` (tasks) markers |
| `/cal-day 2026-04-10` | Drill into a specific day's events and tasks |
| `/add-event` | Add event to local ICS calendar + optionally to Apple Calendar |
| `/remove-event` | Remove an upcoming ICS event |
| `/export-calendar` | Export local calendar to `.ics` file |
| `/import-calendar` | Import events from an `.ics` file |

### Tasks & Planning

| Command | Description |
|---|---|
| `/backlog` | Unified task backlog (Obsidian + LogSeq) |
| `/add-task Write tests` | Add a `LATER` task to today's LogSeq journal |
| `/done Write tests` | Mark a task done in LogSeq or Obsidian |
| `/organize` | Reorganise Planner.md: surface overdue tasks + categorise by `FOCUS_CATEGORIES` |
| `/sync-logseq` | Sync LogSeq `LATER` tasks → Obsidian planner |
| `/sync-universal` | Full task sync through n8n conflict resolution |
| `/google-tasks` | Pull Google Tasks → Obsidian; push completions back |

### LLM & Services

| Command | Description |
|---|---|
| `/models` | Show all providers — enabled/disabled, active model, live status |
| `/ask gemini <query>` | Send one query to a specific provider, bypassing routing |
| `/ask lmstudio <query>` | Same — useful when one provider hits a rate limit |
| `/routing` | Show and update LLM routing per task type |
| `/model enable\|disable <provider>` | Toggle a provider on/off |
| `/services` | Check and start local AI services |
| `/status` | Full system health dashboard |

### Research & Utilities

| Command | Description |
|---|---|
| `/cmd prioritize by deadline` | Custom AI command on your backlog |
| `/develop a FastAPI endpoint` | AI code generation |
| `/index` | Re-index notes and books for RAG search |
| `/gmail` | List snoozed and filtered emails |
| `/help` | Full command list |

---

## How the Planner Works

All agents write into **`Planner.md`** in your Obsidian vault (set by `OBSIDIAN_PLANNER_FILE`). Each agent owns a named section — sections are replaced in-place on every run, never duplicated.

| Section | Written by | When |
|---|---|---|
| `## 🚨 Overdue` | `/organize` | On demand — tasks with past due dates surfaced to top |
| `## Reminders` | `datainput_agent` | Hourly cron — Apple Reminders |
| `## LogSeq LATER Tasks` | `logseq_later_agent` | Hourly cron — LogSeq sync |
| `## Google Tasks` | `google_tasks_agent` | Hourly cron — Google Tasks pull |
| `## AI Calendar Plan` | `calendar_planning_agent` | Hourly cron (optional) |

A second file, **`Inbox.md`**, receives raw LogSeq task dumps from `/sync-logseq`. This is a staging area — tasks land here before you decide what to promote to `Planner.md`.

---

## Agent Pipeline (cron / scheduled)

```bash
python cron_job.py                              # run all agents
python cron_job.py --agents datainput logseq    # run specific agents
```

Agents run in order:
1. **datainput** — Apple Reminders → Obsidian planner → LLM re-organises planner
2. **logseq** — LogSeq `LATER` tasks → Obsidian planner block
3. **calendar_planning** — AI day/week plan → `datainput/calendar_suggestions.md`
4. **google_tasks** — Google Tasks ↔ Obsidian two-way sync

---

## n8n Workflow Automation

n8n runs as a Docker container and automates the morning pipeline on a schedule.

```bash
docker compose up -d n8n        # start n8n at http://localhost:5679
python api_server.py            # start the Python webhook callback server on port 5678
```

Import workflows from `n8n-workflows/`:

| File | Trigger | What it does |
|---|---|---|
| `morning-planning.json` | Weekdays 08:00 | Full pipeline: sync + AI plan |
| `add-task.json` | Inbound webhook | Add task to LogSeq |
| `backlog-digest.json` | Fridays 17:00 | Fetch backlog summary |
| `universal_task_sync.json` | `/sync-universal` | Conflict-resolved task/calendar sync |
| `google_tasks_sync.json` | Cron / manual | Google Tasks pull/push via n8n |

See `README_N8N.md` for detailed import and configuration steps.

---

## LLM Routing

```
ROUTING_CHAT=lmstudio          # all chat → LM Studio
ROUTING_SCHEDULING=lmstudio    # scheduling decisions → LM Studio
ROUTING_PARSING=lmstudio       # task parsing → LM Studio
ROUTING_PLANNING=lmstudio      # daily plan generation → LM Studio
LLM_PRIORITY=lmstudio,groq,gemini,openai,claude   # fallback if LM Studio unavailable
```

To route a single query to a specific provider without changing routing config:
```
/ask gemini find tasks about academic papers in obsidian
/ask groq summarise my overdue tasks
/ask lmstudio summarise my overdue tasks
```

To use Groq as a free cloud fallback (no local GPU needed):
```
ENABLE_GROQ=true
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
LLM_PRIORITY=lmstudio,groq,gemini,openai,claude
```

Browse all available Groq models at [console.groq.com/docs/models](https://console.groq.com/docs/models) and update `GROQ_MODEL` to switch.

To switch to Ollama as the primary backend:
```
ENABLE_OLLAMA=true
ENABLE_LM_STUDIO=false
ROUTING_CHAT=ollama
LLM_PRIORITY=ollama,groq,gemini,openai,claude
```

---

## Google Services Setup

Google Calendar and Tasks credentials are managed via **n8n** — no `token.json` or `credentials.json` required in Python.

1. Start n8n: `docker compose up -d n8n`
2. Open `http://localhost:5679` → Credentials → New → Google Calendar OAuth2
3. Follow the OAuth prompts — credentials are stored inside n8n, not on disk

---

## Tests

```bash
bash scripts/run_tests.sh       # full suite with coverage
pytest tests/ -v                # verbose per-test output
```

Current status: 95 tests passing, 1 skipped.

---

## License

MIT
