# Project Progress — AI Agent Assistant

> This is the PRIMARY handoff document. Any incoming team reads this first.
> Scrum Master updates this at the end of every sprint.

---

## Project Overview

**Project**: AI Agent Assistant
**Repository**: /home/michaelhansen/Projects/github/ai_agent_assistant
**Started**: 2026-03-14
**Product Owner**: Michael Hansen
**Current Sprint**: Sprint-09 ✅ Complete (2026-06-22) — Vault Planning Cleanup (T09-03 Planner.md `/plan` markers verified, T09-04 Dashboard.md static index, T09-05 Inbox.md cleaned; 65 tests pass). Next: Sprint-10 (BLI-050 WhatsApp agent launcher). Stale LM Studio/n8n/Google-OAuth items (BLI-041–045) moved to Deferred/Icebox.
**Current Team**: Claude CLI (SM + dev agents)

---

## What This Project Does

A personal AI assistant that runs from the command line, using local LLMs (Ollama) to:
- Read tasks from LogSeq journals and Obsidian vault
- Sync tasks between LogSeq and Obsidian
- Check Google Calendar and interactively propose a daily schedule
- Run as a regular planning agent (cron/systemd) that prompts for calendar confirmations
- All processing runs locally via Ollama — no cloud required by default

---

## Quick Start for Incoming Team

1. Read this file completely
2. Read `.scrum/decisions.md` for architectural context
3. Read `.scrum/backlog.md` for prioritized work
4. Read current sprint plan: `.scrum/sprints/sprint-06/plan.md`
5. Summarize your understanding to the Product Owner before starting

---

## Codebase Entry Points

| Component | Path | Description |
|-----------|------|-------------|
| Main CLI | `main.py` | Orchestrator and CLI chat entry point (1092 lines) |
| LLM routing | `ai_orchestration.py` | Routes tasks to Ollama with fallback; `list_ollama_models()` |
| LogSeq agent | `logseq_agent.py` | Parses LATER/TODO tasks; `add_task()` and `mark_done()` write-back |
| Obsidian agent | `obsidian_agent.py` | Direct `.md` file parser — no Obsidian app required |
| Calendar agent | `calendar_agent.py` | Fetches Google Calendar, caches as YAML |
| Planning agent | `planning_agent.py` | Executes confirmed task bookings to Google Calendar |
| API server | `api_server.py` | FastAPI webhook server for n8n integration |
| n8n workflows | `n8n-workflows/` | 3 ready-to-import workflow JSON templates |
| Web UI | `app.py` | Streamlit dashboard (optional — CLI is the primary interface) |
| Config | `config.template` | Full config reference; copy to `.config` |
| Config example | `config.example` | Clean starter config for new users (Sprint-03) |
| Tests | `tests/` | pytest test suite |

---

## Sprint History

### Sprint 01 — ✅ Complete
- **Dates**: 2026-03-14 → 2026-03-15
- **Goal**: Remove OpenClaw, Ollama-first LLM, LogSeq task reading, n8n webhook API
- **Delivered**: All 7 tasks — OpenClaw removed, `list_ollama_models()`, LogSeq LATER/TODO parsing with line attribution, `/add-task` + `/done` CLI commands, FastAPI webhook server, n8n workflow templates
- **Commit**: `b445238` | **PO sign-off**: ✅ 2026-03-15

### Sprint 02 — ✅ Complete
- **Dates**: 2026-03-15 (started and completed same day — agents ran in parallel)
- **Goal**: Obsidian direct file parsing, Google Calendar interactive planning, LogSeq→Obsidian sync, cron-safe planning agent, clean CLI entry point
- **Delivered**: All 5 tasks
  - T02-01: `obsidian_agent.py` rewritten — direct `.md` parsing, no app required (592 tasks found in vault)
  - T02-02: `/sync-logseq` command — syncs LogSeq tasks to Obsidian `Inbox.md` with duplicate detection
  - T02-03: `--plan` flag + `handle_planning_session()` — per-task calendar confirmation
  - T02-04: TTY detection for cron safety; `--dry-run` flag; cron + systemd docs in `INSTALL.md`
  - T02-05: Clean CLI entry point — `/help` updated, startup status display, `/review` wired
- **Commit**: `c12f8ba` | **PO sign-off**: ✅ 2026-03-15

### Sprint 03 — ✅ Complete
- **Dates**: 2026-03-15 (started and completed same day — agents ran in parallel)
- **Goal**: Per-task Ollama model routing, clean config.example for new users, LLM-powered evening review
- **Delivered**: All 3 tasks
  - T03-01: `/routing` command — interactive model selector per task type, writes to `.config` immediately
  - T03-02: `config.example` created — clean starter config with one-line comments, cloud keys commented out
  - T03-03: `handle_evening_review()` rewritten — scans Obsidian + LogSeq, generates Ollama summary, optionally appends to journal
- **Commit**: `720f442` | **PO sign-off**: ✅ 2026-03-27

### Untracked work (post-Sprint-03, pre-Sprint-04)
The following agents were added outside of the sprint process (commit `720f442`) and need backlog registration and review:
- **`datainput_agent.py`** — Reads `datainput/reminders.json` (Apple Reminders export), deduplicates against `synced_reminders.json`, appends new tasks to Obsidian planner under `## Reminders`, then calls LLM to re-organise the full planner. Entry: `run(organise=True)`.
- **`logseq_later_agent.py`** — Scans LogSeq journals (last N days) and all pages for `LATER` tasks, deduplicates, writes `## LogSeq LATER Tasks` block to Obsidian planner. Entry: `run(write_to_obsidian=True)`.
- **`calendar_planning_agent.py`** — Gemini-only. Fetches Google Calendar (next 7 days) + Apple Reminders + LogSeq LATER tasks, builds Gemini prompt with user profile (chronotype, deep work window), saves weekly plan to `datainput/calendar_suggestions.md`. Requires `ENABLE_GEMINI=true`. Entry: `run(write_to_obsidian=False)`.
- **`cron_job.py`** — Orchestrates all agents in order with lockfile-based concurrency control and 5-minute hard timeout. Fixed zombie process leak in this period.

### Sprint 04 — ✅ Complete (2026-03-27 → 2026-04-02)
- **Goal**: main.py refactor, test suite, monitoring dashboard, terminal task visibility, agent scrum registration
- **Delivered**: All 4 tasks + BLI-025 (agent registration)
  - T04-01: `main.py` split — `task_utils.py` (97L), `cli_commands.py` (808L), `session.py` (155L), `main.py` reduced to 98 lines
  - T04-02: 13 new tests across 4 files (`test_datainput_agent`, `test_logseq_later_agent`, `test_calendar_planning_agent`, `test_cron_job`); `scripts/run_tests.sh` created; **42 pass, 1 skipped** (pre-existing failures fixed in `7f942ff`)
  - T04-03: `update_manager.py` extended (9 health checks), `scripts/status.py` Rich dashboard, `scripts/rotate_logs.sh`, cron rotation wired
  - T04-04: `terminal_views.py` (`/today`, `/week`), `scripts/remind.py` (3-channel reminders), `--today` CLI flag, `INSTALL.md` updated
- **Commits**: `daec6c2`, `7f942ff` | **PO sign-off**: pending

---

## Known Issues & Technical Debt

| ID | Description | Severity | Sprint introduced | Sprint resolved |
|----|-------------|----------|-------------------|-----------------|
| DEBT-001 | OpenClaw tightly coupled across 10+ files — removal needs careful ordering | High | Pre-sprint | ✅ Sprint-01 |
| DEBT-002 | Apple Reminders integration only works on macOS — dead code on Linux | Med | Pre-sprint | Sprint-04 (flag only) |
| DEBT-003 | `main.py` is now 1092 lines — should be split into focused modules | Med | Pre-sprint | ✅ Sprint-04 |
| DEBT-004 | `app.py` (Streamlit) duplicates logic from `main.py` — divergence risk | Low | Pre-sprint | — |
| DEBT-005 | New agents (datainput, logseq_later, calendar_planning) not registered in scrum backlog | Med | Post-Sprint-03 | ✅ Sprint-04 |
| DEBT-006 | Test suite does not cover new agents or cron orchestration | Med | Post-Sprint-03 | ✅ Sprint-04 |
| DEBT-007 | `system_status.json` only checks git/Ollama/venv — insufficient for full health picture | Low | Post-Sprint-03 | ✅ Sprint-04 |

---

### Sprint-05 — ✅ Complete (2026-04-03)
- **Goal**: Local ICS calendar engine + Google Tasks two-way sync
- **Delivered**: All 6 tasks — BLI-030 through BLI-035
  - `local_calendar_agent.py`: add/remove/list/today events, auto-creates `.ics`, no OAuth
  - `/add-event`, `/remove-event`, `/export-calendar`, `/import-calendar` CLI commands
  - `/today` and `/week` now read from local ICS first, fall back to Google YAML cache
  - `google_tasks_agent.py`: pull tasks → Obsidian, push `[x]` completions → Google Tasks
  - `cron_job.py`: `google_tasks` agent added to AGENT_MAP; `/google-tasks` CLI command
  - `check_local_calendar()` + `check_google_tasks()` in `/status` dashboard
- **Commit**: `908395d` | **Tests**: 95 passed, 1 skipped (22 new tests)
- **Side-effect**: T06-04 Universal Task Sync ICS path now unblocked

---

## Team Handoff Log

| Date | Handed from | Handed to | Sprint | Notes |
|------|------------|-----------|--------|-------|
| 2026-04-03 | Dev agent | Scrum Master | Sprint-06 | T06-03 completed. NanoClaw LogSeq skill added with `list-later`, `add-task`, `mark-done`, and `sync-to-obsidian`; `run_skill()` mount routing fixed; full suite green. See `.scrum/sprints/sprint-06/handoff.md`. |
| 2026-04-03 | Scrum Master | PO review | Sprint-06 | Sprint-06 architecture drafted. ADR-008/009/010 added. BLI-036–040 in backlog. Awaiting PO confirmation to plan Sprint-05 then Sprint-06. |
| 2026-04-02 | Scrum Master | PO review | Sprint-04 | Sprint-04 complete. All 4 tasks done, 42 tests pass. Awaiting PO sign-off and Sprint-05 planning. |
| 2026-03-27 | Scrum Master | PO review | Sprint-04 | Sprint-04 plan drafted. Awaiting PO review before dev starts. |
| 2026-03-15 | Dev agents | Scrum Master | Sprint-03 | All Sprint-03 tasks verified complete. Commit pending PO sign-off. |
| 2026-03-15 | Scrum Master | Dev agents | Sprint-03 | Sprint-01 and Sprint-02 complete. Sprint-03 started early — 3 parallel tasks ready. Run: `python scrum.py agent sprint-run` |
| 2026-03-15 | Dev agents | Scrum Master | Sprint-02 | All Sprint-02 tasks verified complete. Committed c12f8ba. |
| 2026-03-15 | Scrum Master (review) | Dev agents | Sprint-01 | File write permissions resolved. All 7 tasks applied and committed b445238. |
| 2026-03-14 | Product Owner (manual) | Claude CLI agents | Sprint-01 | Initial scrum setup |

---

### Sprint-06 Status — In Progress (2026-04-03)
- **Goal**: Distributed, secure, containerised architecture — LM Studio, NanoClaw, n8n Universal Task Sync, CLI Router
- **Status**: Wave 1 complete and Wave 2 complete. T06-01, T06-02, and T06-03 are done; Wave 3 remains blocked on Sprint-05 ICS engine for T06-04 and depends on completed NanoClaw skills for T06-05.
- **Tracks**:
  - **Inference**: T06-01 (LM Studio) — complete
  - **Containers/Security**: T06-02 → T06-03 complete; T06-05 now unblocked from the NanoClaw side
  - **Data flows**: T06-04 (Universal Task Sync) — still requires Sprint-05 ICS engine
- **New config keys introduced**: `ENABLE_LM_STUDIO`, `LM_STUDIO_MODEL`, `NANOCLAW_ENABLED`
- **Infrastructure requirement**: Docker must be running for NanoClaw Skills; n8n must be running for Universal Task Sync
- **Wave 2 delivery note**: LogSeq NanoClaw now supports extracting `LATER` tasks from LogSeq and syncing them into the Obsidian planner block for manual organisation or later scheduling by the planning agent.

---

## Blockers & Risks

| ID | Description | Owner | Status |
|----|-------------|-------|--------|
| RISK-001 | Ollama must be installed and running | Product Owner | ✅ Resolved — `ollama list` returns `qwen2.5:14b` |
| RISK-002 | Google Calendar `token.json` must exist | Product Owner | ✅ Resolved — `token.json` and `credentials.json` present |
| RISK-003 | `LOGSEQ_DIR` and `WORKSPACE_DIR` must be set in `.config` | Product Owner | ✅ Resolved — both set in `.config` |
