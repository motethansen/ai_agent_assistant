# AI Agent Assistant

A local-first personal AI assistant that bridges your Markdown notes (Obsidian + LogSeq), your calendar, and your task lists — all from the terminal, powered by local LLMs. Optimized for **headless, low-memory operation** on Apple Silicon and Linux.

> **Primary LLM**: Ollama (local, headless)
> **Fallback chain**: Ollama → Groq → Gemini → OpenAI → Claude

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

### Local LLM (Headless)

| Dependency | Why | Install |
|---|---|---|
| **Ollama** | **Headless local LLM** — zero GUI overhead, significantly faster and lower-RAM. Best for Apple Silicon and Linux. | `curl -fsSL https://ollama.com/install.sh \| sh` then `ollama pull qwen3.5:9b` |

> You need at least one local LLM **or** a cloud API key (Gemini/OpenAI). **Ollama is the primary backend.**

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
| `AI_Assistant_Token` | HuggingFace Inference API | Yes — free tier gives access to thousands of open-source models | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |

> **Adding more LLMs:** Groq hosts many open-source models (Llama, Qwen, Kimi K2, and more). See the full list at [console.groq.com/docs/models](https://console.groq.com/docs/models) and set `GROQ_MODEL` in `.config` to any active model ID.

> **HuggingFace models:** Browse inference-ready models at [huggingface.co/models](https://huggingface.co/models) — filter by "Inference API" to find ones available on the free tier. Confirmed working: `Qwen/Qwen2.5-72B-Instruct` (chat), `Qwen/Qwen2.5-Coder-32B-Instruct` (code), `facebook/bart-large-cnn` (summarisation).

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

### Optional — Tool-Calling & Automation

| Dependency | Why | Install |
|---|---|---|
| **FastAPI** | Internal **API Server** (`api_server.py`) — serves as the "brain" and Tool hub. Replaces NanoClaw Docker skills. | `pip install fastapi uvicorn` (done by installer) |
| **Docker** | Runs n8n for scheduled automation and Google connector | [orbstack.dev](https://orbstack.dev) (macOS) / [docs.docker.com](https://docs.docker.com/desktop/) |

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
| `AI_Assistant_Token` | HuggingFace token — used for RAG embeddings and the Inference API | `hf_...` |
| `ENABLE_OLLAMA` | Use Ollama (primary local backend) | `true` |
| `OLLAMA_MODEL` | Default Ollama model | `qwen3.5:9b` |
| `OLLAMA_NUM_CTX` | Context window size (optimized for RAM) | `4096` |
| `LLM_PRIORITY` | Fallback chain | `ollama,groq,gemini,openai,claude` |
| `ROUTING_CHAT` | LLM for chat | `ollama` |
| `ROUTING_SCHEDULING` | LLM for scheduling | `ollama` |
| `ROUTING_PARSING` | LLM for task parsing | `ollama` |
| `ROUTING_PLANNING` | LLM for daily plan generation | `ollama` |
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
ROUTING_CHAT=ollama          # all chat → Ollama
ROUTING_SCHEDULING=ollama    # scheduling decisions → Ollama
ROUTING_PARSING=ollama       # task parsing → Ollama
ROUTING_PLANNING=ollama      # daily plan generation → Ollama
LLM_PRIORITY=ollama,groq,gemini,openai,claude   # fallback if Ollama unavailable
```

To route a single query to a specific provider without changing routing config:
```
/ask gemini find tasks about academic papers in obsidian
/ask groq summarise my overdue tasks
/ask ollama summarise my overdue tasks
```

To use Groq as a free cloud fallback (no local GPU needed):
```
ENABLE_GROQ=true
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
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
