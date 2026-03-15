# Dev Agent Task Prompt — T02-05

> **ACTION REQUIRED: You are a Claude Code agent with file-editing tools (Read, Edit, Write, Bash).**
> **READ the actual source files in the project, then APPLY all changes directly to disk using your tools.**
> **Do NOT output code as text blocks. Write changes to the actual files.**
> **Project root: /home/michaelhansen/Projects/github/ai_agent_assistant**

> Self-contained — you have no other context. Read everything here carefully before acting.
> PREREQUISITES: T02-01 (Obsidian file-based agent) and T02-03 (--plan flag) must be complete.

---

## Identity & Role

You are a senior software developer on **AI Agent Assistant** — a personal CLI agent using local Ollama LLMs to manage tasks and Google Calendar.

You are cleaning up the CLI entry point so all core commands work end-to-end and `python main.py` is the single clean way to use the assistant.

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| CLI display | `rich` library |
| Config | `.config` via `config_utils.get_config_value()` |

---

## Relevant Existing Code

### main.py — current CLI args (line 847+)

```python
parser.add_argument("--docs",    action="store_true")
parser.add_argument("--stats",   action="store_true")
parser.add_argument("--morning", action="store_true")
parser.add_argument("--evening", action="store_true")
parser.add_argument("--chat",    action="store_true")
parser.add_argument("--backlog", action="store_true")
parser.add_argument("--file",    type=str, default="daily_note.md")
# After T02-03: --plan, --dry-run added
```

### main.py — chat command handler (around line 560+)

Currently handles: `/backlog`, `/sync`, `/models`, `/add-task`, `/done`, `/settings`, `/help`, `/cmd`

After T02-01: `/done` works for Obsidian too
After T02-02: `/sync-logseq` added
After T02-03: `/plan` added

### main.py — startup block (around line 460+)

Current startup: loads history, prints banner, checks Ollama.

---

## Your Task

**Task ID**: T02-05
**Title**: Clean CLI entry point
**Sprint**: Sprint-02
**Backlog item**: BLI-014

### Description

Audit and clean up the `main.py` entry point. Ensure all core commands are wired and working. Update `/help` to list every command. Add `--no-web` flag. Confirm `python main.py --help` exits cleanly.

### Changes to make

**`main.py`** — add `--no-web` flag (no-op but documented):
```python
parser.add_argument("--no-web", action="store_true",
    help="Suppress any Streamlit/web UI references (CLI-only mode)")
```

**`main.py`** — update `/help` command handler to list ALL current commands:

```
Available commands:
  /backlog              Show all pending tasks (Obsidian + LogSeq)
  /plan                 Run interactive planning session with Google Calendar
  /add-task <text>      Add a LATER task to today's LogSeq journal
  /done <text>          Mark a matching task done in LogSeq or Obsidian
  /sync-logseq          Sync LogSeq tasks to Obsidian Inbox
  /models               Show and select installed Ollama models
  /review               Show tasks completed today
  /settings             View/edit configuration
  /help                 Show this help
  /quit                 Exit
```

**`main.py`** — verify startup sequence:
1. Read `WORKSPACE_DIR` and `LOGSEQ_DIR` from config — print status for each (set/not set)
2. Check Ollama is running and list models (Sprint-01 `list_ollama_models()`)
3. If `AUTO_SYNC_LOGSEQ=true` in config, run LogSeq → Obsidian sync silently at startup

**`main.py`** — wire `/review` command if not already present:
- Shows tasks marked `- [x]` or `DONE` today across Obsidian and LogSeq journals
- Simple file scan, no LLM needed

**`INSTALL.md`** — add "Quick Start" section at the top:
```markdown
## Quick Start
python main.py          # Launch interactive CLI chat
python main.py --backlog # Print task list and exit
python main.py --plan    # Run calendar planning session
python main.py --plan --dry-run  # Preview plan without booking
```

### Acceptance Criteria
- [ ] `python main.py --help` exits code 0 and lists all flags cleanly
- [ ] `python main.py` launches CLI without any Streamlit import error
- [ ] Startup shows: Ollama status + models, WORKSPACE_DIR status, LOGSEQ_DIR status
- [ ] `/help` lists all commands: `/backlog`, `/plan`, `/add-task`, `/done`, `/sync-logseq`, `/models`, `/review`, `/settings`, `/help`, `/quit`
- [ ] `/review` shows tasks completed today (basic implementation — no LLM required)
- [ ] `--no-web` flag accepted without error
- [ ] `INSTALL.md` Quick Start section added

---

## Completion Report

### 1. Files modified
### 2. Acceptance criteria check (✅/❌ per item)
### 3. Any issues or deviations
