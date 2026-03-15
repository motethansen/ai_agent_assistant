## Sprint-02 Plan — AI Agent Assistant

**Date**: 2026-03-15 | **Sprint dates**: 2026-03-22 → 2026-03-29

---

### Sprint Goal

Enable Obsidian task management and Google Calendar planning so the assistant maintains a unified task list and can propose a daily schedule — all from the CLI.

---

### Sprint Backlog

| Task ID | BLI | Title | Agent | Estimate | Dependencies |
|---------|-----|-------|-------|----------|--------------|
| T02-01 | BLI-010 | Obsidian task reading and writing via CLI | dev-1 | M | None |
| T02-02 | BLI-011 | LogSeq → Obsidian task sync | dev-1 | L | T02-01 |
| T02-03 | BLI-012 | Planning agent with Google Calendar scheduling | dev-2 | L | None |
| T02-04 | BLI-013 | Scheduled / cron-triggered planning agent | dev-2 | M | T02-03 |
| T02-05 | BLI-014 | Clean CLI entry point (`/backlog`, `/plan`, `/sync`, `/review`) | dev-1 | S | T02-01, T02-03 |

**Velocity**: 2L + 2M + 1S — consistent with Sprint-01 throughput.

---

### Task Acceptance Criteria

---

#### T02-01 — Obsidian task reading and writing via CLI
**Agent**: dev-1 | **BLI**: BLI-010 | **Estimate**: M

- [x] `obsidian_agent.py` reads tasks from all `.md` files under `WORKSPACE_DIR` — no Obsidian app required
- [x] Collects tasks marked with `- [x]` (incomplete) and `- [x]` (done)
- [x] Tasks include source attribution: file path + line number
- [x] `/done <task-text>` marks the matching task as `- [x]` in the source `.md` file
- [x] `python main.py --backlog` shows Obsidian tasks alongside LogSeq tasks, grouped by source
- [x] `WORKSPACE_DIR` not set → clear error message, no crash
- [x] `WORKSPACE_DIR` documented with example paths in `config.template` and `INSTALL.md`
- **Output file**: `tasks/T02-01-output.md`

---

#### T02-02 — LogSeq → Obsidian task sync
**Agent**: dev-1 | **BLI**: BLI-011 | **Estimate**: L | **Depends on**: T02-01

- [x] `/sync-logseq` CLI command pulls all open `LATER`/`TODO` tasks from LogSeq and appends them to a configurable Obsidian page (default: `Inbox.md`)
- [x] Duplicate detection: tasks already present in `Inbox.md` are not re-added (matched by task text)
- [x] Each synced task gets a `#logseq` source tag and the originating file path as a comment
- [x] Sync can also run automatically on startup if `AUTO_SYNC_LOGSEQ=true` in config
- [x] Summary printed after sync: "X tasks synced, Y duplicates skipped"
- [x] `SYNC_TARGET_PAGE` added to `config.template` with default value `Inbox.md`
- **Output file**: `tasks/T02-02-output.md`

---

#### T02-03 — Planning agent with Google Calendar scheduling
**Agent**: dev-2 | **BLI**: BLI-012 | **Estimate**: L

- [x] `planning_agent.py` reads pending tasks from unified Obsidian + LogSeq list (via existing agents)
- [x] Fetches Google Calendar for the next 7 days and identifies free blocks ≥ 30 min
- [x] For each unscheduled task, agent proposes a time slot and prints: `"Schedule 'Buy milk' on Tuesday 10:00–10:30? [y/n/s]"` (s = skip)
- [x] User confirms (`y`), skips (`n/s`), or provides alternative time interactively
- [x] Confirmed tasks are added to Google Calendar via `calendar_manager` with task description as event title
- [x] If `token.json` is missing, prints a clear setup message and exits gracefully (no crash)
- [x] `python main.py --plan` triggers the planning session from the CLI
- **Output file**: `tasks/T02-03-output.md`

---

#### T02-04 — Scheduled / cron-triggered planning agent
**Agent**: dev-2 | **BLI**: BLI-013 | **Estimate**: M | **Depends on**: T02-03

- [x] `PLAN_TIME` setting added to `config.template` (default: `08:00`)
- [x] `INSTALL.md` updated with cron setup: `0 8 * * * cd /path/to/project && python main.py --plan`
- [x] `INSTALL.md` updated with systemd timer setup (unit file template included)
- [x] When run non-interactively (no TTY), agent prints a concise plan summary to stdout and exits — no interactive prompts hang the process
- [x] If no unscheduled tasks exist, agent exits silently with code 0
- [x] `--plan --dry-run` flag shows proposed schedule without writing to calendar
- **Output file**: `tasks/T02-04-output.md`

---

#### T02-05 — Clean CLI entry point
**Agent**: dev-1 | **BLI**: BLI-014 | **Estimate**: S | **Depends on**: T02-01, T02-03

- [x] `python main.py` launches CLI cleanly — no Streamlit import required at startup
- [x] Available Ollama models listed at startup (reuses Sprint-01 `list_ollama_models()`)
- [x] All core commands work end-to-end: `/backlog`, `/plan`, `/sync-logseq`, `/add-task`, `/done`, `/review`, `/models`
- [x] `/help` output updated to list all current commands with one-line descriptions
- [x] `--no-web` flag documented in `--help` output and `INSTALL.md` (suppresses any Streamlit references)
- [x] `python main.py --help` exits with code 0 and lists all flags
- **Output file**: `tasks/T02-05-output.md`

---

### Dependency Graph

```
T02-01 ──► T02-02
                  \
                   ──► T02-05
                  /
T02-03 ──► T02-04
```

T02-01 and T02-03 can start in parallel on day 1. T02-02, T02-04, T02-05 unlock as dependencies complete.

---

### Risks

| Risk | Mitigation |
|------|------------|
| 🟡 `token.json` (Google Calendar OAuth) may not exist in dev environment | T02-03 must handle missing credentials gracefully; PO to confirm token exists before sprint |
| 🟡 `WORKSPACE_DIR` (Obsidian) not set in `.config` | T02-01 must fail cleanly; PO to set path before testing |
| 🟡 T02-03 is an L — if Google Calendar API surface is complex, may need to scope down to read-only (view free slots, no write) | Flag early on day 2 if blocking |

---
