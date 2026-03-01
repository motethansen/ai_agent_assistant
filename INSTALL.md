# Installation Guide

This project requires setting up a few local and cloud components to function as an AI agent assistant.

## Prerequisites

- Python 3.10+
- Google Cloud Project with Calendar API enabled.
- `credentials.json` (OAuth Client ID) from Google Cloud Console.
- [Ollama](https://ollama.com/) installed locally.
- [OpenClaw](https://openclaw.ai/) for enhanced agentic capabilities.

## Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd ai_agent_assistant
    ```

2.  **Run the Self-Repairing Installation Script:**
    We provide a robust `install.sh` script to automate your setup.
    ```bash
    chmod +x install.sh
    ./install.sh
    ```
    This script will:
    - **Verify Dependencies:** Ensure Python 3.11+, Git, and Ollama are present.
    - **Prepare Environment:** Create `.venv` and install all required libraries.
    - **Manage Services:** Start Ollama and automatically pull the configured `OLLAMA_MODEL` (default: `llama3`).
    - **Configure System:** Guide you through `.config` creation (API keys, paths).
    - **Warming & Verification:** Pre-load the AI model and run a full diagnostic to ensure the assistant is working.

3.  **Local Services (Ollama & OpenClaw):**
    - The system is **Local-First**. It will always try to use your local machine before hitting cloud APIs.
    - You can manually manage services using: `./scripts/manage_services.sh {start|check}`.

4.  **Configure `.config`:**
    Open `.config` (managed by the installer) and refine your settings:
    - `LLM_PRIORITY`: Set your preferred model order (e.g., `ollama, openclaw, gemini`).
    - `GEMINI_API_KEY`: Optional cloud fallback.
    - `CALENDAR_ID`: Usually 'primary' or a specific ID.

6.  **Google Calendar API:**
    Place your `credentials.json` in the root directory. The first time you run the script, it will open a browser window for OAuth authentication and save a `token.json`.

## Running the Assistant

```bash
python3 main.py
```
