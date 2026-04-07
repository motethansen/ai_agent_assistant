#!/usr/bin/env python3
"""Standalone system status dashboard."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
import update_manager
from rich.console import Console
from rich.table import Table

console = Console()

# Map check keys to human-readable labels
CHECK_LABELS = {
    "git": "Git",
    "lm_studio": "LM Studio",
    "ollama": "Ollama",
    "gemini": "Gemini API key",
    "google_calendar": "Google Calendar",
    "logseq_dir": "LogSeq dir",
    "obsidian_vault": "Obsidian vault",
    "cron_last_run": "Last cron run",
    "reminders_sync": "Reminders sync",
    "venv": "Venv",
}

STATUS_ICONS = {
    "ok": "[green]OK[/green]",
    "warning": "[yellow]WARN[/yellow]",
    "error": "[red]ERROR[/red]",
    "disabled": "[dim]DISABLED[/dim]",
    "missing": "[dim]MISSING[/dim]",
    # Legacy statuses from git check
    "up_to_date": "[green]OK[/green]",
    "update_available": "[yellow]WARN[/yellow]",
}

STATUS_SYMBOLS = {
    "ok": "✅",
    "warning": "⚠️ ",
    "error": "❌",
    "disabled": "—",
    "missing": "—",
    "up_to_date": "✅",
    "update_available": "⚠️ ",
}


def normalise_status(raw):
    """Normalise status values for display."""
    if raw in ("ok", "up_to_date"):
        return "ok"
    if raw in ("warning", "update_available"):
        return "warning"
    if raw in ("disabled", "missing"):
        return raw
    return "error"


def main():
    checks = update_manager.run_all_checks()

    last_check_raw = checks.get("last_check", "")
    try:
        last_check_dt = datetime.datetime.fromisoformat(last_check_raw)
        last_check_str = last_check_dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        last_check_str = last_check_raw or "unknown"

    table = Table(
        title=f"AI Agent Assistant — System Status\nLast check: {last_check_str}",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        box=None,
    )
    table.add_column("Check", style="bold", min_width=20)
    table.add_column("Status", min_width=12)
    table.add_column("Detail")

    any_error = False

    for key, label in CHECK_LABELS.items():
        result = checks.get(key)
        if result is None:
            continue

        raw_status = result.get("status", "error")
        message = result.get("message", "")
        norm = normalise_status(raw_status)

        if norm == "error":
            any_error = True

        symbol = STATUS_SYMBOLS.get(raw_status, STATUS_SYMBOLS.get(norm, "❓"))
        status_text = STATUS_ICONS.get(raw_status, STATUS_ICONS.get(norm, "[red]ERROR[/red]"))

        table.add_row(label, f"{symbol} {status_text}", message)

    console.print()
    console.print(table)
    console.print()

    sys.exit(1 if any_error else 0)


if __name__ == "__main__":
    main()
