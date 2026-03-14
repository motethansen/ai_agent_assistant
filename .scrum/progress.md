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

### Sprint 01 — In Progress
- **Dates**: 2026-03-14 → TBD
- **Team**: Claude CLI agents
- **Goal**: Remove OpenClaw, make Ollama the default LLM, get LogSeq task reading working end-to-end
- **Plan**: `.scrum/sprints/sprint-01/plan.md`
- **Completed**: —
- **Deferred**: —
- **Demo approved by PO**: Pending

---

## Known Issues & Technical Debt

| ID | Description | Severity | Sprint introduced | Sprint resolved |
|----|-------------|----------|-------------------|-----------------|
| DEBT-001 | OpenClaw tightly coupled across 10+ files — removal needs careful ordering | High | Pre-sprint | Sprint-01 |
| DEBT-002 | Apple Reminders integration only works on macOS — dead code on Linux | Med | Pre-sprint | — |
| DEBT-003 | `main.py` is 867 lines — should be split into focused modules after OpenClaw removal | Med | Pre-sprint | — |
| DEBT-004 | `app.py` (Streamlit) duplicates logic from `main.py` — divergence risk | Low | Pre-sprint | — |

---

## Team Handoff Log

| Date | Handed from | Handed to | Sprint | Notes |
|------|------------|-----------|--------|-------|
| 2026-03-14 | Product Owner (manual) | Claude CLI agents | Sprint-01 | Initial scrum setup |

---

## Blockers & Risks

| ID | Description | Owner | Status |
|----|-------------|-------|--------|
| RISK-001 | Ollama must be installed and running for dev agents to test locally | Product Owner | Open — verify `ollama list` works before sprint-run |
| RISK-002 | Google Calendar credentials (`token.json`) must exist before calendar tasks can be tested | Product Owner | Open |
| RISK-003 | `LOGSEQ_DIR` and `WORKSPACE_DIR` (Obsidian) must be set in `.env` before LogSeq/Obsidian tasks run | Product Owner | Open |
