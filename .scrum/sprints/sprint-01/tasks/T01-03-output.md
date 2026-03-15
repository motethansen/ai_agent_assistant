All changes look correct. Here's the completion report:

---

## Completion Report

### 1. Files Modified

- **`ai_orchestration.py`** — added `list_ollama_models()` and updated `get_llm()` Ollama block
- **`main.py`** — added startup Ollama check in `handle_chat_mode()` and replaced `/models` command handler

### 2. Acceptance Criteria Check

- ✅ `list_ollama_models()` added to `ai_orchestration.py` — runs `ollama list`, skips header, returns list of name strings
- ✅ Startup prints available Ollama models (or warning if none found) — added at top of `handle_chat_mode()` after banner
- ✅ If Ollama is not running, startup prints clear message and continues — both startup block and `get_llm()` handle this gracefully
- ✅ `/models` command works in CLI chat loop — shows numbered list with current model marked, prompts for selection
- ✅ Selected model is written to config via `_update_config_key()` and used in subsequent LLM calls (reads `OLLAMA_MODEL` via `get_config_value`)
- ✅ `ROUTING_SCHEDULING`, `ROUTING_PARSING`, `ROUTING_CHAT` all default to `ollama` in `config.template` — already correct, no change needed

### 3. Issues or Deviations

None. The `config.template` already had the correct routing defaults from a prior task, so no changes were needed there. The `get_llm()` fallback logic restructures the `if model_name == "ollama"` block into a nested check so that if Ollama is down, it re-routes to the next available LLM in priority order before falling through to the existing `elif` branches.