# Project Progress — AI Agent Assistant

> This is the PRIMARY handoff document. Any incoming team reads this first.
> Scrum Master updates this at the end of every sprint.

---

## Project Overview

**Project**: AI Agent Assistant
**Repository**: /home/michaelhansen/Projects/github/ai_agent_assistant
**Started**: 2026-03-14
**Product Owner**: Michael Hansen
**Current Sprint**: Sprint-03
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
4. Read current sprint plan: `.scrum/sprints/sprint-03/plan.md`
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

### Sprint 03 — 🔄 In Progress
- **Dates**: 2026-03-15 → 2026-03-22 (started early)
- **Goal**: Per-task Ollama model routing, clean config.example for new users, LLM-powered evening review
- **Plan**: `.scrum/sprints/sprint-03/plan.md`
- **Tasks**: T03-01 (interactive /routing), T03-02 (config.example), T03-03 (evening review with LLM summary)
- **All 3 tasks independent — run in parallel**: `python scrum.py agent sprint-run`

---

## Known Issues & Technical Debt

| ID | Description | Severity | Sprint introduced | Sprint resolved |
|----|-------------|----------|-------------------|-----------------|
| DEBT-001 | OpenClaw tightly coupled across 10+ files — removal needs careful ordering | High | Pre-sprint | ✅ Sprint-01 |
| DEBT-002 | Apple Reminders integration only works on macOS — dead code on Linux | Med | Pre-sprint | — |
| DEBT-003 | `main.py` is now 1092 lines — should be split into focused modules | Med | Pre-sprint | — |
| DEBT-004 | `app.py` (Streamlit) duplicates logic from `main.py` — divergence risk | Low | Pre-sprint | — |

---

## Team Handoff Log

| Date | Handed from | Handed to | Sprint | Notes |
|------|------------|-----------|--------|-------|
| 2026-03-15 | Scrum Master | Dev agents | Sprint-03 | Sprint-01 and Sprint-02 complete. Sprint-03 started early — 3 parallel tasks ready. Run: `python scrum.py agent sprint-run` |
| 2026-03-15 | Dev agents | Scrum Master | Sprint-02 | All Sprint-02 tasks verified complete. Committed c12f8ba. |
| 2026-03-15 | Scrum Master (review) | Dev agents | Sprint-01 | File write permissions resolved. All 7 tasks applied and committed b445238. |
| 2026-03-14 | Product Owner (manual) | Claude CLI agents | Sprint-01 | Initial scrum setup |

---

## Blockers & Risks

| ID | Description | Owner | Status |
|----|-------------|-------|--------|
| RISK-001 | Ollama must be installed and running | Product Owner | ✅ Resolved — `ollama list` returns `qwen2.5:14b` |
| RISK-002 | Google Calendar `token.json` must exist | Product Owner | ✅ Resolved — `token.json` and `credentials.json` present |
| RISK-003 | `LOGSEQ_DIR` and `WORKSPACE_DIR` must be set in `.config` | Product Owner | ✅ Resolved — both set in `.config` |
