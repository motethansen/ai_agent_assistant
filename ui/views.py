"""Rich terminal output formatters — tables, panels, calendar grids."""

import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box
from rich.text import Text
from rich.rule import Rule

console = Console()


# ── Task views ────────────────────────────────────────────────────────────────

def print_tasks(tasks: list[dict], title: str = "Tasks") -> None:
    if not tasks:
        console.print(f"[dim]No tasks found.[/dim]")
        return

    table = Table(
        title=title,
        box=box.SIMPLE_HEAD,
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("", width=2)
    table.add_column("Task", ratio=3)
    table.add_column("Due", width=12)
    table.add_column("Priority", width=10)
    table.add_column("File", ratio=2, style="dim")

    today = datetime.date.today()
    for t in tasks:
        done = t.get("done", False)
        status = "✓" if done else "·"
        status_style = "green" if done else "white"

        text = t.get("text") or t.get("clean_text") or t.get("task", "")
        if done:
            text = f"[dim strike]{text}[/dim strike]"

        due = t.get("due_date")
        if due:
            if due < today:
                due_str = f"[red]{due}[/red]"
            elif due == today:
                due_str = f"[yellow]{due}[/yellow]"
            else:
                due_str = str(due)
        else:
            due_str = ""

        prio = t.get("priority", "")
        prio_map = {
            "highest": "[red]● highest[/red]",
            "high":    "[orange1]● high[/orange1]",
            "medium":  "[yellow]● medium[/yellow]",
            "low":     "[dim]● low[/dim]",
            "lowest":  "[dim]● lowest[/dim]",
        }
        prio_str = prio_map.get(prio, "")

        file_str = t.get("file", "")
        if len(file_str) > 35:
            file_str = "…" + file_str[-34:]

        table.add_row(
            Text(status, style=status_style),
            text,
            due_str,
            prio_str,
            file_str,
        )

    console.print(table)


def print_backlog(tasks: list[dict]) -> None:
    today = datetime.date.today()
    overdue, due_today, due_soon, undated = [], [], [], []

    for t in tasks:
        d = t.get("due_date")
        if d:
            if d < today:
                overdue.append(t)
            elif d == today:
                due_today.append(t)
            elif d <= today + datetime.timedelta(days=7):
                due_soon.append(t)
            else:
                undated.append(t)
        else:
            undated.append(t)

    if overdue:
        console.print(Rule("[red]Overdue[/red]"))
        print_tasks(overdue)
    if due_today:
        console.print(Rule("[yellow]Due Today[/yellow]"))
        print_tasks(due_today)
    if due_soon:
        console.print(Rule("[cyan]Due This Week[/cyan]"))
        print_tasks(due_soon)
    if undated:
        console.print(Rule("[dim]Backlog (no date)[/dim]"))
        print_tasks(undated[:30])


# ── Calendar views ────────────────────────────────────────────────────────────

def print_events(events: list[dict], title: str = "Calendar") -> None:
    if not events:
        console.print(f"[dim]No events found.[/dim]")
        return

    table = Table(
        title=title,
        box=box.SIMPLE_HEAD,
        header_style="bold magenta",
    )
    table.add_column("Date", width=12)
    table.add_column("Time", width=12)
    table.add_column("Event", ratio=1)

    for e in events:
        start = e.get("start")
        if isinstance(start, datetime.datetime):
            date_str = start.strftime("%a %b %d")
            time_str = start.strftime("%H:%M")
            end = e.get("end")
            if isinstance(end, datetime.datetime):
                time_str += f"–{end.strftime('%H:%M')}"
        elif isinstance(start, datetime.date):
            date_str = start.strftime("%a %b %d")
            time_str = "All day"
        else:
            date_str = "?"
            time_str = ""
        table.add_row(date_str, time_str, e.get("summary", ""))

    console.print(table)


def print_today(events: list[dict], tasks: list[dict]) -> None:
    today = datetime.date.today()
    console.print(Rule(f"[bold]{today.strftime('%A, %B %d %Y')}[/bold]"))

    if events:
        print_events(events, title="Today's Events")
    else:
        console.print("[dim]No calendar events today.[/dim]")

    console.print()

    today_tasks = [
        t for t in tasks
        if t.get("due_date") == today or t.get("scheduled_date") == today
    ]
    overdue = [
        t for t in tasks
        if t.get("due_date") and t.get("due_date") < today and not t.get("done")
    ]

    if overdue:
        console.print(Rule("[red]Overdue[/red]"))
        print_tasks(overdue[:10])
        console.print()

    if today_tasks:
        print_tasks(today_tasks, title="Today's Tasks")
    else:
        console.print("[dim]No tasks due today.[/dim]")


# ── Status views ──────────────────────────────────────────────────────────────

def print_status(config_summary: dict, providers: list[dict]) -> None:
    console.print(Rule("[bold]AI Agent Assistant — Status[/bold]"))

    cfg_table = Table(box=box.SIMPLE, show_header=False)
    cfg_table.add_column("Key", style="cyan", width=20)
    cfg_table.add_column("Value")
    for k, v in config_summary.items():
        cfg_table.add_row(k, str(v))
    console.print(Panel(cfg_table, title="Configuration"))

    llm_table = Table(box=box.SIMPLE, header_style="bold")
    llm_table.add_column("Provider", width=16)
    llm_table.add_column("Available", width=10)
    llm_table.add_column("Free tier")
    llm_table.add_column("Used for")
    for p in providers:
        avail = "[green]✓ yes[/green]" if p.get("available") else "[red]✗ no[/red]"
        tasks = ", ".join(p.get("configured_for", [])) or "—"
        llm_table.add_row(
            p.get("provider", "?"),
            avail,
            p.get("free_tier", ""),
            tasks,
        )
    console.print(Panel(llm_table, title="LLM Providers"))


def print_model_routing(providers: list[dict]) -> None:
    """Show current LLM routing config."""
    import config as cfg
    table = Table(title="LLM Routing", box=box.SIMPLE_HEAD, header_style="bold cyan")
    table.add_column("Task type", width=14)
    table.add_column("Provider", width=16)
    table.add_column("Available", width=10)

    routing = {
        "chat":     cfg.llm.routing_chat(),
        "planning": cfg.llm.routing_planning(),
        "notes":    cfg.llm.routing_notes(),
        "quick":    cfg.llm.routing_quick(),
        "offline":  cfg.llm.routing_offline(),
    }
    avail_map = {p["provider"]: p.get("available", False) for p in providers}

    for task, provider in routing.items():
        avail = avail_map.get(provider, False)
        avail_str = "[green]✓[/green]" if avail else "[red]✗[/red]"
        table.add_row(task, provider, avail_str)

    console.print(table)
    console.print(
        "[dim]Change routing: edit ROUTING_* keys in .config or run /model[/dim]"
    )


# ── Help ─────────────────────────────────────────────────────────────────────

def print_help() -> None:
    commands = [
        ("/today",               "Today's calendar events + tasks"),
        ("/week",                "7-day task and event overview"),
        ("/plan",                "Generate today's AI schedule"),
        ("/plan week",           "Generate weekly AI schedule"),
        ("/backlog",             "All pending tasks grouped by urgency"),
        ("/reschedule",         "Move overdue/today tasks to a new date (interactive)"),
        ("/add-task <txt>",      "Add task to inbox  · due:YYYY-MM-DD  · #gcal → becomes calendar event"),
        ("/done <text>",         "Mark a task complete"),
        ("/sync",                "Run LogSeq → Obsidian sync now"),
        ("/sync-reminders",      "Pull Apple Reminders into inbox"),
        ("/notes <question>",    "Ask a question about your notes"),
        ("/organise",                    "Suggest folder moves + wikilinks (dry run)"),
        ("/organise-projects [folder]",  "Write per-project _plan.md — sorts tasks, enriches URL tasks"),
        ("/links",                       "Suggest wikilinks only (dry run)"),
        ("/kg",                  "Show knowledge graph stats"),
        ("/kg <question>",       "Query knowledge graph in plain English"),
        ("/rebuild-kg",          "Force full knowledge graph rebuild"),
        ("/cal",                 "Show upcoming calendar events"),
        ("/cal-export",          "Convert #gcal tasks → .ics file (import into Apple Calendar)"),
        ("/model",               "Show LLM routing"),
        ("/status",              "System status + provider health"),
        ("/chat",                "Open multi-turn chat mode"),
        ("/help",                "Show this help"),
        ("/exit",                "Exit the assistant"),
    ]

    table = Table(box=box.SIMPLE, show_header=False, expand=True)
    table.add_column("Command", style="cyan", width=36)
    table.add_column("Description")
    for cmd, desc in commands:
        table.add_row(cmd, desc)

    console.print(Panel(table, title="[bold]Commands[/bold]"))
