import pytest
from unittest.mock import patch, MagicMock
import ai_orchestration

@patch('ai_orchestration.get_config_value')
@patch('ai_orchestration.is_ollama_running')
def test_get_routing_ollama_preference(mock_ollama_running, mock_get_config):
    # Setup: User wants ollama for chat, and it is running
    def side_effect(key, default):
        if key == "ROUTING_CHAT": return "ollama"
        if key == "ENABLE_OLLAMA": return "true"
        return default
    
    mock_get_config.side_effect = side_effect
    mock_ollama_running.return_value = True
    
    # Reload MODELS_ENABLED to simulate config change
    ai_orchestration.MODELS_ENABLED["ollama"] = True
    
    route = ai_orchestration.get_routing("chat")
    assert route == "ollama"

@patch('ai_orchestration.get_config_value')
@patch('ai_orchestration.is_ollama_running')
def test_get_routing_fallback_to_gemini(mock_ollama_running, mock_get_config):
    # Setup: User wants ollama, but it's NOT running. Gemini is enabled.
    def side_effect(key, default):
        if key == "ROUTING_CHAT": return "ollama"
        if key == "ENABLE_GEMINI": return "true"
        if key == "ENABLE_OLLAMA": return "true"
        if key == "ENABLE_OPENCLAW": return "false"
        return default
    
    mock_get_config.side_effect = side_effect
    mock_ollama_running.return_value = False
    
    # Mock global api_key check
    with patch('ai_orchestration.api_key', 'valid_key'):
        ai_orchestration.MODELS_ENABLED["gemini"] = True
        ai_orchestration.MODELS_ENABLED["ollama"] = True
        ai_orchestration.MODELS_ENABLED["openclaw"] = False
        
        route = ai_orchestration.get_routing("chat")
        assert route == "gemini"

@patch('ai_orchestration.get_config_value')
@patch('ai_orchestration.is_ollama_running')
def test_get_routing_openclaw_preference(mock_ollama_running, mock_get_config):
    # Setup: User wants openclaw for scheduling
    def side_effect(key, default):
        if key == "ROUTING_SCHEDULING": return "openclaw"
        if key == "ENABLE_OPENCLAW": return "true"
        return default
    
    mock_get_config.side_effect = side_effect
    ai_orchestration.MODELS_ENABLED["openclaw"] = True
    
    route = ai_orchestration.get_routing("scheduling")
    assert route == "openclaw"
