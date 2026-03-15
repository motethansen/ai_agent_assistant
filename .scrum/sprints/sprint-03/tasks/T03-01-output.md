Both changes applied. Here's the completion report:

---

## Completion Report — T03-01

### 1. Files Modified
- `main.py` — lines 801–807: replaced read-only routing display with interactive selector
- `config.template` — lines 59–63: updated routing comment and reordered keys (CHAT first)

### 2. Acceptance Criteria
- ✅ `/routing` shows current routing assignments for chat, scheduling, parsing
- ✅ `/routing` lists installed Ollama models by number
- ✅ User can select a task type and assign any installed model to it
- ✅ Selection written to `.config` via `_update_config_key`, effective immediately
- ✅ If no Ollama models found, prints a clear warning via `render_warning`
- ✅ `config.template` routing comments updated with model name examples

### 3. Issues / Deviations
None. The existing `list_ollama_models()`, `_update_config_key()`, and `get_config_value()` functions were all already in place and required no changes.