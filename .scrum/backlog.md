# Product Backlog — AI Agent Assistant

> Maintained by: Product Owner + Scrum Master
> Last updated: 2026-04-02
> Format: ID | Priority | Story | Acceptance Criteria | Estimate | Status

---

## Epics

| Epic ID | Title | Description | Status |
|---------|-------|-------------|--------|
| E01 | Remove OpenClaw | Strip all OpenClaw code, config, and docs from the project | Sprint-01 |
| E02 | Ollama-First Local LLM | Make Ollama the primary local LLM with multi-model support | Sprint-01 |
| E03 | LogSeq Task Management | Read and write tasks from LogSeq journals and pages via CLI | Sprint-01 |
| E04 | Obsidian Task Management | Read/write Obsidian tasks; cross-sync with LogSeq | Sprint-02 |
| E05 | Google Calendar Planning Agent | Regular planning agent that checks calendar and confirms scheduling with user | Sprint-02 |
| E06 | CLI Personal Agent | Clean CLI entry point using local Ollama models, no Streamlit required | Sprint-02 |
| E07 | n8n Workflow Integration | Event-driven agent triggers via n8n — expose HTTP API and provide workflow templates | Sprint-01 |
| E08 | Agent Documentation & Scrum Registration | Register all agents added outside sprint process into backlog with full docs | Sprint-04 |
| E09 | Code Quality & Maintainability | Split main.py, expand test suite, enforce structural hygiene | Sprint-04 |
| E10 | Observability & Monitoring | Health dashboard, log rotation, and service status visibility | Sprint-04 |
| E11 | Terminal Task Visibility | /today, /week calendar view, and terminal reminders via at/osascript | Sprint-04 |
| E12 | Local ICS Calendar Engine | Replace Google Calendar API with local RFC 5545 ICS file — add, remove, export, import events | Sprint-05 |
| E13 | Google Tasks Two-Way Sync | Pull tasks from Google Tasks into Obsidian; push Obsidian completions back to Google Tasks | Sprint-05 |

---

## Backlog Items

### 🔴 Priority 1 — Must Have

#### BLI-001
- **Story**: As a developer, I want all OpenClaw references removed so the project has no dependency on an external gateway service
- **Acceptance Criteria**:
  - [x] `ai_orchestration.py` — no OpenClaw imports, functions, or routing logic
  - [x] `monitoring_agent.py` — no OpenClaw health check
  - [x] `main.py` — no OpenClaw startup, key management, or status references
  - [x] `chat_ui.py` and `app.py` — no OpenClaw status rendering
  - [x] `config.template` — no OpenClaw settings
  - [x] `OPENCLAW_SETUP.md` deleted
  - [x] `test_openclaw_direct.py` deleted
  - [x] `scripts/check_ai_working.py` — OpenClaw sections removed
  - [x] `tests/` — all OpenClaw test cases removed or updated
  - [x] `README.md`, `INSTALL.md` — all OpenClaw references removed
  - [ ] `PLAN.md` — 8 historical references remain (low priority cleanup)
- **Epic**: E01
- **Estimate**: L
- **Status**: ✅ Done — 2026-03-14 (git commit pending for file deletions)

#### BLI-002
- **Story**: As a user, I want Ollama to be the primary local LLM so that all task processing, parsing, and chat runs locally without cloud dependency by default
- **Acceptance Criteria**:
  - [ ] `ai_orchestration.py` routes all tasks to Ollama by default
  - [ ] Fallback chain is: `ollama → gemini → openai → claude`
  - [ ] `config.template` updated — only `ENABLE_OLLAMA=true` enabled by default
  - [ ] `ROUTING_SCHEDULING`, `ROUTING_PARSING`, `ROUTING_CHAT` all default to `ollama`
  - [ ] `LLM_PRIORITY=ollama,gemini,openai,claude`
  - [ ] `monitoring_agent.py` only checks Ollama health
- **Epic**: E02
- **Estimate**: M
- **Status**: ✅ Done — 2026-03-15 (T01-03)
- **Notes**: Depends on BLI-001 (done)

#### BLI-003
- **Story**: As a user, I want to select from my installed Ollama models at startup or via a CLI command so I can switch between llama3, mistral, qwen2, etc. without editing config files
- **Acceptance Criteria**:
  - [ ] On startup, system queries `ollama list` and shows available models
  - [ ] `/models` CLI command shows installed Ollama models and allows selection
  - [ ] Selected model is persisted to config for the session
  - [ ] Graceful fallback message if Ollama is not running
- **Epic**: E02
- **Estimate**: M
- **Status**: ✅ Done — 2026-03-15 (T01-03)

#### BLI-004
- **Story**: As a user, I want a working LogSeq task integration so that tasks written as `LATER` or `TODO` in my journals and pages are read by the planning agent
- **Acceptance Criteria**:
  - [ ] `logseq_agent.py` correctly parses LATER/TODO tasks from `journals/YYYY_MM_DD.md`
  - [ ] Tasks from pages (`pages/<name>.md`) are also collected
  - [ ] `LOGSEQ_DIR` in config is clearly documented with Linux and Mac example paths
  - [ ] `python main.py --backlog` shows LogSeq tasks in the unified task list
  - [ ] Tasks include source attribution (file + line number)
  - [ ] A minimal working config snippet provided in INSTALL.md
- **Epic**: E03
- **Estimate**: M
- **Status**: ✅ Done — 2026-03-15 (T01-04)

#### BLI-005
- **Story**: As a user, I want to add and update tasks in LogSeq from the CLI so I can capture tasks without opening the LogSeq app
- **Acceptance Criteria**:
  - [ ] `/add-task` CLI command creates a new `LATER` entry in today's LogSeq journal file
  - [ ] Tasks can be marked done from the CLI (updates the source `.md` file directly)
  - [ ] No LogSeq app needs to be running — operates on markdown files directly
- **Epic**: E03
- **Estimate**: M
- **Status**: ✅ Done — 2026-03-15 (T01-05)

---

### 🟡 Priority 2 — Should Have

#### BLI-010
- **Story**: As a user, I want Obsidian tasks to be readable and writable from the CLI so I can manage my full task list from one place
- **Acceptance Criteria**:
  - [ ] `obsidian_agent.py` reads tasks from `WORKSPACE_DIR` via direct file parsing (no Obsidian app required)
  - [ ] Tasks can be marked done or updated from the CLI
  - [ ] `WORKSPACE_DIR` documented clearly in config and INSTALL.md
  - [ ] `python main.py --backlog` shows Obsidian tasks alongside LogSeq tasks
- **Epic**: E04
- **Estimate**: M
- **Status**: ✅ Done — 2026-03-15 (T02-01)

#### BLI-011
- **Story**: As a user, I want tasks synced from LogSeq to Obsidian so Obsidian is my single task dashboard regardless of where tasks were captured
- **Acceptance Criteria**:
  - [x] Sync command pulls new LATER/TODO tasks from LogSeq and appends them to a configured Obsidian page (e.g. `Inbox.md`)
  - [x] Duplicate detection prevents re-adding already-synced tasks
  - [x] Sync triggered via `/sync-logseq` CLI command or automatically on startup
  - [x] Each synced task gets a `#logseq` source tag
- **Epic**: E04
- **Estimate**: L
- **Status**: ✅ Done — 2026-03-15 (T02-02)

#### BLI-012
- **Story**: As a user, I want a planning agent that checks my Google Calendar and asks me whether to schedule pending tasks so my calendar reflects my actual priorities
- **Acceptance Criteria**:
  - [x] Planning agent reads pending tasks from Obsidian + LogSeq unified list
  - [x] Agent reads Google Calendar for the next 7 days and identifies free slots
  - [x] Agent proposes a schedule (task → time slot) and presents it in the CLI
  - [x] User confirms, skips, or reschedules each suggestion interactively
  - [x] Confirmed tasks are added to Google Calendar via `calendar_manager`
- **Epic**: E05
- **Estimate**: L
- **Status**: ✅ Done — 2026-03-15 (T02-03)

#### BLI-013
- **Story**: As a user, I want the planning agent to run on a regular schedule so I get prompted for calendar planning without remembering to run it manually
- **Acceptance Criteria**:
  - [x] A cron job or systemd timer triggers `python main.py --plan` daily at a configurable time
  - [x] Setup instructions in INSTALL.md for both cron and systemd
  - [x] Agent skips silently if no unscheduled tasks are found
  - [x] Prints a clear summary when planning is ready for review
- **Epic**: E05
- **Estimate**: M
- **Status**: ✅ Done — 2026-03-15 (T02-04)

#### BLI-014
- **Story**: As a user, I want a clean CLI entry point using my installed Ollama models so I can run the assistant from any terminal without needing Streamlit
- **Acceptance Criteria**:
  - [x] `python main.py` launches CLI chat cleanly with no web UI dependency
  - [x] Available Ollama models shown at startup
  - [x] Core commands work: `/backlog`, `/plan`, `/sync`, `/add-task`, `/review`
  - [x] `--no-web` flag (or equivalent) documented clearly
- **Epic**: E06
- **Estimate**: S
- **Status**: ✅ Done — 2026-03-15 (T02-05)

---

### 🟢 Priority 3 — Nice to Have

#### BLI-020
- **Story**: As a user, I want per-task-type model routing across multiple Ollama models so I can experiment with different local models for chat vs scheduling vs parsing
- **Acceptance Criteria**:
  - [x] `ROUTING_CHAT`, `ROUTING_SCHEDULING`, `ROUTING_PARSING` each accept any Ollama model name
  - [x] Model names map to full Ollama identifiers (`llama3:8b`, `mistral:latest`, `qwen2.5:14b`, etc.)
  - [x] `/routing` CLI command shows current assignments and allows interactive change
- **Epic**: E06
- **Estimate**: M
- **Status**: ✅ Done — 2026-03-15 (T03-01)

#### BLI-021
- **Story**: As a developer, I want a minimal `config.example` with sane defaults so contributors can get started in under 5 minutes
- **Acceptance Criteria**:
  - [x] `config.example` contains only the settings needed for Ollama + LogSeq + Obsidian + Google Calendar
  - [x] Every setting has a one-line comment
  - [x] Cloud API keys shown but commented out for reference
  - [x] OpenClaw section fully absent
- **Epic**: E02
- **Estimate**: S
- **Status**: ✅ Done — 2026-03-15 (T03-02)

#### BLI-022
- **Story**: As a user, I want an evening review agent to summarise what I completed that day across Obsidian and LogSeq so I have a daily log without manual effort
- **Acceptance Criteria**:
  - [x] `/review` shows tasks marked done today across Obsidian and LogSeq
  - [x] Summary generated by local LLM and printed in CLI
  - [x] Optionally appended to today's LogSeq journal file
- **Epic**: E06
- **Estimate**: M
- **Status**: ✅ Done — 2026-03-15 (T03-03)

#### BLI-023
- **Story**: As a user, I want a webhook HTTP API so that n8n workflows can trigger agent tasks (add task, run plan, query backlog) without me running a CLI command manually
- **Acceptance Criteria**:
  - [ ] `api_server.py` — FastAPI server exposing at minimum: `POST /webhook/add-task`, `GET /webhook/backlog`, `POST /webhook/plan`
  - [ ] Server reads `LOGSEQ_DIR` and `WORKSPACE_DIR` from `.env` config (same as main.py)
  - [ ] Each endpoint returns JSON with `status`, `message`, and relevant data
  - [ ] `POST /webhook/add-task` body: `{"description": "...", "date": "YYYY-MM-DD" (optional)}`
  - [ ] API port configurable via `WEBHOOK_PORT` in `.config` (default: `5678`)
  - [ ] Server can be started independently: `python api_server.py`
  - [ ] `docker-compose.yml` added with n8n service pointing to the same network as the API
  - [ ] `config.template` updated with `WEBHOOK_PORT` and `N8N_PORT` settings
- **Epic**: E07
- **Estimate**: M
- **Status**: ✅ Done — 2026-03-15 (T01-06 / T01-07)

#### BLI-024
- **Story**: As a user, I want ready-made n8n workflow JSON templates so I can import them and immediately have event-driven automations without building from scratch
- **Acceptance Criteria**:
  - [ ] `n8n-workflows/` directory created with at minimum 3 workflow JSON files
  - [ ] Workflow 1: **Morning Planning** — cron trigger at 8am → `POST /webhook/plan` → sends summary to console/webhook
  - [ ] Workflow 2: **Add Task from Text** — manual/webhook trigger with task text → `POST /webhook/add-task`
  - [ ] Workflow 3: **Backlog Digest** — cron trigger weekly → `GET /webhook/backlog` → formats and outputs task list
  - [ ] Each workflow JSON is importable via n8n UI (File → Import)
  - [ ] `README_N8N.md` added explaining: how to start n8n, import workflows, configure the webhook URL
- **Epic**: E07
- **Estimate**: S
- **Status**: ✅ Done — 2026-03-15 (T01-06 / T01-07)
- **Notes**: Depends on BLI-023 (API must exist before workflows can be built)

---

---

### Sprint-04 Items

#### BLI-025 — Register new agents in scrum
- **Story**: As a team, we want the three agents added post-Sprint-03 properly documented in the scrum backlog so their purpose, config requirements, and entry points are tracked
- **Acceptance Criteria**:
  - [x] `datainput_agent.py` documented: reads Apple Reminders JSON → Obsidian planner, LLM organiser. Config: `WORKSPACE_DIR`, `OBSIDIAN_PLANNER_FILE`. Entry: `run(organise=True)`
  - [x] `logseq_later_agent.py` documented: scans LogSeq LATER tasks → Obsidian planner block. Config: `LOGSEQ_DIR`, `WORKSPACE_DIR`. Entry: `run(write_to_obsidian=True, days=N)`
  - [x] `calendar_planning_agent.py` documented: Gemini-only weekly plan from Calendar + Reminders + LogSeq → `datainput/calendar_suggestions.md`. Config: `ENABLE_GEMINI`, `GEMINI_API_KEY`, `DEEP_WORK_START/END`, `CHRONOTYPE`. Entry: `run(write_to_obsidian=False)`
  - [x] `cron_job.py` orchestration documented: lockfile, timeout, agent order, `--agents` flag
  - [x] PO has reviewed and confirmed description accuracy
- **Epic**: E03 / E04
- **Estimate**: S
- **Status**: ✅ Done — 2026-03-27 (scrum docs updated by SM)

#### BLI-026 — Split main.py into focused modules
- **Story**: As a developer, I want `main.py` split into focused modules so the codebase is maintainable and functions are easy to find and test
- **Acceptance Criteria**:
  - [ ] `cli_commands.py` — all `handle_*()` functions and interactive chat command handlers
  - [ ] `task_utils.py` — `get_unified_tasks()` and task-related helpers
  - [ ] `session.py` — startup display, file watcher, background sync loop
  - [ ] `main.py` reduced to ≤150 lines — thin orchestrator + argparse only
  - [ ] All existing CLI arguments and chat commands still work after refactor
  - [ ] No functional changes — this is purely structural
- **Epic**: E06
- **Estimate**: L
- **Status**: ✅ Done — 2026-04-02 (T04-01)

#### BLI-027 — Expand test suite to cover all agents
- **Story**: As a developer, I want tests for all agents and the cron orchestrator so regressions are caught before they reach production
- **Acceptance Criteria**:
  - [ ] `tests/test_datainput_agent.py` — sync new reminders, skip duplicates, organise planner (mock LLM)
  - [ ] `tests/test_logseq_later_agent.py` — parse LATER tasks, deduplication, Obsidian write
  - [ ] `tests/test_calendar_planning_agent.py` — mock Gemini response, file output
  - [ ] `tests/test_cron_job.py` — lockfile prevents double-run, `--agents` flag runs subset
  - [ ] `scripts/run_tests.sh` — single command to run full suite with coverage report
  - [ ] All new tests pass with `pytest tests/ -v`
- **Epic**: E03 / E04 / E05
- **Estimate**: L
- **Status**: ✅ Done — 2026-04-02 (T04-02) — 42 pass, 1 skipped; pre-existing failures fixed in `7f942ff`

#### BLI-028 — Monitoring and status dashboard
- **Story**: As a user, I want a rich terminal status dashboard that shows the health of all services and data sources so I can diagnose issues at a glance
- **Acceptance Criteria**:
  - [ ] `update_manager.py` extended to check: Gemini API key present, Google Calendar token valid, LogSeq dir reachable, Obsidian vault reachable, last cron run time + result, last reminders sync time, `datainput/reminders.json` age
  - [ ] `/status` CLI command renders a Rich-formatted dashboard (table or panel layout)
  - [ ] `python scripts/status.py` runs the same dashboard standalone (no main.py required)
  - [ ] `logs/system_status.json` updated to include all new checks with timestamps
  - [ ] Log rotation: keep last 7 days of `cron_sync.log`, archive older files to `logs/archive/`
- **Epic**: E06
- **Estimate**: M
- **Status**: ✅ Done — 2026-04-02 (T04-03)

#### BLI-029 — Terminal task and calendar visibility
- **Story**: As a user, I want to see today's tasks and calendar events in a compact terminal view and get timed reminders so I have full task visibility without leaving the terminal
- **Acceptance Criteria**:
  - [ ] `/today` CLI command shows: today's calendar events (from `datainput/googlecalendar.yml`), tasks due today from Obsidian + LogSeq + Apple Reminders, and overdue tasks flagged in red
  - [ ] `/week` CLI command shows a compact 7-day Rich table: date | events | tasks due
  - [ ] `python main.py --today` equivalent to `/today` for scripting/cron use
  - [ ] macOS terminal reminder: `python scripts/remind.py "Task text" "HH:MM"` uses `osascript` to trigger a macOS notification at the specified time via `at` command
  - [ ] `scripts/remind.py` documented in INSTALL.md under "Terminal Reminders"
- **Epic**: E05 / E06
- **Estimate**: M
- **Status**: ✅ Done — 2026-04-02 (T04-04)

---

### Sprint-05 Items

#### BLI-030 — Local ICS calendar engine
- **Story**: As a user, I want a local calendar that works without Google OAuth so I can manage tasks and events on any Linux/Unix machine without cloud dependency
- **Supersedes**: BLI-012, BLI-013 (Google Calendar API replaced as primary calendar path — see ADR-006)
- **Acceptance Criteria**:
  - [ ] `local_calendar_agent.py` created — reads/writes `datainput/local_calendar.ics` using the `icalendar` Python library
  - [ ] `add_event(summary, start_dt, end_dt, description=None)` — appends a new `VEVENT` with a stable UUID-based `UID`
  - [ ] `remove_event(uid=None, summary=None)` — removes matching `VEVENT`(s); UID match is exact, summary match is case-insensitive substring
  - [ ] `list_events(start_date=None, end_date=None)` — returns events in date range; defaults to next 7 days
  - [ ] `get_today_events()` — returns events for today only
  - [ ] Creates `datainput/local_calendar.ics` with correct VCALENDAR header if it does not exist
  - [ ] `/add-event` CLI command: prompts for summary, date, start time, end time, optional description — calls `add_event()`
  - [ ] `/remove-event` CLI command: lists upcoming events with index, user picks one to remove — calls `remove_event(uid=...)`
  - [ ] `icalendar` added to `requirements.txt`
- **Epic**: E05
- **Estimate**: M
- **Status**: 📋 Backlog

#### BLI-031 — ICS export and import
- **Story**: As a user, I want to export my local calendar as a standard `.ics` file and import events from an external `.ics` so I can sync with Google Calendar, Apple Calendar, or any compliant app
- **Acceptance Criteria**:
  - [ ] `/export-calendar [path]` CLI command: copies `datainput/local_calendar.ics` to the given path (default: `~/calendar_export.ics`); prints: `Exported N events to <path>`
  - [ ] `/import-calendar <file>` CLI command: loads events from an external `.ics` file, merges into `datainput/local_calendar.ics`, deduplicates by `UID`; prints: `Imported N new events (M duplicates skipped)`
  - [ ] Duplicate detection: if a `UID` already exists in the local calendar, the event is skipped (not overwritten)
  - [ ] Import handles malformed or partial `.ics` files gracefully — logs warnings, continues
  - [ ] `INSTALL.md` updated with a "Calendar Sync" section: how to import `.ics` into Google Calendar / Apple Calendar manually
- **Epic**: E05
- **Estimate**: S
- **Status**: 📋 Backlog

#### BLI-032 — Update terminal views and planning agent to use local ICS
- **Story**: As a user, I want `/today`, `/week`, and the planning agent to use my local ICS calendar so all calendar features work without a Google API token
- **Acceptance Criteria**:
  - [ ] `terminal_views.py` — `render_today()` and `render_week()` read from `local_calendar_agent.list_events()` instead of `datainput/googlecalendar.yml`
  - [ ] `calendar_planning_agent.py` — reads upcoming events from `local_calendar_agent.list_events()` as context for the LLM planning prompt; Google Calendar API call removed from the default path
  - [ ] `/status` health check (`update_manager.py`) — replace Google Calendar cache age check with ICS file age check (`datainput/local_calendar.ics`)
  - [ ] `config.example` — Google Calendar fields moved to optional/commented-out section; `LOCAL_CALENDAR_FILE` added (default: `datainput/local_calendar.ics`)
  - [ ] Google Calendar API path (`calendar_agent.py`) remains intact as an optional import source — no deletion, just demotion
  - [ ] `python main.py --today` works with zero Google credentials present
- **Epic**: E05 / E10
- **Estimate**: M
- **Status**: 📋 Backlog

#### BLI-033 — Google Tasks pull: fetch tasks → Obsidian planner
- **Story**: As a user, I want tasks I add in Google Tasks to appear automatically in my Obsidian planner so Google Tasks works as a mobile capture tool feeding my local system
- **Acceptance Criteria**:
  - [ ] `google_tasks_agent.py` created with `_get_service()` — OAuth2 using `credentials.json`; scope: `https://www.googleapis.com/auth/tasks`
  - [ ] `fetch_tasks(list_id)` — returns all non-completed tasks from the specified list as `[{id, title, due, notes}]`
  - [ ] `get_task_lists()` — returns available task lists; used to resolve `GOOGLE_TASKS_LIST` name → `list_id`
  - [ ] `sync_to_obsidian()` — pulls new tasks, appends to Obsidian planner under `## Google Tasks` as `- [ ] <title>` with optional `📅 <due>` and sub-bullet notes; deduplicates against `datainput/synced_google_tasks.json`
  - [ ] `datainput/synced_google_tasks.json` written as `{task_id: {title, synced_date}}` after each pull
  - [ ] `ENABLE_GOOGLE_TASKS=false` in `.config` skips all API calls silently
  - [ ] `GOOGLE_TASKS_LIST=@default` — configurable; `@default` maps to "My Tasks"
  - [ ] `INSTALL.md` updated: note that `token.json` must be deleted and re-auth run to pick up the `tasks` scope
- **Epic**: E13
- **Estimate**: M
- **Status**: 📋 Backlog

#### BLI-034 — Google Tasks push: mark tasks complete from Obsidian done status
- **Story**: As a user, I want tasks I mark done in Obsidian to be automatically marked complete in Google Tasks so both systems stay in sync without manual updates
- **Acceptance Criteria**:
  - [ ] `sync_completions_to_google()` — scans Obsidian planner for `- [x] <title>` lines; normalises title (strip whitespace, lowercase) and matches against titles in `datainput/synced_google_tasks.json`
  - [ ] For each match: calls `tasks().update()` with `status: completed` on Google Tasks; removes the entry from `synced_google_tasks.json`
  - [ ] Tasks not found in `synced_google_tasks.json` are silently skipped (user may have other done tasks unrelated to Google Tasks)
  - [ ] If Google Tasks API call fails for a task, log the error and continue — do not abort the full run
  - [ ] `run(sync_back=True)` — calls `sync_to_obsidian()` then optionally `sync_completions_to_google()`; `sync_back=False` skips writeback
- **Epic**: E13
- **Estimate**: S
- **Status**: 📋 Backlog
- **Notes**: Depends on BLI-033 (agent + JSON tracking file must exist)

#### BLI-035 — Google Tasks cron integration and CLI command
- **Story**: As a user, I want Google Tasks sync to run automatically on schedule and be triggerable from the CLI so tasks are always up to date without manual intervention
- **Acceptance Criteria**:
  - [ ] `cron_job.py` — `run_google_tasks_agent()` function added; gated on `ENABLE_GOOGLE_TASKS=true`; runs after `run_logseq_later_agent()` in the default agent order
  - [ ] `python cron_job.py --agents google_tasks` — runs only the Google Tasks agent
  - [ ] `/google-tasks` CLI chat command: triggers `google_tasks_agent.run(sync_back=True)` and prints summary: `Pulled N new tasks, marked M complete in Google Tasks`
  - [ ] `/status` dashboard (`update_manager.py`) — new `check_google_tasks()` health check: shows `ENABLE_GOOGLE_TASKS` status, age of `synced_google_tasks.json`, last sync timestamp
  - [ ] `config.example` updated with `ENABLE_GOOGLE_TASKS=false` and `GOOGLE_TASKS_LIST=@default`
- **Epic**: E13
- **Estimate**: S
- **Status**: 📋 Backlog
- **Notes**: Depends on BLI-033 and BLI-034

---

## Deferred / Icebox

| ID | Title | Reason deferred | Date |
|----|-------|-----------------|------|
| — | Streamlit web dashboard (app.py) | Keeping existing code, not a sprint priority — CLI first | 2026-03-14 |
| — | Apple Reminders integration | macOS only — not applicable on Linux | 2026-03-14 |
| — | Book Agent / Travel Agent | Out of scope for current sprint focus | 2026-03-14 |

---

## Sprint-02 Placeholder

Sprint-02 will address the Priority 2 backlog items (BLI-010 through BLI-014). Planned scope:

| Task | BLI | Title | Estimate |
|------|-----|-------|----------|
| T02-01 | BLI-010 | Obsidian task reading/writing via CLI | M |
| T02-02 | BLI-011 | LogSeq → Obsidian task sync | L |
| T02-03 | BLI-012 | Planning agent with Google Calendar scheduling | L |
| T02-04 | BLI-013 | Scheduled/cron-triggered planning agent | M |
| T02-05 | BLI-014 | Clean CLI entry point (`/backlog`, `/plan`, `/sync`, `/review`) | S |

Sprint-02 start date: 2026-03-22 (after Sprint-01 review)

## Sprint-03 Placeholder

Sprint-03 will address Priority 3 backlog items (BLI-020 through BLI-022):

| Task | BLI | Title | Estimate |
|------|-----|-------|----------|
| T03-01 | BLI-020 | Per-task Ollama model routing | M |
| T03-02 | BLI-021 | config.example with sane defaults | S |
| T03-03 | BLI-022 | Evening review agent | M |

Sprint-03 start date: TBD (after Sprint-02 review)

## Sprint-04 Plan

Sprint-04 addresses DEBT-003 (main.py), DEBT-006 (tests), DEBT-007 (monitoring), and new BLI-028/BLI-029:

| Task | BLI | Title | Estimate | Agent |
|------|-----|-------|----------|-------|
| T04-01 | BLI-026 | Split main.py into cli_commands, task_utils, session modules | L | dev-1 |
| T04-02 | BLI-027 | Expand test suite — datainput, logseq_later, calendar_planning, cron_job | L | dev-2 |
| T04-03 | BLI-028 | Monitoring dashboard — extended health checks + /status + log rotation | M | dev-3 |
| T04-04 | BLI-029 | Terminal task/calendar view — /today, /week, scripts/remind.py | M | dev-2 |

Sprint-04 start date: 2026-03-27

## Sprint-05 Placeholder

Sprint-05 delivers two parallel tracks: local ICS calendar engine (ADR-006) and Google Tasks two-way sync (ADR-007).

| Task | BLI | Title | Estimate | Agent | Track |
|------|-----|-------|----------|-------|-------|
| T05-01 | BLI-030 | Local ICS calendar engine (`local_calendar_agent.py`, `/add-event`, `/remove-event`) | M | dev-1 | ICS |
| T05-02 | BLI-031 | ICS export + import (`/export-calendar`, `/import-calendar`) | S | dev-1 | ICS |
| T05-03 | BLI-032 | Update `/today`, `/week`, planning agent to use local ICS | M | dev-2 | ICS |
| T05-04 | BLI-033 | Google Tasks pull: `google_tasks_agent.py` + `sync_to_obsidian()` | M | dev-3 | Tasks |
| T05-05 | BLI-034 | Google Tasks push: `sync_completions_to_google()` | S | dev-3 | Tasks |
| T05-06 | BLI-035 | Cron + CLI (`/google-tasks`, `/status` check, `config.example`) | S | dev-3 | Tasks |

**Dependency order**:
- T05-01 → T05-02, T05-03 (ICS track sequential then parallel)
- T05-04 → T05-05 → T05-06 (Tasks track sequential)
- ICS track and Tasks track are fully independent — run in parallel

Sprint-05 start date: TBD (awaiting PO confirmation)

---

## Changelog

| Date | Changed by | Change |
|------|------------|--------|
| 2026-04-02 | Product Owner | Added BLI-033, BLI-034, BLI-035 — Google Tasks two-way sync (ADR-007). Sprint-05 updated with Tasks track. |
| 2026-04-02 | Product Owner | Added BLI-030, BLI-031, BLI-032 — local ICS calendar engine replaces Google Calendar API (ADR-006). Sprint-05 placeholder added. |
| 2026-04-02 | Scrum Master | Marked Sprint-04 items Done: BLI-026 (T04-01), BLI-027 (T04-02), BLI-028 (T04-03), BLI-029 (T04-04). Sprint-04 complete. |
| 2026-03-27 | Scrum Master | Added BLI-025 (agent registration, marked Done), BLI-026 (main.py split), BLI-027 (test suite), BLI-028 (monitoring dashboard), BLI-029 (terminal task visibility). Updated DEBT table. |
| 2026-03-15 | Scrum Master | Marked Sprint-03 BLI items Done: BLI-020 (T03-01), BLI-021 (T03-02), BLI-022 (T03-03). |
| 2026-03-15 | Scrum Master | Marked Sprint-02 BLI items Done: BLI-010 (T02-01), BLI-011 (T02-02), BLI-012 (T02-03), BLI-013 (T02-04), BLI-014 (T02-05). All AC checkboxes updated. |
| 2026-03-15 | Scrum Master | Marked BLI-001 Done; updated BLI-002 through BLI-005, BLI-023, BLI-024 statuses to reflect Sprint-01 ready-to-implement state; added Sprint-02 and Sprint-03 placeholders |
| 2026-03-14 | Product Owner | Initial backlog — OpenClaw removal, Ollama-first, LogSeq/Obsidian CLI, Calendar planning agent |
