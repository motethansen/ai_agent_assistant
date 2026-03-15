All changes applied. Here's the summary:

---

### 1. Summary

Audited and fixed the full LogSeq task-reading pipeline. Four files were modified.

---

### 2. Modified Files

#### `logseq_agent.py`
- `parse_later_tasks()` → renamed to `parse_tasks()`, now matches both `LATER` and `TODO` via `r"^\s*-\s+(LATER|TODO)\s+(.*)"`.
- Source attribution now includes 1-based line number: `f"{source}:{line_num}"` → e.g. `journal/2026_03_14:42`.
- All internal callers (`get_tasks_for_date`, `get_recent_tasks`, `get_all_page_tasks`) updated.
- `parse_later_tasks` kept as a backward-compatibility alias.
- Minor string updates: "No LATER tasks found." → "No tasks found."

#### `main.py` — `get_unified_tasks()` and `--backlog`
- Replaced the raw `parse_logseq_tasks` loop with `LogSeqAgent` (`get_recent_tasks(days=14)` + `get_all_page_tasks()`).
- If `LOGSEQ_DIR` is not set: prints `ℹ️  LOGSEQ_DIR not set — skipping LogSeq tasks. Set it in .env`
- If `LOGSEQ_DIR` is set but missing: prints `⚠️  LOGSEQ_DIR is set but does not exist: <path>`
- Added `--backlog` CLI argument: calls `get_unified_tasks()` then `chat_ui.render_backlog()` and exits.

#### `config.template`
- Improved `LOGSEQ_DIR` comment with Linux and Mac path examples.

#### `INSTALL.md`
- Added "LogSeq Setup" section: how to find the graph path, sample config snippet, task format examples (`- LATER` / `- TODO`), and `--backlog` usage.

---

### 3. Dependencies Added
None.

---

### 4. Integration Notes for T01-05 (task write-back)

The updated `LogSeqAgent.parse_tasks()` now returns `source` as `"journal/2026_03_14:42"` (with line number). T01-05 can split on `:` to recover the file date and line number for targeted in-place edits. The `parse_tasks` method signature is unchanged: `(text, source="") → list[dict]`.

---

### 5. Known Limitations

- `get_recent_tasks(days=14)` counts files, not calendar days — if you have gaps in journaling, it reaches back further than 14 calendar days.
- Journal tasks and page tasks may duplicate if the same task text appears in both; no deduplication is done.
- The `--backlog` display depends on `chat_ui.render_backlog()` — if that function is not yet implemented, it will raise an `AttributeError`.