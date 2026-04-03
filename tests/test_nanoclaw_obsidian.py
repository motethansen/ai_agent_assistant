"""
Tests for nanoclaw.client and nanoclaw/skills/obsidian_skill/skill_runner.py.

All tests mock subprocess.run — no real Docker container is required.
"""
import importlib
import io
import json
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# nanoclaw.client tests
# ---------------------------------------------------------------------------

class TestRunSkill:
    """Tests for nanoclaw.client.run_skill()."""

    def test_run_skill_success(self):
        """run_skill returns parsed dict when Docker exits 0 with valid JSON."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({"files": ["Planner.md", "Inbox.md"]})

        with patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
             patch("nanoclaw.client.get_config_value", return_value="/fake/vault"), \
             patch("nanoclaw.client.subprocess.run", return_value=mock_proc):
            import nanoclaw.client as client
            result = client.run_skill("obsidian_skill", "list_files")

        assert result == {"files": ["Planner.md", "Inbox.md"]}

    def test_run_skill_disabled(self):
        """run_skill raises RuntimeError immediately when NANOCLAW_ENABLED=false."""
        with patch("nanoclaw.client.NANOCLAW_ENABLED", False):
            import nanoclaw.client as client
            with pytest.raises(RuntimeError, match="disabled"):
                client.run_skill("obsidian_skill", "list_files")

    def test_run_skill_docker_failure(self):
        """run_skill raises RuntimeError when Docker exits non-zero."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "container startup error"

        with patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
             patch("nanoclaw.client.get_config_value", return_value="/fake/vault"), \
             patch("nanoclaw.client.subprocess.run", return_value=mock_proc):
            import nanoclaw.client as client
            with pytest.raises(RuntimeError, match="failed"):
                client.run_skill("obsidian_skill", "find_tasks")

    def test_run_skill_invalid_json(self):
        """run_skill raises RuntimeError when container stdout is not valid JSON."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "this is not json"

        with patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
             patch("nanoclaw.client.get_config_value", return_value="/fake/vault"), \
             patch("nanoclaw.client.subprocess.run", return_value=mock_proc):
            import nanoclaw.client as client
            with pytest.raises(RuntimeError, match="invalid JSON"):
                client.run_skill("obsidian_skill", "list_files")

    def test_run_skill_write_true_uses_rw_mount(self):
        """run_skill passes :rw volume mount when write=True."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({"status": "created", "path": "Note.md"})

        with patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
             patch("nanoclaw.client.get_config_value", return_value="/my/vault"), \
             patch("nanoclaw.client.subprocess.run", return_value=mock_proc) as mock_run:
            import nanoclaw.client as client
            client.run_skill("obsidian_skill", "create_file", "Note.md", "# Hello", write=True)

        cmd = mock_run.call_args[0][0]
        assert "/my/vault:/vault:rw" in cmd

    def test_run_skill_write_false_uses_ro_mount(self):
        """run_skill passes :ro volume mount when write=False (default)."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({"files": []})

        with patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
             patch("nanoclaw.client.get_config_value", return_value="/my/vault"), \
             patch("nanoclaw.client.subprocess.run", return_value=mock_proc) as mock_run:
            import nanoclaw.client as client
            client.run_skill("obsidian_skill", "list_files")

        cmd = mock_run.call_args[0][0]
        assert "/my/vault:/vault:ro" in cmd


# ---------------------------------------------------------------------------
# skill_runner.py tests (runs in-process, no Docker)
# ---------------------------------------------------------------------------

class TestSkillRunner:
    """Tests for the container-side skill_runner entry point."""

    def _run_runner(self, argv, vault_dir):
        """Helper: import skill_runner with patched env and sys.argv, capture stdout."""
        captured = io.StringIO()

        # Patch env and argv before reloading the module
        env_patch = patch.dict("os.environ", {"WORKSPACE_DIR": str(vault_dir)})
        argv_patch = patch("sys.argv", argv)
        stdout_patch = patch("sys.stdout", captured)

        # Force reimport so os.environ["WORKSPACE_DIR"] is picked up fresh
        if "nanoclaw.skills.obsidian_skill.skill_runner" in sys.modules:
            del sys.modules["nanoclaw.skills.obsidian_skill.skill_runner"]

        with env_patch, argv_patch, stdout_patch:
            try:
                import nanoclaw.skills.obsidian_skill.skill_runner as runner
                runner.VAULT = str(vault_dir)
                runner.agent.__init__(workspace_dir=str(vault_dir))
                runner.main()
            except SystemExit:
                pass

        raw = captured.getvalue().strip()
        return json.loads(raw) if raw else {}

    def test_read_file_returns_content(self, tmp_path):
        """read_file action returns JSON with 'content' key."""
        note = tmp_path / "Note.md"
        note.write_text("# Hello World\n- [ ] My task")

        result = self._run_runner(
            ["skill_runner.py", "read_file", "Note.md"],
            tmp_path,
        )

        assert "content" in result
        assert "Hello World" in result["content"]

    def test_read_file_missing_returns_error(self, tmp_path):
        """read_file on a non-existent file returns error JSON, exits 1."""
        result = self._run_runner(
            ["skill_runner.py", "read_file", "DoesNotExist.md"],
            tmp_path,
        )
        assert "error" in result

    def test_find_tasks_returns_task_list(self, tmp_path):
        """find_tasks action returns tasks from markdown files."""
        note = tmp_path / "Tasks.md"
        note.write_text("- [ ] Write tests\n- [x] Old task\n- [ ] Review PR\n")

        result = self._run_runner(
            ["skill_runner.py", "find_tasks"],
            tmp_path,
        )

        assert "tasks" in result
        assert "count" in result
        incomplete = [t for t in result["tasks"] if not t.get("done")]
        assert len(incomplete) == 2

    def test_list_files_returns_md_files(self, tmp_path):
        """list_files action returns all .md files in the vault."""
        (tmp_path / "Alpha.md").write_text("# A")
        (tmp_path / "Beta.md").write_text("# B")
        (tmp_path / "note.txt").write_text("ignored")

        result = self._run_runner(
            ["skill_runner.py", "list_files"],
            tmp_path,
        )

        assert "files" in result
        assert "Alpha.md" in result["files"]
        assert "Beta.md" in result["files"]
        assert "note.txt" not in result["files"]

    def test_unknown_action_returns_error(self, tmp_path):
        """Unknown action prints error JSON and exits 1."""
        result = self._run_runner(
            ["skill_runner.py", "explode"],
            tmp_path,
        )
        assert "error" in result
