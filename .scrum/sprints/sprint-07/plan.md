# Sprint-07 Plan — LM Studio Native SDK + n8n Local Setup + Google Connector Migration

**Sprint**: 07
**Goal**: Replace all fragile HTTP/OpenAI-compat LM Studio calls with the official `lmstudio` SDK; get n8n running locally with all workflows imported and verified; begin migrating Google Calendar and Tasks auth out of Python and into n8n.
**Status**: 🔲 Not started
**Epics**: E07, E18, E19

---

## Task Summary

| Task | BLI | Title | Estimate | Agent | Wave |
|------|-----|-------|----------|-------|------|
| T07-01 | BLI-044 | LM Studio Python SDK — replace `_call_lmstudio()`, add streaming, SDK health check | M | **Claude Code** | Wave 1 |
| T07-02 | BLI-045 | `lms` CLI service lifecycle — `manage_services.sh`, `install.sh`, `service.sh` | S | **Claude Code** | Wave 1 |
| T07-03 | BLI-043 | n8n local setup — OrbStack/Docker, workflow import, API server wiring, verification | S | **Claude Code** | Wave 1 |
| T07-04 | BLI-041 | Remove Google Calendar OAuth from Python — `calendar_manager.py` cleanup, n8n credential | M | **Gemini** | Wave 2 |
| T07-05 | BLI-042 | Remove Google Tasks OAuth from Python — route sync via n8n trigger | M | **Gemini** | Wave 2 |

---

## Execution Waves

```
Wave 1 (parallel — no shared files):
  ┌─────────────────────────────────┐  ┌──────────────────────────────────┐  ┌──────────────────────────────┐
  │ T07-01 LM Studio SDK (Claude)   │  │ T07-02 lms CLI services (Claude) │  │ T07-03 n8n local setup       │
  │ ai_orchestration.py             │  │ manage_services.sh               │  │ docker-compose.yml           │
  │ requirements.txt                │  │ install.sh                       │  │ install.sh (n8n section)     │
  │ tests/test_ai_orchestration.py  │  │ service.sh                       │  │ INSTALL.md                   │
  └─────────────────────────────────┘  └──────────────────────────────────┘  └──────────────────────────────┘

Wave 2 (after T07-03 — n8n must be running for Google connector migration):
  ┌─────────────────────────────────────┐  ┌─────────────────────────────────────┐
  │ T07-04 Google Calendar → n8n        │  │ T07-05 Google Tasks → n8n           │
  │ calendar_manager.py (strip OAuth)   │  │ google_tasks_agent.py (strip OAuth) │
  │ n8n-workflows/ (new GCal workflow)  │  │ n8n-workflows/ (new Tasks workflow) │
  │ INSTALL.md                          │  │ cron_job.py                         │
  └─────────────────────────────────────┘  └─────────────────────────────────────┘
```

**Why this order:**
- T07-01, T07-02, T07-03 touch different files entirely — safe to run in parallel
- T07-04 and T07-05 both need n8n running (T07-03) before configuring Google credentials in the n8n UI
- T07-04 and T07-05 touch different files — safe to run in parallel in Wave 2

---

## Task Prompts

### T07-01 — LM Studio Python SDK (Claude Code)

```
You are a senior Python engineer working on ai_agent_assistant.

TASK: Replace the raw OpenAI-compat HTTP calls to LM Studio with the official
`lmstudio` Python SDK (pip package: `lmstudio`).

CONTEXT:
- Current implementation: `_call_lmstudio()` in `ai_orchestration.py` (line ~129)
  uses `import openai; openai.OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")`
- The `lmstudio` SDK connects via WebSocket to the LM Studio daemon
- SDK docs: https://lmstudio.ai/docs/python
- Quick example: `import lmstudio as lms; result = lms.llm("model-name").respond("prompt")`
- `is_lmstudio_running()` currently does a raw HTTP GET to /v1/models

CHANGES REQUIRED:

1. `requirements.txt` — add `lmstudio` (the PyPI package name)

2. `ai_orchestration.py`:
   - `is_lmstudio_running()`: replace HTTP check with SDK client check:
     ```python
     def is_lmstudio_running():
         try:
             import lmstudio as lms
             lms.list_downloaded_models()  # or similar no-op check
             return True
         except Exception:
             return False
     ```
   - `_call_lmstudio(prompt, system=None, model=None)`: rewrite using SDK:
     ```python
     import lmstudio as lms
     model_id = model or get_config_value("LM_STUDIO_MODEL", "")
     m = lms.llm(model_id)
     chat = [{"role": "user", "content": prompt}]
     if system:
         chat.insert(0, {"role": "system", "content": system})
     result = m.respond(chat)
     return str(result), f"lmstudio/{model_id}"
     ```
   - Wrap both in try/except; on failure return ("LLM error: ...", "lmstudio/unknown")

3. `tests/test_ai_orchestration.py` (or create `tests/test_lmstudio.py`):
   - Test `_call_lmstudio()` with `lmstudio` SDK mocked
   - Test `is_lmstudio_running()` returns False when SDK raises connection error

CONSTRAINTS:
- All changes gated on `ENABLE_LM_STUDIO=true` — zero effect when false
- Do not remove the `MODELS_ENABLED["lmstudio"]` flag check
- Run: `bash scripts/run_tests.sh` — all tests must pass
```

---

### T07-02 — `lms` CLI Service Lifecycle (Claude Code)

```
You are a senior shell/Python engineer working on ai_agent_assistant.

TASK: Integrate the `lms` CLI (LM Studio's command-line tool) into the service
management scripts so that LM Studio's server and model loading are managed
automatically alongside Ollama.

CONTEXT:
- `lms` ships with LM Studio — no separate install
- Key commands:
  - `lms server start` / `lms server stop` — start/stop inference server
  - `lms ps` — list models currently loaded in memory (empty = not ready)
  - `lms load <model>` — load a model into memory
  - `lms daemon start` — headless operation (Linux, no GUI)
- All LM Studio features gated on `ENABLE_LM_STUDIO=true` in `.config`

CHANGES REQUIRED:

1. `scripts/manage_services.sh`:
   - Add `start_lmstudio()` function:
     - If `lms` not in PATH: print install link and return
     - Run `lms server start`
     - Read `LM_STUDIO_MODEL` from .config
     - If model not in `lms ps` output: run `lms load <model>`
     - Print green "LM Studio ready: <model>"
   - In `start_ollama()` (existing): call `start_lmstudio()` after Ollama
     if `ENABLE_LM_STUDIO=true`
   - Add `lmstudio` to `check_services()` output

2. `install.sh` `run_service_checks()`:
   - LM Studio health: if `lms` available and `ENABLE_LM_STUDIO=true`,
     use `lms ps` to check if model is loaded; print model name on success
   - If `lms` not found but `ENABLE_LM_STUDIO=true`: add to ISSUES with
     advice "Open LM Studio at least once to register the lms CLI"

3. `service.sh` `cmd_start()`:
   - If `ENABLE_LM_STUDIO=true` and `lms` available: call `lms daemon start`
     before starting the Python daemon (for headless Linux use)

4. `INSTALL.md`:
   - Add note to LM Studio section: "For headless use (Linux server):
     `lms daemon start` — runs the inference engine without the GUI.
     Must have run LM Studio GUI once on the machine first."

CONSTRAINTS:
- All `lms` calls wrapped in `command -v lms > /dev/null 2>&1 || return` guard
- Zero effect when `ENABLE_LM_STUDIO=false`
- Do not break existing Ollama management
```

---

### T07-03 — n8n Local Setup + Verification (Claude Code)

```
You are a senior DevOps/Python engineer working on ai_agent_assistant.

TASK: Complete the n8n local setup: verify docker-compose.yml, update INSTALL.md
with a dedicated n8n section, update `run_service_checks()` in install.sh, and
verify the api_server.py webhook endpoint is reachable from n8n.

CONTEXT:
- docker-compose.yml already has n8n service on port 5679 (N8N_PORT)
- n8n-workflows/ has 4 JSON files ready to import
- api_server.py runs on port 5678 (WEBHOOK_PORT) and is the callback target
- OrbStack is the container runtime on macOS (docker CLI compatible)
- `./install.sh n8n` subcommand already runs setup_n8n() + run_service_checks()

CHANGES REQUIRED:

1. `INSTALL.md` — add **n8n Setup** section (after LM Studio section):
   ```
   ## n8n Setup (workflow automation)

   n8n runs as a Docker container and handles event-driven workflows between
   your local data sources and external services.

   ### Start n8n
   docker compose up -d n8n
   # UI: http://localhost:5679

   ### Import workflows
   1. Open http://localhost:5679
   2. Top-right menu → Import from file
   3. Import each file from n8n-workflows/:
      - morning-planning.json
      - add-task.json
      - backlog-digest.json
      - universal_task_sync.json
   4. Open each workflow → toggle Active

   ### Start the Python API server (n8n callback target)
   python api_server.py
   # Listens on port 5678

   ### Verify
   ./run.sh
   /sync-universal
   # n8n logs should show: POST /webhook/task-sync received

   ### Persistent service
   ./service.sh install   # macOS launchd / Linux systemd
   ```

2. `api_server.py` — verify `GET /health` endpoint exists for the service
   check in install.sh; add it if missing (returns `{"status": "ok"}`)

3. `run_service_checks()` in `install.sh` — n8n check already exists;
   also check api_server health endpoint at `WEBHOOK_PORT`

4. `README_N8N.md` — update with OrbStack note: "On macOS with OrbStack,
   use `docker compose` directly — OrbStack provides full Docker CLI compatibility"

CONSTRAINTS:
- Do not modify docker-compose.yml service definitions
- Run: `bash scripts/run_tests.sh` — all tests must pass
```

---

### T07-04 — Google Calendar OAuth → n8n (Gemini)

```
You are a senior Python engineer working on ai_agent_assistant.

TASK: Remove the direct Google Calendar OAuth flow from Python. Google Calendar
credentials should live in n8n's credential store, not in token.json/credentials.json.

CONTEXT (read ADR-010 in .scrum/decisions.md for full rationale):
- `calendar_manager.py` contains the OAuth flow (`get_calendar_service()`)
- `calendar_agent.py` uses it for background sync — already disabled (ENABLE_GOOGLE_CALENDAR=false)
- `local_calendar_agent.py` is the primary calendar (local ICS, no auth required)
- n8n Universal Task Sync workflow handles calendar via n8n's Google Calendar node

CHANGES REQUIRED:

1. `calendar_manager.py`:
   - Remove `get_calendar_service()` OAuth flow entirely
   - Remove `token.json`/`credentials.json` references
   - Keep only `get_busy_slots_from_yaml()` (reads the YAML cache) and
     `import_ics_from_google_export(path)` (one-time ICS import helper)
   - Add module docstring: "Legacy module — Google Calendar auth moved to n8n (ADR-010).
     Use local_calendar_agent.py for calendar operations."

2. `calendar_agent.py`:
   - Remove `start_background_calendar_sync()` entirely (already gated off)
   - Keep `CalendarAgent.get_busy_slots_from_yml()` for YAML cache reads
   - Add module docstring pointing to n8n for live calendar data

3. `main.py`:
   - Remove the `from calendar_agent import start_background_calendar_sync` import
   - Remove the `is_google_calendar_enabled()` guard (no longer needed)

4. `INSTALL.md`:
   - Google Calendar section: replace OAuth setup steps with n8n credential setup:
     "Configure Google Calendar in n8n: open n8n UI → Credentials → New →
     Google Calendar OAuth2 → follow prompts. No token.json required."

5. `config.example`:
   - Remove `ENABLE_GOOGLE_CALENDAR` key (no longer meaningful)
   - Add comment: "# Google Calendar is managed via n8n — see INSTALL.md"

CONSTRAINTS:
- Do NOT delete calendar_manager.py or calendar_agent.py — other code may import them
- Do NOT touch local_calendar_agent.py (correct primary path)
- Run: `bash scripts/run_tests.sh` — all tests must pass
```

---

### T07-05 — Google Tasks OAuth → n8n (Gemini)

```
You are a senior Python engineer working on ai_agent_assistant.

TASK: Remove the direct Google Tasks OAuth flow from google_tasks_agent.py.
Task sync should trigger an n8n workflow instead of calling the Google Tasks API directly.

CONTEXT (read ADR-010 and BLI-042 in .scrum/backlog.md):
- `google_tasks_agent.py` has its own OAuth2 flow using the Tasks scope
- The intended architecture: Python triggers n8n → n8n fetches/pushes Google Tasks
  via its own Google Tasks node → n8n calls back to api_server.py to write tasks

CHANGES REQUIRED:

1. `google_tasks_agent.py`:
   - Remove `_get_service()` OAuth flow and all `googleapiclient` imports
   - `sync_to_obsidian()`: replace with `n8n_client.trigger("google-tasks-pull", {})`
     and return 0 (n8n will call back via /webhook/add-task to write tasks)
   - `sync_completions_to_google()`: replace with
     `n8n_client.trigger("google-tasks-push", {"completions": completed_titles})`
     where `completed_titles` is still read from Obsidian planner (that logic stays)
   - `run()`: simplify to just call both triggers if `ENABLE_GOOGLE_TASKS=true`
   - Add module docstring: "Google Tasks auth moved to n8n (ADR-010).
     This module now triggers n8n workflows; n8n manages API credentials."

2. `n8n-workflows/google_tasks_sync.json`:
   - Create a new n8n workflow with 3 nodes:
     - Trigger: webhook `POST /webhook/google-tasks-pull`
     - Google Tasks node: fetch all incomplete tasks from @default list
     - HTTP Request: POST each task to `api_server.py /webhook/add-task`
   - Export as importable JSON

3. `cron_job.py` `run_google_tasks_agent()`:
   - No change needed — already calls `google_tasks_agent.run()`

4. `INSTALL.md` Google Tasks section:
   - Replace OAuth setup with: "Configure Google Tasks in n8n: Credentials →
     New → Google Tasks OAuth2. Then import google_tasks_sync.json workflow."

CONSTRAINTS:
- `ENABLE_GOOGLE_TASKS` flag still respected — when false, triggers are skipped
- `datainput/synced_google_tasks.json` dedup file — update api_server.py handler
  to write this when receiving /webhook/add-task from n8n (if not already done)
- Run: `bash scripts/run_tests.sh` — all tests must pass
```

---

## Definition of Done

- [ ] `bash scripts/run_tests.sh` — zero failures
- [ ] `./run.sh` starts cleanly with no import errors
- [ ] `lmstudio` SDK used for LM Studio calls when `ENABLE_LM_STUDIO=true`
- [ ] `lms server start` called by `manage_services.sh` when LM Studio enabled
- [ ] n8n running at `http://localhost:5679`, all 4 workflows imported and active
- [ ] `calendar_manager.py` has no OAuth flow
- [ ] `google_tasks_agent.py` has no OAuth flow
- [ ] `INSTALL.md` updated for all three areas (LM Studio CLI, n8n, Google credentials via n8n)
- [ ] All new config keys documented in `config.example`

---

## New Dependencies

| Package | Why | Added by |
|---------|-----|----------|
| `lmstudio` | Official LM Studio Python SDK | T07-01 |

## Config Keys (unchanged — no new keys this sprint)

All Sprint-07 changes use existing keys: `ENABLE_LM_STUDIO`, `LM_STUDIO_MODEL`, `ENABLE_GOOGLE_TASKS`, `ENABLE_GOOGLE_CALENDAR`, `N8N_WEBHOOK_URL`.
