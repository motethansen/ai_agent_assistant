# T04-04 — Terminal task and calendar visibility

**Sprint**: 04 | **BLI**: BLI-029 | **Estimate**: M | **Agent**: dev-2
**Independent** — can run in parallel with T04-01 and T04-03

## Context

The system has full access to Google Calendar, Obsidian tasks, LogSeq tasks, and Apple Reminders — but there is no quick terminal view of what's happening today or this week. Users need to run multiple commands or open apps.

This task adds `/today` and `/week` compact Rich views and a `scripts/remind.py` terminal reminder tool.

**Decisions confirmed by PO (2026-03-27):**
- `scripts/remind.py` logs to file AND triggers n8n webhook in addition to macOS notification
- `/week` and `/today` always use the YAML cache; auto-refresh the cache if it is stale (>6h old)

## What to Do

### 1. `/today` command

Add to the chat command dispatcher:

```python
elif user_input.strip() == "/today":
    handle_today_view()
```

`handle_today_view()` in `cli_commands.py`:
1. Load Google Calendar events from `datainput/googlecalendar.yml` — auto-refresh cache if missing or >6h old (call `calendar_agent.fetch_and_cache()` silently)
2. Filter calendar events for today's date
3. Load unified tasks (`get_unified_tasks()`) — filter for tasks with a due date matching today
4. Additionally flag tasks whose due date is before today as "overdue"
5. Render a Rich table:

```
Today — Friday 27 March 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Time     Type        Description                 Source
 ───────  ──────────  ──────────────────────────  ──────────────
 09:00    📅 Event    Team standup                Google Cal
 11:00    📅 Event    Dentist                     Google Cal
 ─────    ✅ Task     Write project proposal      Obsidian
 ─────    ⚠️  OVERDUE  Fix login bug (due Mar 25)  LogSeq
```

- Events sorted by time; tasks below events (interleaved by time if task has a time component)
- Overdue tasks highlighted in red with `⚠️ OVERDUE` label

### 2. `/week` command

```python
elif user_input.strip() == "/week":
    handle_week_view()
```

`handle_week_view()` in `cli_commands.py`:
- Auto-refresh YAML cache if missing or >6h old (same logic as `/today`)
- Show next 7 days as a compact Rich table

```
Week view — 27 Mar → 02 Apr 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Date        Events        Tasks Due
 ──────────  ────────────  ────────────────────
 Fri 27 Mar  2 events      3 tasks
 Sat 28 Mar  —             1 task
 Sun 29 Mar  —             —
 Mon 30 Mar  3 events      2 tasks
 Tue 31 Mar  1 event       —
 Wed 01 Apr  2 events      1 task
 Thu 02 Apr  —             4 tasks
```

- Count summary only (no full text — keeps it compact)

### 3. Cache auto-refresh helper

Create `_ensure_calendar_cache(max_age_hours=6)` in `cli_commands.py`:
```python
def _ensure_calendar_cache(max_age_hours=6):
    """Refresh datainput/googlecalendar.yml if missing or older than max_age_hours."""
    cache_path = "datainput/googlecalendar.yml"
    if os.path.exists(cache_path):
        age_hours = (time.time() - os.path.getmtime(cache_path)) / 3600
        if age_hours <= max_age_hours:
            return  # Cache is fresh
        print(f"[Calendar] Cache is {age_hours:.1f}h old — refreshing...")
    else:
        print("[Calendar] No cache found — fetching...")
    try:
        import calendar_agent
        calendar_agent.fetch_and_cache()
    except Exception as e:
        print(f"[Calendar] Could not refresh cache: {e} — using existing data if available")
```

### 4. `--today` CLI flag

Add `--today` to argparse in `main.py`:
```python
parser.add_argument("--today", action="store_true", help="Show today's tasks and events, then exit")
```
Calls `handle_today_view()` non-interactively and exits.

### 5. `scripts/remind.py`

```
Usage: python scripts/remind.py "Task text" "HH:MM"
```

Three delivery mechanisms — all attempted, failures are non-fatal:

**A — macOS notification via `at` + `osascript`:**
```bash
echo 'osascript -e "display notification \"TASK\" with title \"Reminder\""' | at HH:MM
```
Skip silently if not on macOS or `at` not available.

**B — Log to file `logs/reminders.log`:**
```
2026-03-27 14:30 | SCHEDULED | Call dentist | set at 2026-03-27 09:15
```
Append one line per reminder set. Always runs.

**C — n8n webhook via `n8n_client.trigger()`:**
```python
n8n_client.trigger("reminder-set", {
    "task": "Call dentist",
    "remind_at": "14:30",
    "set_at": datetime.now().isoformat()
})
```
Skip silently if `N8N_WEBHOOK_URL` is not set in `.config` or request fails.

**Output to terminal:**
```
✅ Reminder set: "Call dentist" at 14:30
   📋 Logged to logs/reminders.log
   📨 Sent to n8n
   🔔 macOS notification scheduled
```
Only print lines for delivery mechanisms that actually succeeded.

### 6. Document in INSTALL.md

Add a "Terminal Reminders" section:
```markdown
## Terminal Reminders

Set a one-off reminder from the terminal:

    python scripts/remind.py "Call dentist" "14:30"

This will:
- Schedule a macOS notification at the given time (macOS only, requires `at` command)
- Log the reminder to `logs/reminders.log`
- Send a webhook event to n8n if `N8N_WEBHOOK_URL` is configured

To enable the `at` command on macOS, run: `sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.atrun.plist`
```

## Acceptance Criteria

- [ ] `/today` renders a Rich table of today's events + tasks (sourced from YAML cache + vault)
- [ ] `/today` auto-refreshes YAML cache if >6h old before rendering
- [ ] `/today` highlights overdue tasks in red
- [ ] `/week` renders a compact 7-day count summary table
- [ ] `/week` auto-refreshes YAML cache if >6h old
- [ ] `python main.py --today` calls the same view non-interactively and exits
- [ ] `scripts/remind.py "text" "HH:MM"` logs to `logs/reminders.log`
- [ ] `scripts/remind.py` sends n8n webhook via `n8n_client.trigger("reminder-set", payload)` when `N8N_WEBHOOK_URL` is set
- [ ] `scripts/remind.py` schedules macOS notification via `at` + `osascript` on macOS
- [ ] No crash if any delivery mechanism is unavailable — graceful skip with message
- [ ] `INSTALL.md` has "Terminal Reminders" section with `at` enable instructions

## Notes

- YAML cache path: `datainput/googlecalendar.yml` (set by `calendar_agent.py`)
- `get_unified_tasks()` is in `task_utils.py` after T04-01 — use it
- Tasks without a due date do NOT appear in `/today` or `/week`
- `n8n_client` is already implemented in `n8n_client.py` — import and call `trigger(path, payload)`
- Use `rich.table.Table` and `rich.console.Console`
- `remind.py` must work standalone: `python scripts/remind.py` — do not require `main.py` to be importable
