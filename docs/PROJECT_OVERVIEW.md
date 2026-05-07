# AI Agent Assistant — Architecture & Agent Reference

Technical overview of the system's agents, data flows, LLM routing, and knowledge graph design.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Sources                             │
│  Obsidian vault (.md)  ·  LogSeq graph (.md)  ·  Apple Reminders│
│  Apple Calendar (read-only)                                     │
└───────────┬─────────────────┬──────────────┬────────────────────┘
            │                 │              │
            ▼                 ▼              ▼
┌───────────────────────────────────────────────────────────────┐
│                        Integrations                           │
│  integrations/obsidian.py   integrations/logseq.py           │
│  integrations/calendar.py                                     │
└───────┬───────────────────────────────────────────┬───────────┘
        │                                           │
        ▼                                           ▼
┌──────────────────────────┐          ┌─────────────────────────┐
│         Agents           │          │      LLM Router          │
│  planning_agent          │◄────────►│  llm/router.py           │
│  knowledge_agent (KG)    │          │                          │
│  notes_agent             │          │  gemini-flash  (chat)    │
│  sync_agent              │          │  gemini-pro    (planning)│
│  reminders_agent         │          │  groq          (quick)   │
└──────────┬───────────────┘          │  ollama        (offline) │
           │                          └─────────────────────────┘
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Terminal UI (ui/)                         │
│  chat.py — multi-turn chat with history                        │
│  commands.py — /command dispatcher                             │
│  views.py — Rich-rendered calendar, task, and status views     │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Cron Orchestrator                        │
│  cron_job.py — sync · knowledge graph · morning plan           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agents

### `agents/planning_agent.py`

Generates a concrete daily or weekly schedule from the user's tasks and calendar events.

- **Entry:** `run(mode="today" | "week")`
- **Reads:** Obsidian tasks (via `ObsidianVault`), Apple Calendar events (via `CalendarReader`)
- **Writes:** Returns a markdown plan string; cron runner writes it into `Dashboard.md`
- **LLM:** `ROUTING_PLANNING` (default: `gemini-pro`)
- **Triggered by:** `/plan`, `/plan week`, `python main.py --plan`, morning cron (07:00–10:00 window)

### `agents/knowledge_agent.py`

Builds and maintains a **semantic RDF/OWL knowledge graph** over the entire Obsidian vault. The graph is persisted as a human-readable Turtle (`.ttl`) file and is SPARQL-queryable at runtime.

- **Entry:** `run(full_rebuild=False)`, `query(sparql_str)`, `graph_stats()`
- **Graph file:** `output/knowledge_graph.ttl`
- **Incremental updates:** tracks file mtimes in `output/.kg_mtimes.json` — only re-indexes changed files
- **LLM role:** `ROUTING_REASONING` (Groq) translates plain-English `/kg` questions into SPARQL
- **Triggered by:** `/kg`, `/rebuild-kg`, daily cron job

**Graph schema:**

| Class | Properties |
|---|---|
| `kn:Note` | `kn:path`, `kn:title`, `kn:modified`, `kn:text`, `kn:hasTag`, `kn:linksTo`, `kn:hasTask` |
| `kn:Task` | `kn:text`, `kn:file`, `kn:dueDate`, `kn:priority`, `kn:isDone`, `kn:hasTag` |
| `kn:Tag` | `kn:name` |

**Namespace prefix:** `PREFIX kn: <http://knowledgebase.local/>`

Broken wikilinks are indexed as `kn:danglingLink true` so they can be surfaced and fixed. The graph is rebuilt from scratch with `/rebuild-kg` or `python cron_job.py --rebuild-kg`.

### `agents/notes_agent.py`

Analyses the vault structure and suggests improvements: folder moves and new wikilinks between semantically related notes. Operates in two modes — full analysis (`/organise`) or links-only (`/links`). Both modes are dry-run by default and require explicit confirmation before applying changes.

- **Entry:** `run(subdir=None)`, `run_links_only(subdir=None)`, `apply(result)`
- **LLM:** `ROUTING_NOTES` (default: `gemini-flash`)
- **Triggered by:** `/organise`, `/links`

### `agents/sync_agent.py`

Syncs LogSeq `LATER`/`TODO` tasks into the Obsidian vault, deduplicating by task text so re-runs are safe.

- **Entry:** `run()`
- **Reads:** LogSeq journals (last `LOGSEQ_JOURNAL_DAYS` days) and all LogSeq pages
- **Writes:** Obsidian inbox note
- **Triggered by:** `/sync`, morning cron (every run)

### `agents/reminders_agent.py`

Exports Apple Reminders (via AppleScript on macOS), deduplicates against a sync ledger, and adds new items to the Obsidian inbox.

- **Entry:** `run(export_first=True)`
- **Reads:** AppleScript → `datainput/reminders.json`
- **Dedup ledger:** `datainput/synced_reminders.json`
- **Triggered by:** `/sync-reminders`

---

## Integrations

### `integrations/obsidian.py`

Direct file-system read/write for Obsidian `.md` files. No REST API dependency — operates on the vault directory via `WORKSPACE_DIR`.

Key operations:
- `ObsidianVault.get_tasks()` — parse all `[ ]` task lines with due dates, tags, and priorities
- `ObsidianVault.mark_task_done(text)` — toggle `[ ]` → `[x]`
- `ObsidianVault.list_notes()` — enumerate vault notes with titles and first lines
- `ObsidianVault.read_section(name)` / `write_section(name, content)` — named-section read/write in the inbox note
- `parse_task_metadata(line)` — extract due date, priority, tags from a task line

### `integrations/logseq.py`

Parses LogSeq journals and page files for `LATER` and `TODO` markers. Handles the `[[date]]` journal link format and nested block structure.

### `integrations/calendar.py`

Two classes:

| Class | Role |
|---|---|
| `CalendarReader` | Reads Apple Calendar events via EventKit (macOS) or ICS files |
| `CalendarWriter` | Writes `#gcal`-tagged Obsidian tasks to a local `.ics` file |

The `.ics` export path is set by `LOCAL_CALENDAR_FILE` (default: `output/local_calendar.ics`).

---

## LLM Router (`llm/router.py`)

Single entry point for all LLM calls. Task types map to providers via `.config` `ROUTING_*` keys.

```python
from llm.router import ask, stream, provider_for

response = ask("Summarise my tasks", task="planning")
for chunk in stream("What's on my calendar?", task="chat"):
    print(chunk, end="")
```

### Provider map

| Provider key | Module | Notes |
|---|---|---|
| `gemini-flash` | `llm/gemini.py` | Fast, good for chat and note queries |
| `gemini-pro` | `llm/gemini.py` | Higher-quality reasoning, used for planning |
| `groq` | `llm/groq.py` | Very low latency, used for quick/reasoning tasks |
| `ollama` | `llm/ollama.py` | Local, offline. Only active when `OLLAMA_ENABLED=true` |

### Routing config

| Task type | Config key | Default |
|---|---|---|
| Chat / freeform | `ROUTING_CHAT` | `gemini-flash` |
| Day/week planning | `ROUTING_PLANNING` | `gemini-pro` |
| Vault note queries | `ROUTING_NOTES` | `gemini-flash` |
| Fast single-turn | `ROUTING_QUICK` | `groq` |
| Reasoning / SPARQL | `ROUTING_REASONING` | `groq` |
| Offline fallback | `ROUTING_OFFLINE` | `ollama` |

### Fallback chain

If the primary provider returns an error or is unavailable, the router falls back through:
```
gemini-flash → gemini-pro → groq → ollama
```

---

## Terminal UI (`ui/`)

### `ui/chat.py`

Multi-turn conversational chat with:
- **Conversation history** persisted to `output/chat_history.json` (last 50 messages)
- **Context window:** last 6 turns sent to the LLM per request
- **Streaming output** via the router's `stream()` interface
- **Slash commands** work inline — type `/today` mid-conversation
- **Exit from chat:** `/back` returns to main loop; `/exit` or Ctrl-C exits the assistant

### `ui/commands.py`

Slash command dispatcher. Each command is a handler function; `dispatch(line)` routes `/cmd arg` to the correct handler and returns a string response or `None` (for commands that print directly).

### `ui/views.py`

Rich terminal rendering:
- `print_today(events, tasks)` — today's view with overdue highlighting
- `print_events(events)` — event list with time and calendar name
- `print_tasks(tasks)` / `print_backlog(tasks)` — task list grouped by urgency
- `print_model_routing(providers)` — provider availability and routing table
- `print_status(config, providers)` — full system health panel
- `print_help()` — command reference table

---

## Cron Orchestrator (`cron_job.py`)

Runs via launchd (macOS) or crontab on `SYNC_INTERVAL_MINUTES` (default: 30 min).

```bash
python cron_job.py              # run once and exit
python cron_job.py --loop       # continuous (for testing)
python cron_job.py --rebuild-kg # force full KG rebuild, then exit
```

**Lock file:** `output/.cron.lock` — prevents concurrent runs. Auto-cleared after 5 minutes.

**Log:** `output/cron.log` — timestamped run log.

### Job schedule

| Job | Frequency | Agents called |
|---|---|---|
| **Sync** | Every run | `sync_agent.run()` |
| **Knowledge graph** | Once daily (any time) | `knowledge_agent.run()` |
| **Morning plan** | Once daily, 07:00–10:00 | `planning_agent.run()` → writes `Dashboard.md` |

---

## Data & Output Files

| Path | Written by | Contents |
|---|---|---|
| `output/knowledge_graph.ttl` | `knowledge_agent` | Full RDF graph in Turtle format |
| `output/.kg_mtimes.json` | `knowledge_agent` | File mtime cache for incremental updates |
| `output/cron.log` | `cron_job` | Timestamped cron run log |
| `output/chat_history.json` | `ui/chat.py` | Last 50 chat messages |
| `output/local_calendar.ics` | `CalendarWriter` | ICS export of `#gcal`-tagged tasks |
| `datainput/reminders.json` | `reminders_agent` | Apple Reminders export |
| `datainput/synced_reminders.json` | `reminders_agent` | Sync dedup ledger |

---

## Configuration Reference

Full list of supported `.config` keys:

```ini
# Paths
WORKSPACE_DIR=          # Obsidian vault root (required)
LOGSEQ_DIR=             # LogSeq graph root (required for sync)
OBSIDIAN_DASHBOARD_FILE=Dashboard.md
LOGSEQ_JOURNAL_DAYS=2

# LLM routing
ROUTING_CHAT=gemini-flash
ROUTING_PLANNING=gemini-pro
ROUTING_NOTES=gemini-flash
ROUTING_QUICK=groq
ROUTING_REASONING=groq
ROUTING_OFFLINE=ollama

# Gemini
GEMINI_API_KEY=
GEMINI_FLASH_MODEL=gemini-2.0-flash
GEMINI_PRO_MODEL=gemini-2.5-flash-preview-04-17

# Groq
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile

# Ollama
OLLAMA_ENABLED=false
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_HOST=http://localhost:11434

# Planning
CHRONOTYPE=morning_owl
DEEP_WORK_START=09:00
DEEP_WORK_END=12:00
FOCUS_CATEGORIES=dev,writing,learning

# Sync
SYNC_INTERVAL_MINUTES=30

# Calendar
GCAL_TAG=gcal
LOCAL_CALENDAR_FILE=output/local_calendar.ics
APPLE_CALENDAR_NAME=Home
```
