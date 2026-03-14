import requests
import time
import subprocess
import os
from config_utils import get_config_value

class MonitoringAgent:
    """
    Checks the status of the Ollama server and ensures it is running.
    """
    def __init__(self):
        self.ollama_host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
        self.manage_script = "scripts/manage_services.sh"

    def ensure_services(self):
        """Checks and starts services if stopped."""
        if not self.check_ollama():
            print("🔍 MonitoringAgent: Ollama is down. Attempting to start...")
            if os.path.exists(self.manage_script):
                subprocess.run(["bash", self.manage_script, "start"], capture_output=True)
                time.sleep(5)

    def check_ollama(self):
        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=3)
            return response.status_code == 200
        except Exception:
            return False

    def run_health_checks(self):
        self.ensure_services()
        status = {
            "ollama": self.check_ollama(),
        }
        return status

if __name__ == "__main__":
    agent = MonitoringAgent()
    print("Health Checks:", agent.run_health_checks())
