# T06-05 — CLI Router: Lightweight Delegation Layer

**Sprint**: 06 | **BLI**: BLI-040 | **Estimate**: L | **LLM Agent**: Claude Code
**Wave**: 3 — run in parallel with T06-04 (zero file overlap)
**Depends on**: T06-02 + T06-03 (NanoClaw Skills must exist), T06-01 (LM Studio added to chain)

---

## Context

Currently `main.py` and `cli_commands.py` call agent functions directly (e.g. `obsidian_agent.find_tasks()`, `logseq_later_agent.run()`). This means the Python host has tight coupling to the agent implementations and cannot delegate to containerised Skills.

This task introduces a routing layer in `ai_orchestration.py` with two functions:
- `route(task_type, prompt, **kwargs)` — decides whether to dispatch to a NanoClaw Skill or the existing LLM chain
- `send_to_n8n(flow_type, payload)` — wraps `n8n_client.trigger()` with a standard envelope

Then updates `cli_commands.py` so that commands which trigger data flows (`/sync-logseq`, `/sync-universal`, `/plan`) call `send_to_n8n()` instead of direct agent functions — but **only when the relevant feature flags are enabled**.

The critical invariant: **when `NANOCLAW_ENABLED=false` and n8n is not running, all existing commands must behave exactly as before**. This is a progressive enhancement, not a replacement.

Key files to read before starting:
- `ai_orchestration.py` — understand the full file; `route()` and `send_to_n8n()` go here
- `cli_commands.py` — find the command dispatch section; identify which commands call agents directly
- `nanoclaw/client.py` (T06-02) — `run_skill(skill_name, action, *args, write=False)` — what `route()` will call
- `n8n_client.py` — `trigger(path, payload)`, `is_n8n_running()` — what `send_to_n8n()` wraps
- `config_utils.py` — `get_config_value("NANOCLAW_ENABLED", "false")`
- All existing tests — run `bash scripts/run_tests.sh` first to confirm baseline before making any changes

---

## What to Do

### 1. `ai_orchestration.py` — Add `route()` function

Add near the bottom of the file, after the existing `generate()` and `generate_with()` functions:

```python
def route(task_type: str, prompt: str = None, action: str = None, args: list = None, **kwargs):
    """
    Route a task to either a NanoClaw Skill or the local LLM chain.

    For file-IO task types ("obsidian", "logseq"), dispatches to the appropriate
    NanoClaw Skill when NANOCLAW_ENABLED=true. Falls back to direct LLM routing otherwise.

    For all other task types, routes through the existing LLM chain (generate()).

    task_type: "obsidian" | "logseq" | "chat" | "scheduling" | "parsing" | ...
    prompt: LLM prompt (used for non-container task types)
    action: Skill action name (used for obsidian/logseq task types)
    args: positional args to pass to the Skill action
    write: passed to run_skill() — set True for any mutation action

    Returns:
      - For Skill dispatch: parsed JSON dict from the container
      - For LLM dispatch: (response_text, model_name) tuple
    """
    nanoclaw_enabled = get_config_value("NANOCLAW_ENABLED", "false").lower() == "true"
    args = args or []
    write = kwargs.get("write", False)

    if nanoclaw_enabled and task_type in ("obsidian", "logseq"):
        try:
            from nanoclaw.client import run_skill
            skill_name = f"{task_type}_skill"
            return run_skill(skill_name, action, *args, write=write)
        except RuntimeError as e:
            import logging
            logging.getLogger(__name__).warning(
                "NanoClaw dispatch failed (%s), falling back to direct call: %s", task_type, e
            )
            # Fall through to direct LLM routing

    # Default: existing LLM chain
    if prompt:
        return generate(prompt, task_type=task_type)
    return None
```

### 2. `ai_orchestration.py` — Add `send_to_n8n()` function

Add immediately after `route()`:

```python
def send_to_n8n(flow_type: str, payload: dict) -> bool:
    """
    Send a data-flow event to n8n with a standard envelope.

    flow_type: identifies the n8n workflow to trigger (e.g. "task-sync", "morning-plan")
    payload: arbitrary dict — merged into the standard envelope

    Returns True if n8n accepted the payload. False if n8n is down (never raises).
    """
    from n8n_client import trigger, is_n8n_running
    import datetime

    if not is_n8n_running():
        import logging
        logging.getLogger(__name__).warning(
            "send_to_n8n: n8n not reachable — flow '%s' not sent", flow_type
        )
        return False

    envelope = {
        "flow_type": flow_type,
        "sent_at": datetime.datetime.now().isoformat(),
        **payload,
    }
    return trigger(flow_type, envelope)
```

### 3. `cli_commands.py` — Update `/sync-logseq` to optionally use `send_to_n8n()`

Find the function that handles the `/sync-logseq` command (likely `sync_logseq_to_obsidian()`). Add an n8n notification after the sync completes — do NOT replace the existing sync logic, just add the notification:

```python
# At the end of sync_logseq_to_obsidian(), after the sync loop:
from ai_orchestration import send_to_n8n
send_to_n8n("logseq-synced", {
    "tasks_synced": len(new_tasks),
    "source": "logseq",
    "target": "obsidian",
})
```

This is fire-and-forget — if n8n is down, the sync still completes, the n8n call just returns False silently.

### 4. `cli_commands.py` — Update `/plan` to optionally use `send_to_n8n()`

Find `handle_morning_planning()` or `handle_planning_session()`. After the planning session is complete, add:

```python
from ai_orchestration import send_to_n8n
send_to_n8n("morning-plan", {
    "tasks_scheduled": len(confirmed_tasks),
    "plan_date": str(datetime.date.today()),
})
```

Again, fire-and-forget — do not change the existing planning flow.

### 5. `tests/test_router.py` — Write tests

```python
from unittest.mock import patch, MagicMock
import pytest


# Test 1: route() dispatches to NanoClaw when NANOCLAW_ENABLED=true and task_type="obsidian"
def test_route_dispatches_to_nanoclaw():
    mock_result = {"files": ["Planner.md"]}
    with patch("ai_orchestration.get_config_value", return_value="true"), \
         patch("nanoclaw.client.run_skill", return_value=mock_result) as mock_skill, \
         patch("nanoclaw.client.NANOCLAW_ENABLED", True):
        import ai_orchestration
        result = ai_orchestration.route("obsidian", action="list_files")
        mock_skill.assert_called_once_with("obsidian_skill", "list_files", write=False)
        assert result == mock_result


# Test 2: route() falls back to LLM when NANOCLAW_ENABLED=false
def test_route_falls_back_to_llm():
    with patch("ai_orchestration.get_config_value", return_value="false"), \
         patch("ai_orchestration.generate", return_value=("response text", "ollama")) as mock_gen:
        import ai_orchestration
        result = ai_orchestration.route("chat", prompt="Hello?")
        mock_gen.assert_called_once()
        assert result == ("response text", "ollama")


# Test 3: route() falls back to LLM when NanoClaw raises RuntimeError
def test_route_falls_back_on_nanoclaw_failure():
    with patch("ai_orchestration.get_config_value", return_value="true"), \
         patch("nanoclaw.client.run_skill", side_effect=RuntimeError("Docker not running")), \
         patch("nanoclaw.client.NANOCLAW_ENABLED", True), \
         patch("ai_orchestration.generate", return_value=("fallback", "ollama")) as mock_gen:
        import ai_orchestration
        result = ai_orchestration.route("obsidian", action="list_files", prompt="list files")
        mock_gen.assert_called_once()


# Test 4: send_to_n8n() returns False and does not raise when n8n is down
def test_send_to_n8n_n8n_down():
    with patch("ai_orchestration.is_n8n_running", return_value=False):
        import ai_orchestration
        result = ai_orchestration.send_to_n8n("logseq-synced", {"tasks_synced": 3})
        assert result is False


# Test 5: send_to_n8n() includes flow_type and sent_at in envelope
def test_send_to_n8n_envelope_shape():
    with patch("ai_orchestration.is_n8n_running", return_value=True), \
         patch("ai_orchestration.trigger") as mock_trigger:
        mock_trigger.return_value = True
        import ai_orchestration
        ai_orchestration.send_to_n8n("morning-plan", {"tasks_scheduled": 2})
        call_payload = mock_trigger.call_args[0][1]
        assert call_payload["flow_type"] == "morning-plan"
        assert "sent_at" in call_payload
        assert call_payload["tasks_scheduled"] == 2


# Test 6: existing CLI commands unchanged when both flags disabled
def test_sync_logseq_still_works_without_nanoclaw():
    """Regression: /sync-logseq must complete even when n8n is down and NanoClaw disabled."""
    with patch("cli_commands.is_n8n_running", return_value=False), \
         patch("ai_orchestration.get_config_value", return_value="false"), \
         patch("cli_commands.logseq_agent") as mock_logseq, \
         patch("cli_commands.obsidian_agent") as mock_obsidian:
        mock_logseq.get_tasks.return_value = []
        mock_obsidian.read_file.return_value = ""
        from cli_commands import sync_logseq_to_obsidian
        # Must not raise — sync completes regardless of n8n/NanoClaw state
        sync_logseq_to_obsidian()
```

---

## Acceptance Criteria

- [ ] `ai_orchestration.route()` exists — dispatches to NanoClaw when `NANOCLAW_ENABLED=true` and `task_type in ("obsidian", "logseq")`
- [ ] `ai_orchestration.route()` falls back to `generate()` when NanoClaw disabled or raises
- [ ] `ai_orchestration.send_to_n8n()` exists — wraps `n8n_client.trigger()` with standard envelope, returns False silently when n8n is down
- [ ] `/sync-logseq` sends `send_to_n8n("logseq-synced", ...)` after sync (fire-and-forget)
- [ ] `/plan` sends `send_to_n8n("morning-plan", ...)` after planning session (fire-and-forget)
- [ ] ALL existing CLI commands work identically when `NANOCLAW_ENABLED=false` and n8n is unreachable — zero regression
- [ ] `tests/test_router.py` — all 6 tests pass
- [ ] Full test suite still passes: `bash scripts/run_tests.sh`
- [ ] `decisions.md` — ADR-011 (architecture diagram) added showing Router → NanoClaw / n8n split (ASCII diagram is fine)

---

## Notes

- `send_to_n8n()` must import `trigger` and `is_n8n_running` from `n8n_client` inside the function body — do not add a top-level import that would break when n8n is not installed
- The `route()` fallback chain must log a warning via `logging.getLogger(__name__).warning()` — not print directly — so tests can suppress it
- Do NOT remove any existing direct agent calls from `cli_commands.py` — the n8n calls are additions, not replacements
- Run the full test suite BEFORE making any changes to confirm the baseline: `bash scripts/run_tests.sh`. Then run again after each file you modify to catch regressions immediately
- After finishing, run: `bash scripts/run_tests.sh` — all tests must pass before considering this task complete
