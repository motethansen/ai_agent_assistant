"""
AI Agent Assistant — entry point.

Usage:
    python main.py              # interactive terminal (default)
    python main.py --plan       # generate today's plan and exit
    python main.py --plan week  # generate weekly plan and exit
    python main.py --sync       # run LogSeq sync and exit
    python main.py --status     # show system status and exit
    python main.py --today      # show today's tasks and events and exit
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ai-agent",
        description="AI Agent Assistant — personal productivity with LLM",
    )
    parser.add_argument("--plan", nargs="?", const="today", metavar="MODE",
                        help="Generate plan (today/week) and exit")
    parser.add_argument("--sync", action="store_true", help="Run LogSeq sync and exit")
    parser.add_argument("--status", action="store_true", help="Show system status and exit")
    parser.add_argument("--today", action="store_true", help="Show today's view and exit")
    parser.add_argument("--chat", action="store_true", help="Start in chat mode directly")
    parser.add_argument("--api", nargs="?", const=7890, metavar="PORT", type=int,
                        help="Start HTTP API server for distributed agents (default port 7890)")
    args = parser.parse_args()

    warnings = config.validate()
    if warnings:
        for w in warnings:
            print(f"  ⚠ {w}", file=sys.stderr)
        print()

    if args.api:
        try:
            import uvicorn
        except ImportError:
            print("uvicorn not installed — run: pip install fastapi uvicorn", file=sys.stderr)
            sys.exit(1)
        from api.server import app
        port = args.api if isinstance(args.api, int) else 7890
        print(f"Starting AI Agent Assistant API on port {port}…")
        uvicorn.run(app, host="0.0.0.0", port=port)
        return

    if args.status:
        from ui.commands import cmd_status
        cmd_status("")
        return

    if args.sync:
        from ui.commands import cmd_sync
        cmd_sync("")
        return

    if args.today:
        from ui.commands import cmd_today
        cmd_today("")
        return

    if args.plan:
        from ui.commands import cmd_plan
        cmd_plan(args.plan if args.plan != "today" else "")
        return

    from ui.chat import run_interactive, run_chat
    if args.chat:
        run_chat()
    else:
        run_interactive()


if __name__ == "__main__":
    main()
