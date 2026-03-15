# Dev Agent Task Prompt — T03-01

> **ACTION REQUIRED: You are a Claude Code agent with file-editing tools (Read, Edit, Write, Bash).**
> **READ the actual source files in the project, then APPLY all changes directly to disk using your tools.**
> **Do NOT output code as text blocks. Write changes to the actual files.**
> **Project root: /home/michaelhansen/Projects/github/ai_agent_assistant**

> Self-contained — no dependencies. Can run in parallel with T03-02 and T03-03.

---

## Identity & Role

You are a senior software developer on **AI Agent Assistant** — a personal CLI agent using local Ollama LLMs.

You are extending the `/routing` command from a read-only display into an interactive selector that lets the user pick which installed Ollama model handles chat, scheduling, and parsing tasks.

---

## Relevant Existing Code

### ai_orchestration.py — routing functions

```python
def list_ollama_models():
    """Returns list of installed model names from `ollama list`, e.g. ['llama3:latest', 'qwen2.5:14b']"""

def get_routing(task_type="chat", query="") -> str:
    """Reads ROUTING_{task_type} from config, falls back through LLM_PRIORITY. Returns model name."""
```

### main.py — existing /routing handler (around line 801)

```python
elif command == "routing":
    routing_info = {}
    for task_type in ["chat", "scheduling", "parsing"]:
        config_val = get_config_value(f"ROUTING_{task_type.upper()}", "auto")
        active = ai_orchestration.get_routing(task_type)
        routing_info[task_type] = {"config": config_val, "active": active}
    chat_ui.render_routing(routing_info)
    # Currently read-only — no way to change from here
```

### main.py — _update_config_key helper (line 23)

```python
def _update_config_key(config_path, key, value):
    """Updates or appends KEY=value in the .config file."""
```

### config.template — current routing section

```
ROUTING_SCHEDULING=ollama
ROUTING_PARSING=ollama
ROUTING_CHAT=ollama
```

---

## Your Task

**Task ID**: T03-01
**Title**: Per-task Ollama model routing via `/routing` command
**Sprint**: Sprint-03
**Backlog item**: BLI-020

### Changes to make

**`main.py`** — replace the existing `/routing` handler with an interactive version:

```python
elif command == "routing":
    ollama_models = ai_orchestration.list_ollama_models()
    if not ollama_models:
        chat_ui.render_warning("No Ollama models found. Run: ollama pull <model>")
    else:
        task_types = ["chat", "scheduling", "parsing"]
        print("\n--- Current Routing ---")
        for i, tt in enumerate(task_types, 1):
            current = get_config_value(f"ROUTING_{tt.upper()}", "ollama")
            print(f"  {i}. {tt:<12} → {current}")
        print("\n--- Installed Ollama Models ---")
        for j, m in enumerate(ollama_models, 1):
            print(f"  {j}. {m}")
        try:
            route_choice = input("\nChange routing for which task type? (1=chat 2=scheduling 3=parsing, Enter=skip): ").strip()
            if route_choice.isdigit() and 1 <= int(route_choice) <= 3:
                tt = task_types[int(route_choice) - 1]
                model_choice = input(f"Select model number for {tt}: ").strip()
                if model_choice.isdigit() and 1 <= int(model_choice) <= len(ollama_models):
                    selected = ollama_models[int(model_choice) - 1]
                    _update_config_key(config_path, f"ROUTING_{tt.upper()}", selected)
                    chat_ui.render_success(f"Routing for {tt} → {selected}. Effective immediately.")
                else:
                    chat_ui.render_warning("Invalid model selection.")
        except (EOFError, KeyboardInterrupt):
            pass
```

**`config.template`** — update routing comments to show model name examples:

```
# --- Model Routing ---
# Accepts: ollama model name (e.g. llama3:latest, qwen2.5:14b, mistral:latest) or auto
ROUTING_CHAT=ollama
ROUTING_SCHEDULING=ollama
ROUTING_PARSING=ollama
```

### Acceptance Criteria
- [ ] `/routing` shows current routing assignments for chat, scheduling, parsing
- [ ] `/routing` lists installed Ollama models by number
- [ ] User can select a task type and assign any installed model to it
- [ ] Selection is written to `.config` via `_update_config_key` and takes effect immediately
- [ ] If no Ollama models found, prints a clear warning
- [ ] `config.template` routing comments updated with model name examples

---

## Completion Report

### 1. Files modified
### 2. Acceptance criteria check (✅/❌ per item)
### 3. Any issues or deviations
