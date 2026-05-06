"""
Background cron runner — orchestrates all agents on a schedule.

Runs every SYNC_INTERVAL_MINUTES (default 30 min).
Three jobs with different frequencies:
  - Sync (every run): LogSeq → Obsidian
  - Knowledge graph (once daily, any time): incremental RDF index update
  - Morning plan (once daily, 07:00–10:00 window): generate today's schedule

Usage:
    python cron_job.py              # run once and exit
    python cron_job.py --loop       # run continuously on SYNC_INTERVAL_MINUTES
    python cron_job.py --rebuild-kg # force full knowledge graph rebuild, then exit

Deployed via launchd (macOS) or crontab — see install.sh.
"""

import argparse
import datetime
import sys
import time
from pathlib import Path

_LOCK_FILE     = Path(__file__).parent / "output" / ".cron.lock"
_LOG_FILE      = Path(__file__).parent / "output" / "cron.log"
_PLAN_LAST_RUN = Path(__file__).parent / "output" / ".plan_last_run"
_KG_LAST_RUN   = Path(__file__).parent / "output" / ".kg_last_run"
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


def _should_run_plan() -> bool:
    """True once daily during the morning window (07:00–10:00)."""
    now = datetime.datetime.now()
    if not (7 <= now.hour < 10):
        return False
    if not _PLAN_LAST_RUN.exists():
        return True
    try:
        last = datetime.date.fromisoformat(_PLAN_LAST_RUN.read_text().strip())
        return last < datetime.date.today()
    except (ValueError, OSError):
        return True


def _mark_plan_run() -> None:
    _PLAN_LAST_RUN.parent.mkdir(parents=True, exist_ok=True)
    _PLAN_LAST_RUN.write_text(datetime.date.today().isoformat())


def _should_run_kg() -> bool:
    """True once per calendar day."""
    if not _KG_LAST_RUN.exists():
        return True
    try:
        last = datetime.date.fromisoformat(_KG_LAST_RUN.read_text().strip())
        return last < datetime.date.today()
    except (ValueError, OSError):
        return True


def _mark_kg_run() -> None:
    _KG_LAST_RUN.parent.mkdir(parents=True, exist_ok=True)
    _KG_LAST_RUN.write_text(datetime.date.today().isoformat())


def run_once() -> None:
    if not _acquire_lock():
        _log("skipped — another instance is running")
        return

    try:
        # 1. Sync LogSeq → Obsidian (every interval)
        _log("sync started")
        from agents.sync_agent import run as sync_run
        result = sync_run()
        _log(
            f"sync done — {result['tasks_added']} tasks, "
            f"{result['notes_added']} notes, {result['skipped']} skipped"
        )

        # 2. Knowledge graph (once daily — incremental)
        if _should_run_kg():
            _log("knowledge graph update started")
            try:
                from agents.knowledge_agent import run as kg_run
                kg = kg_run()
                _log(
                    f"knowledge graph done — {kg['indexed']} indexed, "
                    f"{kg['skipped']} skipped, {kg.get('removed', 0)} removed"
                )
                _mark_kg_run()
            except Exception as e:
                _log(f"knowledge graph error: {e}")

        # 3. Morning plan (once daily, 07:00–10:00)
        if _should_run_plan():
            _log("morning plan started")
            try:
                from agents.planning_agent import run_today
                run_today()
                _mark_plan_run()
                _log("morning plan written to Dashboard")
            except Exception as e:
                _log(f"morning plan error: {e}")

    except Exception as e:
        _log(f"cron error: {e}")
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
    parser.add_argument("--rebuild-kg", action="store_true", help="Force full knowledge graph rebuild and exit")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).parent))
    import config

    if args.rebuild_kg:
        print("Rebuilding knowledge graph from scratch...")
        from agents.knowledge_agent import run as kg_run, graph_stats
        result = kg_run(full_rebuild=True)
        s = graph_stats()
        print(f"Done — {result['indexed']} indexed · {s['triples']} triples · {s['notes']} notes · {s['tasks']} tasks")
        sys.exit(0)

    interval = args.interval or config.sync.interval_minutes()

    if args.loop:
        run_loop(interval)
    else:
        run_once()
