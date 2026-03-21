"""
n8n webhook client.

Sends event payloads to n8n workflow webhook triggers.
Each workflow in n8n is identified by a path slug configured on the Webhook node.

Usage:
    from n8n_client import trigger

    trigger("task-completed", {"task": "Review wireframes", "status": "done"})
    trigger("schedule-ready", {"schedule": [...]})
    trigger("gmail-digest",   {"emails": [...]})
"""
import json
import logging
import requests
from config_utils import get_config_value

logger = logging.getLogger(__name__)

N8N_BASE = get_config_value("N8N_WEBHOOK_URL", "http://localhost:5678/webhook")


def trigger(path: str, payload: dict, timeout: int = 10) -> bool:
    """
    POST payload to n8n webhook at {N8N_BASE}/{path}.

    Returns True on success, False on any error (never raises).
    """
    url = f"{N8N_BASE}/{path}"
    try:
        resp = requests.post(
            url,
            json=payload,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        logger.debug("n8n webhook %s -> %s", path, resp.status_code)
        return True
    except requests.exceptions.ConnectionError:
        logger.warning("n8n not reachable at %s (is Docker running?)", url)
    except requests.exceptions.HTTPError as e:
        logger.warning("n8n webhook %s returned error: %s", path, e)
    except Exception as e:
        logger.warning("n8n trigger failed (%s): %s", path, e)
    return False


def is_n8n_running() -> bool:
    """Quick health check — returns True if n8n is up."""
    base = get_config_value("N8N_WEBHOOK_URL", "http://localhost:5678/webhook")
    health_url = base.replace("/webhook", "/healthz")
    try:
        return requests.get(health_url, timeout=3).status_code == 200
    except Exception:
        return False
