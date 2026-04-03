# Architecture & Design Decisions — [PROJECT NAME]

> This file is CRITICAL for team handoffs. Every significant decision must be logged here.
> Any new Scrum Master or dev agent team reads this before starting work.

---

## How to Use This File

When making a decision that affects:
- Technology choices
- File/folder structure
- API contracts
- Auth / security approaches
- Data models
- External service integrations

...add an entry here. Future agents (and you) will thank you.

---

## Decisions Log

### ADR-001 — Ollama-first LLM with cloud fallback
- **Date**: 2026-03-15
- **Sprint**: Sprint-01
- **Team**: Claude dev agents
- **Status**: Accepted

**Context**: Project originally used OpenClaw as an LLM gateway. Goal was local-first, privacy-preserving operation.

**Decision**: All LLM calls route to Ollama by default. Fallback chain: `ollama → gemini → openai → claude`. Routing is per task type (`ROUTING_CHAT`, `ROUTING_SCHEDULING`, `ROUTING_PARSING`) and configurable via `/routing` CLI command.

**Reasoning**: Ollama is free, local, and private. Cloud providers are fallback for capability gaps (e.g. Gemini for calendar planning).

**Consequences**: `calendar_planning_agent.py` is Gemini-only (requires `ENABLE_GEMINI=true`). All other agents default to Ollama.

**Affected files**: `ai_orchestration.py`, `config.example`, `calendar_planning_agent.py`

---

### ADR-002 — No LangChain for LLM invocation
- **Date**: 2026-03-15
- **Sprint**: Sprint-01
- **Team**: Claude dev agents
- **Status**: Accepted

**Context**: Project originally used LangChain adapters for all LLM providers.

**Decision**: LangChain removed for all LLM calls. Direct SDK calls only: `anthropic`, `openai`, `google-genai`, Ollama HTTP. LangChain kept only for Chroma vector store + document loaders in `rag_agent.py`.

**Reasoning**: LangChain added abstraction overhead and version instability. Direct SDKs are simpler and more predictable.

**Consequences**: Any new LLM provider must be added as a direct SDK call in `ai_orchestration.py`.

**Affected files**: `ai_orchestration.py`, `rag_agent.py`

---

### ADR-003 — Apple Reminders via AppleScript bulk fetch
- **Date**: 2026-03-21
- **Sprint**: Post-Sprint-03
- **Team**: Michael Hansen (PO)
- **Status**: Accepted

**Context**: Apple Reminders has no public REST API. Per-item AppleScript calls are extremely slow for large lists (100+ items).

**Decision**: Use bulk property access (`name of every reminder`) to fetch all properties in one Apple Event per property type, then filter/combine in Python. Data stored as JSON in `datainput/reminders.json`.

**Reasoning**: Reduces Apple Events from N×4 to 4 total. Handles 100+ reminders without timeout.

**Consequences**: macOS-only. Linux deployments will skip this data source. `debug_reminders.py` must be run manually (or via cron) to refresh the JSON; the rest of the system reads from JSON only.

**Affected files**: `debug_reminders.py`, `reminders_manager.py`, `datainput_agent.py`

---

### ADR-004 — Terminal reminders: three delivery channels
- **Date**: 2026-03-27
- **Sprint**: Sprint-04
- **Team**: Claude Scrum Master + PO
- **Status**: Accepted

**Context**: `scripts/remind.py` needed to decide how to deliver timed reminders set from the terminal.

**Decision**: Three non-fatal delivery channels attempted in sequence:
1. **macOS notification** via `at` + `osascript` (macOS only)
2. **Log to file** `logs/reminders.log` (always, on all platforms)
3. **n8n webhook** via `n8n_client.trigger("reminder-set", payload)` (when `N8N_WEBHOOK_URL` configured)

**Reasoning**: n8n allows downstream automation (e.g. forward to Slack, email, calendar). Log file gives audit trail. macOS notification gives in-context pop-up. None are required — all fail gracefully.

**Consequences**: `scripts/remind.py` must import `n8n_client` (already exists). n8n webhook path `reminder-set` must be documented in `README_N8N.md`.

**Affected files**: `scripts/remind.py` (new), `logs/reminders.log` (new), `n8n_client.py`

---

### ADR-007 — Google Tasks two-way sync via dedicated agent
- **Date**: 2026-04-02
- **Sprint**: Sprint-05
- **Team**: Michael Hansen (PO)
- **Status**: Accepted

**Context**: The user adds tasks in Google Tasks and wants them automatically pulled into the local task list (Obsidian planner), and wants tasks marked done locally to flow back to Google Tasks. This is a two-way sync problem that must handle deduplication, task identity across systems, and auth.

**Decision**: Build `google_tasks_agent.py` following the same pattern as `datainput_agent.py`:

- **Pull** (`sync_to_obsidian()`): Fetch all incomplete tasks from the configured Google Tasks list. Deduplicate against `datainput/synced_google_tasks.json` (keyed by Google Tasks `task_id`). Write new tasks to the Obsidian planner under a `## Google Tasks` section as `- [ ] <title>`. Store `{task_id: {title, synced_date}}` in the JSON so we can later match them for completion.
- **Push** (`sync_completions_to_google()`): Scan the Obsidian planner for `- [x]` lines whose text matches a title in `synced_google_tasks.json`. For each match, call `tasks().update(status='completed')` on Google Tasks. Remove the entry from the JSON to avoid re-processing.
- **Identity**: Use Google Tasks `task_id` as the canonical key. Title-based matching for completion detection (normalised: strip whitespace, lowercase).
- **Config flag**: `ENABLE_GOOGLE_TASKS=false` — all API calls skipped if not set to `true`. Follows same pattern as `ENABLE_GOOGLE_CALENDAR`.
- **Auth**: Google Tasks requires the `https://www.googleapis.com/auth/tasks` scope. This scope must be added to `calendar_manager.py` (or a new `SCOPES` list). Existing `token.json` must be deleted and OAuth re-run to pick up the new scope. Document this in `INSTALL.md`.

**Task list selection**: `GOOGLE_TASKS_LIST=@default` (the "My Tasks" list). User can override with a specific list name; agent resolves name → `list_id` at startup.

**Scheduling**: Added as step in `cron_job.py` (`run_google_tasks_agent()`), gated on `ENABLE_GOOGLE_TASKS=true`. Runs after `datainput` and `logseq_later` steps. Sync interval determined by cron frequency (default: hourly).

**Reasoning**: Two-way sync gives Google Tasks as an input channel (mobile-friendly capture) while keeping Obsidian as the planning surface. The JSON tracking file avoids duplicate entries and enables reliable completion writeback without modifying Obsidian task text.

**Consequences**:
- `token.json` must be regenerated with the new scope — document clearly in INSTALL.md
- Title matching for completion sync is approximate — if the user edits a task title in Obsidian after syncing, it won't be found for writeback
- `calendar_manager.py` SCOPES list needs `tasks` scope added, or a separate auth helper in `google_tasks_agent.py`

**Affected files**: `google_tasks_agent.py` (new), `datainput/synced_google_tasks.json` (new, auto-created), `cron_job.py`, `config.example`, `INSTALL.md`

---

### ADR-006 — Replace Google Calendar API with local ICS calendar engine
- **Date**: 2026-04-02
- **Sprint**: Sprint-05
- **Team**: Michael Hansen (PO)
- **Status**: Accepted

**Context**: BLI-012/013 implemented Google Calendar integration via OAuth2 (`token.json` + `credentials.json`). This creates a cloud dependency, requires manual token setup, and does not work without internet access. The user wants a local-first calendar system that works on any Linux/Unix machine.

**Decision**: Replace Google Calendar API with a local ICS file engine (`local_calendar_agent.py`) backed by `datainput/local_calendar.ics`. The `.ics` file (RFC 5545 iCalendar format) is the single source of truth and doubles as the export artifact — it can be imported directly by Google Calendar, Apple Calendar, Outlook, or any compliant app.

- **Add event**: append a new `VEVENT` with a stable `UID`, `DTSTART`, `DTEND`, `SUMMARY`, optional `DESCRIPTION`
- **Remove event**: locate `VEVENT` by `UID` (preferred) or `SUMMARY` match and delete it from the file
- **Export**: `datainput/local_calendar.ics` is always ready to import — no separate export step
- **Import**: load an external `.ics` (e.g. exported from Google Calendar) and merge, deduplicating by `UID`
- **Google Calendar**: demoted to optional import-only path — no live API calls required

**Reasoning**: ICS is the universal calendar interchange format. A local file needs no auth, no internet, works on any OS, and is version-controllable. Users who need online sync can import the `.ics` into their preferred calendar app manually or via cron.

**Consequences**:
- `calendar_agent.py` and `datainput/googlecalendar.yml` are superseded — kept but no longer the primary path
- ADR-005 (YAML cache auto-refresh) is superseded for the primary calendar path
- `credentials.json` / `token.json` are no longer required for basic calendar use
- `calendar_planning_agent.py` should be updated to read from local ICS instead of Google Calendar API

**Affected files**: `local_calendar_agent.py` (new), `cli_commands.py`, `terminal_views.py`, `calendar_planning_agent.py`, `config.example`, `INSTALL.md`

---

### ADR-008 — LM Studio as secondary local inference backend
- **Date**: 2026-04-03
- **Sprint**: Sprint-06
- **Team**: Scrum Master (SM prompt)
- **Status**: Proposed

**Context**: Ollama is the primary local LLM backend. Some users prefer LM Studio for its GUI-based model management, quantisation selection, and hardware acceleration tuning. LM Studio exposes an OpenAI-compatible API on `localhost:1234/v1`, making integration straightforward.

**Decision**: Add LM Studio as an optional provider in `ai_orchestration.py`. When `ENABLE_LM_STUDIO=true`, it is inserted into the fallback chain between Ollama and Gemini: `ollama → lmstudio → gemini → openai → claude`. A health check (`GET /v1/models`) runs before each request; if the server is not running, the chain falls through silently.

**Reasoning**: Zero new dependencies — LM Studio's OpenAI-compatible endpoint means the `openai` SDK already installed handles the calls. Users who run LM Studio for UI management get automatic integration with no code duplication.

**Consequences**:
- `LM_STUDIO_MODEL` must match the currently loaded model in LM Studio exactly; drift between config and LM Studio UI will cause failures
- Health check adds a small latency overhead (~50ms) before each call if LM Studio is enabled but not running
- `/status` dashboard must show LM Studio status to make the health state visible

**Affected files**: `ai_orchestration.py`, `update_manager.py`, `config.example`, `INSTALL.md`

---

### ADR-009 — NanoClaw Skills for sandboxed agent execution
- **Date**: 2026-04-03
- **Sprint**: Sprint-06
- **Team**: Scrum Master (SM prompt)
- **Status**: Proposed

**Context**: ObsidianAgent and LogSeqAgent operate directly on host filesystem paths (`WORKSPACE_DIR`, `LOGSEQ_DIR`). A bug or prompt injection in the LLM response could cause unintended file writes, deletions, or path traversal to areas outside the intended vault. Running agents in isolated containers eliminates this risk.

**Decision**: Wrap ObsidianAgent and LogSeqAgent as NanoClaw Skills. Each Skill is a Docker container with:
- Only the relevant directory mounted as a volume (`WORKSPACE_DIR` or `LOGSEQ_DIR`)
- Read-only by default; read/write only when the `--write` flag is explicitly passed
- JSON output contract — host code parses stdout, never executes arbitrary container output
- Invoked via `nanoclaw run <skill_name> <action> [args]` subprocess call from the Python host

The Python host retains a fallback path: if NanoClaw is not installed, existing direct-import behaviour is used unchanged (gated on `NANOCLAW_ENABLED=false` in `.config`).

**Reasoning**: Containers provide a hard boundary — even if an LLM generates a malicious file path, the container filesystem prevents it from reaching the host. The JSON interface prevents code injection via stdout. The fallback ensures zero regression for users who don't need the security layer.

**Consequences**:
- Docker must be running for NanoClaw Skills to operate — document clearly in `INSTALL.md`
- Performance: container startup adds ~200–500ms per agent invocation — acceptable for non-real-time cron use; not suitable for interactive chat commands without pre-warming
- NanoClaw Skill manifests (`skill.yaml`) must be versioned alongside agent code — any agent API change requires a corresponding Skill update

**Affected files**: `nanoclaw/skills/obsidian_skill/` (new), `nanoclaw/skills/logseq_skill/` (new), `docker-compose.yml`, `cron_job.py`, `ai_orchestration.py`, `INSTALL.md`

---

### ADR-010 — n8n as Universal Task Sync middleware
- **Date**: 2026-04-03
- **Sprint**: Sprint-06
- **Team**: Scrum Master (SM prompt)
- **Status**: Proposed

**Context**: Google Calendar auth (`credentials.json`, `token.json`) and retry logic currently live in `calendar_manager.py`. When conflicts arise between local `.md` tasks and calendar events (e.g. same task exists in both with different state), resolution is undefined. A dedicated n8n workflow centralises this orchestration and makes the conflict rules visible and editable without touching Python code.

**Decision**: Build a `universal_task_sync.json` n8n workflow that receives a unified payload of local tasks and calendar events, applies conflict resolution rules as n8n Function nodes, and calls back into the Python API server for any write operations. Google Calendar auth and retry logic are handled entirely within n8n's Google Calendar nodes — removed from `calendar_manager.py`. Python CLI triggers the flow via `n8n_client.trigger("task-sync", payload)`.

**Conflict resolution rules** (encoded in n8n, not Python):
1. Local task + matching calendar event → skip calendar write, log `exists`
2. Local task, no calendar match → create Google Calendar event via n8n node
3. Calendar event, no local task → webhook back to `POST /webhook/add-task` → creates LogSeq task

**Reasoning**: n8n's visual workflow makes conflict rules inspectable and modifiable without code changes. Moving Google Calendar auth to n8n eliminates `token.json` from the Python runtime — credentials are stored in n8n's encrypted credential store instead. n8n's built-in retry/backoff handles transient API failures better than the current Python implementation.

**Consequences**:
- n8n must be running (Docker) for Universal Task Sync to function — degrade gracefully (log warning, skip sync) when n8n is unreachable
- Google Calendar credentials must be re-entered in n8n's credential UI — one-time migration from `token.json`
- `calendar_manager.py` auth/retry code can be removed after migration; keep the module for legacy ICS import path only
- `/sync-universal` CLI command requires n8n to be reachable — document this dependency clearly

**Affected files**: `n8n-workflows/universal_task_sync.json` (new), `n8n_client.py`, `cli_commands.py`, `calendar_manager.py`, `api_server.py`, `README_N8N.md`

---

### ADR-005 — Calendar views use YAML cache with auto-refresh
- **Date**: 2026-03-27
- **Sprint**: Sprint-04
- **Team**: Claude Scrum Master + PO
- **Status**: Accepted

**Context**: `/today` and `/week` commands need calendar data. Live API calls on every invocation would be slow and could hit rate limits.

**Decision**: Both commands read from `datainput/googlecalendar.yml` (the existing cache). A helper `_ensure_calendar_cache(max_age_hours=6)` auto-refreshes the cache silently if it is missing or older than 6 hours before rendering.

**Reasoning**: Cache-first keeps the commands fast. Auto-refresh avoids stale data without requiring the user to manually run `/pull`. 6h threshold balances freshness vs. API call frequency.

**Consequences**: If Google Calendar API is unreachable, the last cached data is used and a warning is printed. No hard failure.

**Affected files**: `cli_commands.py`, `calendar_agent.py`

---

## Stack Reference

> Quick reference for any incoming agent team.

| Layer | Technology | Notes |
|-------|-----------|-------|
| LLM (primary) | Ollama (local) | HTTP to `localhost:11434`. Model: `qwen2.5:14b` |
| LLM (secondary local) | LM Studio | OpenAI-compatible API on `localhost:1234/v1`. Optional — `ENABLE_LM_STUDIO=true`. See ADR-008. |
| LLM (cloud fallback) | Gemini (`google-genai`), OpenAI, Claude (`anthropic`) | Used only when Ollama unavailable or `ROUTING_*` overrides |
| Agent isolation | NanoClaw (Docker Skills) | Containerised ObsidianAgent + LogSeqAgent. Gated on `NANOCLAW_ENABLED=true`. See ADR-009. |
| CLI / Terminal UI | Rich | `chat_ui.py`, status dashboard, `/today`, `/week` |
| Web UI (optional) | Streamlit | `app.py` — not the primary interface |
| Vector DB / RAG | Chroma via LangChain | `rag_agent.py` only — LangChain not used elsewhere |
| Calendar (primary) | Local ICS file (`datainput/local_calendar.ics`) | RFC 5545. No auth required. Importable by Google/Apple/Outlook. See ADR-006. |
| Calendar (optional import) | Google Calendar API | Legacy path. `token.json` + `credentials.json` still supported for one-time ICS import. |
| Task sources | Obsidian (markdown), LogSeq (markdown), Apple Reminders (AppleScript→JSON) | All read via direct file/subprocess — no app required |
| Automation | n8n (Docker, port 5678) | Webhooks via `n8n_client.py` |
| API server | FastAPI | `api_server.py` — webhook endpoints for n8n |
| Config | `.config` key=value | Parsed by `config_utils.py` |
| Tests | pytest + unittest.mock | `tests/` directory |
| Scheduling | cron / systemd | `cron_job.py` — lockfile + timeout safety |

---

## External Services & Credentials Locations

> Never store credentials here. Just note where they live.

| Service | Credential location | Notes |
|---------|-------------------|-------|
| Google Calendar | `credentials.json`, `token.json` (repo root) | OAuth2. Do not commit. |
| Gemini API | `GEMINI_API_KEY` in `.config` | Required for `calendar_planning_agent.py` |
| OpenAI API | `OPENAI_API_KEY` in `.config` | Optional fallback |
| Anthropic (Claude) | `ANTHROPIC_API_KEY` in `.config` | Optional fallback |
| Gmail | `gmail_token.json` (repo root) | OAuth2 for `gmail_agent.py` |
| HuggingFace | `HF_TOKEN` in `.config` | Optional, for `rag_agent.py` embedding models |
