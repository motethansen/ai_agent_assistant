import requests
import time
import subprocess
import os
from config_utils import get_config_value

class MonitoringAgent:
    """
    Checks the status of the Ollama and OpenClaw servers and ensures they are running.
    """
    def __init__(self):
        self.ollama_host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
        self.openclaw_endpoint = get_config_value("OPENCLAW_ENDPOINT", "http://localhost:18789/v1")
        self.manage_script = "scripts/manage_services.sh"

    def ensure_services(self):
        """Checks and starts services if stopped."""
        if not self.check_ollama() or not self.check_openclaw():
            print("🔍 MonitoringAgent: Some services are down. Attempting to start...")
            if os.path.exists(self.manage_script):
                subprocess.run(["bash", self.manage_script, "start"], capture_output=True)
                # Wait a bit for startup
                time.sleep(5)

    def check_ollama(self):
        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=3)
            return response.status_code == 200
        except Exception:
            return False

    def check_openclaw(self):
        if "localhost" in self.openclaw_endpoint or "127.0.0.1" in self.openclaw_endpoint:
            try:
                # Standard OpenAI-compatible health check/ping
                response = requests.get(f"{self.openclaw_endpoint.replace('/v1', '')}/health", timeout=3)
                if response.status_code == 200:
                    return True
                
                # Fallback to models list
                response = requests.get(f"{self.openclaw_endpoint}/models", timeout=3)
                return response.status_code in [200, 401]
            except Exception:
                return False
        return True

    def run_health_checks(self):
        self.ensure_services()
        status = {
            "ollama": self.check_ollama(),
            "openclaw": self.check_openclaw()
        }
        return status

if __name__ == "__main__":
    agent = MonitoringAgent()
    print("Health Checks:", agent.run_health_checks())
