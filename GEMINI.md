# GEMINI.md: AI-Powered Markdown-Calendar-AI Bridge

## Project Overview
This project is an automated "AI Assistant" that synchronizes tasks from local Markdown files (like Obsidian or Logseq) with a Google Calendar. It uses the Gemini AI model to intelligently schedule these tasks into the user's available free time slots.

### Main Technologies
- **Python 3**: Core programming language.
- **Watchdog**: For real-time monitoring of Markdown file changes.
- **Google Calendar API**: To read busy slots and create new events.
- **Google GenAI SDK**: Interfaces with Gemini (specifically `gemini-flash-latest`) for scheduling and chat.
- **Chromadb**: Local vector database for RAG-based context retrieval from notes and books.
- **Streamlit**: Web-based "Mission Control" dashboard with interactive chat.
- **Regex (re)**: For parsing and updating specific headers within Markdown files.

## Architecture
1. **Observer Layer (`observer.py` & `main.py`)**: Listens for modifications to `.md` files in Obsidian vaults and LogSeq journals.
2. **Parser (`observer.py`)**: Extracts tasks from a `## Tasks` section (Obsidian) or from LogSeq's block-based `TODO/LATER` structure.
3. **Multi-Agent Orchestrator (`ai_orchestration.py`)**: Coordinates multiple specialized agents:
    - **RAG Agent (`rag_agent.py`)**: Retrieves context from local markdown notes.
    - **Gmail Agent (`gmail_agent.py`)**: Monitors snoozed and filtered emails.
    - **Book Agent (`book_agent.py`)**: Manages and deep-searches local book libraries (PDF/EPUB).
    - **File System Agent (`file_system_agent.py`)**: Safely performs I/O operations.
4. **Calendar Manager (`calendar_manager.py`)**: Fetches appointments to identify "Busy" blocks and syncs AI-generated schedules.
5. **Sync Engine (`main.py` & `cron_job.py`)**: 
    - Pushes scheduled tasks to Google Calendar.
    - Updates the Markdown file's `## Today's Plan` section.
    - Manages the interactive CLI and Web UI chat loops.

## Building and Running

### Prerequisites
- Python 3.10+
- Google Cloud Project with Calendar and Gmail APIs enabled.
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

# Run interactive chat mode
python3 main.py --chat

# Launch the Web Mission Control
make run-ui
```

## Development Conventions
- **Action Loops**: The AI can propose actions (create file, index book, etc.) which require user confirmation in the CLI or UI.
- **RAG Support**: Large documents and book libraries are indexed page-by-page into a local `vector_db` for semantic search.
- **Timezone Safety**: All calendar operations are timezone-aware to prevent scheduling shifts.
- **Security**: API keys and tokens are stored in `.env`, `credentials.json`, and `token.json`, all of which are ignored by Git.

## Key Files
- `main.py`: Entry point and CLI orchestration.
- `app.py`: Streamlit Web UI and Mission Control.
- `ai_orchestration.py`: Multi-agent coordination and prompt engineering.
- `calendar_manager.py`: Google Calendar API wrapper.
- `book_agent.py`: PDF/EPUB indexing and deep search.
- `gmail_agent.py`: Gmail integration.
- `rag_agent.py`: Notes indexing and context retrieval.
- `BLOG_POST.md`: Narrated documentation of the project's development journey.
