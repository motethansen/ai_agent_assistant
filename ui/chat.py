"""
Terminal chat interface — interactive loop with history and streaming output.
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
_HISTORY_MAX = 50

_CHAT_SYSTEM = """You are a personal productivity assistant with access to the user's Obsidian notes and task system.
Be concise, practical, and actionable. Format responses as clean markdown.
If you don't know something, say so. Never invent tasks or events."""


def _load_history() -> list[dict]:
    try:
        return json.loads(_HISTORY_FILE.read_text())[-_HISTORY_MAX:]
    except (OSError, json.JSONDecodeError):
        return []


def _save_history(history: list[dict]) -> None:
    _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _HISTORY_FILE.write_text(json.dumps(history[-_HISTORY_MAX:], indent=2, default=str))


def _banner() -> None:
    from llm.router import all_providers
    providers = all_providers()
    available = [p["provider"] for p in providers if p.get("available")]
    active = config.llm.routing_chat()

    console.print()
    console.print(Rule("[bold cyan]AI Agent Assistant[/bold cyan]"))
    console.print(f"  Active LLM: [cyan]{active}[/cyan]  |  "
                  f"Available: [dim]{', '.join(available) or 'none'}[/dim]")
    console.print(f"  Vault: [dim]{config.paths.obsidian() or 'not set'}[/dim]")
    console.print(f"  Type [bold]/help[/bold] for commands, [bold]/chat[/bold] to chat, [bold]exit[/bold] to quit")
    console.print(Rule())
    console.print()


def run_chat() -> None:
    """Open-ended freeform chat with streaming output."""
    history = _load_history()
    console.print("[dim]Chat mode — type your message. /back to return to commands.[/dim]")

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]you[/bold cyan]")
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

        history.append({"role": "user", "content": user_input, "ts": str(datetime.datetime.now())})

        console.print("[bold green]assistant[/bold green]: ", end="")
        full_response = ""
        for chunk in router.stream(user_input, task="chat", system=_CHAT_SYSTEM):
            console.print(chunk, end="")
            full_response += chunk
        console.print()

        history.append({"role": "assistant", "content": full_response, "ts": str(datetime.datetime.now())})
        _save_history(history)


def run_interactive() -> None:
    """Main interactive loop — commands + chat."""
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
        else:
            # Plain text → treat as chat
            history.append({"role": "user", "content": user_input, "ts": str(datetime.datetime.now())})
            console.print("[bold green]assistant[/bold green]: ", end="")
            full_response = ""
            for chunk in router.stream(user_input, task="chat", system=_CHAT_SYSTEM):
                console.print(chunk, end="")
                full_response += chunk
            console.print()
            history.append({"role": "assistant", "content": full_response, "ts": str(datetime.datetime.now())})
            _save_history(history)
