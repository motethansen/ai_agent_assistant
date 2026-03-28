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
| LLM (cloud fallback) | Gemini (`google-genai`), OpenAI, Claude (`anthropic`) | Used only when Ollama unavailable or `ROUTING_*` overrides |
| CLI / Terminal UI | Rich | `chat_ui.py`, status dashboard, `/today`, `/week` |
| Web UI (optional) | Streamlit | `app.py` — not the primary interface |
| Vector DB / RAG | Chroma via LangChain | `rag_agent.py` only — LangChain not used elsewhere |
| Calendar | Google Calendar API | Auth via `token.json` + `credentials.json`. Cache: `datainput/googlecalendar.yml` |
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
