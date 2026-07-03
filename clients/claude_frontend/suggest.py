#!/usr/bin/env python3
"""
Suggest.py — Non-interactive one-shot mode

Fetches today's and overdue tasks, asks Claude for top 3 focus + suggestions.
Outputs markdown to stdout (intended for piping to WhatsApp, kanban, etc.).

Usage:
    python suggest.py

Environment:
    ASSISTANT_API_URL    API base URL (default: http://localhost:7890)
    ASSISTANT_API_KEY    API authentication key (from .config)
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

import httpx
from claude_agent_sdk import query, ClaudeAgentOptions

# ────────────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────────────

def load_config():
    """Load API URL and key from environment or .config file."""
    url = os.getenv("ASSISTANT_API_URL", "http://localhost:7890")
    key = os.getenv("ASSISTANT_API_KEY", "")

    # Fall back to parsing .config
    if not key:
        config_path = Path(__file__).parent.parent.parent / ".config"
        if config_path.exists():
            with open(config_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ASSISTANT_API_KEY="):
                        key = line.split("=", 1)[1].strip()
                        break

    return url, key


API_URL, API_KEY = load_config()
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}

# ────────────────────────────────────────────────────────────────────────────
# API Fetch
# ────────────────────────────────────────────────────────────────────────────

async def fetch_tasks() -> str:
    """Fetch today's and overdue tasks."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{API_URL}/tasks",
                headers=HEADERS,
                params={"include_done": False}
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        print(f"Error fetching tasks: {e}", file=sys.stderr)
        return ""

    tasks = data.get("tasks", [])
    today = datetime.now().date()

    # Separate today and overdue
    today_tasks = [t for t in tasks if t.get("due_date") == str(today)]
    overdue_tasks = [t for t in tasks if t.get("due_date") and t["due_date"] < str(today)]

    lines = []
    if overdue_tasks:
        lines.append("**Overdue:**")
        for t in overdue_tasks:
            prio = f" [{t['priority']}]" if t.get("priority") else ""
            lines.append(f"- {t.get('text', 'Untitled')}{prio}")

    if today_tasks:
        if overdue_tasks:
            lines.append("")
        lines.append("**Today:**")
        for t in today_tasks:
            prio = f" [{t['priority']}]" if t.get("priority") else ""
            lines.append(f"- {t.get('text', 'Untitled')}{prio}")

    return "\n".join(lines) if lines else "No tasks for today or overdue."


# ────────────────────────────────────────────────────────────────────────────
# Claude Query
# ────────────────────────────────────────────────────────────────────────────

async def main():
    """Fetch tasks and get Claude's top 3 + suggestions."""
    # Get tasks
    tasks_text = await fetch_tasks()

    # Build prompt
    prompt = f"""Given these tasks:

{tasks_text}

Please provide:
1. **Top 3 Focus Areas** — rank by urgency + impact
2. **Quick Suggestions** — how to tackle them efficiently
3. **Energy Check** — estimated effort level + time blocks

Keep it concise and actionable. Use markdown formatting."""

    system_prompt = """You are a productivity advisor. Help the user focus on what matters most today.
Be direct, practical, and motivating. Assume they work in time blocks (90-120 min deep work).
Suggest realistic schedules based on task complexity and energy patterns."""

    # Query Claude with options
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        permission_mode="bypassPermissions",  # No tool calls needed
    )

    collected = []
    try:
        async for message in query(prompt=prompt, options=options):
            # Collect AssistantMessage content
            if hasattr(message, "content") and message.content:
                for block in message.content:
                    if hasattr(block, "text"):
                        collected.append(block.text)
    except Exception as e:
        print(f"Error querying Claude: {e}", file=sys.stderr)
        sys.exit(1)

    # Print result
    result = "".join(collected)
    print(result)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
