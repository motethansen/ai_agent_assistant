"""
chat_ui.py — Terminal chat UI for AI Agent Assistant.

Design: compact, information-dense, similar to Claude Code / LM Studio terminal.
  - Persistent status line showing active model
  - Streamed responses render inline (no heavy panel box)
  - Model + timing badge after each response
  - prompt_toolkit input with styled prompt showing model name
"""
import os
import time
import json
import datetime

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich.live import Live
from rich import box

console = Console()

HISTORY_FILE = os.path.expanduser("~/.ai_agent_assistant_history.json")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _active_model_label():
    """Return a short label for the currently configured LLM."""
    try:
        from config_utils import get_config_value
        lms = get_config_value("ENABLE_LM_STUDIO", "false").lower() == "true"
        if lms:
            model = get_config_value("LM_STUDIO_MODEL", "lmstudio")
            return model, "lmstudio"
        ollama = get_config_value("ENABLE_OLLAMA", "true").lower() == "true"
        if ollama:
            model = get_config_value("OLLAMA_MODEL", "ollama")
            return model, "ollama"
        for provider in ("gemini", "openai", "claude"):
            enabled = get_config_value(f"ENABLE_{provider.upper()}", "false").lower() == "true"
            if enabled:
                return provider, provider
    except Exception:
        pass
    return "unknown", "unknown"


def _fmt_seconds(seconds):
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    return f"{seconds:.1f}s"


# ── Banner ─────────────────────────────────────────────────────────────────────

def print_banner():
    """Compact startup banner showing model and status."""
    model_name, provider = _active_model_label()

    try:
        from ai_orchestration import is_lmstudio_running, is_ollama_running
        if provider == "lmstudio":
            running = is_lmstudio_running()
        elif provider == "ollama":
            running = is_ollama_running()
        else:
            running = True
        status = "[green]●[/green] online" if running else "[red]●[/red] offline"
    except Exception:
        status = "[dim]●[/dim] unknown"

    console.print()
    console.print(Panel(
        f"[bold white]AI Agent Assistant[/bold white]  "
        f"[dim]│[/dim]  "
        f"[cyan]{model_name}[/cyan]  "
        f"[dim]via[/dim]  [bold]{provider}[/bold]  "
        f"[dim]│[/dim]  {status}\n"
        f"[dim]Type a message to chat · /help for commands · /quit to exit[/dim]",
        border_style="bright_black",
        padding=(0, 2),
    ))
    console.print()


def print_startup_status():
    """Print model / workspace status lines below the banner."""
    try:
        from config_utils import get_config_value
        from ai_orchestration import is_lmstudio_running, is_ollama_running, MODELS_ENABLED

        model_name, provider = _active_model_label()

        # LLM status
        if provider == "lmstudio":
            ok = is_lmstudio_running()
            icon = "[green]✓[/green]" if ok else "[yellow]⚠[/yellow]"
            console.print(f"  {icon}  LM Studio  [cyan]{model_name}[/cyan]  "
                          f"[dim]localhost:1234[/dim]")
        elif provider == "ollama":
            ok = is_ollama_running()
            icon = "[green]✓[/green]" if ok else "[yellow]⚠[/yellow]"
            host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
            console.print(f"  {icon}  Ollama  [cyan]{model_name}[/cyan]  [dim]{host}[/dim]")

        # Routing
        routing = get_config_value("ROUTING_CHAT", provider)
        console.print(f"  [dim]routing → {routing}  ·  "
                      f"priority: {get_config_value('LLM_PRIORITY', provider)}[/dim]")

        # Workspace
        ws = get_config_value("WORKSPACE_DIR", None)
        ls = get_config_value("LOGSEQ_DIR", None)
        ws_icon = "[green]✓[/green]" if ws and ws != "." else "[yellow]⚠[/yellow]"
        ls_icon = "[green]✓[/green]" if ls else "[dim]—[/dim]"
        console.print(f"  {ws_icon}  Obsidian  [dim]{ws or 'not set'}[/dim]")
        console.print(f"  {ls_icon}  LogSeq    [dim]{ls or 'not set'}[/dim]")
        console.print()

    except Exception as e:
        console.print(f"  [dim]Could not load status: {e}[/dim]\n")


# ── Input prompt ───────────────────────────────────────────────────────────────

def make_input_fn():
    """
    Return a get_input() callable.
    Uses prompt_toolkit with a styled prompt showing the model name.
    Falls back to plain input() if prompt_toolkit is unavailable.
    """
    model_name, _ = _active_model_label()
    short_model = model_name.split("/")[-1][:24]  # trim long model IDs

    try:
        from prompt_toolkit import prompt as pt_prompt
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.styles import Style
        from prompt_toolkit.formatted_text import HTML

        input_history = FileHistory(os.path.expanduser("~/.ai_agent_input_history"))
        style = Style.from_dict({"prompt": "ansicyan bold"})

        def get_input():
            return pt_prompt(
                HTML(f"<prompt>❯</prompt> "),
                history=input_history,
                style=style,
            ).strip()

    except ImportError:
        def get_input():
            return input(f"❯ ").strip()

    return get_input


# ── Message rendering ──────────────────────────────────────────────────────────

def render_user_message(text):
    """Render the user's message with a subtle 'You' label."""
    console.print()
    console.print(f"[bold green]You[/bold green]  [dim]│[/dim]  {text}")
    console.print()


def render_streaming(stream_iterator, model_name=""):
    """
    Stream LLM response inline — no heavy panel.
    Shows a header line with model name, streams markdown, ends with a timing badge.
    Returns (full_text, elapsed_seconds).
    """
    short = (model_name.split("/")[-1] if "/" in model_name else model_name)[:32]

    # Header rule
    console.print(Rule(
        f"[bold cyan]{short}[/bold cyan]",
        style="bright_black",
        align="left",
    ))

    full_text = ""
    t0 = time.time()

    with Live(console=console, refresh_per_second=12, vertical_overflow="visible") as live:
        for chunk in stream_iterator:
            content = ""
            if hasattr(chunk, "content") and chunk.content:
                content = chunk.content
            elif isinstance(chunk, str):
                content = chunk
            if content:
                full_text += content
                try:
                    live.update(Markdown(full_text))
                except Exception:
                    live.update(Text(full_text))

    elapsed = time.time() - t0

    # Footer with timing
    console.print()
    console.print(
        f"[dim]  {_fmt_seconds(elapsed)}  ·  {short}[/dim]"
    )
    console.print()

    return full_text


def render_response(text, model_name=""):
    """Non-streaming response render (fallback)."""
    short = (model_name.split("/")[-1] if "/" in model_name else model_name)[:32]
    console.print(Rule(
        f"[bold cyan]{short}[/bold cyan]",
        style="bright_black",
        align="left",
    ))
    try:
        console.print(Markdown(text))
    except Exception:
        console.print(text)
    console.print()


# ── Status / info messages ─────────────────────────────────────────────────────

def render_error(msg):
    console.print(f"\n[bold red]Error[/bold red]  [dim]│[/dim]  {msg}\n")


def render_info(msg):
    console.print(f"[dim]{msg}[/dim]")


def render_success(msg):
    console.print(f"[green]✓[/green]  {msg}")


def render_warning(msg):
    console.print(f"[yellow]⚠[/yellow]  {msg}")


# ── Command help ───────────────────────────────────────────────────────────────

COMMAND_DESCRIPTIONS = {
    # Calendar & tasks
    "today":          "Today's events + tasks due today",
    "week":           "7-day summary of events and tasks",
    "plan":           "/plan [today|week|month|year|backlog]  — tasks by horizon",
    "cal":            "/cal [month year]  — month grid with event/task markers",
    "cal-day":        "/cal-day YYYY-MM-DD  — drill into a specific day",
    # Task management
    "backlog":        "Unified task backlog (Obsidian + LogSeq)",
    "add-task":       "/add-task <text>  — add LATER task to today's LogSeq journal",
    "done":           "/done <text>  — mark a matching task done",
    "add-event":      "Add an event to your local ICS calendar",
    "remove-event":   "Remove an upcoming ICS calendar event",
    "export-calendar":"Export local calendar to .ics file",
    "import-calendar":"Import events from an .ics file",
    # Sync & planning
    "sync-logseq":    "Sync LogSeq LATER tasks → Obsidian planner",
    "sync-universal": "Full task sync through n8n conflict resolution",
    "google-tasks":   "Sync Google Tasks ↔ Obsidian",
    "reschedule":     '/reschedule <date> [--dry-run]  — move overdue tasks to a new date',
    "sync":           "Manually trigger task sync from Obsidian and Reminders",
    "pull":           "Sync calendar → Markdown (two-way sync)",
    # LLM & services
    "models":         "Show and select installed models",
    "ask":            "/ask <provider> <query>  — send one query to a specific provider",
    "routing":        "Show current LLM routing config",
    "services":       "Check and start local AI services",
    "model":          "/model enable|disable <provider>",
    "settings":       "/settings [set KEY value]  — view or update config",
    "status":         "Full system health dashboard",
    # Research
    "organize":       "Reorganise planner: surface overdue tasks + categorise by project",
    "cmd":            "/cmd <instruction>  — custom AI command on backlog",
    "develop":        "/develop <prompt>  — AI code generation",
    "gmail":          "List snoozed and filtered emails",
    "gmail-filter":   "Manage Gmail search filters",
    "index":          "Re-index notes and books for RAG search",
    # Misc
    "stats":          "Focus analytics for today",
    "ui":             "Launch Streamlit web dashboard",
    "docs":           "Show project documentation",
    "create-agent":   "Scaffold a new custom agent",
    "define-agent":   "Link an agent to a specific LLM",
    "list-agents":    "Show available custom agents",
    "history":        "Show recent conversation history",
    "clear-history":  "Clear conversation history",
    "help":           "Show this help",
    "quit":           "Exit",
}

# Group labels for the help table
_COMMAND_GROUPS = [
    ("Calendar & Tasks",   ["today", "week", "plan", "cal", "cal-day"]),
    ("Task Management",    ["backlog", "add-task", "done", "add-event", "remove-event",
                            "export-calendar", "import-calendar"]),
    ("Sync & Planning",    ["sync-logseq", "sync-universal", "google-tasks", "reschedule", "sync", "pull", "organize"]),
    ("LLM & Services",     ["models", "ask", "routing", "services", "model", "settings", "status"]),
    ("Research & AI",      ["cmd", "develop", "gmail", "gmail-filter", "index"]),
    ("Misc",               ["stats", "ui", "docs", "create-agent", "define-agent",
                            "list-agents", "history", "clear-history", "help", "quit"]),
]


def render_command_help():
    """Render slash commands grouped by category."""
    model_name, provider = _active_model_label()
    console.print()
    console.print(Rule(
        f"[bold]Commands[/bold]  [dim]model: {model_name} via {provider}[/dim]",
        style="bright_black",
    ))
    console.print()

    for group_label, cmds in _COMMAND_GROUPS:
        table = Table(
            box=box.SIMPLE,
            show_header=False,
            pad_edge=False,
            title=f"[dim]{group_label}[/dim]",
            title_justify="left",
            title_style="bold",
        )
        table.add_column("cmd", style="cyan", min_width=20, no_wrap=True)
        table.add_column("desc", style="")
        for cmd in cmds:
            desc = COMMAND_DESCRIPTIONS.get(cmd, "")
            table.add_row(f"/{cmd}", desc)
        console.print(table)

    console.print()


# ── Settings / routing / models ────────────────────────────────────────────────

def render_settings(config_path):
    """Render API key and LLM config status."""
    from config_utils import get_config_value

    console.print()
    console.print(Rule("[bold]Configuration[/bold]", style="bright_black"))
    console.print()

    # API keys
    key_table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", pad_edge=False)
    key_table.add_column("Key", style="cyan", min_width=22)
    key_table.add_column("Status", width=8)
    key_table.add_column("Preview")
    for key, label in [
        ("OPENAI_API_KEY", "OpenAI"),
        ("GEMINI_API_KEY", "Gemini"),
        ("CLAUDE_API_KEY", "Claude"),
        ("HF_TOKEN",       "HuggingFace"),
    ]:
        val = get_config_value(key, "")
        if not val or "your_" in val or "here" in val:
            key_table.add_row(label, "[red]not set[/red]", "[dim]—[/dim]")
        else:
            preview = f"{val[:6]}…{val[-4:]}" if len(val) > 12 else "***"
            key_table.add_row(label, "[green]set[/green]", f"[dim]{preview}[/dim]")
    console.print(key_table)

    # Routing
    route_table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", pad_edge=False)
    route_table.add_column("Setting", style="cyan", min_width=22)
    route_table.add_column("Value")
    for key in ["LM_STUDIO_MODEL", "OLLAMA_MODEL", "LLM_PRIORITY",
                "ROUTING_CHAT", "ROUTING_SCHEDULING", "ROUTING_PARSING", "ROUTING_PLANNING",
                "ENABLE_LM_STUDIO", "ENABLE_OLLAMA", "ENABLE_GEMINI", "ENABLE_CLAUDE"]:
        val = get_config_value(key, "")
        route_table.add_row(key, val or "[dim]not set[/dim]")
    console.print(route_table)
    console.print(f"[dim]  config: {config_path}[/dim]")
    console.print("[dim]  update: /settings set KEY value[/dim]\n")


def render_models(models_status):
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", pad_edge=False,
                  title="[bold]Models[/bold]", title_justify="left")
    table.add_column("Provider", style="cyan", min_width=12)
    table.add_column("Enabled", width=8)
    table.add_column("Available", width=10)
    for name, info in models_status.items():
        enabled = "[green]yes[/green]" if info["enabled"] else "[dim]no[/dim]"
        available = "[green]yes[/green]" if info["available"] else "[dim]no[/dim]"
        table.add_row(name, enabled, available)
    console.print()
    console.print(table)
    console.print()


def render_routing(routing_info):
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", pad_edge=False,
                  title="[bold]LLM Routing[/bold]", title_justify="left")
    table.add_column("Task Type", style="cyan", min_width=14)
    table.add_column("Config", width=12)
    table.add_column("Active")
    for task_type, info in routing_info.items():
        table.add_row(task_type, info["config"], f"[cyan]{info['active']}[/cyan]")
    console.print()
    console.print(table)
    console.print()


def render_services(lmstudio_status=None, ollama_status=None):
    """Render service status. Accepts lmstudio_status and/or ollama_status booleans."""
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", pad_edge=False,
                  title="[bold]Services[/bold]", title_justify="left")
    table.add_column("Service", style="cyan", min_width=14)
    table.add_column("Status")

    try:
        from ai_orchestration import is_lmstudio_running, is_ollama_running, MODELS_ENABLED
        from config_utils import get_config_value

        if MODELS_ENABLED.get("lmstudio"):
            model = get_config_value("LM_STUDIO_MODEL", "")
            running = lmstudio_status if lmstudio_status is not None else is_lmstudio_running()
            status = "[green]running[/green]" if running else "[red]stopped[/red]"
            table.add_row(f"LM Studio  [dim]{model}[/dim]", status)

        if MODELS_ENABLED.get("ollama"):
            running = ollama_status if ollama_status is not None else is_ollama_running()
            status = "[green]running[/green]" if running else "[red]stopped[/red]"
            table.add_row("Ollama", status)

    except Exception:
        # Fallback: old single-arg behaviour
        if ollama_status is not None:
            s = "[green]running[/green]" if ollama_status else "[red]stopped[/red]"
            table.add_row("Ollama", s)

    console.print()
    console.print(table)
    console.print()


# ── Backlog / history ──────────────────────────────────────────────────────────

def render_backlog(tasks):
    cats = {}
    for t in tasks:
        cat = t.get("category", "Uncategorized")
        cats.setdefault(cat, []).append(t)

    console.print()
    console.print(Rule(
        f"[bold]Backlog[/bold]  [dim]{len(tasks)} tasks[/dim]",
        style="bright_black",
    ))
    console.print()

    for cat, task_list in cats.items():
        table = Table(box=box.SIMPLE, show_header=False, pad_edge=False,
                      title=f"[dim]{cat}[/dim]", title_justify="left", title_style="bold")
        table.add_column("src", width=5, style="dim")
        table.add_column("task")
        table.add_column("due", width=12, style="dim")
        for t in task_list:
            src_map = {"Obsidian": "obs", "Logseq": "lsq", "Reminders": "rem"}
            src = src_map.get(t.get("source", ""), t.get("source", "")[:3])
            table.add_row(src, t.get("task", ""), t.get("due_date", "") or "")
        console.print(table)

    console.print()


def render_history_summary(history, count=10):
    recent = history[-(count * 2):]
    if not recent:
        console.print("[dim]No conversation history.[/dim]")
        return

    console.print()
    console.print(Rule("[bold]History[/bold]", style="bright_black"))
    console.print()
    for msg in recent:
        role = msg.get("role", "")
        content = msg.get("content", "")[:120]
        ts = msg.get("timestamp", "")[:16]
        if role == "user":
            console.print(f"[dim]{ts}[/dim]  [green]You[/green]  {content}")
        else:
            label, _ = _active_model_label()
            short = label.split("/")[-1][:20]
            console.print(f"[dim]{ts}[/dim]  [cyan]{short}[/cyan]  {content}")
    console.print()


# ── Conversation history persistence ──────────────────────────────────────────

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_history(history):
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history[-200:], f, indent=2)
    except IOError:
        pass


def add_to_history(role, content, history):
    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.datetime.now().isoformat(),
    })
    return history
