# Dev Agent Task Prompt — T02-01

> **ACTION REQUIRED: You are a Claude Code agent with file-editing tools (Read, Edit, Write, Bash).**
> **READ the actual source files in the project, then APPLY all changes directly to disk using your tools.**
> **Do NOT output code as text blocks. Write changes to the actual files.**
> **Project root: /home/michaelhansen/Projects/github/ai_agent_assistant**

> Self-contained — you have no other context. Read everything here carefully before acting.
> No dependencies — this task can start immediately.

---

## Identity & Role

You are a senior software developer on **AI Agent Assistant** — a personal CLI agent that uses local Ollama LLMs to manage tasks from LogSeq and Obsidian and interact with Google Calendar.

You are replacing the existing Obsidian CLI-based agent with a direct markdown file parser so that tasks can be read and written without the Obsidian app running.

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| Task source | Obsidian vault — markdown files under `WORKSPACE_DIR` |
| Task format | `- [ ] task text` (incomplete), `- [x] task text` (done) |
| Config | `.config` file via `config_utils.get_config_value()` |
| CLI display | `rich` library |

---

## Relevant Existing Code

### obsidian_agent.py (current — uses Obsidian CLI subprocess, requires app running)

The current `ObsidianAgent` class shells out to the `obsidian` CLI command. This is unreliable (requires the Obsidian app to be open). You need to **replace it** with a direct file-based implementation that reads and writes `.md` files directly.

Keep the class name `ObsidianAgent` and preserve method signatures used by `main.py`:
- `get_tasks(todo=True, done=False)` — returns list of task dicts
- `update_task(path, line, action="done")` — marks a task done in the file

New methods to add:
- `get_all_tasks(include_done=False)` — scans all `.md` files under `WORKSPACE_DIR`
- `mark_done(task_text)` — finds matching `- [ ]` task and rewrites as `- [x]`

### main.py — get_unified_tasks() (lines 42–110, relevant section)

```python
def get_unified_tasks(obsidian_path):
    obsidian_tasks = []
    try:
        agent = ObsidianAgent()
        raw_obs_tasks = agent.get_tasks(todo=True, format="json")
        if raw_obs_tasks:
            for t in raw_obs_tasks:
                text = t.get("text", "")
                clean_text = re.sub(r"^-\s+\[[ xX]\]\s+", "", text).strip()
                task_data = {
                    "task": clean_text,
                    "category": "Uncategorized",
                    "due_date": None,
                    "source": "Obsidian",
                    "file": t.get("file", ""),
                    "line": t.get("line", "")
                }
                # ... category and date extraction ...
                obsidian_tasks.append(task_data)
    except Exception as e:
        print(f"ObsidianAgent error: {e}")
    # ... LogSeq tasks below ...
```

### config.template — WORKSPACE_DIR section

```
WORKSPACE_DIR=/home/michaelhansen/Documents/Obsidian
```

---

## Your Task

**Task ID**: T02-01
**Title**: Obsidian task reading and writing via CLI (direct file parsing)
**Sprint**: Sprint-02
**Backlog item**: BLI-010

### Description

Rewrite `obsidian_agent.py` to parse Obsidian markdown files directly from disk — no Obsidian app or CLI required. Wire it into `get_unified_tasks()` in `main.py` so `python main.py --backlog` shows Obsidian tasks alongside LogSeq tasks.

### Changes to make

**`obsidian_agent.py`** — full rewrite (keep class name `ObsidianAgent`):

```python
class ObsidianAgent:
    def __init__(self, workspace_dir=None):
        # Read WORKSPACE_DIR from config if not provided
        self.workspace_dir = workspace_dir or get_config_value("WORKSPACE_DIR", None)

    def get_tasks(self, todo=True, done=False, format="dict"):
        """Scan all .md files and return tasks. Replaces CLI version."""
        # Walk workspace_dir recursively
        # Match lines: r"^\s*-\s+\[([ xX])\]\s+(.*)"
        # [ ] = incomplete (include if todo=True)
        # [x]/[X] = done (include if done=True)
        # Return list of dicts: {"text": str, "file": str, "line": int, "done": bool}

    def get_all_tasks(self, include_done=False):
        """Convenience wrapper — returns all incomplete tasks by default."""

    def mark_done(self, task_text: str) -> bool:
        """Find a matching - [ ] task by text and rewrite as - [x]. Returns True if found."""

    def update_task(self, path: str, line: int, action: str = "done"):
        """Mark a specific task done by file path and line number. Used by main.py."""
```

**`main.py`** — update `get_unified_tasks()`:
- Replace the try/except `ObsidianAgent()` block: pass `WORKSPACE_DIR` from config explicitly
- If `WORKSPACE_DIR` not set or path doesn't exist: print `"ℹ️  WORKSPACE_DIR not set — skipping Obsidian tasks"` and continue
- Ensure returned task dicts include `source: "obsidian:<relative_path>:<line>"` format

**`main.py`** — update the `/done` command handler (around line 782):
- After attempting `ls.mark_done()` (LogSeq), also attempt `ObsidianAgent().mark_done()` if not found in LogSeq
- Print which system the task was marked done in

**`config.template`** — update WORKSPACE_DIR comment:
```
# WORKSPACE_DIR: Path to your Obsidian vault directory (contains .md files).
# Linux example: WORKSPACE_DIR=/home/yourname/Documents/Obsidian
# Mac example:   WORKSPACE_DIR=/Users/yourname/Documents/Obsidian
WORKSPACE_DIR=/home/michaelhansen/Documents/Obsidian
```

**`INSTALL.md`** — add "Obsidian Setup" section explaining:
- What WORKSPACE_DIR should point to
- That the Obsidian app does NOT need to be running
- Supported task formats: `- [ ] task` and `- [x] done task`

### Acceptance Criteria
- [ ] `obsidian_agent.py` reads tasks directly from `.md` files — no Obsidian app needed
- [ ] `get_tasks()` returns tasks with `file` (relative path) and `line` (1-indexed) attributes
- [ ] `mark_done(task_text)` finds matching `- [ ]` line and rewrites as `- [x]`
- [ ] `update_task(path, line, action="done")` marks the specific line done
- [ ] `python main.py --backlog` shows Obsidian tasks grouped by source file
- [ ] `WORKSPACE_DIR` not set → friendly info message, no crash
- [ ] `config.template` and `INSTALL.md` updated with Obsidian setup instructions

---

## Completion Report

After applying all changes, write a brief report:

### 1. Files modified
### 2. Acceptance criteria check (✅/❌ per item)
### 3. Integration notes for T02-02
What T02-02 needs to know about the updated ObsidianAgent write API.
### 4. Any issues or deviations
