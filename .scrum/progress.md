# Project Progress — AI Agent Assistant

> This is the PRIMARY handoff document. Any incoming team reads this first.
> Scrum Master updates this at the end of every sprint.

---

## Project Overview

**Project**: AI Agent Assistant
**Repository**: /home/michaelhansen/Projects/github/ai_agent_assistant
**Started**: 2026-03-14
**Product Owner**: Michael Hansen
**Current Sprint**: Sprint-01
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
4. Read current sprint plan: `.scrum/sprints/sprint-01/plan.md`
5. Summarize your understanding to the Product Owner before starting

---

## Codebase Entry Points

| Component | Path | Description |
|-----------|------|-------------|
| Main CLI | `main.py` | Orchestrator and CLI chat entry point (867 lines) |
| LLM routing | `ai_orchestration.py` | Routes tasks to Ollama / Gemini / OpenAI / Claude with fallback |
| LogSeq agent | `logseq_agent.py` | Parses LATER/TODO tasks from LogSeq journals and pages |
| Obsidian agent | `obsidian_agent.py` | Reads/writes tasks and files in Obsidian vault |
| Calendar agent | `calendar_agent.py` | Fetches Google Calendar, caches as YAML, background sync |
| Planning agent | `planning_agent.py` | Executes confirmed task bookings to Google Calendar |
| Monitoring | `monitoring_agent.py` | Health checks for Ollama and other services |
| Web UI | `app.py` | Streamlit dashboard (optional — CLI is the primary interface) |
| Config | `config.template` | Copy to `.env` and fill in paths and API keys |
| Tests | `tests/` | pytest test suite |

---

## Sprint History

### Sprint 01 — ✅ Complete
- **Dates**: 2026-03-14 → 2026-03-15 (closed early)
- **Team**: Claude CLI agents
- **Goal**: Remove OpenClaw, make Ollama the default LLM, get LogSeq task reading working end-to-end
- **Plan**: `.scrum/sprints/sprint-01/plan.md`
- **Latest standup**: `.scrum/sprints/sprint-01/standup-2026-03-15.md`
- **Completed (2/7)**:
  - T01-01: OpenClaw removed from tests, scripts, agents ✅
  - T01-02: OpenClaw removed from core (ai_orchestration.py, main.py, config) ✅
- **Ready to implement (5/7)** — implementations documented in task output files, pending code application:
  - T01-03: Ollama-first routing + `list_ollama_models()` + `/models` interactive selector
  - T01-04: LogSeq TODO parsing + source attribution + `--backlog` CLI flag
  - T01-05: `/add-task` and `/done` commands in CLI (depends on T01-04)
  - T01-06: FastAPI webhook server + docker-compose (new files)
  - T01-07: n8n workflow JSON templates + README_N8N.md (depends on T01-06)
- **Deferred**: —
- **Demo approved by PO**: ✅ 2026-03-15 — all 8 demos passed, commit b445238

### Sprint 02 — Planned (2026-03-22 onward)
- **Goal**: Obsidian task management, Google Calendar planning agent, clean CLI entry point
- **BLIs**: BLI-010, BLI-011, BLI-012, BLI-013, BLI-014
- **Details**: See backlog.md Sprint-02 Placeholder section

### Sprint 03 — Planned (TBD)
- **Goal**: Per-task model routing, config.example cleanup, evening review agent
- **BLIs**: BLI-020, BLI-021, BLI-022
- **Details**: See backlog.md Sprint-03 Placeholder section

---

## Known Issues & Technical Debt

| ID | Description | Severity | Sprint introduced | Sprint resolved |
|----|-------------|----------|-------------------|-----------------|
| DEBT-001 | OpenClaw tightly coupled across 10+ files — removal needs careful ordering | High | Pre-sprint | ✅ Sprint-01 |
| DEBT-002 | Apple Reminders integration only works on macOS — dead code on Linux | Med | Pre-sprint | — |
| DEBT-003 | `main.py` is 867 lines — should be split into focused modules after OpenClaw removal | Med | Pre-sprint | — |
| DEBT-004 | `app.py` (Streamlit) duplicates logic from `main.py` — divergence risk | Low | Pre-sprint | — |

---

## Team Handoff Log

| Date | Handed from | Handed to | Sprint | Notes |
|------|------------|-----------|--------|-------|
| 2026-03-15 | Scrum Master (review) | Dev agents | Sprint-01 | File write permissions resolved. T01-03 through T01-07 ready to implement — apply code from task output files. Commit T01-01/T01-02 deletions first. |
| 2026-03-14 | Product Owner (manual) | Claude CLI agents | Sprint-01 | Initial scrum setup |

---

## Blockers & Risks

| ID | Description | Owner | Status |
|----|-------------|-------|--------|
| RISK-001 | Ollama must be installed and running for dev agents to test locally | Product Owner | Open — verify `ollama list` works before sprint-run |
| RISK-002 | Google Calendar credentials (`token.json`) must exist before calendar tasks can be tested | Product Owner | Open |
| RISK-003 | `LOGSEQ_DIR` and `WORKSPACE_DIR` (Obsidian) must be set in `.env` before LogSeq/Obsidian tasks run | Product Owner | Open |
