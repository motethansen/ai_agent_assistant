# T04-02 — Expand test suite

**Sprint**: 04 | **BLI**: BLI-027 | **Estimate**: L | **Agent**: dev-2
**Depends on**: T04-01 complete (imports from new module paths)

## Context

Three agents added post-Sprint-03 have zero test coverage: `datainput_agent.py`, `logseq_later_agent.py`, `calendar_planning_agent.py`. The cron orchestrator `cron_job.py` also has no tests. Existing test files live in `tests/` and use `pytest` with `unittest.mock`.

## What to Do

### 1. `tests/test_datainput_agent.py`
Test `datainput_agent.py`:
- `sync_reminders_to_planner()` — given a `reminders.json` with 2 tasks and an empty `synced_reminders.json`, both tasks are appended to the planner under `## Reminders`
- Duplicate detection — if a task key is already in `synced_reminders.json`, it is not added again
- `organise_planner()` — mock `ai_orchestration.generate()` to return a valid organised string; verify it is written back to the planner file
- `run(organise=False)` — `organise_planner()` is NOT called

### 2. `tests/test_logseq_later_agent.py`
Test `logseq_later_agent.py`:
- Parser correctly extracts `LATER` tasks from a journal fixture file (create a temp file)
- Tasks from both journals and pages directories are collected
- Duplicate tasks (same text from different files) are deduplicated
- When `write_to_obsidian=True`, the `## LogSeq LATER Tasks` block is written to the Obsidian planner

### 3. `tests/test_calendar_planning_agent.py`
Test `calendar_planning_agent.py`:
- Mock `ai_orchestration.generate()` (Gemini path) to return a plan string
- Verify the plan is saved to `datainput/calendar_suggestions.md`
- When `ENABLE_GEMINI=false` in config, `run()` exits early and returns `None`

### 4. `tests/test_cron_job.py`
Test `cron_job.py`:
- Lockfile prevents concurrent run: create the lockfile manually before calling the cron run function; verify it exits early with a "already running" message
- `--agents datainput` flag: verify only the datainput agent function is called (mock all agent `run()` functions)
- Stale lock: write a lockfile with a timestamp >300s ago; verify it is removed and run proceeds

### 5. `scripts/run_tests.sh`
Create a shell script:
```bash
#!/bin/bash
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
pytest tests/ -v --tb=short "$@"
```
Make it executable.

## Acceptance Criteria

- [ ] `tests/test_datainput_agent.py` — all cases pass, no real filesystem writes (use `tmp_path`)
- [ ] `tests/test_logseq_later_agent.py` — all cases pass
- [ ] `tests/test_calendar_planning_agent.py` — all cases pass, Gemini mocked
- [ ] `tests/test_cron_job.py` — all cases pass, all agents mocked
- [ ] `scripts/run_tests.sh` is executable and runs `pytest tests/ -v`
- [ ] `pytest tests/ -v` — zero failures across full suite

## Notes

- Use `pytest`'s `tmp_path` fixture for all file operations — do NOT write to real vault/LogSeq dirs
- Mock `ai_orchestration.generate` at the module level with `@patch('datainput_agent.ai_orchestration.generate')`
- Import paths will be from the new modules after T04-01 — update if needed
- Do not add real API keys or credentials to any test file
