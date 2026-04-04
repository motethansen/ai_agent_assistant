import sys
import pytest
from unittest.mock import patch, MagicMock


def test_call_lmstudio_success():
    """_call_lmstudio returns response text when SDK call succeeds."""
    mock_lms = MagicMock()
    mock_model = MagicMock()
    mock_lms.llm.return_value = mock_model
    mock_model.respond.return_value = "Hello from LM Studio"

    with patch.dict(sys.modules, {"lmstudio": mock_lms}), \
         patch("ai_orchestration.get_config_value", return_value="test-model"):
        import ai_orchestration
        text, model_name = ai_orchestration._call_lmstudio("Say hello", system="Be brief")

    assert text == "Hello from LM Studio"
    assert model_name == "lmstudio/test-model"
    # system message should have been prepended
    call_args = mock_model.respond.call_args[0][0]
    assert call_args[0] == {"role": "system", "content": "Be brief"}
    assert call_args[1] == {"role": "user", "content": "Say hello"}


def test_call_lmstudio_no_system():
    """_call_lmstudio omits system message when none provided."""
    mock_lms = MagicMock()
    mock_model = MagicMock()
    mock_lms.llm.return_value = mock_model
    mock_model.respond.return_value = "response"

    with patch.dict(sys.modules, {"lmstudio": mock_lms}), \
         patch("ai_orchestration.get_config_value", return_value="my-model"):
        import ai_orchestration
        text, model_name = ai_orchestration._call_lmstudio("Hello")

    call_args = mock_model.respond.call_args[0][0]
    assert call_args == [{"role": "user", "content": "Hello"}]
    assert model_name == "lmstudio/my-model"


def test_call_lmstudio_sdk_error_returns_tuple():
    """_call_lmstudio returns error tuple (no raise) when SDK raises."""
    mock_lms = MagicMock()
    mock_lms.llm.side_effect = Exception("connection refused")

    with patch.dict(sys.modules, {"lmstudio": mock_lms}), \
         patch("ai_orchestration.get_config_value", return_value=""):
        import ai_orchestration
        text, model_name = ai_orchestration._call_lmstudio("Hello")

    assert text.startswith("LLM error:")
    assert model_name == "lmstudio/unknown"


def test_is_lmstudio_running_true():
    """is_lmstudio_running returns True when SDK call succeeds."""
    mock_lms = MagicMock()
    mock_lms.list_downloaded_models.return_value = []

    with patch.dict(sys.modules, {"lmstudio": mock_lms}):
        import ai_orchestration
        result = ai_orchestration.is_lmstudio_running()

    assert result is True


def test_is_lmstudio_running_false():
    """is_lmstudio_running returns False when SDK raises a connection error."""
    mock_lms = MagicMock()
    mock_lms.list_downloaded_models.side_effect = Exception("could not connect")

    with patch.dict(sys.modules, {"lmstudio": mock_lms}):
        import ai_orchestration
        result = ai_orchestration.is_lmstudio_running()

    assert result is False


def test_check_lm_studio_disabled():
    """check_lm_studio returns disabled status without making any network call."""
    with patch("update_manager.get_config_value", return_value="false"):
        import update_manager
        result = update_manager.check_lm_studio()

    assert result["status"] == "disabled"
    assert "ENABLE_LM_STUDIO=false" in result["message"]


def test_check_lm_studio_error():
    """check_lm_studio returns error status when server is unreachable."""
    import requests

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
