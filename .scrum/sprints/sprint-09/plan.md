# Sprint-09 Plan — Vault Planning Cleanup + Backlog Categories + Planner Integration

**Sprint**: 09
**Goal**: Harden the planning pipeline: fix date-bucket bugs in the backlog view, wire `/plan` output into `010 Planning/Planner.md` via section markers, tag tasks in `Task Categories.md` by category, and clean up stale vault files.
**Status**: ✅ Complete — 2026-06-22 (T09-03/04/05 verified done; T09-01/02 done earlier)
**Epics**: E11 (Terminal Task Visibility), E12 (Obsidian Round-trip)

---

## Task Summary

| Task | Title | Estimate | Status |
|------|-------|----------|--------|
| T09-01 | Fix `print_backlog()` future-date bucket — dated tasks >7 days out fell into "Backlog (no date)" | S | ✅ Done (2026-06-11) |
| T09-02 | Add category tags to `010 Planning/Task Categories.md` (`#vizneo`, `#urbanlife`, etc.) | M | ✅ Done (2026-06-11) |
| T09-03 | Wire `/plan` output into `010 Planning/Planner.md` structured sections via `write_section()` | M | ✅ Done (2026-06-22) |
| T09-04 | Archive root `Dashboard.md` → convert to static index pointing to `010 Planning/` | S | ✅ Done (2026-06-22) |
| T09-05 | Clean `000 Inbox/Inbox.md` — remove junk preamble text at top | S | ✅ Done (2026-06-22) |

---

## T09-01 — Fix `print_backlog()` future-date bucket ✅

**File**: `ui/views.py` `print_backlog()`

**Bug**: The `else` branch put tasks with `due_date > today + 7 days` into `undated`, labelled
"Backlog (no date)". Those tasks lost their due-date display and sort order.

**Fix**: Added a `future` list; dated tasks >7 days out now appear under an "Upcoming" rule,
sorted by due date. `undated` now contains only tasks with no `due_date` at all.

---

## T09-02 — Category tags in Task Categories.md

Add `#tag` markers to every task line in `010 Planning/Task Categories.md` so the
`Backlog.md` dynamic query `group by tags` can group them automatically.

Tag scheme:
- `#vizneo` — Vizneo / RefTeam
- `#winedragons` — WineDragons project
- `#urbanlife` — UrbanLife.Works
- `#academic` — Academic writing
- `#substack` — Substack / Medium
- `#coding` — Coding, repos, courses
- `#hobbies` — AI electronics, science
- `#languages` — Thai, Japanese
- `#finance` — Finance tasks
- `#recipes` — Recipes / food

---

## T09-03 — Wire `/plan` into Planner.md sections

`agents/planning_agent.py:run()` already calls `vault.write_section(section, ...)`.
The section names `"today-plan"` and `"week-plan"` need matching markers in
`010 Planning/Planner.md`:

```markdown
<!-- agent:today-plan:start -->
<!-- agent:today-plan:end -->
```

`integrations/obsidian.py:write_section()` will insert/replace content between those
markers on every `/plan` run. The Planner.md structure should have:

1. Static header with callout
2. `## Today's Plan` section with agent markers
3. `## Overdue` — manually maintained
4. `## Scheduled (Future)` — manually maintained

---

## T09-04 — Archive root Dashboard.md

The file at vault root `Dashboard.md` has old May 2026 content and is no longer the
agent write target (that moved to `010 Planning/Planner.md`). Convert it to a static
index linking to the live planning files.

---

## T09-05 — Clean 000 Inbox/Inbox.md

Remove the junk preamble at the top of `000 Inbox/Inbox.md`:
```
i thought you can create the folder and file in obsidian# Inbox
```

---

## Definition of Done

- [x] `/backlog` shows a proper "Upcoming" section for tasks due 8+ days out
- [x] `Task Categories.md` has `#tag` on every task
- [x] `010 Planning/Planner.md` has `<!-- agent:today-plan:start/end -->` markers (also `week-plan`)
- [x] `/plan` output appears under "Today's Plan" in Planner.md — verified `write_section("today-plan")` replaces between markers (placeholder restored after test)
- [x] Root `Dashboard.md` is a static index, not a stale agent dump
- [x] `000 Inbox/Inbox.md` has clean content (no junk preamble)
- [x] `bash scripts/run_tests.sh` — zero failures (65 passed, 2026-06-22)
