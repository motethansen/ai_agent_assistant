# Sprint-08 Plan — Time-Horizon Planner + Cal Grid + Ollama Planning + n8n Morning Trigger

**Sprint**: 08
**Goal**: Full time-bucketed task planner in the terminal, unix `cal`-style month grid with task/event markers, Ollama-backed plan generation (removing the Gemini-only gate), and a wired n8n morning-plan webhook that orchestrates the full pipeline.
**Status**: ✅ Complete — 2026-04-06
**Epics**: E11 (Terminal Task Visibility), E07 (n8n Workflow Integration), E06 (CLI Personal Agent)

---

## Task Summary

| Task | BLI | Title | Estimate | Wave |
|------|-----|-------|----------|------|
| T08-01 | BLI-046 | `/plan` command — time-horizon task buckets (today/week/month/year/backlog) | M | Wave 1 |
| T08-02 | BLI-047 | `/cal` command — unix cal-style month grid with task/event markers | M | Wave 1 |
| T08-03 | BLI-048 | Ollama-backed plan generation — remove Gemini-only gate in `calendar_planning_agent.py` | S | Wave 2 |
| T08-04 | BLI-049 | n8n `morning-plan` webhook — full pipeline trigger via `api_server.py` | S | Wave 2 |

---

## Execution Waves

```
Wave 1 (parallel — both in terminal_views.py but different functions):
  ┌─────────────────────────────────┐  ┌─────────────────────────────────────┐
  │ T08-01 /plan time-horizon view  │  │ T08-02 /cal month grid              │
  │ terminal_views.py               │  │ terminal_views.py                   │
  │ cli_commands.py                 │  │ cli_commands.py                     │
  └─────────────────────────────────┘  └─────────────────────────────────────┘

Wave 2 (after Wave 1 — T08-04 uses T08-03 Ollama output):
  ┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐
  │ T08-03 Ollama plan generation        │  │ T08-04 n8n morning-plan webhook      │
  │ calendar_planning_agent.py           │  │ api_server.py                        │
  │ ai_orchestration.py (no change)      │  │ n8n-workflows/morning-planning.json  │
  └──────────────────────────────────────┘  └──────────────────────────────────────┘
```

---

## Definition of Done

- [x] `bash scripts/run_tests.sh` — zero failures (95 passed, 2 skipped)
- [x] `/plan` shows tasks in 5 time-horizon buckets; `/plan today` filters to today only
- [x] `/cal` renders a Rich month grid with `•` on days that have tasks or events
- [x] `/cal-day YYYY-MM-DD` drills into a single day's events and tasks
- [x] `calendar_planning_agent.generate_plan()` works with Ollama (no `ENABLE_GEMINI=true` required)
- [x] `POST /webhook/morning-plan` returns a plan JSON and writes `datainput/calendar_suggestions.md`
- [x] All new CLI commands listed in `/help` output
