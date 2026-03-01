import pytest
import os
from observer import parse_markdown_tasks, parse_logseq_tasks, update_markdown_plan

def test_parse_markdown_tasks_with_valid_tasks(tmp_path):
    # Setup temporary file
    p = tmp_path / "test_note.md"
    p.write_text("""
# Test Daily Note
## Tasks
- [ ] Task 1
- [x] Task 2
- [ ] #dev Task 3 ^2026-03-01
## Today's Plan
""")
    
    tasks = parse_markdown_tasks(str(p))
    assert len(tasks) == 3
    assert tasks[2]["category"] == "dev"
    assert tasks[2]["due_date"] == "2026-03-01"

def test_parse_logseq_later_tasks(tmp_path):
    p = tmp_path / "journal.md"
    p.write_text("""
- LATER Important task
- DONE Finished task
- LATER #personal Buy milk
""")
    
    tasks = parse_logseq_tasks(str(p))
    assert len(tasks) == 2
    assert tasks[0]["task"] == "Important task"
    assert tasks[1]["category"] == "personal"

def test_update_markdown_plan(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text("""
# My Day
## Tasks
- [ ] Task A
## Today's Plan
- **08:00 - 09:00**: Old Plan
""")
    
    new_schedule = [
        {"task": "New Task", "start": "2026-03-01T10:00:00", "end": "2026-03-01T11:00:00"}
    ]
    
    update_markdown_plan(str(p), new_schedule)
    
    content = p.read_text()
    assert "## Today's Plan" in content
    assert "10:00 - 11:00" in content
    assert "New Task" in content
    assert "Old Plan" not in content

def test_update_markdown_plan_append(tmp_path):
    # Test that it creates the section if missing
    p = tmp_path / "no_plan.md"
    p.write_text("# My Day")
    
    new_schedule = [
        {"task": "Appended Task", "start": "2026-03-01T10:00:00", "end": "2026-03-01T11:00:00"}
    ]
    
    update_markdown_plan(str(p), new_schedule)
    
    content = p.read_text()
    assert "## Today's Plan" in content
    assert "Appended Task" in content
