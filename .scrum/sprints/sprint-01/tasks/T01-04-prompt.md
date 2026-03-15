# Dev Agent Task Prompt — T01-04

> **ACTION REQUIRED: You are a Claude Code agent with file-editing tools (Read, Edit, Write, Bash).**
> **READ the actual source files in the project, then APPLY all changes directly to disk using your tools.**
> **Do NOT output code as text blocks. Write changes to the actual files.**
> **Project root: /home/michaelhansen/Projects/github/ai_agent_assistant**
>
> Self-contained — you have no other context. Read everything here carefully before acting.
> This task can run in parallel with T01-01 and T01-02 — it does not depend on them.

---

## Identity & Role

You are a senior software developer working on **AI Agent Assistant** — a personal CLI agent that uses local LLMs (Ollama) to manage tasks from LogSeq and Obsidian and interact with Google Calendar.

You are verifying, fixing, and end-to-end testing the **LogSeq task reading pipeline** so that `python main.py --backlog` correctly shows tasks from LogSeq journals and pages.

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| Task source | LogSeq graph directory (markdown files) |
| Journal format | `journals/YYYY_MM_DD.md` |
| Pages format | `pages/<name>.md` |
| Task marker | Lines starting with `- LATER` or `- TODO` |
| Config | `.env` file via `config_utils.get_config_value()` |
| CLI display | `rich` library |

---

## Relevant Existing Code

### logseq_agent.py (complete file — 240 lines)

```python
"""
LogSeq Agent — reads journals and pages from a LogSeq graph directory.

Journal files: journals/YYYY_MM_DD.md
Pages files:   pages/<name>.md

Tasks are identified by lines starting with "- LATER".
"""
import os
import re
import datetime

MONTHS = {
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'may': '05', 'june': '06', 'july': '07', 'august': '08',
    'september': '09', 'october': '10', 'november': '11', 'december': '12'
}

class LogSeqAgent:
    def __init__(self, logseq_dir):
        self.logseq_dir = logseq_dir
        self.journals_dir = os.path.join(logseq_dir, "journals")
        self.pages_dir = os.path.join(logseq_dir, "pages")

    def _journal_path(self, date_key):
        return os.path.join(self.journals_dir, f"{date_key}.md")

    def _read(self, path):
        if not os.path.exists(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def parse_later_tasks(self, text, source=""):
        tasks = []
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            m = re.match(r"^\s*-\s+LATER\s+(.*)", lines[i])
            if m:
                raw = m.group(1).strip()
                raw = re.sub(r"\{\{(?:renderer|query|clojure|embed|include)\s+.*?\}\}", "", raw).strip()
                raw = re.sub(r"\*\*\d{1,2}:\d{2}\*\*\s*", "", raw).strip()
                raw = re.sub(r"\[\[.*?\]\]:\s*", "", raw).strip()
                task = {"task": raw, "source": source, "properties": {}}
                j = i + 1
                while j < len(lines):
                    nxt = lines[j]
                    prop = re.match(r"^\s+:([\w-]+):\s*(.*)", nxt)
                    if prop:
                        k, v = prop.group(1).lower(), prop.group(2).strip()
                        task["properties"][k] = v
                        if k == "url" and v not in task["task"]:
                            task["task"] += f" ({v})"
                        j += 1
                    elif nxt.strip() == "" or re.match(r"^\s*-\s", nxt):
                        break
                    else:
                        j += 1
                i = j
                tasks.append(task)
            else:
                i += 1
        return tasks

    def get_tasks_for_date(self, date_key):
        path = self._journal_path(date_key)
        text = self._read(path)
        if not text:
            return None, []
        tasks = self.parse_later_tasks(text, source=f"journal/{date_key}")
        return text, tasks

    def get_recent_tasks(self, days=7):
        all_tasks = []
        if not os.path.exists(self.journals_dir):
            return all_tasks
        files = sorted(
            [f for f in os.listdir(self.journals_dir) if re.match(r"\d{4}_\d{2}_\d{2}\.md$", f)],
            reverse=True
        )
        for fname in files[:days]:
            date_key = fname[:-3]
            path = os.path.join(self.journals_dir, fname)
            text = self._read(path)
            tasks = self.parse_later_tasks(text, source=f"journal/{date_key}")
            all_tasks.extend(tasks)
        return all_tasks

    def get_all_page_tasks(self):
        all_tasks = []
        if not os.path.exists(self.pages_dir):
            return all_tasks
        for fname in os.listdir(self.pages_dir):
            if fname.endswith(".md"):
                path = os.path.join(self.pages_dir, fname)
                text = self._read(path)
                tasks = self.parse_later_tasks(text, source=f"page/{fname[:-3]}")
                all_tasks.extend(tasks)
        return all_tasks

    def format_tasks(self, tasks):
        if not tasks:
            return "No LATER tasks found."
        lines = []
        for i, t in enumerate(tasks, 1):
            lines.append(f"{i}. {t['task']}  _(source: {t['source']})_")
        return "\n".join(lines)

    def context_for_recent(self, days=7):
        tasks = self.get_recent_tasks(days)
        header = f"LogSeq recent journals (last {days} days) — LATER tasks ({len(tasks)} found):"
        return f"{header}\n{self.format_tasks(tasks)}"

    def context_for_all_page_tasks(self):
        tasks = self.get_all_page_tasks()
        header = f"LogSeq pages — LATER tasks ({len(tasks)} found):"
        return f"{header}\n{self.format_tasks(tasks)}"
```

### main.py — get_unified_tasks() (relevant section)

```python
def get_unified_tasks(obsidian_path):
    """Merges tasks from Obsidian, LogSeq, and Apple Reminders."""
    # ... obsidian tasks ...

    # LogSeq tasks
    logseq_dir = get_config_value("LOGSEQ_DIR", None)
    if logseq_dir and os.path.exists(logseq_dir):
        from logseq_agent import LogSeqAgent
        ls_agent = LogSeqAgent(logseq_dir)
        ls_tasks = ls_agent.get_recent_tasks(days=14)
        # ls_tasks are dicts: {"task": str, "source": str, "properties": dict}
        # unified list expects: {"task": str, "category": str, "source": str}
        for t in ls_tasks:
            logseq_tasks.append({
                "task": t["task"],
                "category": t["properties"].get("category", "Personal"),
                "source": t["source"]
            })

    # ... merge and return ...
```

### config.template — LogSeq section

```
LOGSEQ_DIR=/path/to/your/logseq/graph
```

---

## Your Task

**Task ID**: T01-04
**Title**: Verify and fix LogSeq task parsing end-to-end
**Sprint**: Sprint-01
**Backlog item**: BLI-004

### Description

Audit the full path from LogSeq directory → `logseq_agent.py` → `get_unified_tasks()` → `--backlog` CLI output. Fix any gaps. Also ensure `TODO` tasks are parsed in addition to `LATER`. Add a clear error when `LOGSEQ_DIR` is not set.

### Specific changes

**`logseq_agent.py`**:
- Update `parse_later_tasks()` to also match `- TODO` lines (rename method to `parse_tasks()` or add a `TODO` branch)
- Include line number in the source string: e.g. `"journal/2026_03_14:42"` — this helps the user navigate to the source
- Ensure `get_recent_tasks()` also calls the updated parser so TODO tasks are included

**`main.py`**:
- In `get_unified_tasks()`, check if `LOGSEQ_DIR` is set and exists; if not, print a clear message: `"ℹ️  LOGSEQ_DIR not set — skipping LogSeq tasks. Set it in .env"`
- Ensure LogSeq tasks appear in the `--backlog` output
- Add `--backlog` CLI argument if it does not already exist: prints the unified task list and exits

**`config.template`**:
- Improve the `LOGSEQ_DIR` comment:
```
# LOGSEQ_DIR: Path to your LogSeq graph folder (the one containing journals/ and pages/).
# Linux example:  LOGSEQ_DIR=/home/yourname/logseq/my-graph
# Mac example:    LOGSEQ_DIR=/Users/yourname/Documents/LogSeq/my-graph
LOGSEQ_DIR=/path/to/your/logseq/graph
```

**`INSTALL.md`**:
- Add a "LogSeq Setup" section explaining how to find the graph path and set `LOGSEQ_DIR`
- Show a sample working config snippet
- Explain task format: `- LATER task description` and `- TODO task description`

### Acceptance Criteria
- [ ] `parse_later_tasks()` (or renamed `parse_tasks()`) matches both `LATER` and `TODO` task lines
- [ ] Source attribution includes line number: `journal/2026_03_14:42`
- [ ] `python main.py --backlog` runs and shows LogSeq tasks (journals + pages) when `LOGSEQ_DIR` is valid
- [ ] When `LOGSEQ_DIR` is not set, a friendly info message is shown (not a crash)
- [ ] When `LOGSEQ_DIR` is set but directory doesn't exist, a warning is shown
- [ ] `config.template` has improved `LOGSEQ_DIR` comment with example paths
- [ ] `INSTALL.md` has a LogSeq Setup section

### Out of Scope
- Do NOT implement task writing back to LogSeq files — that is T01-05
- Do NOT change Obsidian task reading
- Do NOT change the LLM integration

---

## Output Format

### 1. Summary

### 2. New / Modified Files

#### `logseq_agent.py` [MODIFIED]
```python
[complete file content]
```

#### `main.py` [MODIFIED — show get_unified_tasks() and --backlog argument handling only]

#### `config.template` [MODIFIED — show only the changed LOGSEQ_DIR section]

#### `INSTALL.md` [MODIFIED — show only the new LogSeq Setup section]

### 3. Dependencies Added
None

### 4. Integration Notes
[What T01-05 needs to know about the updated logseq_agent.py API]

### 5. Known Limitations
