import os
import subprocess
import json
import datetime
import requests
from config_utils import get_config_value

def check_git_updates():
    """Checks if there are updates available in the git repository."""
    if not os.path.exists(".git"):
        return {"status": "error", "message": "Not a git repository"}
    
    try:
        subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=10)
        local_hash = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        remote_hash = subprocess.check_output(["git", "rev-parse", "@{u}"]).decode().strip()
        
        if local_hash != remote_hash:
            return {"status": "update_available", "message": "New updates available"}
        else:
            return {"status": "up_to_date", "message": "System is up to date"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def check_ollama_health():
    """Checks if Ollama server is reachable."""
    host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
    try:
        response = requests.get(f"{host}/api/tags", timeout=3)
        if response.status_code == 200:
            return {"status": "ok", "message": "Ollama is running"}
        else:
            return {"status": "error", "message": f"Ollama returned {response.status_code}"}
    except Exception:
        return {"status": "error", "message": "Ollama is not reachable"}

def check_venv_health():
    """Checks if the virtual environment is healthy (basic check)."""
    if not os.path.exists(".venv"):
        return {"status": "error", "message": ".venv missing"}
    return {"status": "ok", "message": "Environment looks good"}

def run_all_checks():
    status = {
        "last_check": datetime.datetime.now().isoformat(),
        "git": check_git_updates(),
        "ollama": check_ollama_health(),
        "venv": check_venv_health(),
    }
    
    os.makedirs("logs", exist_ok=True)
    with open("logs/system_status.json", "w") as f:
        json.dump(status, f, indent=4)
    
    return status

if __name__ == "__main__":
    print(json.dumps(run_all_checks(), indent=4))
