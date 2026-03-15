# Installation Guide

This project requires setting up a few local and cloud components to function as an AI agent assistant.

## Prerequisites

- Python 3.10+
- Google Cloud Project with Calendar API enabled.
- `credentials.json` (OAuth Client ID) from Google Cloud Console.
- [Ollama](https://ollama.com/) installed locally.

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

3.  **Local Services (Ollama):**
    - The system is **Local-First**. It will always try to use your local Ollama instance before hitting cloud APIs.
    - You can manually manage services using: `./scripts/manage_services.sh {start|check}`.

4.  **Configure `.config`:**
    Open `.config` (managed by the installer) and refine your settings:
    - `LLM_PRIORITY`: Set your preferred model order (e.g., `ollama,gemini,openai,claude`).
    - `OLLAMA_MODEL`: The local model to use (e.g., `llama3`, `mistral`, `qwen2.5:14b`).
    - `GEMINI_API_KEY`: Optional cloud fallback.
    - `CALENDAR_ID`: Usually 'primary' or a specific ID.

5.  **Google Calendar API:**
    Place your `credentials.json` in the root directory. The first time you run the script, it will open a browser window for OAuth authentication and save a `token.json`.

## LogSeq Setup

If you use [LogSeq](https://logseq.com/) for note-taking, the assistant can read your pending tasks directly from your graph.

### 1. Find your graph path

Your LogSeq graph is a folder on disk that contains `journals/` and `pages/` subdirectories.

| Platform | Typical location |
|----------|-----------------|
| Linux    | `/home/yourname/logseq/my-graph` |
| macOS    | `/Users/yourname/Documents/LogSeq/my-graph` |
| Windows  | `C:\Users\yourname\Documents\LogSeq\my-graph` |

Open LogSeq → **Settings → Graphs** to see the exact path.

### 2. Set LOGSEQ_DIR in .env / .config

```
# LOGSEQ_DIR: Path to your LogSeq graph folder (the one containing journals/ and pages/).
# Linux example:  LOGSEQ_DIR=/home/yourname/logseq/my-graph
# Mac example:    LOGSEQ_DIR=/Users/yourname/Documents/LogSeq/my-graph
LOGSEQ_DIR=/home/yourname/logseq/my-graph
```

### 3. Task format

The assistant parses tasks that start with `- LATER` or `- TODO` (standard LogSeq task markers):

```markdown
- LATER Write sprint retrospective notes
- TODO Review pull request #42
  :category: dev
  :url: https://github.com/...
```

Optional indented properties (`:category:`, `:url:`, etc.) are picked up automatically.

### 4. View your backlog

```bash
python3 main.py --backlog
```

This merges tasks from LogSeq journals (last 14 days), LogSeq pages, Obsidian, and Apple Reminders into one list.

## Running the Assistant

```bash
python3 main.py
```
