import pytest
from unittest.mock import patch, MagicMock
import ai_orchestration


def test_route_dispatches_to_nanoclaw():
    """route() calls run_skill when NANOCLAW_ENABLED=true and task_type is 'obsidian'."""
    mock_run_skill = MagicMock(return_value={"files": ["Planner.md"]})

    with patch("ai_orchestration.get_config_value", return_value="true"), \
         patch("nanoclaw.client.run_skill", mock_run_skill):
        result = ai_orchestration.route("obsidian", action="list_files")

    mock_run_skill.assert_called_once_with("obsidian_skill", "list_files", write=False)
    assert result == {"files": ["Planner.md"]}


def test_route_falls_back_when_disabled():
    """route() calls generate() when NANOCLAW_ENABLED=false."""
    mock_generate = MagicMock(return_value=("text", "ollama"))

    def cfg(key, default):
        if key == "NANOCLAW_ENABLED":
            return "false"
        return default

    with patch("ai_orchestration.get_config_value", side_effect=cfg), \
         patch("ai_orchestration.generate", mock_generate):
        ai_orchestration.route("obsidian", prompt="list files")

    mock_generate.assert_called_once()


def test_route_falls_back_on_nanoclaw_error():
    """route() falls back to generate() silently when run_skill raises RuntimeError."""
    mock_generate = MagicMock(return_value=("fallback", "ollama"))

    with patch("ai_orchestration.get_config_value", return_value="true"), \
         patch("nanoclaw.client.run_skill", side_effect=RuntimeError("Docker not running")), \
         patch("ai_orchestration.generate", mock_generate):
        result = ai_orchestration.route("obsidian", action="x", prompt="x")

    mock_generate.assert_called_once()


def test_route_non_container_type_uses_llm():
    """route() skips NanoClaw entirely for non-obsidian/logseq task types."""
    mock_generate = MagicMock(return_value=("Hello back", "ollama"))
    mock_run_skill = MagicMock()

    with patch("ai_orchestration.get_config_value", return_value="true"), \
         patch("nanoclaw.client.run_skill", mock_run_skill), \
         patch("ai_orchestration.generate", mock_generate):
        ai_orchestration.route("chat", prompt="Hello")

    mock_run_skill.assert_not_called()
    mock_generate.assert_called_once()


def test_send_to_n8n_returns_false_when_down():
    """send_to_n8n() returns False without raising when n8n is not reachable."""
    mock_is_running = MagicMock(return_value=False)
    mock_trigger = MagicMock()

    with patch("n8n_client.is_n8n_running", mock_is_running), \
         patch("n8n_client.trigger", mock_trigger):
        result = ai_orchestration.send_to_n8n("logseq-synced", {})

    assert result is False
    mock_trigger.assert_not_called()


def test_send_to_n8n_envelope_includes_flow_type():
    """send_to_n8n() passes a correct envelope with flow_type and sent_at to trigger()."""
    mock_trigger = MagicMock(return_value=True)
    mock_is_running = MagicMock(return_value=True)

    with patch("n8n_client.is_n8n_running", mock_is_running), \
         patch("n8n_client.trigger", mock_trigger):
        result = ai_orchestration.send_to_n8n("morning-plan", {"x": 1})

    assert result is True
    call_args = mock_trigger.call_args
    path_arg, payload_arg = call_args[0]
    assert path_arg == "morning-plan"
    assert payload_arg["flow_type"] == "morning-plan"
    assert "sent_at" in payload_arg
