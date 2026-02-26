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

2.  **Install Ollama:**
    Follow the instructions at [ollama.com](https://ollama.com/) to install Ollama on your machine.
    Once installed, pull a model (e.g., llama3):
    ```bash
    ollama pull llama3
    ```

3.  **Install OpenClaw:**
    Visit [openclaw.ai](https://openclaw.ai/) for the latest installation instructions. OpenClaw provides a powerful interface for agentic workflows.

4.  **Run the Installation Script:**
    We provide an `install.sh` script to help you set up your local environment and configuration.
    ```bash
    chmod +x install.sh
    ./install.sh
    ```
    This script will:
    - Create a virtual environment (`.venv`).
    - Install Python dependencies.
    - Create a `.config` file from the template (you will need to fill in your API keys).

5.  **Configure `.config`:**
    Open the newly created `.config` file and add your credentials:
    - `GEMINI_API_KEY`: Your Google Gemini API key.
    - `CALENDAR_ID`: Usually 'primary' or a specific Google Calendar ID.
    - `OPENCLAW_API_KEY`: If applicable for your OpenClaw setup.

6.  **Google Calendar API:**
    Place your `credentials.json` in the root directory. The first time you run the script, it will open a browser window for OAuth authentication and save a `token.json`.

## Running the Assistant

```bash
python3 main.py
```
