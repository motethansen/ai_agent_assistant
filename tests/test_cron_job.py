"""
Tests for cron_job.py

All agent run() functions are mocked — no real agents execute.
Uses tmp_path for the lockfile so the real .cron_job.lock is never touched.
"""
import os
import sys
import signal
import datetime
import pytest
from unittest.mock import patch, MagicMock, call

import cron_job


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_lockfile(path, pid, mtime_offset_seconds=0):
    """Write a lockfile with the given PID and optionally backdate its mtime."""
    with open(path, "w") as f:
        f.write(str(pid))
    if mtime_offset_seconds:
        old_time = datetime.datetime.now().timestamp() - mtime_offset_seconds
        os.utime(path, (old_time, old_time))


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_lockfile_prevents_concurrent_run(tmp_path):
    """
    If a fresh lockfile exists for an alive process, _acquire_lock() calls sys.exit(0).
    We write the current process's own PID so os.kill(pid, 0) succeeds,
    and backdate by only 1 second so the lock is NOT stale.
    """
    lock_path = str(tmp_path / ".cron_job.lock")
    _write_lockfile(lock_path, os.getpid(), mtime_offset_seconds=1)

    with patch.object(cron_job, "LOCKFILE", lock_path):
        with pytest.raises(SystemExit) as exc_info:
            cron_job._acquire_lock()

    assert exc_info.value.code == 0


def test_agents_flag_runs_only_specified_agent(tmp_path, monkeypatch):
    """
    Running with --agents datainput should invoke only run_datainput_agent,
    not run_logseq_later_agent, run_calendar_planning_agent, etc.
    """
    lock_path = str(tmp_path / ".cron_job.lock")
    monkeypatch.setattr(sys, "argv", ["cron_job.py", "--agents", "datainput"])

    mock_datainput   = MagicMock(return_value={"new_tasks": [], "organised": False})
    mock_logseq      = MagicMock(return_value=[])
    mock_calendar    = MagicMock(return_value=None)
    mock_legacy_sync = MagicMock(return_value=None)
    mock_health      = MagicMock(return_value=None)

    fake_agent_map = {
        "datainput":   mock_datainput,
        "logseq":      mock_logseq,
        "calendar":    mock_calendar,
        "legacy_sync": mock_legacy_sync,
        "health":      mock_health,
    }

    with patch.object(cron_job, "LOCKFILE", lock_path), \
         patch.object(cron_job, "AGENT_MAP", fake_agent_map), \
         patch("signal.alarm"):  # prevent actual SIGALRM from firing

        cron_job.main()

    mock_datainput.assert_called_once()
    mock_logseq.assert_not_called()
    mock_calendar.assert_not_called()
    mock_legacy_sync.assert_not_called()
    mock_health.assert_not_called()


def test_stale_lock_is_removed_and_run_proceeds(tmp_path, monkeypatch):
    """
    A lockfile older than MAX_RUN_SECONDS is treated as stale.
    The run should proceed (no SystemExit) and complete normally.
    """
    lock_path = str(tmp_path / ".cron_job.lock")
    stale_offset = cron_job.MAX_RUN_SECONDS + 60
    _write_lockfile(lock_path, os.getpid(), mtime_offset_seconds=stale_offset)

    monkeypatch.setattr(sys, "argv", ["cron_job.py", "--agents", "health"])

    mock_health = MagicMock(return_value=None)
    fake_agent_map = {"health": mock_health}

    # os.kill(pid, 0) must succeed (process "exists") so the stale-lock branch is reached.
    # os.kill(pid, SIGTERM) should be a no-op in tests.
    def _fake_kill(pid, sig):
        if sig == 0:
            return   # pretend process is alive so stale-lock branch fires
        if sig == signal.SIGTERM:
            return   # swallow SIGTERM during testing

    with patch.object(cron_job, "LOCKFILE", lock_path), \
         patch.object(cron_job, "AGENT_MAP", fake_agent_map), \
         patch("os.kill", side_effect=_fake_kill), \
         patch("signal.alarm"):

        # Should NOT raise SystemExit for a stale lock
        cron_job.main()

    mock_health.assert_called_once()
