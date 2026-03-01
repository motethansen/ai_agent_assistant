import pytest
from unittest.mock import patch, MagicMock
from monitoring_agent import MonitoringAgent

def test_monitoring_agent_init():
    agent = MonitoringAgent()
    assert hasattr(agent, 'ollama_host')
    assert hasattr(agent, 'openclaw_endpoint')

@patch('requests.get')
def test_check_ollama_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    
    agent = MonitoringAgent()
    assert agent.check_ollama() is True

@patch('requests.get')
def test_check_ollama_failure(mock_get):
    mock_get.side_effect = Exception("Connection refused")
    
    agent = MonitoringAgent()
    assert agent.check_ollama() is False

@patch('requests.get')
def test_run_health_checks(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    
    agent = MonitoringAgent()
    status = agent.run_health_checks()
    assert "ollama" in status
    assert "openclaw" in status
    assert status["ollama"] is True
