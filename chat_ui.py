"""
Rich-based terminal chat UI for the AI Agent Assistant.
Provides markdown rendering, streaming output, and conversation history.
"""
import os
import json
import datetime
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text

console = Console()

HISTORY_FILE = os.path.expanduser("~/.ai_agent_assistant_history.json")


def print_banner():
    """Styled banner using Rich."""
    console.print(Panel(
        "[bold blue]AI Agent Assistant[/bold blue]\n"
        "[dim]Local-first AI task management | Type /commands for help[/dim]",
        border_style="blue",
        padding=(1, 4)
    ))


def render_user_input(text):
    """Show user input styled."""
    console.print(f"\n[bold green]You:[/bold green] {text}")


def render_response(text, model_name=""):
    """Render AI response as markdown in a panel."""
    title = f"AI Assistant [{model_name}]" if model_name else "AI Assistant"
    md = Markdown(text)
    console.print(Panel(md, title=title, border_style="blue", padding=(1, 2)))


def render_streaming(stream_iterator, model_name=""):
    """Render streaming LLM response with live update. Returns full text."""
    title = f"AI Assistant [{model_name}]" if model_name else "AI Assistant"
    full_text = ""
    with Live(console=console, refresh_per_second=8) as live:
        for chunk in stream_iterator:
            content = ""
            if hasattr(chunk, 'content') and chunk.content:
                content = chunk.content
            elif isinstance(chunk, str):
                content = chunk
            if content:
                full_text += content
                try:
                    live.update(Panel(
                        Markdown(full_text),
                        title=title,
                        border_style="blue",
                        padding=(1, 2)
                    ))
                except Exception:
                    live.update(Panel(
                        Text(full_text),
                        title=title,
                        border_style="blue",
                        padding=(1, 2)
                    ))
    return full_text


def render_error(msg):
    """Show error message."""
    console.print(f"[bold red]Error:[/bold red] {msg}")


def render_info(msg):
    """Show info message."""
    console.print(f"[dim]{msg}[/dim]")


def render_success(msg):
    """Show success message."""
    console.print(f"[bold green]{msg}[/bold green]")


def render_warning(msg):
    """Show warning message."""
    console.print(f"[bold yellow]{msg}[/bold yellow]")


COMMAND_DESCRIPTIONS = {
    "sync": "Manually trigger task sync from Obsidian and Reminders",
    "pull": "Sync Calendar -> Markdown (Two-Way Sync)",
    "backlog": "Display the current unified backlog (grouped by category)",
    "stats": "Display focus analytics for today",
    "plan": "Trigger a morning planning session",
    "review": "Trigger an evening review session",
    "ui": "Launch the Streamlit web interface",
    "models": "Show current status of LLM models",
    "model": "Enable/disable models (e.g., /model disable gemini)",
    "routing": "Show current LLM routing configuration",
    "services": "Check and start local AI services (Ollama, OpenClaw)",
    "organize": "AI suggestions for task organization",
    "cmd": "Custom AI command on backlog (e.g., /cmd prioritize by deadline)",
    "develop": "AI code generation (e.g., /develop a flask REST API)",
    "gmail": "List snoozed and filtered emails from Gmail",
    "gmail-filter": "Manage Gmail search filters",
    "index": "Re-index all notes and books for RAG",
    "docs": "Show project documentation",
    "create-agent": "Scaffold a new custom agent",
    "define-agent": "Link an agent to a specific LLM",
    "list-agents": "Show available custom agents",
    "history": "Show recent conversation history",
    "clear-history": "Clear conversation history",
    "exit": "Quit the chat mode",
}


def render_command_help():
    """Render slash commands as a Rich table."""
    table = Table(title="Available Commands", show_header=True, header_style="bold cyan")
    table.add_column("Command", style="cyan", min_width=18)
    table.add_column("Description")
    for cmd, desc in COMMAND_DESCRIPTIONS.items():
        table.add_row(f"/{cmd}", desc)
    console.print(table)


def render_backlog(tasks):
    """Render unified backlog as a Rich table grouped by category."""
    cats = {}
    for t in tasks:
        cat = t.get("category", "Uncategorized")
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(t)

    console.print(f"\n[bold]Unified Backlog[/bold] ({len(tasks)} tasks)\n")

    for cat, task_list in cats.items():
        table = Table(title=f"[{cat.upper()}]", show_header=True, header_style="bold")
        table.add_column("Source", width=8)
        table.add_column("Task")
        table.add_column("Due", width=12)
        for t in task_list:
            source_map = {"Obsidian": "[blue]Obs[/blue]", "Logseq": "[green]LSq[/green]", "Reminders": "[yellow]Rem[/yellow]"}
            source = source_map.get(t.get("source", ""), t.get("source", ""))
            due = t.get("due_date", "") or ""
            table.add_row(source, t.get("task", ""), due)
        console.print(table)
        console.print()


def render_services(ollama_status, openclaw_status):
    """Render service status table."""
    table = Table(title="Local AI Services", show_header=True)
    table.add_column("Service", style="cyan")
    table.add_column("Status")
    table.add_row("Ollama", "[bold green]RUNNING[/bold green]" if ollama_status else "[bold red]STOPPED[/bold red]")
    table.add_row("OpenClaw", "[bold green]RUNNING[/bold green]" if openclaw_status else "[bold red]STOPPED[/bold red]")
    console.print(table)


def render_models(models_status):
    """Render model activation status."""
    table = Table(title="LLM Model Status", show_header=True)
    table.add_column("Model", style="cyan")
    table.add_column("Enabled")
    table.add_column("Available")
    for name, info in models_status.items():
        enabled = "[green]YES[/green]" if info["enabled"] else "[red]NO[/red]"
        available = "[green]YES[/green]" if info["available"] else "[red]NO[/red]"
        table.add_row(name, enabled, available)
    console.print(table)


def render_routing(routing_info):
    """Render routing configuration."""
    table = Table(title="LLM Routing Configuration", show_header=True)
    table.add_column("Task Type", style="cyan")
    table.add_column("Config")
    table.add_column("Active Model")
    for task_type, info in routing_info.items():
        table.add_row(task_type, info["config"], info["active"])
    console.print(table)


def render_history_summary(history, count=10):
    """Show recent conversation history."""
    recent = history[-count*2:] if len(history) > count*2 else history
    if not recent:
        console.print("[dim]No conversation history.[/dim]")
        return

    console.print(f"\n[bold]Recent History[/bold] (last {min(count, len(recent)//2 + 1)} exchanges)\n")
    for msg in recent:
        role = msg.get("role", "")
        content = msg.get("content", "")
        ts = msg.get("timestamp", "")
        if role == "user":
            console.print(f"[dim]{ts[:16]}[/dim] [bold green]You:[/bold green] {content[:100]}{'...' if len(content) > 100 else ''}")
        else:
            console.print(f"[dim]{ts[:16]}[/dim] [blue]AI:[/blue] {content[:100]}{'...' if len(content) > 100 else ''}")


# --- Conversation History ---

def load_history():
    """Load conversation history from file."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_history(history):
    """Save conversation history, keeping last 200 messages."""
    trimmed = history[-200:]
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(trimmed, f, indent=2)
    except IOError:
        pass


def add_to_history(role, content, history):
    """Add a message to history."""
    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.datetime.now().isoformat()
    })
    return history
