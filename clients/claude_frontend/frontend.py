#!/usr/bin/env python3
"""
Claude Agent SDK Terminal Frontend for AI Assistant

Provides an interactive chat loop that wraps the ai_agent_assistant HTTP API
with custom MCP tools, driven by the locally-installed `claude` CLI.

Usage:
    python frontend.py

Environment variables:
    ASSISTANT_API_URL    API base URL (default: http://localhost:7890)
    ASSISTANT_API_KEY    API authentication key (from .config)
    CLAUDE_FRONTEND_SYSTEM_PROMPT  Override the system prompt
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

import httpx
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    create_sdk_mcp_server,
    tool,
)

console = Console()

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
# HTTP Client with error handling
# ────────────────────────────────────────────────────────────────────────────

async def _api_request(endpoint: str, method: str = "GET", **kwargs) -> dict:
    """Make HTTP request to the assistant API."""
    url = f"{API_URL}{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == "GET":
                resp = await client.get(url, headers=HEADERS, **kwargs)
            elif method.upper() == "POST":
                resp = await client.post(url, headers=HEADERS, **kwargs)
            else:
                return {"error": f"Unsupported method: {method}"}

            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        return {"error": f"Cannot connect to API at {API_URL}. Is it running? (python main.py --api)"}
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except:
            detail = str(e)
        return {"error": f"API error: {detail}"}
    except Exception as e:
        return {"error": f"Request failed: {type(e).__name__}: {str(e)}"}

# ────────────────────────────────────────────────────────────────────────────
# MCP Tools — wrap API endpoints
# ────────────────────────────────────────────────────────────────────────────

@tool(
    name="get_tasks",
    description="Fetch tasks from Obsidian. Filter by: today (due today), overdue (past due), week (this week), or all",
    input_schema={"filter": str}
)
async def get_tasks(args: dict) -> dict:
    """Get tasks filtered by status."""
    filter_type = args.get("filter", "all").lower()

    # Map filter to include_done
    include_done = False

    result = await _api_request("/tasks", params={"include_done": include_done})
    if "error" in result:
        return {"content": [{"type": "text", "text": result["error"]}], "is_error": True}

    tasks = result.get("tasks", [])
    today = datetime.now().date()

    # Apply client-side filtering
    if filter_type == "today":
        tasks = [t for t in tasks if t.get("due_date") == str(today)]
        label = "Today's tasks"
    elif filter_type == "overdue":
        tasks = [t for t in tasks if t.get("due_date") and t["due_date"] < str(today)]
        label = "Overdue tasks"
    elif filter_type == "week":
        import datetime as dt
        week_end = today + dt.timedelta(days=7)
        tasks = [t for t in tasks if t.get("due_date") and str(today) <= t["due_date"] <= str(week_end)]
        label = "This week's tasks"
    else:
        label = "All tasks"

    if not tasks:
        return {"content": [{"type": "text", "text": f"No {label.lower()}."}]}

    # Format as markdown
    lines = [f"**{label}** ({len(tasks)} total):\n"]
    for t in tasks:
        status = "✓" if t.get("done") else "○"
        due = f" (due {t['due_date']})" if t.get("due_date") else ""
        prio = f" [{t['priority']}]" if t.get("priority") else ""
        lines.append(f"  {status} {t.get('text', 'Untitled')}{prio}{due}")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


@tool(
    name="get_dashboard",
    description="Fetch dashboard sections: today-plan, week-plan, backlog, focus",
    input_schema={"section": str}
)
async def get_dashboard(args: dict) -> dict:
    """Get dashboard section."""
    section = args.get("section", "").lower().strip()

    result = await _api_request("/dashboard", params={"section": section})
    if "error" in result:
        return {"content": [{"type": "text", "text": result["error"]}], "is_error": True}

    if section:
        content = result.get("content", "")
        return {"content": [{"type": "text", "text": f"**{section}**:\n\n{content}"}]}

    # Show all sections
    sections = result.get("sections", {})
    lines = []
    for sec_name, sec_content in sections.items():
        if sec_content:
            lines.append(f"\n## {sec_name}")
            lines.append(sec_content)

    return {"content": [{"type": "text", "text": "\n".join(lines) or "Dashboard is empty"}]}


@tool(
    name="generate_plan",
    description="Generate a fresh daily or weekly plan using AI",
    input_schema={"mode": str}
)
async def generate_plan(args: dict) -> dict:
    """Generate a plan."""
    mode = args.get("mode", "today").lower()
    if mode not in ("today", "week"):
        return {
            "content": [{"type": "text", "text": "Mode must be 'today' or 'week'"}],
            "is_error": True
        }

    result = await _api_request("/plan", method="POST", params={"mode": mode})
    if "error" in result:
        return {"content": [{"type": "text", "text": result["error"]}], "is_error": True}

    plan_text = result.get("plan", "No plan generated")
    return {"content": [{"type": "text", "text": plan_text}]}


@tool(
    name="add_task",
    description="Add a new task to the inbox",
    input_schema={"text": str, "due_date": str}
)
async def add_task(args: dict) -> dict:
    """Add a task to the vault inbox via POST /tasks."""
    text = args.get("text", "").strip()
    due_date = args.get("due_date", "").strip()

    if not text:
        return {
            "content": [{"type": "text", "text": "Task text is required"}],
            "is_error": True
        }

    result = await _api_request(
        "/tasks", method="POST", json={"text": text, "due_date": due_date}
    )
    if "error" in result:
        return {"content": [{"type": "text", "text": result["error"]}], "is_error": True}
    return {"content": [{"type": "text", "text": f"Added to inbox: {result.get('added', text)}"}]}


@tool(
    name="mark_done",
    description="Mark a task as done (by text match)",
    input_schema={"text_match": str}
)
async def mark_done(args: dict) -> dict:
    """Mark task done."""
    text_match = args.get("text_match", "").strip()
    if not text_match:
        return {
            "content": [{"type": "text", "text": "Task text is required"}],
            "is_error": True
        }

    result = await _api_request(
        "/tasks/done", method="POST", json={"text_match": text_match}
    )
    if "error" in result:
        return {"content": [{"type": "text", "text": result["error"]}], "is_error": True}
    return {"content": [{"type": "text", "text": f"Marked done: {result.get('done', text_match)}"}]}


@tool(
    name="get_status",
    description="Get the assistant's configuration and status",
    input_schema={}
)
async def get_status(args: dict) -> dict:
    """Get status."""
    result = await _api_request("/status")
    if "error" in result:
        return {"content": [{"type": "text", "text": result["error"]}], "is_error": True}

    # Format status as text
    lines = ["**AI Agent Assistant Status**:\n"]
    for key, value in result.items():
        if isinstance(value, dict):
            lines.append(f"  {key}:")
            for k, v in value.items():
                lines.append(f"    {k}: {v}")
        else:
            lines.append(f"  {key}: {value}")

    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


# ────────────────────────────────────────────────────────────────────────────
# System Prompt
# ────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = os.getenv(
    "CLAUDE_FRONTEND_SYSTEM_PROMPT",
    """You are a productivity assistant helping the user manage their daily tasks and planning.

You have access to the following tools to query and manage tasks:
- get_tasks: Fetch tasks from Obsidian (filter: today, overdue, week, all)
- get_dashboard: View dashboard sections (today-plan, week-plan, backlog, focus)
- generate_plan: Create a fresh daily or weekly plan
- add_task: Add a new task to the inbox
- mark_done: Mark a task as complete
- get_status: Check the assistant's configuration

Your role:
1. Help the user review their current workload and priorities
2. Suggest focus areas based on available time and task urgency
3. Help reschedule tasks when needed
4. Generate daily and weekly plans
5. Provide motivation and structured guidance for productive work

Be concise, actionable, and respect the user's existing system (Obsidian, calendar, etc.).
Always check the current state (tasks, calendar, dashboard) before offering recommendations.
""")

# ────────────────────────────────────────────────────────────────────────────
# Interactive Chat
# ────────────────────────────────────────────────────────────────────────────

async def main():
    """Run the interactive chat loop."""
    console.print(
        Panel(
            "🤖 Claude Agent SDK — AI Assistant Frontend\n"
            f"API: {API_URL}\n"
            "Type your request or /help for commands",
            title="Welcome",
            expand=False
        )
    )

    # Create MCP server with custom tools
    mcp_server = create_sdk_mcp_server(
        name="ai_assistant_tools",
        version="1.0.0",
        tools=[
            get_tasks,
            get_dashboard,
            generate_plan,
            add_task,
            mark_done,
            get_status,
        ]
    )

    # Create client with options
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"ai_assistant": mcp_server},
        permission_mode="acceptEdits",  # Auto-accept tool calls
    )

    # Connect and chat
    async with ClaudeSDKClient(options=options) as client:
        # Initial welcome
        initial_prompt = "Hello! What's on my plate today? Give me a quick summary and top 3 focus areas."

        console.print(f"\n[dim]You:[/dim] {initial_prompt}\n")

        try:
            await client.connect(prompt=initial_prompt)

            # Read initial response
            async for message in client.stream_messages():
                if hasattr(message, "content") and message.content:
                    for block in message.content:
                        if hasattr(block, "text"):
                            console.print(f"[bold cyan]Claude:[/bold cyan] {block.text}\n")

            # Interactive loop
            while True:
                try:
                    user_input = console.input("\n[bold]You:[/bold] ").strip()
                except EOFError:
                    console.print("\n[dim]Goodbye.[/dim]")
                    break

                if not user_input:
                    continue

                if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                    console.print("[dim]Goodbye.[/dim]")
                    break

                if user_input == "/help":
                    console.print(
                        Panel(
                            "Available commands:\n"
                            "  /help       This help message\n"
                            "  /exit       Exit the chat\n"
                            "  /tasks      Show today's tasks\n"
                            "  /dashboard  Show dashboard sections\n"
                            "  /plan       Generate a daily plan\n"
                            "\nOr just type naturally — Claude will use tools as needed.",
                            title="Commands"
                        )
                    )
                    continue

                # Send user message and stream response
                try:
                    await client.send_message(user_input)

                    async for message in client.stream_messages():
                        if hasattr(message, "content") and message.content:
                            for block in message.content:
                                if hasattr(block, "text"):
                                    console.print(f"[bold cyan]Claude:[/bold cyan] {block.text}\n")

                except Exception as e:
                    console.print(f"[red]Error:[/red] {e}")

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted.[/dim]")
        finally:
            await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Fatal error:[/red] {e}", file=sys.stderr)
        sys.exit(1)
