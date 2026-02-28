# GEMINI.md: AI-Powered Markdown-Calendar-AI Bridge

## Project Overview
This project is an automated "AI Assistant" that synchronizes tasks from local Markdown files (like Obsidian or Logseq) with a Google Calendar. It uses the Gemini AI model to intelligently schedule these tasks into the user's available free time slots.

### Main Technologies
- **Python 3**: Core programming language.
- **Watchdog**: For real-time monitoring of Markdown file changes.
- **Google Calendar API**: To read busy slots and create new events.
- **Google GenAI SDK**: Interfaces with Gemini (specifically `gemini-flash-latest`) for scheduling logic.
- **Regex (re)**: For parsing and updating specific headers within Markdown files.

## Architecture
1. **Observer Layer (`observer.py` & `main.py`)**: Listens for modifications to `.md` files in Obsidian vaults and LogSeq journals.
2. **Parser (`observer.py`)**: Extracts tasks from a `## Tasks` section (Obsidian) or from LogSeq's block-based `TODO/LATER` structure.
3. **Calendar Manager (`calendar_manager.py`)**: Fetches existing appointments for the day to identify "Busy" blocks.
4. **AI Orchestrator (`ai_orchestration.py`)**: Sends tasks and busy slots to Gemini (or local Ollama) with a prompt to generate an optimized JSON schedule.
5. **Sync Engine (`main.py` & `cron_job.py`)**: 
    - Pushes scheduled tasks to Google Calendar.
    - Updates the Markdown file's `## Today's Plan` section.
    - Can run as a persistent observer or a periodic cron job.

## Building and Running

### Prerequisites
- Python 3.10+
- Google Cloud Project with Calendar API enabled.
- `credentials.json` (OAuth Client ID) in the root directory.

### Setup & Management
```bash
# Unified installation script (macOS/Linux)
./install.sh

# Setup automated hourly sync (cron)
./install.sh cron

# Upgrade to latest code and dependencies
./install.sh upgrade
```

### Running the Project
```bash
# Run the main automation loop
python3 main.py
```

## Development Conventions
- **Debouncing**: `main.py` includes a 5-second debounce in the `on_modified` event to prevent multiple triggers from quick saves.
- **Markdown Headers**: The system strictly follows a two-header convention:
    - `## Tasks`: Where the user logs pending items.
    - `## Today's Plan`: Where the AI writes back the finalized schedule.
- **Security**: API keys and tokens are stored in `.env`, `credentials.json`, and `token.json`, all of which are ignored by Git.
- **JSON Sanitization**: `ai_orchestration.py` includes a cleanup function to ensure the AI's output is valid JSON before parsing.

## Key Files
- `main.py`: Entry point and orchestration logic.
- `calendar_manager.py`: Google Calendar API wrapper.
- `ai_orchestration.py`: Gemini prompt and response handling.
- `observer.py`: Markdown task parser.
- `requirements.txt`: Project dependencies.
- `BLOG_POST.md`: Narrated documentation of the project's development journey.
