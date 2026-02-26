import pytest
import os
from observer import parse_markdown_tasks

def test_parse_markdown_tasks_with_valid_tasks(tmp_path):
    # Setup temporary file
    d = tmp_path / "sub"
    d.mkdir()
    p = d / "test_note.md"
    p.write_text("""
# Test Daily Note
## Tasks
- [ ] Task 1
- [x] Task 2
- [ ] Task 3
## Today's Plan
""")
    
    tasks = parse_markdown_tasks(str(p))
    assert len(tasks) == 3
    # Check that it extracted the task descriptions correctly
    task_names = [t["task"] for t in tasks]
    assert "Task 1" in task_names
    assert "Task 2" in task_names
    assert "Task 3" in task_names

def test_parse_markdown_tasks_with_no_tasks_section(tmp_path):
    p = tmp_path / "empty_note.md"
    p.write_text("# Just a Title")
    
    tasks = parse_markdown_tasks(str(p))
    assert tasks == []

def test_parse_markdown_tasks_with_empty_tasks_section(tmp_path):
    p = tmp_path / "empty_tasks.md"
    p.write_text("""# Note
## Tasks
## Next Section""")
    
    tasks = parse_markdown_tasks(str(p))
    assert tasks == []
