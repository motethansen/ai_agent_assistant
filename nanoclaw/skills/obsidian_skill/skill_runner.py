#!/usr/bin/env python3
"""
NanoClaw Obsidian Skill runner — container entry point.

Usage (inside container):
    python skill_runner.py <action> [args...]

Actions:
    read_file   <relative-path>
    create_file <relative-path> <content> [--overwrite]
    update_file <relative-path> <content>
    list_files  [subdirectory]
    find_tasks

All output is a single JSON object on stdout.
On any error: {"error": "<message>"} is printed and the process exits with code 1.
"""
import json
import os
import sys

# Vault is mounted at /vault — set before any import that reads config
os.environ["WORKSPACE_DIR"] = "/vault"
VAULT = "/vault"

from obsidian_agent import ObsidianAgent  # noqa: E402 (import after env set)

agent = ObsidianAgent(workspace_dir=VAULT)


def _vault_path(rel_path: str) -> str:
    """Resolve a caller-supplied relative path to an absolute path inside /vault.
    Rejects any path that would escape the vault via path traversal."""
    abs_path = os.path.normpath(os.path.join(VAULT, rel_path))
    if not abs_path.startswith(VAULT):
        raise ValueError(f"Path traversal rejected: {rel_path!r}")
    return abs_path


def action_read_file(args: list) -> dict:
    if not args:
        return {"error": "read_file requires <relative-path>"}
    path = _vault_path(args[0])
    content = agent.read_file(path)
    if content is None:
        return {"error": f"File not found: {args[0]}"}
    return {"content": content, "path": args[0]}


def action_create_file(args: list) -> dict:
    if len(args) < 2:
        return {"error": "create_file requires <relative-path> <content> [--overwrite]"}
    rel_path = args[0]
    content = args[1]
    overwrite = "--overwrite" in args
    path = _vault_path(rel_path)
    created = agent.create_file(path, content, overwrite=overwrite)
    if not created:
        return {"error": f"File already exists (use --overwrite to replace): {rel_path}"}
    return {"status": "created", "path": rel_path}


def action_update_file(args: list) -> dict:
    if len(args) < 2:
        return {"error": "update_file requires <relative-path> <content>"}
    rel_path = args[0]
    content = args[1]
    path = _vault_path(rel_path)
    if not os.path.exists(path):
        return {"error": f"File not found: {rel_path}"}
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return {"status": "updated", "path": rel_path}
    except OSError as exc:
        return {"error": str(exc)}


def action_list_files(args: list) -> dict:
    subdir = args[0] if args else ""
    base = _vault_path(subdir) if subdir else VAULT
    if not os.path.isdir(base):
        return {"error": f"Directory not found: {subdir or '/vault'}"}
    files = []
    for root, dirs, filenames in os.walk(base):
        # Skip hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in filenames:
            if fname.endswith(".md"):
                abs_f = os.path.join(root, fname)
                files.append(os.path.relpath(abs_f, VAULT))
    return {"files": sorted(files)}


def action_find_tasks(args: list) -> dict:
    include_done = "--include-done" in args
    tasks = agent.get_tasks(todo=True, done=include_done)
    return {"tasks": tasks, "count": len(tasks)}


ACTIONS = {
    "read_file": action_read_file,
    "create_file": action_create_file,
    "update_file": action_update_file,
    "list_files": action_list_files,
    "find_tasks": action_find_tasks,
}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "action required. Available: " + ", ".join(ACTIONS)}))
        sys.exit(1)

    action = sys.argv[1]
    args = sys.argv[2:]

    handler = ACTIONS.get(action)
    if handler is None:
        print(json.dumps({"error": f"unknown action: {action!r}. Available: {', '.join(ACTIONS)}"}))
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
