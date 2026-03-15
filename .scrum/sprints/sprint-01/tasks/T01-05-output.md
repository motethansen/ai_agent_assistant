All changes applied. Here's the completion report:

---

## Completion Report

### 1. Files modified
- `logseq_agent.py` — added `add_task()` and `mark_done()` methods
- `main.py` — added `/add-task` and `/done` command handlers
- `chat_ui.py` — added both commands to `COMMAND_DESCRIPTIONS`

### 2. Acceptance criteria check

| AC | Status | Note |
|----|--------|------|
| `add_task(description)` appends `- LATER <description>` | ✅ | Writes `\n- LATER {description}\n` in append mode |
| Creates journal file if it doesn't exist | ✅ | `open(..., "a")` creates file if absent |
| Creates `journals/` directory if missing | ✅ | `os.makedirs(self.journals_dir, exist_ok=True)` |
| `/add-task` calls `add_task()` and shows file path | ✅ | Uses `chat_ui.render_success` + `render_info` for path |
| `mark_done()` finds matching LATER/TODO and rewrites as DONE | ✅ | Regex match on group(3), writes `DONE` in place |
| `/done` reports success or "not found" | ✅ | `render_success` or `render_warning` |
| No LogSeq app required | ✅ | Direct file I/O only |
| `/help` lists both new commands | ✅ | Added to `COMMAND_DESCRIPTIONS` in `chat_ui.py` |

### 3. Integration notes for Sprint-02

- `LogSeqAgent.add_task(description, date_key=None)` returns the file path written — Sprint-02 tasks (e.g., BLI-011 Obsidian sync) can use this return value for cross-vault linking.
- `mark_done(task_text, days_back=14)` does substring matching on task text — Sprint-02 could extend this to accept task IDs or line numbers for precision matching.
- Both methods operate on `journals/` only — page write-back (BLI-011) will need a separate `add_page_task()` method following the same pattern.

### 4. Issues or deviations

None. The task prompt referenced `parse_tasks()` as a T01-04 addition, but the existing code has `parse_later_tasks()` — the write methods don't depend on that, so no issue. The `args` variable pattern in `main.py` uses `parts[1:]` joined (matching existing command style) rather than a separate `args` split, which is consistent with how the rest of the command handlers work.