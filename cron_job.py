"""
Background cron runner — runs the sync agent on a configurable interval.

Usage:
    python cron_job.py              # run once and exit
    python cron_job.py --loop       # run continuously on SYNC_INTERVAL_MINUTES

The process uses a lock file to prevent concurrent runs.
Set up via launchd (macOS) or crontab — see install.sh.
"""

import argparse
import datetime
import sys
import time
from pathlib import Path

_LOCK_FILE = Path(__file__).parent / "output" / ".cron.lock"
_LOG_FILE  = Path(__file__).parent / "output" / "cron.log"
_LOCK_TIMEOUT_SECONDS = 300


def _log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOG_FILE, "a") as f:
        f.write(line + "\n")


def _acquire_lock() -> bool:
    _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _LOCK_FILE.exists():
        age = time.time() - _LOCK_FILE.stat().st_mtime
        if age < _LOCK_TIMEOUT_SECONDS:
            return False
        _LOCK_FILE.unlink()
    _LOCK_FILE.write_text(str(datetime.datetime.now()))
    return True


def _release_lock() -> None:
    if _LOCK_FILE.exists():
        _LOCK_FILE.unlink()


def run_once() -> None:
    if not _acquire_lock():
        _log("skipped — another instance is running")
        return

    try:
        _log("sync started")
        from agents.sync_agent import run as sync_run
        result = sync_run()
        _log(
            f"sync done — {result['tasks_added']} tasks, "
            f"{result['notes_added']} notes, {result['skipped']} skipped"
        )
    except Exception as e:
        _log(f"sync error: {e}")
    finally:
        _release_lock()


def run_loop(interval_minutes: int) -> None:
    _log(f"cron loop started — interval: {interval_minutes} min")
    while True:
        run_once()
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Agent Assistant cron runner")
    parser.add_argument("--loop", action="store_true", help="Run continuously on schedule")
    parser.add_argument("--interval", type=int, default=None, help="Override sync interval (minutes)")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).parent))
    import config

    interval = args.interval or config.sync.interval_minutes()

    if args.loop:
        run_loop(interval)
    else:
        run_once()
