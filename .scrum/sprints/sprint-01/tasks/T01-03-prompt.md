# Dev Agent Task Prompt — T01-03

> **ACTION REQUIRED: You are a Claude Code agent with file-editing tools (Read, Edit, Write, Bash).**
> **READ the actual source files in the project, then APPLY all changes directly to disk using your tools.**
> **Do NOT output code as text blocks. Write changes to the actual files.**
> **Project root: /home/michaelhansen/Projects/github/ai_agent_assistant**
>
> Self-contained — you have no other context. Read everything here carefully before acting.
> PREREQUISITE: T01-02 must be complete (ai_orchestration.py already has no OpenClaw).

---

## Identity & Role

You are a senior software developer working on **AI Agent Assistant** — a personal CLI agent that uses local LLMs (Ollama) to manage tasks from LogSeq and Obsidian and interact with Google Calendar.

You are making Ollama the **primary and default** local LLM, adding model discovery from `ollama list`, and ensuring a clean startup experience when Ollama is available.

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| Primary LLM | Ollama (`langchain-ollama`, `ChatOllama`) |
| Fallback LLMs | Gemini, OpenAI, Claude (all disabled by default) |
| Config | `.env` file via `config_utils.get_config_value()` |
| CLI display | `rich` library |

---

## Relevant Existing Code

### ai_orchestration.py — key sections (after T01-02 cleanup)

```python
# MODELS_ENABLED — ollama is the only one true by default
MODELS_ENABLED = {
    "gemini": get_config_value("ENABLE_GEMINI", "false").lower() == "true",
    "openai": get_config_value("ENABLE_OPENAI", "false").lower() == "true",
    "claude": get_config_value("ENABLE_CLAUDE", "false").lower() == "true",
    "ollama": get_config_value("ENABLE_OLLAMA", "true").lower() == "true",
}

def is_ollama_running():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False

def get_routing(task_type="chat", query=""):
    explicit = get_config_value(f"ROUTING_{task_type.upper()}", None)
    if explicit:
        explicit = explicit.strip().lower()
        if _is_model_available(explicit):
            return explicit
    # fallback through priority list
    priority_str = get_config_value("LLM_PRIORITY", "ollama,gemini,openai,claude")
    for model in [m.strip().lower() for m in priority_str.split(",")]:
        if _is_model_available(model):
            return model
    return "ollama"

def get_llm(model_type="chat", query=""):
    model_name = get_routing(model_type, query)
    if model_name == "ollama":
        model = get_config_value("OLLAMA_MODEL", "llama3")
        host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
        ctx_size = int(get_config_value("OLLAMA_NUM_CTX", "8192"))
        return ChatOllama(model=model, base_url=host, num_ctx=ctx_size, temperature=0), f"ollama/{model}"
    ...
```

### config.template — Ollama section (current state after T01-02)

```
# --- Ollama Settings ---
OLLAMA_MODEL=llama3
OLLAMA_HOST=http://localhost:11434
OLLAMA_NUM_CTX=8192

ENABLE_OLLAMA=true
ENABLE_GEMINI=false
ENABLE_OPENAI=false
ENABLE_CLAUDE=false

ROUTING_SCHEDULING=ollama
ROUTING_PARSING=ollama
ROUTING_CHAT=ollama

LLM_PRIORITY=ollama,gemini,openai,claude
```

### main.py — startup block (relevant area, around lines 590-610)

```python
# Current startup check area
ollama_up = ai_orchestration.is_ollama_running()
# ... existing startup logic ...
```

---

## Your Task

**Task ID**: T01-03
**Title**: Refactor ai_orchestration.py to Ollama-first routing with model discovery
**Sprint**: Sprint-01
**Backlog item**: BLI-002 + BLI-003

### Description

Make the system Ollama-centric:
1. Add a `list_ollama_models()` function that calls `ollama list` and returns installed model names
2. At startup (in `main.py`), query and display available Ollama models
3. Ensure routing always prefers Ollama; print a clear warning if Ollama is not running
4. Add a `/models` command in `main.py`'s chat loop that shows installed Ollama models and lets the user select one, updating `OLLAMA_MODEL` in the session config

### Changes to make

**`ai_orchestration.py`** — add:

```python
def list_ollama_models():
    """Query Ollama for installed models. Returns list of model name strings."""
    import subprocess
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().splitlines()
        # Skip header line "NAME   ID   SIZE   MODIFIED"
        models = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])  # e.g. "llama3:latest", "mistral:latest"
        return models
    except Exception:
        return []
```

Also update the startup warning in `get_llm()` — if Ollama is selected but not running, print a clear message:
```
⚠️  Ollama is not running. Start it with: ollama serve
    Falling back to next available LLM.
```

**`main.py`** — at startup, after the existing service checks, add:

```python
models = ai_orchestration.list_ollama_models()
if models:
    print(f"✅ Ollama models available: {', '.join(models)}")
else:
    print("⚠️  No Ollama models found. Run: ollama pull llama3")
```

**`main.py`** — add `/models` command to the chat command handler:

When user types `/models`:
1. Call `ai_orchestration.list_ollama_models()`
2. Print numbered list of installed models
3. Prompt: "Select a model number (or press Enter to keep current):"
4. If user selects a number, update `OLLAMA_MODEL` via `_update_config_key(config_path, "OLLAMA_MODEL", selected_model)`
5. Print confirmation: "✅ Switched to [model]. Effective immediately."

### Acceptance Criteria
- [ ] `list_ollama_models()` added to `ai_orchestration.py`, returns list of strings
- [ ] Startup prints available Ollama models (or a warning if none found)
- [ ] If Ollama is not running, startup prints clear message and gracefully continues
- [ ] `/models` command works in the CLI chat loop — shows list and allows selection
- [ ] Selected model is written to config and used in subsequent LLM calls
- [ ] `ROUTING_SCHEDULING`, `ROUTING_PARSING`, `ROUTING_CHAT` all default to `ollama` in config.template

### Out of Scope
- Do NOT change the fallback logic for Gemini/OpenAI/Claude
- Do NOT build a model download UI — just list what is installed
- Do NOT change the `/settings` command structure

---

## Completion Report

After applying all changes to the actual files, write a brief report covering:

### 1. Files modified
List each file you edited/created.

### 2. Acceptance criteria check
Go through each AC item and confirm ✅ or ❌ with a one-line note.

### 3. Any issues or deviations
Note anything you couldn't apply and why.
