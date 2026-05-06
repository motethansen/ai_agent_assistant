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
        "organise":        cmd_organise,
        "organize":        cmd_organise,
        "links":           cmd_links,
        "cal":             cmd_cal,
        "cal-export":      cmd_cal_export,
        "model":           cmd_model,
        "status":          cmd_status,
        "kg":              cmd_kg,
        "rebuild-kg":      cmd_rebuild_kg,
        "help":            cmd_help,
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
            f"{s['triples']} triples · {s['notes']} notes · "
            f"{s['tasks']} tasks · {s['tags']} tags"
        )
        return

    # Pass natural-language query to LLM to convert to SPARQL, then execute
    from llm import router
    system = (
        "You are a SPARQL query generator for a personal knowledge graph.\n"
        "Prefix: PREFIX kn: <http://knowledgebase.local/>\n"
        "Classes: kn:Note, kn:Task, kn:Tag\n"
        "Properties: kn:path, kn:title, kn:modified, kn:text, kn:file, "
        "kn:dueDate, kn:priority, kn:isDone (boolean), kn:name, "
        "kn:hasTag, kn:linksTo, kn:hasTask\n"
        "Return ONLY the SPARQL SELECT query — no explanation, no markdown fences."
    )
    console.print("[dim]Generating SPARQL query...[/dim]")
    sparql = router.ask(arg, task="quick", system=system)
    sparql = sparql.strip().lstrip("```sparql").lstrip("```").rstrip("```").strip()

    results = kg_query(sparql)
    if not results:
        console.print("[dim]No results.[/dim]")
        return
    if "error" in results[0]:
        console.print(f"[red]SPARQL error:[/red] {results[0]['error']}")
        console.print(f"[dim]Generated query:\n{sparql}[/dim]")
        return

    from rich.table import Table
    from rich import box
    if not results:
        console.print("[dim]No results.[/dim]")
        return
    keys = list(results[0].keys())
    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold cyan")
    for k in keys:
        table.add_column(k)
    for row in results[:50]:
        table.add_row(*[row.get(k, "") for k in keys])
    console.print(table)
    if len(results) > 50:
        console.print(f"[dim]… {len(results) - 50} more rows not shown[/dim]")


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
        f"{s['triples']} triples · {s['tasks']} tasks · {s['tags']} tags"
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


def cmd_help(_arg: str) -> None:
    views.print_help()
