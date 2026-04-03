#!/usr/bin/env python3
"""
NanoClaw LogSeq Skill runner — container entry point.

Usage (inside container):
    python skill_runner.py <action> [args...]

Actions:
    list-later       [days]
    add-task         <description>
    mark-done        <task-text>
    sync-to-obsidian [days]

All output is a single JSON object on stdout.
On any error: {"error": "<message>"} is printed and the process exits with code 1.
"""
import json
import io
import os
import sys
from contextlib import redirect_stdout

# LogSeq graph is mounted at /logseq — set before any import that reads config
os.environ["LOGSEQ_DIR"] = "/logseq"
os.environ.setdefault("WORKSPACE_DIR", "/vault")
LOGSEQ_DIR = "/logseq"

from logseq_agent import LogSeqAgent  # noqa: E402 (import after env set)
from logseq_later_agent import scan_later_tasks, write_summary_to_obsidian  # noqa: E402 (import after env set)

agent = LogSeqAgent(logseq_dir=LOGSEQ_DIR)


def action_list_later(args: list) -> dict:
    days = int(args[0]) if args else 7
    with redirect_stdout(io.StringIO()):
        tasks = scan_later_tasks(days=days, logseq_dir=LOGSEQ_DIR)
    return {"tasks": tasks}


def action_add_task(args: list) -> dict:
    description = " ".join(args).strip()
    if not description:
        return {"error": "add-task requires <description>"}
    agent.add_task(description)
    return {"status": "added", "task": description}


def action_mark_done(args: list) -> dict:
    task_text = " ".join(args).strip()
    if not task_text:
        return {"error": "mark-done requires <task-text>"}
    agent.mark_done(task_text)
    return {"status": "marked-done", "task": task_text}


def action_sync_to_obsidian(args: list) -> dict:
    days = int(args[0]) if args else 7
    with redirect_stdout(io.StringIO()):
        tasks = scan_later_tasks(days=days, logseq_dir=LOGSEQ_DIR)
        write_summary_to_obsidian(tasks)
    return {"status": "synced", "tasks": len(tasks)}


ACTIONS = {
    "list-later": action_list_later,
    "add-task": action_add_task,
    "mark-done": action_mark_done,
    "sync-to-obsidian": action_sync_to_obsidian,
}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "action required. Available: " + ", ".join(ACTIONS)}))
        sys.exit(1)

    action = sys.argv[1]
    args = sys.argv[2:]

    handler = ACTIONS.get(action)
    if handler is None:
        print(json.dumps({"error": f"unknown action: {action}"}))
        sys.exit(1)

    try:
        result = handler(args)
    except Exception as exc:
        result = {"error": str(exc)}

    print(json.dumps(result))

    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
