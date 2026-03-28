# T04-01 — Split main.py into focused modules

**Sprint**: 04 | **BLI**: BLI-026 | **Estimate**: L | **Agent**: dev-1

## Context

`main.py` is 1092 lines and contains mixed concerns: CLI argument handling, interactive chat commands, task utilities, file watcher setup, and startup display. This makes it hard to navigate, test, and extend.

This is a **structural refactor only** — no functional changes.

## What to Do

Split `main.py` into these four files:

### 1. `task_utils.py`
Move here:
- `get_unified_tasks()` — merges Obsidian + LogSeq + Apple Reminders tasks
- Any helper functions that operate on task lists (filtering, formatting, deduplication helpers)

### 2. `cli_commands.py`
Move here:
- `handle_morning_planning()`
- `handle_planning_session()`
- `handle_evening_review()`
- `sync_logseq_to_obsidian()`
- `sync_calendar_to_markdown()`
- `execute_actions()`
- All individual `/command` handler functions called from within `handle_chat_mode()`
- `handle_chat_mode()` itself (the main chat loop)

### 3. `session.py`
Move here:
- `display_stats()`
- `display_docs()`
- `TaskSyncHandler` (Watchdog event handler class)
- The file watcher startup code
- The background calendar sync loop

### 4. `main.py` (reduced)
Keep only:
- Imports from the new modules
- `argparse` setup and argument parsing
- `if __name__ == "__main__"` block that calls the appropriate function

## Acceptance Criteria

- [ ] `cli_commands.py` exists with all `handle_*()` and chat command functions
- [ ] `task_utils.py` exists with `get_unified_tasks()` and helpers
- [ ] `session.py` exists with startup, watcher, and background loop
- [ ] `main.py` is ≤150 lines
- [ ] All CLI flags still work: `--morning`, `--plan`, `--dry-run`, `--evening`, `--chat`, `--backlog`, `--stats`, `--docs`, `--no-web`, `--file`
- [ ] All chat commands still work in `python main.py --chat`
- [ ] `python main.py` starts cleanly with no import errors
- [ ] No functional changes — pure structural refactor

## Notes

- Check all inter-module imports carefully — circular imports are the main risk
- `get_unified_tasks()` is called from multiple places; make sure all call sites are updated
- Do NOT change any function signatures or return values
- Run `python main.py --help` to verify argparse still works after refactor
