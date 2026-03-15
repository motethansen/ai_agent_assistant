All changes are in place. Here is the completion report:

---

## Completion Report — T02-01

### 1. Files Modified

| File | Change |
|------|--------|
| `obsidian_agent.py` | Full rewrite — direct `.md` file parsing, no subprocess/CLI |
| `main.py` | `get_unified_tasks()` replaced CLI block with `ObsidianAgent(workspace_dir=…)`; `/done` handler now falls through to Obsidian if LogSeq misses |
| `config.template` | Updated `WORKSPACE_DIR` comment with clearer wording and both platform examples |
| `INSTALL.md` | Added **Obsidian Setup** section (vault path, config, task formats, backlog, `/done`) |

### 2. Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| `obsidian_agent.py` reads tasks from `.md` files — no Obsidian app needed | ✅ |
| `get_tasks()` returns `file` (relative path) and `line` (1-indexed) attributes | ✅ |
| `mark_done(task_text)` finds matching `- [ ]` and rewrites as `- [x]` | ✅ |
| `update_task(path, line, action="done")` marks the specific line done | ✅ |
| `python main.py --backlog` shows Obsidian tasks grouped by source file | ✅ (source key is `obsidian:<rel_path>:<line>`) |
| `WORKSPACE_DIR` not set → friendly info message, no crash | ✅ |
| `config.template` and `INSTALL.md` updated | ✅ |

### 3. Integration Notes for T02-02

T02-02 can use `ObsidianAgent` for writes via:

- **`update_task(path, line, action="done")`** — targeted line-level write; `path` may be relative (resolved against `workspace_dir`) or absolute; only `action="done"` is implemented.
- **`mark_done(task_text)`** — fuzzy text match; returns `True`/`False`; rewrites the first match found across all vault files.
- **`workspace_dir`** is always resolved from `WORKSPACE_DIR` config if not passed explicitly — constructing `ObsidianAgent()` with no args is safe as long as config is set.
- To add new write operations (e.g. `mark_todo`, `append_task`), follow the `_mark_done_in_file` pattern: read lines, mutate, write back atomically.

### 4. Issues / Deviations

- Line 434 in `main.py` still has a legacy `ObsidianAgent()` call (inside a `try` block in an unrelated path). Left untouched — it's guarded by try/except and is a separate feature flow (not part of `get_unified_tasks`).
- The `obsidian_path` parameter to `get_unified_tasks()` is no longer used for the primary Obsidian path (replaced by `WORKSPACE_DIR` config). The parameter is kept to preserve the existing call signature.