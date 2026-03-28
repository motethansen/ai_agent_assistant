# T04-03 — Monitoring and status dashboard

**Sprint**: 04 | **BLI**: BLI-028 | **Estimate**: M | **Agent**: dev-3
**Independent** — can run in parallel with T04-01

## Context

`update_manager.py` currently checks only git, Ollama, and venv. It writes to `logs/system_status.json`. The system has many more critical data sources whose health is invisible: Google Calendar cache age, Obsidian vault reachability, last cron run, reminders sync age.

The goal is a Rich terminal status dashboard accessible via `/status` in the chat or `python scripts/status.py` standalone.

## What to Do

### 1. Extend `update_manager.py`

Add these new check functions:

```python
def check_gemini():
    """GEMINI_API_KEY present in .config and non-empty."""

def check_google_calendar():
    """datainput/googlecalendar.yml exists; return age in hours."""

def check_logseq_dir():
    """LOGSEQ_DIR from config exists and is a directory."""

def check_obsidian_vault():
    """WORKSPACE_DIR from config exists and is a directory."""

def check_cron_last_run():
    """Parse last timestamp line from logs/cron_sync.log."""

def check_reminders_sync():
    """Age of datainput/reminders.json in hours."""
```

Update `run_all_checks()` to call all new checks and include results in `system_status.json`.

Status values: `"ok"`, `"warning"`, `"error"`. Include `"message"` and `"age_hours"` where relevant.

### 2. Create `scripts/status.py`

Standalone Rich dashboard. No dependency on `main.py`.

Layout — use Rich `Table` or `Panel`:

```
┌─ AI Agent Assistant — System Status ──────────────────────────┐
│ Last check: 2026-03-27 09:40                                   │
├────────────────────┬──────────┬──────────────────────────────┤
│ Check              │ Status   │ Detail                        │
├────────────────────┼──────────┼──────────────────────────────┤
│ Git                │ ✅ OK    │ Up to date                    │
│ Ollama             │ ✅ OK    │ Running (localhost:11434)     │
│ Gemini API key     │ ✅ OK    │ Key present                   │
│ Google Calendar    │ ✅ OK    │ Updated 2.1h ago              │
│ LogSeq dir         │ ✅ OK    │ /path/to/logseq               │
│ Obsidian vault     │ ✅ OK    │ /path/to/obsidian             │
│ Last cron run      │ ✅ OK    │ 45 min ago                    │
│ Reminders sync     │ ⚠️  WARN │ Last synced 26h ago           │
│ Venv               │ ✅ OK    │ .venv present                 │
└────────────────────┴──────────┴──────────────────────────────┘
```

- Green for ok, yellow for warning (>24h stale), red for error
- Exits with code 1 if any check is "error"

### 3. Wire `/status` into chat commands

In `cli_commands.py` (or `main.py` chat loop), add:
```python
elif user_input.strip() == "/status":
    import subprocess
    subprocess.run(["python", "scripts/status.py"])
```

### 4. Log rotation in `scripts/rotate_logs.sh`

```bash
#!/bin/bash
# Keep last 7 days of cron_sync.log, archive older lines
# Archive destination: logs/archive/YYYY-MM/cron_sync_YYYY-MM-DD.log
```

Call `bash scripts/rotate_logs.sh` at the end of `cron_job.py` main run block.

## Acceptance Criteria

- [ ] `update_manager.py` has 6 new check functions, all included in `run_all_checks()`
- [ ] `logs/system_status.json` includes all new checks after running `python update_manager.py`
- [ ] `scripts/status.py` renders a Rich dashboard with all checks, colour-coded
- [ ] `/status` in chat mode calls the dashboard
- [ ] `scripts/rotate_logs.sh` keeps last 7 days, archives older entries
- [ ] Log rotation called at end of `cron_job.py`
- [ ] `scripts/status.py` exits 0 when all ok, exits 1 when any check is "error"

## Notes

- `scripts/status.py` must be runnable with `python scripts/status.py` from repo root
- Do not require `main.py` or `chat_ui.py` to be importable in `status.py`
- Use `rich` library (already in requirements)
- For `check_cron_last_run()`: parse lines matching `^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}` pattern in `logs/cron_sync.log`
