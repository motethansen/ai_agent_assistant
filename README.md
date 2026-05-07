# AI Agent Assistant

A **local-first personal AI assistant** that bridges your Markdown notes (Obsidian + LogSeq), Apple Calendar, and task lists — all from the terminal, powered by a smart LLM routing layer. Optimised for headless, low-memory operation on Apple Silicon and Linux.

> **Primary LLMs:** Gemini Flash (chat/notes) · Gemini Pro (planning) · Groq (fast queries)
> **Offline fallback:** Ollama (local, headless)

---

## What It Does

- **Reads tasks** from Obsidian and LogSeq (`LATER` / `TODO` markers) and Apple Reminders
- **Generates AI plans** (daily or weekly) using your calendar events and task backlog
- **Builds a semantic knowledge graph** (RDF/OWL) over your entire vault — queryable in plain English
- **Suggests wikilinks and folder moves** to keep your vault well-organised
- **Syncs LogSeq → Obsidian** incrementally, deduplicating on every run
- **Exports calendar events** from tagged Obsidian tasks to `.ics`
- **Multi-turn chat** with full conversation history and streaming output
- **Runs a background cron** every 30 minutes: sync + knowledge graph + morning plan
- Works completely **offline** with Ollama — no cloud accounts required

---

## Dependencies

### Required

| Dependency | Why | Install |
|---|---|---|
| **Python 3.11+** | Runtime | `brew install python@3.12` / `apt install python3.12` |
| **Git** | Clone and updates | `brew install git` / `apt install git` |

### Optional — Cloud API Keys

At least one key is recommended for full functionality.

| Key | Provider | Free tier | Notes |
|---|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio | Yes — generous free quota | Primary for chat and planning |
| `GROQ_API_KEY` | Groq | Yes — very fast inference | Best for quick/reasoning tasks |
| `OLLAMA_ENABLED` | Local (no key) | Always free | Set `OLLAMA_ENABLED=true` in `.config` |

### Optional — Local LLM (Offline)

| Dependency | Why | Install |
|---|---|---|
| **Ollama** | Headless local LLM — zero cloud dependency | `curl -fsSL https://ollama.com/install.sh \| sh` then `ollama pull qwen2.5:7b` |

### Optional — Apple Integrations (macOS only)

| Integration | How | Notes |
|---|---|---|
| **Apple Reminders** | `/sync-reminders` exports via AppleScript | Requires Terminal access in System Settings → Privacy → Automation |
| **Apple Calendar** | `APPLE_CALENDAR_NAME` in `.config` | Read-only via `CalendarReader` |

---

## Quick Start

```bash
git clone https://github.com/motethansen/ai_agent_assistant
cd ai_agent_assistant
cp config.example .config        # edit: set WORKSPACE_DIR, API keys
./install.sh
./run.sh                         # start the terminal assistant
```

On first run, `install.sh` will:
1. Check for Python 3.11+
2. Create a `.venv` and install all Python dependencies
3. Validate your `.config` and warn about any missing keys
4. Register a background cron job for sync + knowledge graph updates

To upgrade an existing installation:
```bash
./install.sh upgrade
```

---

## Configuration

All settings live in `.config` (copy from `config.example`). **Never commit `.config`** — it contains your API keys.

### Paths

| Key | Description | Example |
|---|---|---|
| `WORKSPACE_DIR` | Obsidian vault root | `/path/to/vault` |
| `LOGSEQ_DIR` | LogSeq graph root | `/path/to/logseq` |
| `OBSIDIAN_DASHBOARD_FILE` | Dashboard note (relative to vault) | `Dashboard.md` |
| `LOGSEQ_JOURNAL_DAYS` | Days of journals to scan | `2` |

### LLM Routing

| Key | Default | Description |
|---|---|---|
| `ROUTING_CHAT` | `gemini-flash` | LLM for chat and freeform questions |
| `ROUTING_PLANNING` | `gemini-pro` | LLM for daily/weekly plan generation |
| `ROUTING_NOTES` | `gemini-flash` | LLM for vault search and note questions |
| `ROUTING_QUICK` | `groq` | LLM for fast single-turn queries |
| `ROUTING_REASONING` | `groq` | LLM for SPARQL generation and knowledge graph queries |
| `ROUTING_OFFLINE` | `ollama` | Offline fallback when cloud providers are unavailable |

### LLM Providers

| Key | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio key |
| `GEMINI_FLASH_MODEL` | Flash model ID (default: `gemini-2.0-flash`) |
| `GEMINI_PRO_MODEL` | Pro model ID (default: `gemini-2.5-flash-preview-04-17`) |
| `GROQ_API_KEY` | Groq API key |
| `GROQ_MODEL` | Groq model ID (default: `llama-3.3-70b-versatile`) |
| `OLLAMA_ENABLED` | `true` / `false` |
| `OLLAMA_MODEL` | Ollama model (default: `qwen2.5:7b`) |
| `OLLAMA_HOST` | Ollama server URL (default: `http://localhost:11434`) |

### Planning

| Key | Description | Example |
|---|---|---|
| `CHRONOTYPE` | Shapes plan scheduling | `morning_owl` |
| `DEEP_WORK_START` | Focus block start | `09:00` |
| `DEEP_WORK_END` | Focus block end | `12:00` |
| `FOCUS_CATEGORIES` | Task categories for plan prioritisation | `dev,writing,learning` |

---

## Terminal Commands

Start the assistant: `./run.sh` or `python main.py`

### Views

| Command | Description |
|---|---|
| `/today` | Today's calendar events + tasks due today |
| `/week` | 7-day task and event overview |
| `/cal` | Upcoming calendar events (default 14 days) |
| `/cal <N>` | Events over the next N days |
| `/status` | System status — providers, vault path, config health |
| `/model` | Show LLM routing table |

### Planning & Tasks

| Command | Description |
|---|---|
| `/plan` | AI-generated schedule for today |
| `/plan week` | AI-generated 7-day plan |
| `/backlog` | All pending tasks grouped by urgency |
| `/add-task <text>` | Add task to Obsidian inbox (supports `due:YYYY-MM-DD`) |
| `/done <text>` | Mark a task complete in Obsidian |

### Notes & Vault

| Command | Description |
|---|---|
| `/notes <question>` | Ask a question about your Obsidian vault |
| `/organise` | Suggest folder moves and wikilinks (dry run with confirmation) |
| `/links` | Suggest wikilinks only (dry run with confirmation) |

### Knowledge Graph (Semantic Database)

| Command | Description |
|---|---|
| `/kg` | Show knowledge graph stats (notes, tasks, tags, links, triples) |
| `/kg <question>` | Query the graph in plain English — converts to SPARQL automatically |
| `/rebuild-kg` | Force a full knowledge graph rebuild from scratch |

### Sync

| Command | Description |
|---|---|
| `/sync` | Run LogSeq → Obsidian sync |
| `/sync-reminders` | Export Apple Reminders → Obsidian inbox |
| `/cal-export` | Export `#gcal`-tagged tasks to `.ics` file |

### Chat & System

| Command | Description |
|---|---|
| `/chat` | Open multi-turn chat mode with history |
| `/help` | Show full command list |
| `/exit` or `/quit` | Exit the assistant |

---

## Knowledge Graph

The assistant builds a **semantic RDF/OWL knowledge graph** over your Obsidian vault. It indexes notes, tasks, tags, and wikilinks into a Turtle (`.ttl`) file and exposes a SPARQL query interface.

```
output/knowledge_graph.ttl    # persisted graph (human-readable Turtle)
output/.kg_mtimes.json        # mtime cache for incremental updates
```

**Graph schema:**

| Class | Properties |
|---|---|
| `kn:Note` | `kn:path`, `kn:title`, `kn:modified`, `kn:text`, `kn:hasTag`, `kn:linksTo`, `kn:hasTask` |
| `kn:Task` | `kn:text`, `kn:file`, `kn:dueDate`, `kn:priority`, `kn:isDone`, `kn:hasTag` |
| `kn:Tag` | `kn:name` |

**Example queries via `/kg`:**

```
/kg show all overdue tasks
/kg which notes link to my project notes?
/kg tasks tagged #urgent due this week
/kg find notes without any outgoing links
```

The `/kg` command translates plain English into SPARQL, executes it, and renders results as a table. Use `/rebuild-kg` after large vault reorganisations; incremental updates run automatically via cron.

---

## Agent Pipeline (Background Cron)

The cron runner executes on `SYNC_INTERVAL_MINUTES` (default 30 min) via launchd (macOS) or crontab:

```bash
python cron_job.py              # run once and exit
python cron_job.py --loop       # run continuously (for manual testing)
python cron_job.py --rebuild-kg # force full knowledge graph rebuild
```

**Jobs and their frequency:**

| Job | Frequency | What it does |
|---|---|---|
| **Sync** | Every run | LogSeq `LATER`/`TODO` tasks → Obsidian |
| **Knowledge graph** | Once daily (any time) | Incremental RDF index update |
| **Morning plan** | Once daily (07:00–10:00 window) | AI schedule → `Dashboard.md` |

---

## CLI Flags

```bash
python main.py                  # interactive terminal (default)
python main.py --plan           # generate today's plan and exit
python main.py --plan week      # generate weekly plan and exit
python main.py --sync           # run LogSeq sync and exit
python main.py --status         # show system status and exit
python main.py --today          # show today's tasks and events and exit
python main.py --chat           # start directly in chat mode
```

---

## Tests

```bash
pytest                          # full suite
pytest tests/ -v                # verbose per-test output
pytest --html=output/test_report.html   # with HTML report
```

---

## License

MIT
