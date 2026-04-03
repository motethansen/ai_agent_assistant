import pytest
from unittest.mock import patch, MagicMock
import requests


def test_call_lmstudio_success():
    """_call_lmstudio returns response text when server is reachable."""
    mock_health = MagicMock()
    mock_health.status_code = 200

    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "Hello from LM Studio"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_completion

    mock_openai_module = MagicMock()
    mock_openai_module.OpenAI.return_value = mock_client

    import sys
    with patch("ai_orchestration.requests.get", return_value=mock_health), \
         patch("ai_orchestration.get_config_value", return_value="test-model"), \
         patch.dict(sys.modules, {"openai": mock_openai_module}):
        import ai_orchestration
        text, model_name = ai_orchestration._call_lmstudio("Say hello", system="Be brief")

    assert text == "Hello from LM Studio"
    assert "lmstudio" in model_name


def test_call_lmstudio_unreachable():
    """_call_lmstudio raises RuntimeError with 'not reachable' when server is down."""
    with patch("ai_orchestration.requests.get", side_effect=requests.exceptions.ConnectionError):
        import ai_orchestration
        with pytest.raises(RuntimeError, match="not reachable"):
            ai_orchestration._call_lmstudio("Hello")


def test_check_lm_studio_disabled():
    """check_lm_studio returns disabled status without making any network call."""
    with patch("update_manager.get_config_value", return_value="false"):
        import update_manager
        result = update_manager.check_lm_studio()

    assert result["status"] == "disabled"
    assert "ENABLE_LM_STUDIO=false" in result["message"]


def test_check_lm_studio_error():
    """check_lm_studio returns error status when server is unreachable."""
    def cfg_side_effect(key, default):
        if key == "ENABLE_LM_STUDIO":
            return "true"
        return default

    with patch("update_manager.get_config_value", side_effect=cfg_side_effect), \
         patch("update_manager.requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
        import update_manager
        result = update_manager.check_lm_studio()

    assert result["status"] == "error"
    assert "not reachable" in result["message"].lower() or "refused" in result["message"].lower()
