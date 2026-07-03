"""
Board watcher — reacts to edits of the Today Kanban board within seconds.

Watches the kanban file (and the Planner) for changes via watchdog; on change,
debounces 2s and runs kanban_agent.process_board() so /commands and questions
typed as cards are answered while Obsidian is still open.

Run:  python watcher.py          (foreground)
      python main.py --watch     (same, via the CLI entry point)

The agent's own writes to the board also fire the watcher; process_board()
is idempotent (hash-tracked cards), so the follow-up run is a no-op.
"""

import sys
import time
import threading
from pathlib import Path

import config

_DEBOUNCE_SECS = 2.0


def run(verbose: bool = True) -> None:
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        sys.exit("watchdog not installed — run: pip install watchdog")

    vault = Path(config.paths.obsidian())
    from agents.kanban_agent import _KANBAN_REL
    board = vault / _KANBAN_REL
    if not board.exists():
        sys.exit(f"board not found: {board}")

    timer_lock = threading.Lock()
    pending: list[threading.Timer] = []

    def _process():
        from agents import kanban_agent
        try:
            result = kanban_agent.process_board()
            if verbose and result.get("handled"):
                print(f"[watcher] handled {result['handled']} card(s)")
        except Exception as exc:
            print(f"[watcher] error: {exc}")

    class Handler(FileSystemEventHandler):
        def on_modified(self, event):
            if Path(str(event.src_path)).name != board.name:
                return
            with timer_lock:
                while pending:
                    pending.pop().cancel()
                t = threading.Timer(_DEBOUNCE_SECS, _process)
                pending.append(t)
                t.start()

    observer = Observer()
    observer.schedule(Handler(), str(board.parent), recursive=False)
    observer.start()
    if verbose:
        print(f"[watcher] watching {board}")
        print("[watcher] add a card starting with / or ending with ? to the "
              "📥 Queued column — Ctrl+C to stop")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    run()
