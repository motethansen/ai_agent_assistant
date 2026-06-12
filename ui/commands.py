"""
CLI command dispatcher — handles all / commands from the chat interface.

Each command is a function that receives the argument string and the console.
Returns a string response, or None for commands that print directly.
"""

import datetime
import sys
from rich.console import Console
from rich.markdown import Markdown

from ui import views

console = views.console


def dispatch(line: str) -> str | None:
    """Parse and execute a slash command. Returns text to print, or None."""
    line = line.strip()
    if not line.startswith("/"):
        return None

    parts = line[1:].split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    handlers = {
        "today":           cmd_today,
        "week":            cmd_week,
        "plan":            cmd_plan,
        "backlog":         cmd_backlog,
        "add-task":        cmd_add_task,
        "done":            cmd_done,
        "sync":            cmd_sync,
        "sync-reminders":  cmd_sync_reminders,
        "notes":           cmd_notes,
        "organise":          cmd_organise,
        "organize":          cmd_organise,
        "organise-projects": cmd_organise_projects,
        "organize-projects": cmd_organise_projects,
        "reschedule":        cmd_reschedule,
        "links":             cmd_links,
        "cal":             cmd_cal,
        "cal-export":      cmd_cal_export,
        "model":           cmd_model,
        "status":          cmd_status,
        "kg":              cmd_kg,
        "rebuild-kg":      cmd_rebuild_kg,
        "kanban":          cmd_kanban,
        "kanban-add":      cmd_kanban_add,
        "help":            cmd_help,
        "exit":            cmd_exit,
        "quit":            cmd_exit,
    }

    handler = handlers.get(cmd)
    if handler is None:
        return f"Unknown command: /{cmd} — type /help for a list"
    return handler(arg)


# ── Command implementations ───────────────────────────────────────────────────

def cmd_today(_arg: str) -> None:
    from integrations.obsidian import ObsidianVault
    from integrations.calendar import CalendarReader
    vault = ObsidianVault()
    tasks = vault.get_tasks()
    events = CalendarReader().get_today_events()
    views.print_today(events, tasks)


def cmd_week(_arg: str) -> None:
    from integrations.obsidian import ObsidianVault
    from integrations.calendar import CalendarReader
    vault = ObsidianVault()
    today = datetime.date.today()
    tasks = vault.get_tasks()
    events = CalendarReader().get_events(days_ahead=7)
    views.print_events(events, title=f"Events — next 7 days")
    console.print()
    week_tasks = [
        t for t in tasks
        if t.get("due_date") and t["due_date"] <= today + datetime.timedelta(days=7)
    ]
    views.print_tasks(week_tasks, title="Tasks due this week")


def cmd_plan(arg: str) -> None:
    mode = "week" if "week" in arg.lower() else "today"
    console.print(f"[dim]Generating {mode} plan...[/dim]")
    from agents.planning_agent import run
    plan = run(mode=mode)
    console.print(Markdown(plan))


def cmd_backlog(_arg: str) -> None:
    from integrations.obsidian import ObsidianVault
    tasks = ObsidianVault().get_tasks()
    views.print_backlog(tasks)


def cmd_add_task(arg: str) -> str:
    if not arg.strip():
        return "Usage: /add-task <description>  or  /add-task <description> due:YYYY-MM-DD"
    from integrations.obsidian import ObsidianVault
    vault = ObsidianVault()

    # Parse optional due date suffix: "buy milk due:2026-05-10"
    import re
    due_match = re.search(r'\bdue:(\d{4}-\d{2}-\d{2})\b', arg)
    due_str = ""
    description = arg.strip()
    if due_match:
        due_str = f" 📅 {due_match.group(1)}"
        description = arg[:due_match.start()].strip()

    task_line = f"- [ ] {description}{due_str}"

    existing = vault.read_section("inbox") or ""
    combined = (task_line + "\n" + existing).strip() if existing else task_line
    vault.write_section("inbox", combined)
    return f"Added to inbox: {description}{due_str}"


def cmd_done(arg: str) -> str:
    if not arg.strip():
        return "Usage: /done <task text>"
    from integrations.obsidian import ObsidianVault
    if ObsidianVault().mark_task_done(arg.strip()):
        return f"Marked done: {arg.strip()}"
    return f"Task not found: {arg.strip()}"


def cmd_sync(_arg: str) -> None:
    console.print("[dim]Running LogSeq → Obsidian sync...[/dim]")
    from agents.sync_agent import run
    result = run()
    console.print(
        f"[green]Sync complete[/green] — "
        f"{result['tasks_added']} tasks added, "
        f"{result['notes_added']} note entries, "
        f"{result['skipped']} skipped"
    )


def cmd_kanban(_arg: str) -> str:
    from agents.kanban_agent import run
    result = run()
    if "error" in result:
        return f"[red]Kanban error:[/red] {result['error']}"
    return (
        f"[green]Kanban refreshed[/green] — "
        f"{result['added']} task(s) added to Queued, "
        f"{result['skipped']} already on board"
    )


def cmd_kanban_add(arg: str) -> str:
    if not arg.strip():
        return "Usage: /kanban-add <task description>"
    from agents.kanban_agent import add_task
    ok = add_task(arg.strip())
    if ok:
        return f"Added to Queued: {arg.strip()}"
    return f"Already on board (skipped): {arg.strip()}"


def cmd_sync_reminders(_arg: str) -> None:
    console.print("[dim]Exporting Apple Reminders...[/dim]")
    from agents.reminders_agent import run
    result = run(export_first=True)
    if result["errors"]:
        for e in result["errors"]:
            console.print(f"[red]Error:[/red] {e}")
    console.print(
        f"[green]Done[/green] — "
        f"{result['exported']} reminders found, "
        f"{result['added']} added, "
        f"{result['skipped']} already synced"
    )


def cmd_notes(arg: str) -> None:
    if not arg.strip():
        console.print("[dim]Enter a question about your notes, or use /organise to restructure.[/dim]")
        return
    from integrations.obsidian import ObsidianVault
    from llm import router

    vault = ObsidianVault()
    notes = vault.list_notes()
    notes_context = "\n".join(
        f"- {n['title']}: {' | '.join(n['first_lines'][:2])[:100]}"
        for n in notes[:60]
    )
    prompt = f"""The user is asking about their Obsidian notes. Here is a summary of their vault:

{notes_context}

User question: {arg}

Answer based on the notes above. If the answer isn't in the notes, say so clearly."""

    console.print("[dim]Searching notes...[/dim]")
    for chunk in router.stream(prompt, task="notes"):
        console.print(chunk, end="")
    console.print()


def cmd_organise(arg: str) -> None:
    console.print("[dim]Analysing vault structure...[/dim]")
    from agents.notes_agent import run, apply

    subdir = arg.strip() or None
    result = run(subdir=subdir)

    if not result["moves"] and not result["links"]:
        console.print(f"[green]Vault looks well organised![/green] ({result['note_count']} notes analysed)")
        return

    console.print(f"\nAnalysed [bold]{result['note_count']}[/bold] notes.\n")

    if result["moves"]:
        console.print("[bold cyan]Suggested folder moves:[/bold cyan]")
        for m in result["moves"]:
            console.print(f"  [dim]{m['path']}[/dim] → [green]{m['suggested_folder']}[/green]  ({m.get('reason', '')})")

    if result["links"]:
        console.print("\n[bold cyan]Suggested wikilinks:[/bold cyan]")
        for lk in result["links"]:
            links = ", ".join(f"[[{l}]]" for l in lk["suggested_links"])
            console.print(f"  [dim]{lk['path']}[/dim] → {links}  ({lk.get('reason', '')})")

    console.print()
    answer = console.input("[bold]Apply these changes? (y/N):[/bold] ").strip().lower()
    if answer == "y":
        stats = apply(result)
        console.print(
            f"[green]Done[/green] — {stats['moves_done']} moved, "
            f"{stats['links_added']} linked"
        )
        if stats["errors"]:
            for e in stats["errors"]:
                console.print(f"  [red]Error:[/red] {e}")
    else:
        console.print("[dim]No changes made.[/dim]")


def cmd_organise_projects(arg: str) -> None:
    subdir = arg.strip() or None
    scope = f"[bold]{subdir}[/bold]" if subdir else "whole vault"
    console.print(f"[dim]Scanning {scope} for projects...[/dim]")
    console.print("[dim]URL-only tasks will be fetched — this may take a moment.[/dim]")

    from agents.project_agent import run
    stats = run(subdir=subdir)

    if stats["projects_updated"] == 0 and not stats["errors"]:
        console.print("[green]No projects with open tasks found.[/green]")
        return

    console.print(
        f"\n[green]Done[/green] — "
        f"[bold]{stats['projects_updated']}[/bold] project plan(s) written, "
        f"[bold]{stats['url_tasks']}[/bold] URL task(s) enriched"
        + (f", [bold]{stats['skipped']}[/bold] skipped" if stats["skipped"] else "")
    )
    if stats["errors"]:
        for e in stats["errors"]:
            console.print(f"  [red]Error:[/red] {e}")
    console.print("[dim]Each project folder now contains a _plan.md.[/dim]")


def _parse_target_date(expr: str) -> datetime.date | None:
    """
    Parse a natural-language date expression into a datetime.date.

    Supported:
        today, tomorrow
        next week           → next Monday
        next weekend        → next Saturday
        next month          → 1st of next calendar month
        monday … sunday     → next occurrence of that weekday
        in N days / in N weeks
        YYYY-MM-DD          → literal ISO date
    """
    import re as _re
    expr = expr.strip().lower()
    today = datetime.date.today()

    _SIMPLE = {
        "today":        today,
        "tomorrow":     today + datetime.timedelta(days=1),
        "next week":    today + datetime.timedelta(days=(7 - today.weekday())),
        "next weekend":  None,  # computed below
        "next month":   None,  # computed below
        "weekend":      None,  # alias
    }

    if expr == "today":
        return today
    if expr == "tomorrow":
        return today + datetime.timedelta(days=1)
    if expr in ("next week",):
        days = (7 - today.weekday()) % 7 or 7   # next Monday
        return today + datetime.timedelta(days=days)
    if expr in ("next weekend", "weekend"):
        days = (5 - today.weekday()) % 7 or 7   # next Saturday
        return today + datetime.timedelta(days=days)
    if expr == "next month":
        if today.month == 12:
            return datetime.date(today.year + 1, 1, 1)
        return datetime.date(today.year, today.month + 1, 1)

    # "in N days"
    m = _re.match(r'in\s+(\d+)\s+days?$', expr)
    if m:
        return today + datetime.timedelta(days=int(m.group(1)))

    # "in N weeks"
    m = _re.match(r'in\s+(\d+)\s+weeks?$', expr)
    if m:
        return today + datetime.timedelta(weeks=int(m.group(1)))

    # weekday name  e.g. "friday" or "next friday"
    _DAYS = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    for day_name in _DAYS:
        if expr == day_name or expr == f"next {day_name}":
            target_wd = _DAYS.index(day_name)
            days = (target_wd - today.weekday()) % 7 or 7
            return today + datetime.timedelta(days=days)

    # ISO literal
    try:
        return datetime.date.fromisoformat(expr)
    except ValueError:
        pass

    return None


def _parse_selection(arg: str, tasks: list[dict]) -> list[dict] | None:
    """
    Parse a task-selection token against the numbered task list.
    Returns list of selected tasks, or None if arg is unrecognised.

    Tokens:
        all             → every task
        overdue         → tasks with due_date < today
        today           → tasks due today
        1,3,5           → specific 1-based indices
        1-4             → inclusive range
    """
    import re as _re
    arg = arg.strip().lower()
    td = datetime.date.today()

    if arg == "all":
        return list(tasks)
    if arg == "overdue":
        return [t for t in tasks if t.get("due_date") and t["due_date"] < td]
    if arg == "today":
        return [t for t in tasks if t.get("due_date") == td]

    # range: 1-4
    m = _re.match(r'^(\d+)-(\d+)$', arg)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return [tasks[i - 1] for i in range(lo, hi + 1) if 1 <= i <= len(tasks)]

    # comma list: 1,3,5
    if _re.match(r'^[\d,\s]+$', arg):
        indices = [int(x.strip()) for x in arg.split(",") if x.strip().isdigit()]
        return [tasks[i - 1] for i in indices if 1 <= i <= len(tasks)]

    return None


def cmd_reschedule(arg: str) -> None:
    """
    Reschedule overdue and/or today's tasks to a new date.

    Usage:
        /reschedule                           → interactive prompts
        /reschedule overdue next weekend
        /reschedule today in 4 days
        /reschedule all next week
        /reschedule 1,3 next month
        /reschedule 1-5 2026-06-01
    """
    import re as _re
    from integrations.obsidian import ObsidianVault

    vault = ObsidianVault()
    today = datetime.date.today()

    # Load overdue + today tasks sorted overdue-first, then today, then by priority
    all_tasks = vault.get_tasks()
    candidates = sorted(
        [t for t in all_tasks if t.get("due_date") and t["due_date"] <= today],
        key=lambda t: (t["due_date"], t.get("priority_weight", 99)),
    )

    if not candidates:
        console.print("[green]No overdue or today tasks — you're all caught up![/green]")
        return

    # ── Display numbered list ─────────────────────────────────────────────────
    console.print()
    console.print("[bold]Overdue & today tasks:[/bold]")
    for i, t in enumerate(candidates, 1):
        due = t["due_date"]
        age = (today - due).days
        label = "[red]today[/red]" if age == 0 else f"[red]{age}d overdue[/red]"
        prio = f" {t['priority']}" if t.get("priority") else ""
        source = f" [dim]({t['file']}:{t['line']})[/dim]"
        console.print(f"  [bold]{i:>2}.[/bold] {t['text'][:60]}{prio} — {label}{source}")
    console.print()

    # ── Parse inline args or prompt ───────────────────────────────────────────
    # Try to split arg into "selection" + "date expression"
    # Strategy: greedily try longer date expressions first
    selection_str = ""
    date_str = ""

    if arg.strip():
        # Date keywords that may be multi-word
        _DATE_PATTERNS = [
            r'next\s+weekend', r'next\s+week', r'next\s+month',
            r'next\s+\w+day',
            r'in\s+\d+\s+\w+',
            r'\d{4}-\d{2}-\d{2}',
            r'\w+day',     # monday–sunday
            r'tomorrow', r'today',
        ]
        combined = arg.strip()
        date_match = None
        for pat in _DATE_PATTERNS:
            m = _re.search(pat, combined, _re.IGNORECASE)
            if m:
                date_match = m
                break
        if date_match:
            date_str = date_match.group().strip()
            selection_str = combined[:date_match.start()].strip()

    if not selection_str:
        selection_str = console.input(
            "[bold]Which tasks?[/bold] (all / overdue / today / 1,3 / 1-4): "
        ).strip()

    selected = _parse_selection(selection_str, candidates)
    if selected is None:
        console.print(f"[red]Couldn't parse selection:[/red] {selection_str!r}")
        return
    if not selected:
        console.print("[dim]No tasks match that selection.[/dim]")
        return

    if not date_str:
        date_str = console.input(
            "[bold]Reschedule to?[/bold] (next week / next weekend / next month / in N days / YYYY-MM-DD): "
        ).strip()

    new_date = _parse_target_date(date_str)
    if new_date is None:
        console.print(f"[red]Couldn't parse date:[/red] {date_str!r}")
        return

    day_name = new_date.strftime("%A, %d %b %Y")
    console.print(
        f"\nMove [bold]{len(selected)}[/bold] task(s) → "
        f"[green]{day_name}[/green]?"
    )
    for t in selected:
        console.print(f"  · {t['text'][:70]}")
    console.print()

    answer = console.input("[bold]Apply? (y/N):[/bold] ").strip().lower()
    if answer != "y":
        console.print("[dim]No changes made.[/dim]")
        return

    done, failed = 0, []
    for t in selected:
        if vault.update_task_date(t, new_date):
            done += 1
        else:
            failed.append(t["text"])

    console.print(f"\n[green]Rescheduled {done} task(s) to {day_name}.[/green]")
    for f in failed:
        console.print(f"  [red]Failed:[/red] {f}")


def cmd_links(arg: str) -> None:
    from agents.notes_agent import run_links_only, apply

    console.print("[dim]Analysing note connections...[/dim]")
    result = run_links_only(subdir=arg.strip() or None)

    if not result["links"]:
        console.print("[green]No link suggestions.[/green]")
        return

    console.print(f"[bold cyan]Suggested wikilinks ({len(result['links'])} notes):[/bold cyan]")
    for lk in result["links"]:
        links = ", ".join(f"[[{l}]]" for l in lk["suggested_links"])
        console.print(f"  [dim]{lk['path']}[/dim] → {links}")

    answer = console.input("\n[bold]Apply wikilinks? (y/N):[/bold] ").strip().lower()
    if answer == "y":
        stats = apply({"moves": [], "links": result["links"]})
        console.print(f"[green]Done[/green] — {stats['links_added']} notes updated")


def cmd_cal(arg: str) -> None:
    from integrations.calendar import CalendarReader
    days = int(arg.strip()) if arg.strip().isdigit() else 14
    events = CalendarReader().get_events(days_ahead=days)
    views.print_events(events, title=f"Calendar — next {days} days")


def cmd_cal_export(_arg: str) -> None:
    from integrations.obsidian import ObsidianVault
    from integrations.calendar import CalendarWriter
    console.print("[dim]Syncing #gcal tasks to calendar...[/dim]")
    vault = ObsidianVault()
    gcal_tasks = vault.get_tasks(gcal_only=True)
    writer = CalendarWriter()
    stats = writer.sync_from_obsidian(gcal_tasks)
    ics_path = writer.export_ics()
    console.print(
        f"[green]Done[/green] — {stats['added']} events added, {stats['skipped']} skipped\n"
        f"ICS exported to: [cyan]{ics_path}[/cyan]"
    )


def cmd_kg(arg: str) -> None:
    """Query the knowledge graph or show its stats."""
    try:
        from agents.knowledge_agent import graph_stats, query as kg_query
    except ImportError:
        console.print("[red]rdflib not installed — run: pip install rdflib[/red]")
        return

    if not arg.strip():
        s = graph_stats()
        if s["triples"] == 0:
            console.print("[dim]Knowledge graph is empty. Run /rebuild-kg to build it.[/dim]")
            return
        console.print(
            f"[bold]Knowledge graph[/bold]  "
            f"{s['triples']:,} triples · {s['notes']:,} notes · "
            f"{s['tasks']:,} tasks · {s['tags']:,} tags · "
            f"{s['links']:,} links ({s['dangling_links']:,} dangling)"
        )
        return

    # Step 1 — generate SPARQL with explicit field selection rules
    from llm import router
    sparql_system = (
        "You are a SPARQL query generator for a personal Obsidian knowledge graph.\n"
        "PREFIX kn: <http://knowledgebase.local/>\n\n"
        "Schema:\n"
        "  kn:Note  — kn:path (file path), kn:title (note name), kn:modified\n"
        "  kn:Task  — kn:text (task body), kn:file (source path), kn:isDone (boolean),\n"
        "             kn:dueDate, kn:priority\n"
        "  kn:Tag   — kn:name (tag string)\n"
        "  Relations: kn:hasTag, kn:hasTask, kn:linksTo\n\n"
        "RULES — you MUST follow these:\n"
        "  1. Always SELECT human-readable literals, never bare node variables.\n"
        "     For notes: SELECT ?title ?path   For tasks: SELECT ?text ?file ?dueDate\n"
        "  2. Never use SELECT ?s or SELECT ?n — these return opaque URIs.\n"
        "  3. Always add LIMIT 30 unless counting.\n"
        "  4. Tag names are lowercase strings (e.g. \"academic\", \"dev\").\n"
        "  5. kn:isDone values are the string 'true' or 'false'.\n\n"
        "Return ONLY the SPARQL SELECT query — no explanation, no markdown."
    )
    console.print("[dim]Generating SPARQL query...[/dim]")
    sparql = router.ask(arg, task="quick", system=sparql_system)
    # Strip any markdown fences the LLM may have added
    import re as _re
    sparql = _re.sub(r'^```[a-z]*\s*', '', sparql.strip(), flags=_re.IGNORECASE)
    sparql = sparql.rstrip('`').strip()

    results = kg_query(sparql)
    if not results:
        console.print("[dim]No results found in knowledge graph.[/dim]")
        return
    if "error" in results[0]:
        console.print(f"[red]SPARQL error:[/red] {results[0]['error']}")
        console.print(f"[dim]Query used:\n{sparql}[/dim]")
        return

    # Step 2 — ask LLM to interpret results as a natural-language answer
    def _fmt_rows(rows: list[dict], limit: int = 30) -> str:
        lines = []
        for i, row in enumerate(rows[:limit], 1):
            parts = [f"{k}: {v}" for k, v in row.items() if v]
            lines.append(f"{i}. {' | '.join(parts)}")
        if len(rows) > limit:
            lines.append(f"… and {len(rows) - limit} more")
        return "\n".join(lines)

    answer_system = (
        "You are a personal knowledge assistant. "
        "Answer concisely using the search results below. "
        "Use markdown — bullet lists for multiple items, bold for note titles. "
        "Include file paths in parentheses so the user can find the note."
    )
    answer_prompt = (
        f"Question: {arg}\n\n"
        f"Knowledge graph results:\n{_fmt_rows(results)}\n\n"
        "Give a direct, helpful answer based on these results."
    )
    console.print("[dim]Interpreting results...[/dim]")
    answer = router.ask(answer_prompt, task="quick", system=answer_system)
    console.print()
    console.print(Markdown(answer))
    console.print()
    console.print(f"[dim]{len(results)} result(s) · query: {sparql.splitlines()[0][:80]}…[/dim]")


def cmd_rebuild_kg(_arg: str) -> None:
    try:
        from agents.knowledge_agent import run as kg_run, graph_stats
    except ImportError:
        console.print("[red]rdflib not installed — run: pip install rdflib[/red]")
        return
    console.print("[dim]Rebuilding knowledge graph from scratch...[/dim]")
    result = kg_run(full_rebuild=True)
    s = graph_stats()
    console.print(
        f"[green]Done[/green] — {result['indexed']} notes indexed · "
        f"{s['triples']:,} triples · {s['tasks']:,} tasks · "
        f"{s['links']:,} links ({s['dangling_links']:,} dangling)"
    )


def cmd_model(arg: str) -> None:
    from llm.router import all_providers
    providers = all_providers()
    if not arg.strip():
        views.print_model_routing(providers)
        return
    console.print(
        "[dim]To change routing, edit the ROUTING_* keys in .config "
        "and restart the assistant.[/dim]"
    )


def cmd_status(_arg: str) -> None:
    import config
    from llm.router import all_providers
    views.print_status(config.summary(), all_providers())


def cmd_exit(_arg: str) -> None:
    console.print("[dim]Goodbye.[/dim]")
    sys.exit(0)


def cmd_help(_arg: str) -> None:
    views.print_help()
