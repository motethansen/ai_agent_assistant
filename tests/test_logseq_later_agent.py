"""
Tests for logseq_later_agent.py

Uses tmp_path for all file I/O — never touches real vault or LogSeq directories.
"""
import pytest
from unittest.mock import patch

import logseq_later_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logseq_dir(tmp_path):
    """Create minimal journals/ and pages/ subdirectories under tmp_path."""
    (tmp_path / "journals").mkdir()
    (tmp_path / "pages").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_later_tasks_parsed_from_journal(tmp_path):
    """LATER tasks are discovered in a journal file; DONE tasks are ignored."""
    _make_logseq_dir(tmp_path)
    journal = tmp_path / "journals" / "2026_03_27.md"
    journal.write_text(
        "- LATER Write unit tests\n"
        "- DONE Old completed task\n"
        "- LATER Review PR #42\n",
        encoding="utf-8",
    )

    with patch("logseq_later_agent.get_config_value", side_effect=lambda key, default=None: {
        "LOGSEQ_DIR": str(tmp_path),
        "LOGSEQ_JOURNAL_DAYS": "30",
    }.get(key, default)):
        tasks = logseq_later_agent.scan_all_later_tasks(days=30)

    task_texts = [t["task"] for t in tasks]
    assert len(tasks) == 2
    assert any("Write unit tests" in txt for txt in task_texts)
    assert any("Review PR #42" in txt for txt in task_texts)
    assert not any("Old completed task" in txt for txt in task_texts)


def test_later_tasks_parsed_from_pages(tmp_path):
    """LATER tasks in page files are included in results."""
    _make_logseq_dir(tmp_path)
    page = tmp_path / "pages" / "project.md"
    page.write_text(
        "- LATER Refactor the auth module\n",
        encoding="utf-8",
    )

    with patch("logseq_later_agent.get_config_value", side_effect=lambda key, default=None: {
        "LOGSEQ_DIR": str(tmp_path),
        "LOGSEQ_JOURNAL_DAYS": "30",
    }.get(key, default)):
        tasks = logseq_later_agent.scan_all_later_tasks(days=30)

    task_texts = [t["task"] for t in tasks]
    assert any("Refactor the auth module" in txt for txt in task_texts)


def test_deduplication_same_task_in_journal_and_pages(tmp_path):
    """Identical task text in both journals and pages appears only once."""
    _make_logseq_dir(tmp_path)

    shared_task = "Fix the login bug"
    journal = tmp_path / "journals" / "2026_03_27.md"
    journal.write_text(f"- LATER {shared_task}\n", encoding="utf-8")

    page = tmp_path / "pages" / "backlog.md"
    page.write_text(f"- LATER {shared_task}\n", encoding="utf-8")

    with patch("logseq_later_agent.get_config_value", side_effect=lambda key, default=None: {
        "LOGSEQ_DIR": str(tmp_path),
        "LOGSEQ_JOURNAL_DAYS": "30",
    }.get(key, default)):
        tasks = logseq_later_agent.scan_all_later_tasks(days=30)

    matching = [t for t in tasks if shared_task.lower() in t["task"].lower()]
    assert len(matching) == 1, f"Expected 1 deduplicated task, got {len(matching)}"


def test_write_to_obsidian_creates_later_tasks_section(tmp_path):
    """run(write_to_obsidian=True) writes a '## LogSeq LATER Tasks' block to the planner."""
    _make_logseq_dir(tmp_path)

    # Add a journal task so there is something to write
    journal = tmp_path / "journals" / "2026_03_27.md"
    journal.write_text("- LATER Deploy to production\n", encoding="utf-8")

    vault = tmp_path / "vault"
    vault.mkdir()
    planner = vault / "Planner.md"
    planner.write_text("# My Planner\n\n## Tasks\n- [ ] Some task\n", encoding="utf-8")

    def _fake_config(key, default=None):
        return {
            "LOGSEQ_DIR": str(tmp_path),
            "LOGSEQ_JOURNAL_DAYS": "30",
            "WORKSPACE_DIR": str(vault),
            "OBSIDIAN_PLANNER_FILE": "Planner.md",
        }.get(key, default)

    with patch("logseq_later_agent.get_config_value", side_effect=_fake_config):
        logseq_later_agent.run(write_to_obsidian=True, days=30)

    content = planner.read_text(encoding="utf-8")
    assert "## LogSeq LATER Tasks" in content
    assert "Deploy to production" in content
