import os
import subprocess
import pytest
import requests

def test_ollama_presence():
    """
    Checks if Ollama is installed and running.
    """
    try:
        # Check if ollama command is available
        subprocess.check_output(["ollama", "--version"], stderr=subprocess.STDOUT)
        
        # Check if the Ollama server is responding
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        assert response.status_code == 200
        print("✅ Ollama is installed and running.")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.fail("❌ Ollama command not found. Please install Ollama.")
    except requests.exceptions.RequestException:
        pytest.fail("❌ Ollama server is not running on http://localhost:11434.")

def test_openclaw_presence():
    """
    Checks if OpenClaw is installed in the current environment.
    """
    try:
        import openclaw
        print("✅ OpenClaw module is installed.")
    except ImportError:
        pytest.fail("❌ OpenClaw module not found. Run 'pip install openclaw'.")

def test_config_model_flags():
    """
    Verify that model activation flags are correctly defined in config.template.
    """
    template_path = "config.template"
    assert os.path.exists(template_path)
    
    with open(template_path, "r") as f:
        content = f.read()
        assert "ENABLE_GEMINI=true" in content
        assert "ENABLE_OLLAMA=true" in content
        assert "ENABLE_OPENCLAW=true" in content
