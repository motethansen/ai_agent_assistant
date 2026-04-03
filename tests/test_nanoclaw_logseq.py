"""
Tests for the LogSeq NanoClaw skill integration and runner.

All tests mock subprocess.run — no real Docker container is required.
"""
import io
import json
import sys
from unittest.mock import MagicMock, patch

import pytest


def test_run_skill_list_later():
    """run_skill returns parsed task JSON for logseq_skill/list-later."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = json.dumps({
        "tasks": [
            {"task": "LATER Write report", "file": "journals/2026_04_03.md", "line": 5}
        ]
    })

    def _fake_config(key, default=None):
        return {
            "LOGSEQ_DIR": "/fake/logseq",
            "WORKSPACE_DIR": "/fake/vault",
        }.get(key, default)

    with patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
         patch("nanoclaw.client.get_config_value", side_effect=_fake_config), \
         patch("nanoclaw.client.subprocess.run", return_value=mock_proc):
        import nanoclaw.client as client
        result = client.run_skill("logseq_skill", "list-later")

    assert len(result["tasks"]) == 1


def test_run_skill_add_task_uses_write_flag():
    """run_skill mounts the skill volume read-write for add-task mutations."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = json.dumps({"status": "added", "task": "Review PR"})

    def _fake_config(key, default=None):
        return {
            "LOGSEQ_DIR": "/fake/logseq",
            "WORKSPACE_DIR": "/fake/vault",
        }.get(key, default)

    with patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
         patch("nanoclaw.client.get_config_value", side_effect=_fake_config), \
         patch("nanoclaw.client.subprocess.run", return_value=mock_proc) as mock_run:
        import nanoclaw.client as client
        client.run_skill("logseq_skill", "add-task", "Review PR", write=True)

    cmd = mock_run.call_args[0][0]
    assert "/fake/logseq:/logseq:rw" in cmd
    assert any(":rw" in arg for arg in cmd)


def test_run_skill_sync_to_obsidian_mounts_logseq_and_vault_rw():
    """sync-to-obsidian mounts both LogSeq and Obsidian paths with write access."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = json.dumps({"status": "synced", "tasks": 2})

    def _fake_config(key, default=None):
        return {
            "LOGSEQ_DIR": "/fake/logseq",
            "WORKSPACE_DIR": "/fake/vault",
        }.get(key, default)

    with patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
         patch("nanoclaw.client.get_config_value", side_effect=_fake_config), \
         patch("nanoclaw.client.subprocess.run", return_value=mock_proc) as mock_run:
        import nanoclaw.client as client
        client.run_skill("logseq_skill", "sync-to-obsidian", write=True)

    cmd = mock_run.call_args[0][0]
    assert "/fake/logseq:/logseq:rw" in cmd
    assert "/fake/vault:/vault:rw" in cmd


def test_skill_runner_list_later(tmp_path):
    """list-later scans the mounted LogSeq journals directory and returns JSON."""
    journals_dir = tmp_path / "journals"
    journals_dir.mkdir()
    (journals_dir / "2026_04_03.md").write_text("- LATER Write tests\n- DONE Old task\n")

    captured = io.StringIO()
    env_patch = patch.dict("os.environ", {"LOGSEQ_DIR": str(tmp_path)})
    argv_patch = patch("sys.argv", ["skill_runner.py", "list-later", "1"])
    stdout_patch = patch("sys.stdout", captured)

    if "nanoclaw.skills.logseq_skill.skill_runner" in sys.modules:
        del sys.modules["nanoclaw.skills.logseq_skill.skill_runner"]

    with env_patch, argv_patch, stdout_patch:
        try:
            import nanoclaw.skills.logseq_skill.skill_runner as runner
            runner.LOGSEQ_DIR = str(tmp_path)
            runner.agent = runner.LogSeqAgent(logseq_dir=str(tmp_path))
            runner.main()
        except SystemExit:
            pass

    result = json.loads(captured.getvalue().strip())
    assert "tasks" in result


def test_skill_runner_unknown_action():
    """Unknown action prints error JSON and exits 1."""
    captured = io.StringIO()
    env_patch = patch.dict("os.environ", {"LOGSEQ_DIR": "/tmp/logseq"})
    argv_patch = patch("sys.argv", ["skill_runner.py", "bad-action"])
    stdout_patch = patch("sys.stdout", captured)

    if "nanoclaw.skills.logseq_skill.skill_runner" in sys.modules:
        del sys.modules["nanoclaw.skills.logseq_skill.skill_runner"]

    with env_patch, argv_patch, stdout_patch:
        with pytest.raises(SystemExit):
            import nanoclaw.skills.logseq_skill.skill_runner as runner
            runner.main()

    assert "error" in captured.getvalue()


def test_skill_runner_sync_to_obsidian_writes_planner(tmp_path):
    """sync-to-obsidian writes the LogSeq LATER section into the mounted planner."""
    journals_dir = tmp_path / "logseq" / "journals"
    journals_dir.mkdir(parents=True)
    (journals_dir / "2026_04_03.md").write_text("- LATER Schedule roadmap review\n")

    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    planner = vault_dir / "Planner.md"
    planner.write_text("# Planner\n")

    captured = io.StringIO()
    env_patch = patch.dict("os.environ", {
        "LOGSEQ_DIR": str(tmp_path / "logseq"),
        "WORKSPACE_DIR": str(vault_dir),
    })
    argv_patch = patch("sys.argv", ["skill_runner.py", "sync-to-obsidian", "7"])
    stdout_patch = patch("sys.stdout", captured)

    if "nanoclaw.skills.logseq_skill.skill_runner" in sys.modules:
        del sys.modules["nanoclaw.skills.logseq_skill.skill_runner"]

    with env_patch, argv_patch, stdout_patch:
        try:
            import nanoclaw.skills.logseq_skill.skill_runner as runner
            runner.LOGSEQ_DIR = str(tmp_path / "logseq")
            runner.agent = runner.LogSeqAgent(logseq_dir=str(tmp_path / "logseq"))
            runner.main()
        except SystemExit:
            pass

    result = json.loads(captured.getvalue().strip())
    assert result["status"] == "synced"
    assert "## LogSeq LATER Tasks" in planner.read_text(encoding="utf-8")
