# T06-02 — NanoClaw: ObsidianAgent Containerised Skill

**Sprint**: 06 | **BLI**: BLI-037 | **Estimate**: L | **LLM Agent**: Claude Code
**Wave**: 1 — run in parallel with T06-01 (zero file overlap)
**Depends on**: nothing — fully independent

---

## Context

`obsidian_agent.py` reads and writes markdown files directly on the host filesystem at `WORKSPACE_DIR`. A future bug or LLM-generated path could reach files outside the intended vault. This task wraps ObsidianAgent in a NanoClaw Skill — a Docker container that:
- Mounts only `WORKSPACE_DIR` as a volume
- Exposes a CLI interface (`nanoclaw run obsidian_skill <action> [args]`)
- Returns JSON to stdout, which the host Python code parses
- Cannot reach any host path outside the volume

The Python host retains a **direct-import fallback**: if `NANOCLAW_ENABLED=false` in `.config`, existing behaviour is unchanged. This task must not break anything for users without Docker.

Key files to read before starting:
- `obsidian_agent.py` — understand `read_file(path)`, `create_file(path, content, overwrite)`, `update_file(path, content)`, `list_files(directory)`, and `find_tasks()`. These become the Skill's action interface.
- `config_utils.py` — `get_config_value(key, default)` — how to read `WORKSPACE_DIR` and `NANOCLAW_ENABLED`
- `docker-compose.yml` — understand the existing n8n service structure before adding nanoclaw
- `cron_job.py` — this is where NanoClaw dispatch will eventually be wired (see T06-05, not this task)

---

## What to Do

### 1. `nanoclaw/skills/obsidian_skill/skill.yaml` — Skill manifest

```yaml
name: obsidian_skill
version: "1.0"
description: "Sandboxed read/write access to the Obsidian vault"
actions:
  - read_file
  - create_file
  - update_file
  - list_files
  - find_tasks
volumes:
  workspace:
    host_path: "${WORKSPACE_DIR}"
    container_path: /vault
    mode: ro  # default read-only; overridden to rw when --write flag passed
```

### 2. `nanoclaw/skills/obsidian_skill/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Only copy what the skill needs
COPY obsidian_agent.py .
COPY config_utils.py .
COPY skill_runner.py .

RUN pip install --no-cache-dir rich

ENV WORKSPACE_DIR=/vault

ENTRYPOINT ["python", "skill_runner.py"]
```

### 3. `nanoclaw/skills/obsidian_skill/skill_runner.py`

This is the container's entry point. It parses `sys.argv`, calls the appropriate `obsidian_agent.py` method, and prints JSON to stdout:

```python
#!/usr/bin/env python3
"""
NanoClaw Obsidian Skill runner.
Usage: python skill_runner.py <action> [args...]
Output: JSON to stdout
"""
import sys
import json
import os

# Vault is always mounted at /vault inside the container
os.environ["WORKSPACE_DIR"] = "/vault"

from obsidian_agent import ObsidianAgent

agent = ObsidianAgent()

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "action required"}))
        sys.exit(1)

    action = sys.argv[1]
    args = sys.argv[2:]

    try:
        if action == "read_file":
            result = agent.read_file(args[0])
            print(json.dumps({"content": result}))
        elif action == "create_file":
            path, content = args[0], args[1]
            overwrite = "--overwrite" in args
            agent.create_file(path, content, overwrite=overwrite)
            print(json.dumps({"status": "created", "path": path}))
        elif action == "update_file":
            agent.update_file(args[0], args[1])
            print(json.dumps({"status": "updated", "path": args[0]}))
        elif action == "list_files":
            directory = args[0] if args else ""
            files = agent.list_files(directory)
            print(json.dumps({"files": files}))
        elif action == "find_tasks":
            tasks = agent.find_tasks()
            print(json.dumps({"tasks": tasks}))
        else:
            print(json.dumps({"error": f"unknown action: {action}"}))
            sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### 4. `nanoclaw/skills/obsidian_skill/__init__.py`

Empty file — marks directory as a package.

### 5. `nanoclaw/__init__.py` and `nanoclaw/client.py` — Host-side NanoClaw client

`nanoclaw/client.py` is the host-side helper that dispatches to the container:

```python
"""
NanoClaw host client.
Calls a NanoClaw Skill via `docker compose run` and parses JSON output.
"""
import subprocess
import json
import os
from config_utils import get_config_value

NANOCLAW_ENABLED = get_config_value("NANOCLAW_ENABLED", "false").lower() == "true"


def run_skill(skill_name: str, action: str, *args, write: bool = False) -> dict:
    """
    Run a NanoClaw Skill action.
    Returns parsed JSON dict from the container's stdout.
    Raises RuntimeError if Docker is not available or the container exits non-zero.
    """
    if not NANOCLAW_ENABLED:
        raise RuntimeError("NanoClaw is disabled (NANOCLAW_ENABLED=false)")

    workspace_dir = get_config_value("WORKSPACE_DIR", "")
    mode = "rw" if write else "ro"

    cmd = [
        "docker", "compose", "run", "--rm",
        "--volume", f"{workspace_dir}:/vault:{mode}",
        skill_name,
        action,
        *[str(a) for a in args],
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"Skill {skill_name}/{action} failed: {result.stderr.strip()}")

    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Skill returned invalid JSON: {result.stdout!r}") from e
```

### 6. `docker-compose.yml` — Add nanoclaw service

Add to the existing `docker-compose.yml` services block (do not remove the n8n service):

```yaml
  obsidian_skill:
    build:
      context: ./nanoclaw/skills/obsidian_skill
    volumes: []  # volumes are passed at runtime via `docker compose run --volume`
    profiles:
      - nanoclaw  # only built when explicitly requested
```

### 7. `tests/test_nanoclaw_obsidian.py` — Write tests

```python
from unittest.mock import patch, MagicMock
import json
import pytest

# Test 1: run_skill returns parsed JSON when Docker succeeds
def test_run_skill_success():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"files": ["Planner.md", "Inbox.md"]})
    with patch("nanoclaw.client.subprocess.run", return_value=mock_result), \
         patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
         patch("nanoclaw.client.get_config_value", return_value="/fake/vault"):
        from nanoclaw.client import run_skill
        result = run_skill("obsidian_skill", "list_files")
        assert result["files"] == ["Planner.md", "Inbox.md"]

# Test 2: run_skill raises RuntimeError when NANOCLAW_ENABLED=false
def test_run_skill_disabled():
    with patch("nanoclaw.client.NANOCLAW_ENABLED", False):
        from nanoclaw.client import run_skill
        with pytest.raises(RuntimeError, match="disabled"):
            run_skill("obsidian_skill", "list_files")

# Test 3: run_skill raises RuntimeError when Docker exits non-zero
def test_run_skill_docker_failure():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "container error"
    with patch("nanoclaw.client.subprocess.run", return_value=mock_result), \
         patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
         patch("nanoclaw.client.get_config_value", return_value="/fake/vault"):
        from nanoclaw.client import run_skill
        with pytest.raises(RuntimeError, match="failed"):
            run_skill("obsidian_skill", "list_files")

# Test 4: skill_runner main() — read_file action returns JSON content
def test_skill_runner_read_file(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    test_file = vault / "Note.md"
    test_file.write_text("# Hello")
    import sys, io, importlib
    # Patch WORKSPACE_DIR so ObsidianAgent uses tmp_path
    with patch.dict("os.environ", {"WORKSPACE_DIR": str(vault)}):
        import nanoclaw.skills.obsidian_skill.skill_runner as runner
        captured = io.StringIO()
        with patch("sys.argv", ["skill_runner.py", "read_file", "Note.md"]), \
             patch("sys.stdout", captured):
            try:
                runner.main()
            except SystemExit:
                pass
        output = json.loads(captured.getvalue())
        assert "content" in output
```

---

## Acceptance Criteria

- [ ] `nanoclaw/skills/obsidian_skill/skill.yaml` exists with correct manifest
- [ ] `nanoclaw/skills/obsidian_skill/Dockerfile` exists
- [ ] `nanoclaw/skills/obsidian_skill/skill_runner.py` implements all 5 actions with JSON output
- [ ] `nanoclaw/client.py` — `run_skill()` dispatches via `docker compose run`
- [ ] `docker-compose.yml` has `obsidian_skill` service under `nanoclaw` profile
- [ ] When `NANOCLAW_ENABLED=false`, all existing code paths are unchanged (no regression)
- [ ] `tests/test_nanoclaw_obsidian.py` — all 4 tests pass (Docker mocked — no real container needed)
- [ ] Full test suite still passes: `bash scripts/run_tests.sh`
- [ ] `INSTALL.md` gains a "NanoClaw Setup" section: Docker prerequisite, `docker compose --profile nanoclaw build`, test command `docker compose run obsidian_skill list_files`

---

## Notes

- Do NOT call `docker compose build` in code — that is a one-time user setup step documented in INSTALL.md
- The `profiles: [nanoclaw]` setting means the skill image is NOT built during normal `docker compose up` — only when explicitly requested
- `write: bool = False` in `run_skill()` is the safety default — callers must explicitly pass `write=True` for any mutation action
- After finishing, run: `bash scripts/run_tests.sh` — all tests must pass before considering this task complete
