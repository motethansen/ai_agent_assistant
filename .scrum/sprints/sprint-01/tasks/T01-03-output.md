It seems file write permissions need approval. Let me present all the changes clearly so you can review them, then approve:

---

## Summary

Here are all changes for T01-03:

---

### 1. `ai_orchestration.py` — Add `list_ollama_models()` after `is_ollama_running()` (line 94)

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

Also update `get_llm()` — add a warning before the `ChatOllama` instantiation when Ollama isn't running:

```python
def get_llm(model_type="chat", query=""):
    """Returns a LangChain LLM instance based on routing. Also returns the model name used."""
    model_name = get_routing(model_type, query)

    if model_name == "ollama":
        if not is_ollama_running():
            print("⚠️  Ollama is not running. Start it with: ollama serve")
            print("    Falling back to next available LLM.")
            # Re-route skipping ollama
            priority_str = get_config_value("LLM_PRIORITY", "ollama,gemini,openai,claude")
            for m in [x.strip().lower() for x in priority_str.split(",")]:
                if m != "ollama" and _is_model_available(m):
                    model_name = m
                    break
            else:
                # Nothing available — proceed with ollama anyway (will fail gracefully)
                pass
```

---

### 2. `main.py` — Startup display in `handle_chat_mode()` (after line 461, after banner/history load)

```python
    chat_ui.print_banner()
    history = chat_ui.load_history()

    # Show Ollama status at startup
    if ai_orchestration.is_ollama_running():
        models = ai_orchestration.list_ollama_models()
        if models:
            print(f"✅ Ollama models available: {', '.join(models)}")
        else:
            print("⚠️  No Ollama models found. Run: ollama pull llama3")
    else:
        print("⚠️  Ollama is not running. Start it with: ollama serve")
```

### 3. `main.py` — Replace `/models` command (lines 576–581)

**Before:**
```python
elif command == "models":
    models_status = {}
    for m, enabled in ai_orchestration.MODELS_ENABLED.items():
        available = ai_orchestration._is_model_available(m)
        models_status[m] = {"enabled": enabled, "available": available}
    chat_ui.render_models(models_status)
```

**After:**
```python
elif command == "models":
    ollama_models = ai_orchestration.list_ollama_models()
    if not ollama_models:
        chat_ui.render_warning("No Ollama models found. Run: ollama pull llama3")
    else:
        current = get_config_value("OLLAMA_MODEL", "llama3")
        print("\n--- Installed Ollama Models ---")
        for i, m in enumerate(ollama_models, 1):
            marker = " (active)" if m == current or m.split(":")[0] == current else ""
            print(f"  {i}. {m}{marker}")
        try:
            choice = input("\nSelect a model number (or press Enter to keep current): ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = ""
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(ollama_models):
                selected = ollama_models[idx]
                config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".config")
                _update_config_key(config_path, "OLLAMA_MODEL", selected)
                chat_ui.render_success(f"Switched to {selected}. Effective immediately.")
            else:
                chat_ui.render_warning("Invalid selection.")
        else:
            chat_ui.render_info(f"Keeping current model: {current}")
```

---

Please approve the file writes and I'll apply all three changes. Or if you'd like to adjust anything first, let me know.