# Dev Agent Task Prompt — T02-02

> **ACTION REQUIRED: You are a Claude Code agent with file-editing tools (Read, Edit, Write, Bash).**
> **READ the actual source files in the project, then APPLY all changes directly to disk using your tools.**
> **Do NOT output code as text blocks. Write changes to the actual files.**
> **Project root: /home/michaelhansen/Projects/github/ai_agent_assistant**

> Self-contained — you have no other context. Read everything here carefully before acting.
> PREREQUISITE: T02-01 must be complete — `ObsidianAgent` must support direct file writes.

---

## Identity & Role

You are a senior software developer on **AI Agent Assistant** — a personal CLI agent using local Ollama LLMs to manage tasks across LogSeq and Obsidian.

You are building a one-way sync: LogSeq open tasks → Obsidian `Inbox.md`.

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| Source | LogSeq journals + pages (`LOGSEQ_DIR`) |
| Target | Obsidian vault file (`WORKSPACE_DIR/Inbox.md` by default) |
| Config | `.config` via `config_utils.get_config_value()` |

---

## Relevant Existing Code

### logseq_agent.py — read methods (after T01-04)

```python
class LogSeqAgent:
    def get_recent_tasks(self, days=7) -> list:
        # Returns: [{"task": str, "source": "journal/YYYY_MM_DD:line", "properties": dict}]

    def get_all_page_tasks(self) -> list:
        # Returns same format from pages/*.md
```

### obsidian_agent.py — write methods (after T02-01)

```python
class ObsidianAgent:
    def __init__(self, workspace_dir=None): ...

    # After T02-01 this class writes files directly.
    # Read the actual file to confirm append/write method signatures.
```

### config.template — relevant keys

```
WORKSPACE_DIR=/home/michaelhansen/Documents/Obsidian
LOGSEQ_DIR=/home/michaelhansen/Documents/LogSeq
# SYNC_TARGET_PAGE: Obsidian file where LogSeq tasks are synced (relative to WORKSPACE_DIR)
SYNC_TARGET_PAGE=000 Inbox/Inbox.md   ← add this key
```

---

## Your Task

**Task ID**: T02-02
**Title**: LogSeq → Obsidian task sync
**Sprint**: Sprint-02
**Backlog item**: BLI-011

### Description

Add a `/sync-logseq` CLI command that pulls all open LATER/TODO tasks from LogSeq and appends them to a configurable Obsidian page. Duplicates must be detected and skipped.

### Changes to make

**`main.py`** — add `/sync-logseq` command handler in the CLI chat loop:

Logic:
1. Read `LOGSEQ_DIR` and `WORKSPACE_DIR` from config — error if either not set
2. Collect all open tasks from LogSeq: `get_recent_tasks(days=30)` + `get_all_page_tasks()`
3. Read `SYNC_TARGET_PAGE` from config (default: `Inbox.md`)
4. Read current content of the target Obsidian file (create if not exists)
5. For each LogSeq task, check if task text already appears in the file (duplicate detection)
6. Append new tasks in this format:
   ```
   - [ ] <task text> #logseq <!-- source: <logseq_source> -->
   ```
7. Write updated file back to disk
8. Print summary: `"✅ Synced X tasks, skipped Y duplicates → Inbox.md"`

Also support `AUTO_SYNC_LOGSEQ=true` config key — if set, run sync automatically at startup.

**`config.template`** — add:
```
# SYNC_TARGET_PAGE: Obsidian page (relative to WORKSPACE_DIR) where LogSeq tasks are synced
SYNC_TARGET_PAGE=Inbox.md
# AUTO_SYNC_LOGSEQ: Set to true to sync LogSeq tasks to Obsidian on every startup
AUTO_SYNC_LOGSEQ=false
```

### Acceptance Criteria
- [ ] `/sync-logseq` command syncs open LATER/TODO tasks from LogSeq journals + pages to target Obsidian file
- [ ] Duplicate detection: tasks already in the target file are skipped (match by task text)
- [ ] Each synced task gets `#logseq` tag and `<!-- source: ... -->` comment
- [ ] Summary printed: "X tasks synced, Y duplicates skipped → <file>"
- [ ] `SYNC_TARGET_PAGE` in config controls the target file (default `Inbox.md`)
- [ ] `AUTO_SYNC_LOGSEQ=true` triggers sync at startup
- [ ] Both `LOGSEQ_DIR` and `WORKSPACE_DIR` missing → clear error, no crash
- [ ] `config.template` updated with `SYNC_TARGET_PAGE` and `AUTO_SYNC_LOGSEQ`

---

## Completion Report

### 1. Files modified
### 2. Acceptance criteria check (✅/❌ per item)
### 3. Integration notes for T02-05
### 4. Any issues or deviations
