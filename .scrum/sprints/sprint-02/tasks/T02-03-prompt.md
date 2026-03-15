# Dev Agent Task Prompt — T02-03

> **ACTION REQUIRED: You are a Claude Code agent with file-editing tools (Read, Edit, Write, Bash).**
> **READ the actual source files in the project, then APPLY all changes directly to disk using your tools.**
> **Do NOT output code as text blocks. Write changes to the actual files.**
> **Project root: /home/michaelhansen/Projects/github/ai_agent_assistant**

> Self-contained — you have no other context. Read everything here carefully before acting.
> No dependencies — this task can start in parallel with T02-01.

---

## Identity & Role

You are a senior software developer on **AI Agent Assistant** — a personal CLI agent using local Ollama LLMs to manage tasks and Google Calendar.

You are wiring the existing planning infrastructure into a proper `--plan` CLI flow: read tasks, fetch calendar, propose schedule, confirm interactively, write to Google Calendar.

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| Calendar | Google Calendar API via `calendar_manager.py` |
| Task sources | Obsidian + LogSeq via `get_unified_tasks()` in `main.py` |
| LLM | Ollama via `ai_orchestration.generate_schedule()` |
| Config | `.config` via `config_utils.get_config_value()` |

---

## Relevant Existing Code

### calendar_manager.py — key functions

```python
def get_calendar_service() -> service | None:
    """Authenticates and returns Google Calendar service. Returns None if credentials missing."""

def get_busy_slots(service, calendar_ids=['primary'], date_str=None) -> list:
    """Returns list of busy slots: [{"summary": str, "start": str, "end": str}]"""

def create_events(service, schedule, calendar_id='primary'):
    """Creates events on Google Calendar. schedule items: {"task": str, "start": "ISO", "end": "ISO"}"""
```

### planning_agent.py — current state

```python
class PlanningAgent:
    def __init__(self, service, calendar_id): ...
    def execute_plan(self, schedule, obsidian_path):
        """Submits confirmed schedule to Google Calendar and updates Obsidian."""
```

### main.py — handle_morning_planning() (lines 312–360)

```python
def handle_morning_planning(obsidian_path):
    tasks = get_unified_tasks(obsidian_path)
    service = calendar_manager.get_calendar_service()
    busy_slots = CalendarAgent().get_busy_slots_from_yml()
    result = ai_orchestration.generate_schedule(tasks, busy_slots, morning_mode=True, ...)
    schedule = result.get("schedule", [])
    # Asks: "Add these items to your calendar? (y/n/skip)"
    # Calls PlanningAgent.execute_plan(schedule, obsidian_path) on confirm
```

### main.py — CLI args (line 847+)

```python
parser.add_argument("--morning", action="store_true", help="Start morning planning mode")
# --plan does NOT yet exist — add it
```

### ai_orchestration.py — generate_schedule signature

```python
def generate_schedule(tasks, busy_slots, morning_mode=True, workspace_dir=None, logseq_dir=None):
    """Returns {"schedule": [...], "suggestions": [...]} or None"""
```

---

## Your Task

**Task ID**: T02-03
**Title**: Planning agent with Google Calendar interactive scheduling
**Sprint**: Sprint-02
**Backlog item**: BLI-012

### Description

Improve the planning flow: replace the single bulk "add all?" confirm with per-task interactive prompts. Add a `--plan` CLI flag. Handle missing credentials gracefully.

### Changes to make

**`main.py`** — add `--plan` argument:
```python
parser.add_argument("--plan", action="store_true", help="Run interactive planning session against Google Calendar")
```

Wire it to a new `handle_planning_session()` function (or reuse/rename `handle_morning_planning()`).

**`main.py`** — update planning flow to per-task confirmation:

```python
def handle_planning_session(obsidian_path):
    # 1. Check credentials
    if not os.path.exists("token.json"):
        print("⚠️  Google Calendar not connected. Run the assistant once interactively to authenticate.")
        print("    Missing: token.json")
        return

    # 2. Get tasks and calendar
    tasks = get_unified_tasks(obsidian_path)
    if not tasks:
        print("ℹ️  No tasks found in backlog.")
        return

    service = calendar_manager.get_calendar_service()
    if not service:
        print("⚠️  Could not connect to Google Calendar.")
        return

    # 3. Fetch free slots for next 7 days
    busy_slots = []
    for i in range(7):
        day = (datetime.datetime.now() + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        busy_slots.extend(calendar_manager.get_busy_slots(service, date_str=day))

    # 4. Generate schedule via LLM
    result = ai_orchestration.generate_schedule(tasks, busy_slots, morning_mode=True,
                                                workspace_dir=obsidian_path)
    if not result or not result.get("schedule"):
        print("ℹ️  No schedule proposed.")
        return

    # 5. Per-task confirmation
    confirmed = []
    for item in result["schedule"]:
        day_time = item["start"].split("T")[1][:5] if "T" in item["start"] else item["start"]
        date_part = item["start"].split("T")[0] if "T" in item["start"] else ""
        print(f"\nSchedule '{item['task']}' on {date_part} at {day_time}? [y/n/s(kip all)]: ", end="")
        try:
            choice = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if choice == "y":
            confirmed.append(item)
        elif choice == "s":
            break

    # 6. Book confirmed items
    if confirmed:
        calendar_id = get_config_value("CALENDAR_ID", "primary")
        calendar_manager.create_events(service, confirmed, calendar_id=calendar_id)
        print(f"\n✅ Booked {len(confirmed)} event(s) to Google Calendar.")
    else:
        print("No events booked.")
```

Also wire `/plan` as a CLI chat command (same as `--plan` flag).

### Acceptance Criteria
- [ ] `python main.py --plan` triggers the planning session
- [ ] Session reads tasks from unified Obsidian + LogSeq backlog
- [ ] Session fetches Google Calendar for next 7 days and passes busy slots to LLM
- [ ] Each proposed task shows: task name, date, time, and `[y/n/s]` prompt
- [ ] Only `y` items are booked to Google Calendar
- [ ] `s` skips the rest of the proposed schedule
- [ ] `token.json` missing → prints clear setup message and exits gracefully (no crash, no traceback)
- [ ] `/plan` in the chat loop triggers the same flow
- [ ] `--plan --dry-run` shows proposed schedule without booking (add `--dry-run` flag)

---

## Completion Report

### 1. Files modified
### 2. Acceptance criteria check (✅/❌ per item)
### 3. Integration notes for T02-04
What T02-04 needs to know about non-interactive (cron/no-TTY) mode handling.
### 4. Any issues or deviations
