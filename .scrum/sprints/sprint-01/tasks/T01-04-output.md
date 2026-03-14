It seems file write permissions aren't granted in this session. The complete implementation is documented above. Here's a summary of everything that needs to be applied:

---

## 3. Dependencies Added

None.

---

## 4. Integration Notes (for T01-05)

**Updated `LogSeqAgent` API that T01-05 needs to know:**

| Method | Signature | Notes |
|--------|-----------|-------|
| `parse_tasks(text, source)` | → `list[dict]` | Replaces `parse_later_tasks`. Each dict now has `"marker"` key (`"LATER"` or `"TODO"`) in addition to `task`, `source`, `properties`. |
| `parse_later_tasks(text, source)` | → `list[dict]` | Kept as alias — safe to call, delegates to `parse_tasks`. |
| `source` field format | `"journal/2026_03_14:42"` | Colon-delimited line number appended. T01-05 can split on `:` to get file path + line for write-back operations. |
| `get_recent_tasks(days)` | unchanged | Now returns both LATER and TODO tasks. |
| `get_all_page_tasks()` | unchanged | Now returns both LATER and TODO tasks. |

**For T01-05 write-back**: Parse the source string with `source.rsplit(":", 1)` to get `(base_path, line_number)`. The `base_path` maps to `journals/{date_key}.md` or `pages/{name}.md` inside `LOGSEQ_DIR`.

---

## 5. Known Limitations

- **Days parameter is a file count, not a date window**: `get_recent_tasks(days=14)` reads the 14 most recent *files*, not the last 14 calendar days. Journals with no entries in between are skipped naturally, but a 14-day gap with no journals means fewer files are scanned.
- **Page tasks are unordered**: `get_all_page_tasks()` uses `os.listdir()` which has no guaranteed order. Large vaults may be slow.
- **Line numbers shift after edits**: If a LogSeq file is edited between reading and displaying, the `:42` line number may no longer point to the right line. This is acceptable for navigation hints but T01-05 should re-read the file before writing back.
- **Duplicate tasks**: If a task appears in both a journal and a page (e.g. via LogSeq's embed), it will appear twice in `--backlog`. Deduplication is out of scope.