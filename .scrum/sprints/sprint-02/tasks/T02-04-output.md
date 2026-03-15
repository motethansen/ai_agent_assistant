All changes look correct. Here is the completion report:

---

## Completion Report

### 1. Files Modified

| File | Change |
|------|--------|
| `main.py` | Added `import sys`; added `is_interactive = sys.stdin.isatty()` to `handle_planning_session()`; silent exit when no tasks in non-interactive mode; non-interactive schedule print block before per-task confirmation loop; `"Dry run — no events created."` message to `--dry-run` path |
| `config.template` | Added `PLAN_TIME=08:00` with comment |
| `INSTALL.md` | Added "Scheduled Planning (cron / systemd)" section with cron line and systemd service+timer unit files |

Note: `--plan` and `--dry-run` flags + their dispatch in the `if/elif` block were already present from T02-03.

### 2. Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| `--plan` in cron/non-TTY: prints schedule to stdout and exits without hanging | ✅ — `is_interactive` check routes to print-and-return before any `input()` |
| No tasks found in non-interactive mode → silent exit code 0 | ✅ — `if not tasks: if is_interactive: print(...); return` |
| `--plan --dry-run` shows schedule without writing to calendar (TTY and non-TTY) | ✅ — `dry_run` branch runs before `is_interactive` check, always prints and returns |
| `PLAN_TIME` added to `config.template` | ✅ |
| `INSTALL.md` has cron setup with correct path and systemd unit file template | ✅ |
| Interactive mode (TTY) behaviour from T02-03 unchanged | ✅ — per-task `input()` loop only reached when `is_interactive=True` and not dry-run |

### 3. Issues / Deviations

None. The `--plan`/`--dry-run` flags and their dispatch were already present in the codebase (T02-03 had already been applied), so only the TTY-safety changes, config entry, and docs needed to be added.