# Sprint-05 Plan — Local ICS Calendar + Google Tasks Two-Way Sync

**Sprint**: 05
**Goal**: Replace Google Calendar API with a local ICS calendar engine; add Google Tasks two-way sync so tasks captured on mobile appear in Obsidian and completions flow back.
**Status**: ✅ Complete — 2026-04-03
**Epics**: E12, E13

---

## Task Summary

| Task | BLI | Title | Estimate | LLM Agent | Status |
|------|-----|-------|----------|-----------|--------|
| T05-01 | BLI-030 | Local ICS calendar engine — `local_calendar_agent.py`, `/add-event`, `/remove-event` | M | Claude Code | ✅ Done 2026-04-03 |
| T05-02 | BLI-031 | ICS export + import — `/export-calendar`, `/import-calendar` | S | Codex | ✅ Done 2026-04-03 |
| T05-03 | BLI-032 | Wire ICS into `/today`, `/week`, planning agent, `/status` | M | Claude Code | ✅ Done 2026-04-03 |
| T05-04 | BLI-033 | Google Tasks pull — `google_tasks_agent.py`, `sync_to_obsidian()` | M | Gemini | ✅ Done 2026-04-03 |
| T05-05 | BLI-034 | Google Tasks push — `sync_completions_to_google()` | S | Codex | ✅ Done 2026-04-03 |
| T05-06 | BLI-035 | Cron + CLI — `/google-tasks`, `check_google_tasks()`, `config.example` | S | Claude Code | ✅ Done 2026-04-03 |

---

## Execution Waves

```
Wave 1 (parallel):
  T05-01 local_calendar_agent.py (Claude Code)
  T05-04 google_tasks_agent.py   (Gemini)

Wave 2 (each after its Wave 1 dependency):
  T05-02 ICS export/import  (Codex)     — after T05-01
  T05-05 Google Tasks push  (Codex)     — after T05-04

Wave 3 (sequential — both touch update_manager.py):
  T05-03 Wire ICS into views (Claude Code) — first
  T05-06 Cron + CLI          (Claude Code) — after T05-03
```

---

## Commit

`908395d` — all 6 tasks in one commit. 22 new tests. Full suite: **95 passed, 1 skipped**.

## Side-effect unlocked

T06-04 (Universal Task Sync) ICS events path is now unblocked — `local_calendar_agent.list_events()` exists and `handle_universal_sync()` will send real calendar events to n8n instead of an empty list.
