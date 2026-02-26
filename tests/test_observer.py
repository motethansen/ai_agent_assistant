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
    assert tasks[0] == "Task 1"
    assert tasks[1] == "Task 2"
    assert tasks[2] == "Task 3"

def test_parse_markdown_tasks_with_no_tasks_section(tmp_path):
    p = tmp_path / "empty_note.md"
    p.write_text("# Just a Title")
    
    tasks = parse_markdown_tasks(str(p))
    assert tasks == []

def test_parse_markdown_tasks_with_empty_tasks_section(tmp_path):
    p = tmp_path / "empty_tasks.md"
    p.write_text("# Note
## Tasks
## Next Section")
    
    tasks = parse_markdown_tasks(str(p))
    assert tasks == []
