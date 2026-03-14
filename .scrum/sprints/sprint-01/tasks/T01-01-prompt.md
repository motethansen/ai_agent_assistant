# Dev Agent Task Prompt — T01-01

> Self-contained — you have no other context. Read everything here carefully before acting.

---

## Identity & Role

You are a senior software developer working on **AI Agent Assistant** — a personal CLI agent that uses local LLMs (Ollama) to manage tasks from LogSeq and Obsidian and interact with Google Calendar.

You are removing all traces of **OpenClaw** from the peripheral files of the project. A follow-up task (T01-02) will handle the core files. Your scope is: tests, scripts, agent files, and the optional UI files.

Do not modify `ai_orchestration.py` or `main.py` — those are handled in T01-02.

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| Local LLM | Ollama via langchain-ollama |
| Task sources | LogSeq (markdown files), Obsidian (markdown files) |
| Calendar | Google Calendar API via calendar_manager.py |
| CLI UI | Rich library |
| Web UI | Streamlit (app.py) — optional |
| Tests | pytest |

---

## Repository Structure (relevant parts)

```
ai_agent_assistant/
├── monitoring_agent.py
├── chat_ui.py
├── app.py
├── test_openclaw_direct.py        ← DELETE this file
├── OPENCLAW_SETUP.md              ← DELETE this file
├── scripts/
│   ├── check_ai_working.py
│   └── manage_services.sh
└── tests/
    ├── test_monitoring_agent.py
    └── test_routing_logic.py
```

---

## Relevant Existing Code

### monitoring_agent.py
```python
import requests
import time
import subprocess
import os
from config_utils import get_config_value

class MonitoringAgent:
    """
    Checks the status of the Ollama and OpenClaw servers and ensures they are running.
    """
    def __init__(self):
        self.ollama_host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
        self.openclaw_endpoint = get_config_value("OPENCLAW_ENDPOINT", "http://localhost:18789/v1")
        self.manage_script = "scripts/manage_services.sh"

    def ensure_services(self):
        """Checks and starts services if stopped."""
        if not self.check_ollama() or not self.check_openclaw():
            print("🔍 MonitoringAgent: Some services are down. Attempting to start...")
            if os.path.exists(self.manage_script):
                subprocess.run(["bash", self.manage_script, "start"], capture_output=True)
                time.sleep(5)

    def check_ollama(self):
        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=3)
            return response.status_code == 200
        except Exception:
            return False

    def check_openclaw(self):
        if "localhost" in self.openclaw_endpoint or "127.0.0.1" in self.openclaw_endpoint:
            try:
                response = requests.get(f"{self.openclaw_endpoint.replace('/v1', '')}/health", timeout=3)
                if response.status_code == 200:
                    return True
                response = requests.get(f"{self.openclaw_endpoint}/models", timeout=3)
                return response.status_code in [200, 401]
            except Exception:
                return False
        return True

    def run_health_checks(self):
        self.ensure_services()
        status = {
            "ollama": self.check_ollama(),
            "openclaw": self.check_openclaw()
        }
        return status
```

---

## Your Task

**Task ID**: T01-01
**Title**: Remove OpenClaw from tests, scripts, and agent files
**Sprint**: Sprint-01
**Backlog item**: BLI-001

### Description

Remove all OpenClaw references from the following files. Do not touch `ai_orchestration.py` or `main.py`.

### Files to delete entirely
- `test_openclaw_direct.py`
- `OPENCLAW_SETUP.md`

### Files to modify

**`monitoring_agent.py`**
- Remove `self.openclaw_endpoint` from `__init__`
- Remove `check_openclaw()` method entirely
- Update `ensure_services()` to only check Ollama
- Update `run_health_checks()` to return only `{"ollama": ...}`
- Update the class docstring

**`tests/test_monitoring_agent.py`**
- Remove all test cases that reference `check_openclaw` or `openclaw`
- Keep Ollama-related tests intact

**`tests/test_routing_logic.py`**
- Remove all test cases that reference OpenClaw routing or the `openclaw` key
- Keep all other routing tests intact

**`scripts/check_ai_working.py`**
- Remove OpenClaw health check section
- Keep Ollama check intact

**`scripts/manage_services.sh`**
- Remove OpenClaw service start/stop/status commands
- Keep Ollama commands intact

**`chat_ui.py`**
- Remove the OpenClaw row from the service status table (search for "openclaw" in the file)

**`app.py`**
- Remove any OpenClaw status display or reference

### Acceptance Criteria
- [ ] `test_openclaw_direct.py` deleted
- [ ] `OPENCLAW_SETUP.md` deleted
- [ ] `monitoring_agent.py` has no OpenClaw references; `run_health_checks()` returns `{"ollama": bool}`
- [ ] `tests/test_monitoring_agent.py` — no OpenClaw test cases
- [ ] `tests/test_routing_logic.py` — no OpenClaw routing tests
- [ ] `scripts/check_ai_working.py` — no OpenClaw section
- [ ] `scripts/manage_services.sh` — no OpenClaw commands
- [ ] `chat_ui.py` — no OpenClaw status row
- [ ] `app.py` — no OpenClaw references
- [ ] `pytest tests/` passes with no OpenClaw-related failures

### Out of Scope
- Do NOT touch `ai_orchestration.py` — that is T01-02
- Do NOT touch `main.py` — that is T01-02
- Do NOT touch `config.template` — that is T01-02
- Do NOT change any Ollama logic

---

## Output Format

### 1. Summary
[2-3 sentences: what you changed and anything notable]

### 2. New / Modified Files

#### `monitoring_agent.py` [MODIFIED]
```python
[complete file content]
```

#### `tests/test_monitoring_agent.py` [MODIFIED]
```python
[complete file content]
```

#### `tests/test_routing_logic.py` [MODIFIED]
```python
[complete file content]
```

#### `scripts/check_ai_working.py` [MODIFIED]
```python
[complete file content]
```

#### `scripts/manage_services.sh` [MODIFIED]
```bash
[complete file content]
```

#### `chat_ui.py` [MODIFIED — show only the changed section with 5 lines context each side]

#### `app.py` [MODIFIED — show only the changed section with 5 lines context each side]

### 3. Files Deleted
- `test_openclaw_direct.py`
- `OPENCLAW_SETUP.md`

### 4. Integration Notes
[Anything T01-02 needs to know]

### 5. Known Limitations
[Anything not done or assumptions made]
