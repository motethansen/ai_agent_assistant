# T06-01 — LM Studio Local Inference Integration

**Sprint**: 06 | **BLI**: BLI-036 | **Estimate**: M | **LLM Agent**: Claude Code
**Wave**: 1 — run in parallel with T06-02 (zero file overlap)
**Depends on**: nothing — fully independent

---

## Context

The project already supports Ollama (primary), Gemini, OpenAI, and Claude as LLM providers, all routed through `ai_orchestration.py`. LM Studio exposes an OpenAI-compatible REST API on `localhost:1234/v1`, so no new SDK is needed — the `openai` package already installed handles it.

The fallback chain currently is: `ollama → gemini → openai → claude`
After this task it becomes: `ollama → lmstudio → gemini → openai → claude`

LM Studio is opt-in via `ENABLE_LM_STUDIO=true` in `.config`. When disabled, the chain is unchanged.

Key files to read before starting:
- `ai_orchestration.py` — understand `MODELS_ENABLED`, `get_routing()`, `generate()`, `generate_with()`, the fallback chain, and the existing OpenAI provider block (LM Studio reuses the same call pattern)
- `update_manager.py` — understand `run_all_checks()` and the pattern used by `check_gemini()` and `check_google_calendar()` to add a new check
- `config_utils.py` — `get_config_value(key, default)` — how config is read
- `config.example` — where to add the new keys with comments
- `INSTALL.md` — where to add the LM Studio setup section

---

## What to Do

### 1. `ai_orchestration.py` — Add LM Studio provider

Add to `MODELS_ENABLED`:
```python
"lmstudio": get_config_value("ENABLE_LM_STUDIO", "false").lower() == "true",
```

Add a `_call_lmstudio(prompt, system, model)` internal function. Use the `openai` SDK pointing at `http://localhost:1234/v1`:
```python
from openai import OpenAI as _OpenAI

def _call_lmstudio(prompt, system=None, model=None):
    model = model or get_config_value("LM_STUDIO_MODEL", "local-model")
    # Health check first — fail fast if server is not running
    try:
        import requests as _req
        _req.get("http://localhost:1234/v1/models", timeout=2).raise_for_status()
    except Exception:
        raise RuntimeError("LM Studio server not reachable at localhost:1234")
    client = _OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(model=model, messages=messages)
    return resp.choices[0].message.content, model
```

In `generate_with(provider, prompt, system)`, add an `elif provider == "lmstudio":` branch that calls `_call_lmstudio()`.

In the fallback chain (wherever `generate()` iterates providers), insert `lmstudio` between `ollama` and `gemini`. The health check inside `_call_lmstudio` causes it to raise and fall through to the next provider automatically.

### 2. `update_manager.py` — Add `check_lm_studio()`

Follow the exact pattern used by `check_gemini()`. Add:
```python
def check_lm_studio():
    enabled = get_config_value("ENABLE_LM_STUDIO", "false").lower() == "true"
    if not enabled:
        return {"name": "LM Studio", "status": "disabled", "detail": "ENABLE_LM_STUDIO=false"}
    model = get_config_value("LM_STUDIO_MODEL", "(not set)")
    try:
        import requests
        r = requests.get("http://localhost:1234/v1/models", timeout=3)
        r.raise_for_status()
        models = [m["id"] for m in r.json().get("data", [])]
        detail = f"active model: {model} | available: {', '.join(models) or 'none'}"
        return {"name": "LM Studio", "status": "ok", "detail": detail}
    except Exception as e:
        return {"name": "LM Studio", "status": "error", "detail": str(e)}
```

Add `check_lm_studio()` to `run_all_checks()` — include its result in the returned list.

### 3. `config.example` — Add new keys

Add a commented-out section near the Ollama block:
```
# LM Studio (optional local inference — OpenAI-compatible API)
# ENABLE_LM_STUDIO=false
# LM_STUDIO_MODEL=your-model-name-here
```

### 4. `INSTALL.md` — Add LM Studio setup section

Add under a new "LM Studio" heading:
- Download LM Studio from lmstudio.ai
- Load a model via the LM Studio GUI
- Enable the local server: Server tab → Start Server (listens on port 1234 by default)
- Set `ENABLE_LM_STUDIO=true` and `LM_STUDIO_MODEL=<model-name>` in `.config`
- The model name must exactly match what LM Studio shows in the server tab
- Run `python scripts/status.py` to verify the LM Studio row shows green

### 5. `tests/test_lm_studio.py` — Write tests

Create `tests/test_lm_studio.py` with:

```python
from unittest.mock import patch, MagicMock
import pytest

# Test 1: _call_lmstudio returns text when server is reachable
def test_call_lmstudio_success():
    with patch("requests.get") as mock_get, \
         patch("openai.OpenAI") as mock_client:
        mock_get.return_value.raise_for_status = lambda: None
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "LM Studio response"
        mock_client.return_value.chat.completions.create.return_value = mock_resp
        import ai_orchestration
        text, model = ai_orchestration._call_lmstudio("hello", model="test-model")
        assert text == "LM Studio response"

# Test 2: _call_lmstudio raises RuntimeError when server is not reachable
def test_call_lmstudio_unreachable():
    with patch("requests.get", side_effect=Exception("connection refused")):
        import ai_orchestration
        with pytest.raises(RuntimeError, match="not reachable"):
            ai_orchestration._call_lmstudio("hello")

# Test 3: check_lm_studio returns disabled when ENABLE_LM_STUDIO=false
def test_check_lm_studio_disabled():
    with patch("update_manager.get_config_value", return_value="false"):
        import update_manager
        result = update_manager.check_lm_studio()
        assert result["status"] == "disabled"

# Test 4: check_lm_studio returns error when server unreachable but enabled
def test_check_lm_studio_error():
    def fake_config(key, default=None):
        if key == "ENABLE_LM_STUDIO": return "true"
        return default
    with patch("update_manager.get_config_value", side_effect=fake_config), \
         patch("requests.get", side_effect=Exception("refused")):
        import update_manager
        result = update_manager.check_lm_studio()
        assert result["status"] == "error"
```

---

## Acceptance Criteria

- [ ] `MODELS_ENABLED` in `ai_orchestration.py` includes `"lmstudio"` key
- [ ] `_call_lmstudio()` function exists, uses `openai` SDK at `localhost:1234/v1`, runs health check before calling
- [ ] `generate_with("lmstudio", ...)` works without raising when server is mocked
- [ ] LM Studio appears between ollama and gemini in the fallback chain
- [ ] `update_manager.check_lm_studio()` exists and is called in `run_all_checks()`
- [ ] `python scripts/status.py` shows a LM Studio row (disabled or ok/error depending on config)
- [ ] `config.example` updated with commented `ENABLE_LM_STUDIO` and `LM_STUDIO_MODEL`
- [ ] `INSTALL.md` has a "LM Studio" setup section
- [ ] `tests/test_lm_studio.py` — all 4 tests pass
- [ ] Full test suite still passes: `bash scripts/run_tests.sh`

---

## Notes

- Do NOT change any existing provider logic — LM Studio is purely additive
- The `openai` SDK is already in `requirements.txt` — no new dependency needed
- `api_key="lm-studio"` is a dummy value; LM Studio ignores the API key but the SDK requires it
- If `ENABLE_LM_STUDIO=false`, `check_lm_studio()` must return `status: "disabled"` — do NOT attempt a network call
- After finishing, run: `bash scripts/run_tests.sh` — all tests must pass before considering this task complete
