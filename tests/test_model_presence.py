import os
import subprocess
import pytest
import requests

def test_ollama_presence():
    """
    Checks if Ollama is installed and running.
    Optional: skip if not in a local environment.
    """
    try:
        # Check if ollama command is available
        subprocess.check_output(["ollama", "--version"], stderr=subprocess.STDOUT)

        # Check if the Ollama server is responding
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code != 200:
            pytest.skip("Ollama server is not running.")
    except (subprocess.CalledProcessError, FileNotFoundError, requests.exceptions.RequestException):
        pytest.skip("Ollama is not installed or not running.")

def test_config_model_flags():
    """
    Verify that model activation flags are correctly defined in config.template.
    """
    template_path = "config.template"
    assert os.path.exists(template_path)

    with open(template_path, "r") as f:
        content = f.read()
    assert "ENABLE_GEMINI=false" in content
    assert "ENABLE_OLLAMA=true" in content
    assert "ENABLE_OPENCLAW=true" in content

def test_available_models_list():
    """
    Check if we can list models (requires valid GEMINI_API_KEY in .env).
    Skips if key is missing.
    """
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key or "your_" in api_key:
        pytest.skip("No valid GEMINI_API_KEY found for model listing test.")

    try:
        import google.genai as genai
        client = genai.Client(api_key=api_key)
        models = list(client.models.list())
        assert len(models) > 0
    except Exception as e:
        pytest.fail(f"Failed to list models with Gemini API: {e}")
