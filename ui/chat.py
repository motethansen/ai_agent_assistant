"""
Terminal chat interface — conversational AI with history context and streaming.

Visual design mirrors Claude/Gemini chat:
  - Styled turn headers (model name + timestamp)
  - Horizontal rules separating turns
  - Streaming output with full history context sent to LLM
"""

import json
import datetime
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule
from rich.prompt import Prompt

from ui import commands, views
from llm import router
import config

console = views.console

_HISTORY_FILE = Path(__file__).parent.parent / "output" / "chat_history.json"
_HISTORY_MAX   = 50   # messages persisted to disk
_CONTEXT_TURNS = 6    # conversation turns (12 messages) sent to LLM as context

_CHAT_SYSTEM = """You are a personal productivity assistant integrated with the user's Obsidian vault, LogSeq notes, and Apple Calendar.
In this chat you answer questions and discuss plans. You do NOT have live read access to the vault here — use slash commands for that:
  /today, /week, /backlog, /plan, /notes <question>, /kg <question>, /status, /help (full list)
Be concise, practical, and actionable. Format responses as clean markdown.
If you don't know something, say so. Never invent tasks or events."""


# ── History helpers ───────────────────────────────────────────────────────────

def _load_history() -> list[dict]:
    try:
        return json.loads(_HISTORY_FILE.read_text())[-_HISTORY_MAX:]
    except (OSError, json.JSONDecodeError):
        return []


def _save_history(history: list[dict]) -> None:
    _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _HISTORY_FILE.write_text(json.dumps(history[-_HISTORY_MAX:], indent=2, default=str))


def _build_context(history: list[dict]) -> list[dict]:
    """Return the last N turns as LLM-compatible messages, stripping timestamps."""
    turns = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if m.get("role") in ("user", "assistant")
    ]
    return turns[-(_CONTEXT_TURNS * 2):]


# ── Display helpers ───────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M")


def _print_user_turn(text: str) -> None:
    console.print()
    console.print(f"[bold cyan]You[/bold cyan]  [dim]{_ts()}[/dim]")
    console.rule(style="cyan dim")
    console.print(text)
    console.print()


def _print_assistant_header() -> str:
    model = config.llm.routing_chat()
    console.print(f"[bold green]{model}[/bold green]  [dim]{_ts()}[/dim]")
    console.rule(style="green dim")
    return model


def _banner() -> None:
    from llm.router import all_providers
    providers = all_providers()
    available = [p["provider"] for p in providers if p.get("available")]
    active = config.llm.routing_chat()

    console.print()
    console.rule("[bold]AI Agent Assistant[/bold]")
    console.print(
        f"  [cyan]{active}[/cyan]  ·  "
        f"[dim]{', '.join(available) or 'no providers'}[/dim]  ·  "
        f"[dim]{config.paths.obsidian() or 'vault not set'}[/dim]"
    )
    console.print("  [dim]/help · /chat · /status · exit[/dim]")
    console.rule()
    console.print()


# ── Chat modes ────────────────────────────────────────────────────────────────

def run_chat() -> None:
    """Open-ended freeform chat with streaming output and full history context."""
    history = _load_history()
    model = config.llm.routing_chat()
    turn_count = len([m for m in history if m.get("role") == "user"])

    console.print(
        f"\n[dim]Chat  ·  [bold]{model}[/bold]  ·  "
        f"{turn_count} prior turns  ·  /back to return[/dim]"
    )
    console.rule(style="dim")

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]>[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            break

        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() in ("/back", "back", "exit", "quit"):
            break
        if user_input.startswith("/"):
            result = commands.dispatch(user_input)
            if result:
                console.print(result)
            continue

        _send_and_stream(user_input, history)


def run_interactive() -> None:
    """Main interactive loop — slash commands + inline chat."""
    _banner()
    history = _load_history()

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]>[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            break

        if user_input.startswith("/"):
            if user_input.lower() == "/chat":
                run_chat()
                continue
            result = commands.dispatch(user_input)
            if result is not None:
                console.print(result)
        elif user_input.lower() in ("help", "?", "commands"):
            commands.dispatch("/help")
        else:
            _send_and_stream(user_input, history)


def _send_and_stream(user_input: str, history: list[dict]) -> None:
    """Send a message, stream the response, update history."""
    ts = _ts()
    history.append({"role": "user", "content": user_input, "ts": ts})

    context = _build_context(history[:-1])  # history prior to this message

    _print_user_turn(user_input)
    _print_assistant_header()

    full_response = ""
    for chunk in router.stream(user_input, task="chat", system=_CHAT_SYSTEM, history=context):
        console.print(chunk, end="", highlight=False)
        full_response += chunk
    console.print("\n")

    history.append({"role": "assistant", "content": full_response, "ts": _ts()})
    _save_history(history)
