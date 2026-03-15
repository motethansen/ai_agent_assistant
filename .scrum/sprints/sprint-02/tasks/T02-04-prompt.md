# Dev Agent Task Prompt — T02-04

> **ACTION REQUIRED: You are a Claude Code agent with file-editing tools (Read, Edit, Write, Bash).**
> **READ the actual source files in the project, then APPLY all changes directly to disk using your tools.**
> **Do NOT output code as text blocks. Write changes to the actual files.**
> **Project root: /home/michaelhansen/Projects/github/ai_agent_assistant**

> Self-contained — you have no other context. Read everything here carefully before acting.
> PREREQUISITE: T02-03 must be complete — `--plan` flag and `handle_planning_session()` must exist.

---

## Identity & Role

You are a senior software developer on **AI Agent Assistant** — a personal CLI agent using local Ollama LLMs to manage tasks and Google Calendar.

You are making the planning agent safe to run non-interactively (cron, systemd) and adding `--dry-run` support plus setup instructions.

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| Scheduling | cron / systemd timer (Linux) |
| Config | `.config` via `config_utils.get_config_value()` |

---

## Relevant Existing Code

After T02-03, `main.py` will have:

```python
def handle_planning_session(obsidian_path):
    # ...
    # Per-task prompts using input() — these hang in cron/non-TTY context
    choice = input().strip().lower()
```

The problem: `input()` blocks forever when there is no TTY (cron job, systemd). This task fixes that.

### main.py — TTY detection pattern

```python
import sys
is_interactive = sys.stdin.isatty()
```

---

## Your Task

**Task ID**: T02-04
**Title**: Scheduled / cron-triggered planning agent
**Sprint**: Sprint-02
**Backlog item**: BLI-013

### Description

Make `--plan` safe for non-interactive use: detect TTY, skip prompts in cron mode and print a summary instead. Add `--dry-run`. Document cron and systemd setup in `INSTALL.md`.

### Changes to make

**`main.py`** — update `handle_planning_session()`:

1. Add TTY detection at the top:
   ```python
   is_interactive = sys.stdin.isatty()
   ```

2. In cron (non-interactive) mode: skip `input()` calls, print the full proposed schedule to stdout, and exit without booking:
   ```python
   if not is_interactive:
       print("📋 Proposed schedule (non-interactive mode — no calendar writes):")
       for item in result["schedule"]:
           print(f"  [{item['start']}] {item['task']}")
       print(f"\nℹ️  Run interactively to confirm and book: python main.py --plan")
       return
   ```

3. If no tasks found in non-interactive mode: exit silently with code 0 (no output).

**`main.py`** — add `--dry-run` flag:
```python
parser.add_argument("--dry-run", action="store_true",
    help="Show proposed plan without writing to Google Calendar")
```
Pass `dry_run` into `handle_planning_session()`. When dry-run: show the full schedule, print "Dry run — no events created.", exit.

**`config.template`** — add:
```
# PLAN_TIME: Default time for scheduled planning runs (informational — set in your cron/systemd config)
PLAN_TIME=08:00
```

**`INSTALL.md`** — add "Scheduled Planning" section:

```markdown
## Scheduled Planning (cron / systemd)

### cron
Add to your crontab (`crontab -e`):
```
0 8 * * 1-5 cd /home/michaelhansen/Projects/github/ai_agent_assistant && python main.py --plan >> /tmp/ai-plan.log 2>&1
```

### systemd timer
Create `/etc/systemd/user/ai-plan.service`:
```
[Unit]
Description=AI Agent morning planning

[Service]
Type=oneshot
WorkingDirectory=/home/michaelhansen/Projects/github/ai_agent_assistant
ExecStart=/home/michaelhansen/Projects/github/ai_agent_assistant/.venv/bin/python main.py --plan
```

Create `/etc/systemd/user/ai-plan.timer`:
```
[Unit]
Description=Run AI planning daily at 08:00

[Timer]
OnCalendar=Mon-Fri 08:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable: `systemctl --user enable --now ai-plan.timer`
```

### Acceptance Criteria
- [ ] `python main.py --plan` in a cron/non-TTY context prints schedule to stdout and exits without hanging
- [ ] No tasks found in non-interactive mode → silent exit with code 0
- [ ] `python main.py --plan --dry-run` shows proposed schedule without writing to calendar (works in both TTY and non-TTY)
- [ ] `PLAN_TIME` added to `config.template`
- [ ] `INSTALL.md` has cron setup with correct path and systemd unit file template
- [ ] Interactive mode (TTY) behaviour from T02-03 is unchanged

---

## Completion Report

### 1. Files modified
### 2. Acceptance criteria check (✅/❌ per item)
### 3. Any issues or deviations
