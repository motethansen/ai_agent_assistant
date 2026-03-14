# Dev Agent Task Prompt — T01-02

> Self-contained — you have no other context. Read everything here carefully before acting.
> PREREQUISITE: T01-01 must be complete before running this task.

---

## Identity & Role

You are a senior software developer working on **AI Agent Assistant** — a personal CLI agent that uses local LLMs (Ollama) to manage tasks from LogSeq and Obsidian and interact with Google Calendar.

You are removing all OpenClaw references from the **core files**: `ai_orchestration.py`, `main.py`, `config.template`, and the documentation files. T01-01 already cleaned the peripheral files (tests, scripts, agents, UI).

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| Local LLM | Ollama via langchain-ollama |
| Cloud LLM fallbacks | Gemini, OpenAI, Claude (optional, disabled by default) |
| Config | `.env` file read via `config_utils.get_config_value()` |

---

## Relevant Existing Code

### ai_orchestration.py (full file — 534 lines)

Key OpenClaw sections to remove:

```python
# MODELS_ENABLED — remove "openclaw" key (line 45)
MODELS_ENABLED = {
    ...
    "openclaw": get_config_value("ENABLE_OPENCLAW", "true").lower() == "true"  # REMOVE
}

# REMOVE these entire functions (lines 97-166):
def is_openclaw_running(): ...
def ensure_openclaw(): ...

# _is_model_available — remove openclaw branch (lines 203-208):
if model == "openclaw":
    ...

# get_routing — remove openclaw from complexity routing (lines 234-244):
for model in ["ollama", "openclaw", "gemini"]:   # remove "openclaw"
for model in ["openclaw", "openai", ...]:          # remove "openclaw", reorder

# get_llm — remove openclaw branch (lines 261-270):
elif model_name == "openclaw":
    ...

# REMOVE entire function (lines 515-527):
def openclaw_generate(prompt, model=None): ...
```

### main.py (relevant OpenClaw sections)

```python
# REMOVE entire function (lines 42-58):
def _update_openclaw_api_key(provider, api_key): ...

# REMOVE at startup (around lines 594-599):
openclaw_up = ai_orchestration.is_openclaw_running()
...
if ai_orchestration.ensure_openclaw():
    ...

# REMOVE from /settings handler (around line 777):
elif key in ("OPENCLAW_MODEL", "OPENCLAW_ENDPOINT", "OPENCLAW_API_KEY"):
    _update_openclaw_api_key(...)
```

### config.template (OpenClaw section to remove)

```
# --- OpenClaw Settings ---
OPENCLAW_API_KEY=your_openclaw_api_key_here
OPENCLAW_ENDPOINT=http://localhost:18789/v1
OPENCLAW_MODEL=openai/gpt-4o-mini

...
ENABLE_OPENCLAW=true

ROUTING_SCHEDULING=openclaw
ROUTING_CHAT=openclaw

LLM_PRIORITY=openclaw,ollama,gemini
```

---

## Your Task

**Task ID**: T01-02
**Title**: Remove OpenClaw from core: ai_orchestration.py, main.py, config
**Sprint**: Sprint-01
**Backlog item**: BLI-001

### Description

Strip all OpenClaw from the 3 core files and update documentation. After this task, OpenClaw must not exist anywhere in the codebase.

### Files to modify

**`ai_orchestration.py`**:
- Remove `"openclaw"` from `MODELS_ENABLED`
- Delete `is_openclaw_running()` entirely
- Delete `ensure_openclaw()` entirely
- Remove `openclaw` branch from `_is_model_available()`
- Remove `"openclaw"` from all model lists in `get_routing()`
- Update fallback priority default: `"LLM_PRIORITY", "ollama,gemini,openai,claude"`
- Remove `openclaw` branch from `get_llm()`
- Delete `openclaw_generate()` entirely

**`main.py`**:
- Delete `_update_openclaw_api_key()` entirely
- Remove `openclaw_up` startup check and any `ensure_openclaw()` call
- Remove OpenClaw keys from `/settings` handler

**`config.template`**:
- Remove the entire `# --- OpenClaw Settings ---` section
- Change `ENABLE_OPENCLAW=true` → remove it entirely
- Change `ROUTING_SCHEDULING=openclaw` → `ROUTING_SCHEDULING=ollama`
- Change `ROUTING_CHAT=openclaw` → `ROUTING_CHAT=ollama`
- Change `LLM_PRIORITY=openclaw,ollama,gemini` → `LLM_PRIORITY=ollama,gemini,openai,claude`

**`README.md`**, **`INSTALL.md`**, **`PLAN.md`**:
- Remove all mentions of OpenClaw, openclaw CLI, OpenClaw setup, OpenClaw gateway
- Update the LLM priority and routing sections to reflect the new defaults

### Acceptance Criteria
- [ ] `ai_orchestration.py` has zero references to `openclaw`
- [ ] `main.py` has zero references to `openclaw`
- [ ] `config.template` has zero references to `openclaw`
- [ ] `README.md`, `INSTALL.md`, `PLAN.md` have zero references to openclaw
- [ ] `python main.py` starts cleanly (no import errors, no startup crashes)
- [ ] LLM routing still works — `get_routing()` returns `"ollama"` when Ollama is running

### Out of Scope
- Do NOT change any Ollama logic or other LLM provider logic
- Do NOT refactor or reorganize `main.py` beyond OpenClaw removal
- T01-03 will handle the positive Ollama-first improvements

---

## Output Format

### 1. Summary

### 2. New / Modified Files

#### `ai_orchestration.py` [MODIFIED]
```python
[complete file content]
```

#### `main.py` [MODIFIED — show only changed sections with 5 lines context each side]

#### `config.template` [MODIFIED]
```
[complete file content]
```

#### `README.md` [MODIFIED — show only changed sections]

#### `INSTALL.md` [MODIFIED — show only changed sections]

### 3. Dependencies Added
None

### 4. Integration Notes
[Anything T01-03 needs to know about the cleaned ai_orchestration.py]

### 5. Known Limitations
