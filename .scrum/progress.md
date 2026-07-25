# Project Progress — AI Agent Assistant

> This is the PRIMARY handoff document. Any incoming team reads this first.
> Scrum Master updates this at the end of every sprint.

---

## Project Overview

**Project**: AI Agent Assistant
**Repository**: /home/michaelhansen/Projects/github/ai_agent_assistant
**Started**: 2026-03-14
**Product Owner**: Michael Hansen
**Current Sprint**: Sprint-10 ✅ (2026-07-25) — `GET /suggest` morning-focus API: today + overdue tasks distilled to a top-3 by the LLM router; server-side counterpart of `clients/claude_frontend/suggest.py`, ready to wire into the morning brief.

**Recently delivered (reconciled 2026-07-25 against git history):**
- **E23 Two-way Kanban** (Jul 3) — `010 Planning/Today Kanban.md`; `/plan /sync /done /kanban` and `…?` question cards executed into a 🤖 Agent column (`agents/kanban_agent.py`); `python main.py --watch` live watcher.
- **E24 Claude Agent SDK frontend** (Jul 3) — `clients/claude_frontend/` (`frontend.py` interactive, `suggest.py` one-shot) drives the API via SDK tools; deployed on the Mac Mini.
- **API write endpoints** — `POST /tasks`, `POST /tasks/done`.
- **E20 WhatsApp launcher** — DELIVERED at the fleet level in distributed-infra's bridge (`agent <llm> <prompt>` + `assist <sub>`), not in this repo → assistant-side dependency done.
- **Deployment** — API runs on the Mac Mini as launchd `com.mh.aiassistant.api` (:7890, python3.12 venv). Deploy = push from MacBook → `git pull` + kickstart on the mini. Monitored by the **Vantage** service-monitor as `mm-assistant-api`.
- Stale LM Studio / NanoClaw / n8n / Google-OAuth items retired by the April redesign (flat Python package — see `decisions.md`).
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

> Reconciled 2026-07-25 to the post-redesign flat-package structure (the old
> `ai_orchestration.py` / `*_agent.py` / `api_server.py` / `n8n-workflows/` / Streamlit
> `app.py` entries were pre-redesign and no longer exist).

| Component | Path | Description |
|-----------|------|-------------|
| Main CLI | `main.py` | Entry point + flag dispatch: `--api --watch --status --sync --today --plan --chat` |
| API server | `api/server.py` | FastAPI (:7890) — `/tasks` (GET/POST), `/tasks/done`, `/calendar`, `/notes`, `/note`, `/dashboard`, `POST /plan`, **`GET /suggest`**, `/status`, `/llm`, `/health` |
| Agents | `agents/` | `kanban_agent`, `planning_agent`, `notes_agent`, `reminders_agent`, `sync_agent`, `project_agent`, `knowledge_agent` |
| LLM routing | `llm/router.py` | `ask()` / `stream()` with per-task provider + fallback chain; providers: `ollama`, `gemini`, `groq`, `deepseek` |
| Integrations | `integrations/` | `obsidian.py` (vault task parse + write-back), `logseq.py`, `calendar.py` (ICS) |
| Terminal UI | `ui/` | `chat.py`, `commands.py`, `views.py` |
| Claude SDK frontend | `clients/claude_frontend/` | `frontend.py` (interactive) + `suggest.py` (one-shot) over the API |
| Watcher | `watcher.py` | live vault/kanban watchdog (`main.py --watch`) |
| Config | `config.py`, `config.template` | config loader + full reference; copy template to `.config` |
| Tests | `tests/` | pytest suite |

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

### Sprint-06 → Sprint-10 — ✅ Complete (Apr–Jul 2026)

_(Consolidated 2026-07-25 — this section previously read "Sprint-06 In Progress", which was long stale.)_

The **April redesign** (see `decisions.md`) cut n8n / LM Studio / NanoClaw / ChromaDB / Docker in favour of a flat Python package. What the earlier Sprint-06 plan called "containerised LM Studio + NanoClaw + n8n Universal Task Sync" was **superseded** — those tracks are retired. Delivered since:

- **Redesigned structure** — `agents/`, `api/`, `llm/`, `integrations/`, `ui/`, `clients/`.
- **LLM router** — Ollama-first with `gemini → groq → deepseek` fallback (`llm/router.py`).
- **ICS calendar engine** (Sprint-05 → integrated) — `integrations/calendar.py`, replacing the Google Calendar API path.
- **HTTP API** (:7890) — for fleet integration (distributed-infra workers, WhatsApp bridge, Claude SDK frontend).
- **Sprint-09** (2026-06-22) — vault planning cleanup; 65 tests pass.
- **E23/E24** (Jul 3) — two-way Kanban + Claude Agent SDK frontend (see Current Sprint above).
- **Sprint-10** (2026-07-25) — `GET /suggest` morning-focus API.

Config keys `ENABLE_LM_STUDIO` / `LM_STUDIO_MODEL` / `NANOCLAW_ENABLED` are obsolete.

---

## Blockers & Risks

| ID | Description | Owner | Status |
|----|-------------|-------|--------|
| RISK-001 | Ollama must be installed and running | Product Owner | ✅ Resolved — `ollama list` returns `qwen2.5:14b` |
| RISK-002 | Google Calendar `token.json` must exist | Product Owner | ✅ Resolved — `token.json` and `credentials.json` present |
| RISK-003 | `LOGSEQ_DIR` and `WORKSPACE_DIR` must be set in `.config` | Product Owner | ✅ Resolved — both set in `.config` |
