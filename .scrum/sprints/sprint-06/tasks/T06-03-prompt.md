# T06-03 — NanoClaw: LogSeqAgent Containerised Skill

**Sprint**: 06 | **BLI**: BLI-038 | **Estimate**: M | **LLM Agent**: Codex
**Wave**: 2 — start after T06-02 is complete and merged
**Depends on**: T06-02 (NanoClaw ObsidianAgent Skill — base Dockerfile pattern and `nanoclaw/client.py` must exist)

---

## Context

This task follows exactly the same pattern established in T06-02 for ObsidianAgent. This time the subject is `logseq_agent.py` + `logseq_later_agent.py`, which operate on `LOGSEQ_DIR` (journals and pages directories).

The LogSeq Skill is simpler than the Obsidian Skill — it has three actions:
- `list-later` — scan journals + pages for `LATER` tasks, return JSON list
- `add-task` — append a new `LATER` task to today's journal
- `mark-done` — update a specific task line to `DONE`

Mounts `LOGSEQ_DIR` as read-only for `list-later`, and read/write for `add-task` and `mark-done`.

Key files to read before starting:
- `nanoclaw/skills/obsidian_skill/skill_runner.py` — this is your template, follow the same JSON-output pattern exactly
- `nanoclaw/client.py` — `run_skill()` already exists; you will call it with `skill_name="logseq_skill"`
- `logseq_agent.py` — `add_task(description)`, `mark_done(task_text)`, `get_tasks()`
- `logseq_later_agent.py` — `scan_later_tasks(days, logseq_dir)` returns list of `{task, file, line}` dicts
- `docker-compose.yml` — add `logseq_skill` service following the `obsidian_skill` pattern already there
- `config_utils.py` — `get_config_value("LOGSEQ_DIR", "")` for the volume path

---

## What to Do

### 1. `nanoclaw/skills/logseq_skill/skill.yaml`

```yaml
name: logseq_skill
version: "1.0"
description: "Sandboxed read/write access to the LogSeq vault"
actions:
  - list-later
  - add-task
  - mark-done
volumes:
  logseq:
    host_path: "${LOGSEQ_DIR}"
    container_path: /logseq
    mode: ro   # default; overridden to rw for add-task and mark-done
```

### 2. `nanoclaw/skills/logseq_skill/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY logseq_agent.py .
COPY logseq_later_agent.py .
COPY config_utils.py .
COPY skill_runner.py .

RUN pip install --no-cache-dir

ENV LOGSEQ_DIR=/logseq

ENTRYPOINT ["python", "skill_runner.py"]
```

### 3. `nanoclaw/skills/logseq_skill/skill_runner.py`

Parse `sys.argv[1]` as the action. All output is JSON to stdout. Follow the obsidian_skill pattern exactly.

```python
#!/usr/bin/env python3
"""
NanoClaw LogSeq Skill runner.
Usage: python skill_runner.py <action> [args...]
Output: JSON to stdout
"""
import sys
import json
import os
import datetime

os.environ["LOGSEQ_DIR"] = "/logseq"

from logseq_agent import LogSeqAgent
from logseq_later_agent import scan_later_tasks

agent = LogSeqAgent(logseq_dir="/logseq")

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "action required"}))
        sys.exit(1)

    action = sys.argv[1]
    args = sys.argv[2:]

    try:
        if action == "list-later":
            days = int(args[0]) if args else 7
            tasks = scan_later_tasks(days=days, logseq_dir="/logseq")
            print(json.dumps({"tasks": tasks}))
        elif action == "add-task":
            if not args:
                print(json.dumps({"error": "task description required"}))
                sys.exit(1)
            description = " ".join(args)
            agent.add_task(description)
            print(json.dumps({"status": "added", "task": description}))
        elif action == "mark-done":
            if not args:
                print(json.dumps({"error": "task text required"}))
                sys.exit(1)
            task_text = " ".join(args)
            agent.mark_done(task_text)
            print(json.dumps({"status": "marked-done", "task": task_text}))
        else:
            print(json.dumps({"error": f"unknown action: {action}"}))
            sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### 4. `docker-compose.yml` — Add logseq_skill service

Add alongside the existing `obsidian_skill` service (do not modify other services):

```yaml
  logseq_skill:
    build:
      context: ./nanoclaw/skills/logseq_skill
    volumes: []
    profiles:
      - nanoclaw
```

### 5. `tests/test_nanoclaw_logseq.py` — Write tests

```python
from unittest.mock import patch, MagicMock
import json
import pytest


# Test 1: list-later action returns JSON task list
def test_run_skill_list_later():
    tasks = [{"task": "LATER Write report", "file": "journals/2026_04_03.md", "line": 5}]
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"tasks": tasks})
    with patch("nanoclaw.client.subprocess.run", return_value=mock_result), \
         patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
         patch("nanoclaw.client.get_config_value", return_value="/fake/logseq"):
        from nanoclaw.client import run_skill
        result = run_skill("logseq_skill", "list-later", "7")
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["task"] == "LATER Write report"


# Test 2: add-task action with write=True passes correct Docker flags
def test_run_skill_add_task_uses_write_flag():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"status": "added", "task": "Review PR"})
    with patch("nanoclaw.client.subprocess.run", return_value=mock_result) as mock_run, \
         patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
         patch("nanoclaw.client.get_config_value", return_value="/fake/logseq"):
        from nanoclaw.client import run_skill
        run_skill("logseq_skill", "add-task", "Review PR", write=True)
        cmd = mock_run.call_args[0][0]
        # Volume must include :rw when write=True
        assert any(":rw" in arg for arg in cmd)


# Test 3: skill_runner list-later with journal fixture
def test_skill_runner_list_later(tmp_path):
    logseq = tmp_path / "logseq"
    journals = logseq / "journals"
    journals.mkdir(parents=True)
    today = journals / "2026_04_03.md"
    today.write_text("- LATER Write tests\n- DONE Old task\n")
    import sys, io
    with patch.dict("os.environ", {"LOGSEQ_DIR": str(logseq)}):
        import importlib
        import nanoclaw.skills.logseq_skill.skill_runner as runner
        importlib.reload(runner)
        captured = io.StringIO()
        with patch("sys.argv", ["skill_runner.py", "list-later", "1"]), \
             patch("sys.stdout", captured):
            try:
                runner.main()
            except SystemExit:
                pass
        output = json.loads(captured.getvalue())
        assert "tasks" in output


# Test 4: unknown action returns error JSON, exits 1
def test_skill_runner_unknown_action(tmp_path):
    import sys, io
    with patch.dict("os.environ", {"LOGSEQ_DIR": str(tmp_path)}):
        import nanoclaw.skills.logseq_skill.skill_runner as runner
        captured = io.StringIO()
        with patch("sys.argv", ["skill_runner.py", "bad-action"]), \
             patch("sys.stdout", captured):
            with pytest.raises(SystemExit):
                runner.main()
        output = json.loads(captured.getvalue())
        assert "error" in output
```

---

## Acceptance Criteria

- [ ] `nanoclaw/skills/logseq_skill/skill.yaml` — correct manifest with 3 actions
- [ ] `nanoclaw/skills/logseq_skill/Dockerfile` — builds from `python:3.11-slim`, copies only needed files
- [ ] `nanoclaw/skills/logseq_skill/skill_runner.py` — implements `list-later`, `add-task`, `mark-done` with JSON output
- [ ] `docker-compose.yml` — `logseq_skill` service present under `nanoclaw` profile
- [ ] `add-task` and `mark-done` actions are called with `write=True` from host code — never called with read-only mount
- [ ] `tests/test_nanoclaw_logseq.py` — all 4 tests pass (no real Docker calls)
- [ ] Full test suite still passes: `bash scripts/run_tests.sh`

---

## Notes

- Copy the JSON output contract exactly from `obsidian_skill/skill_runner.py` — all output must be a single JSON object on stdout
- The `scan_later_tasks()` function in `logseq_later_agent.py` takes `days` and `logseq_dir` as parameters — pass `/logseq` for the container path
- If `scan_later_tasks` doesn't currently accept `logseq_dir` as a parameter, add it with a default of `get_config_value("LOGSEQ_DIR", "")` — do not break the existing external call signature
- After finishing, run: `bash scripts/run_tests.sh` — all tests must pass before considering this task complete
