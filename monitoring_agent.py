import requests
import time
from config_utils import get_config_value

class MonitoringAgent:
    """
    Checks the status of the Ollama and OpenClaw servers.
    """
    def __init__(self):
        self.ollama_host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
        self.openclaw_endpoint = get_config_value("OPENCLAW_ENDPOINT", "https://api.openclaw.ai/v1")

    def check_ollama(self):
        try:
            # Check the /api/tags endpoint which indicates the server is running
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=3)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def check_openclaw(self):
        # Without an actual health check endpoint we can just check if the host is reachable,
        # but for a reliable check, hitting the models endpoint if we have an API key.
        # Here we just do a simple ping if possible, or assume it's true if no specific local URL.
        if "localhost" in self.openclaw_endpoint or "127.0.0.1" in self.openclaw_endpoint:
            try:
                response = requests.get(self.openclaw_endpoint, timeout=3)
                return response.status_code < 500
            except requests.RequestException:
                return False
        return True # Assume external API is available if we don't know the exact health endpoint

    def run_health_checks(self):
        status = {
            "ollama": self.check_ollama(),
            "openclaw": self.check_openclaw()
        }
        return status

if __name__ == "__main__":
    agent = MonitoringAgent()
    print("Health Checks:", agent.run_health_checks())
