# Development Plan: Markdown-Calendar-AI Bridge

**Goal:** Build an automated system that syncs local markdown tasks (from Obsidian/Logseq) with Google Calendar using an AI model to schedule free slots.

## Tasks & Phases

### Phase 1: Environment Foundation
- [x] Initialize Python virtual environment.
- [x] Install dependencies: `watchdog`, `google-api-python-client`, `google-auth-oauthlib`, and an AI SDK (e.g., `google-generativeai`).
- [x] Create basic project structure.

### Phase 2: Local Observer Layer (Watchdog)
- [x] Implement `watchdog` to monitor `.md` files in a specified directory.
- [x] Create a parser to extract tasks from a `## Tasks` header in markdown files.
- [x] Trigger an event when the file is modified.

### Phase 3: Calendar & Appointments Layer
- [x] Set up Google Cloud Project and enable Calendar API.
- [x] Handle OAuth 2.0 authentication (`credentials.json`, `token.json`).
- [x] Write logic to fetch "Busy" blocks from Google Calendar for the current day.
- [x] Calculate available free time slots.

### Phase 4: AI Orchestration
- [x] Design a prompt that combines extracted tasks and available free slots.
- [x] Call the AI API (e.g., Gemini) to generate a schedule in JSON format.
- [x] Validate the AI's JSON output.

### Phase 5: Sync & Write-Back Loop
- [x] Update Google Calendar with the AI-generated schedule.
- [x] Write the finalized schedule back to the markdown file under a `## Today's Plan` header.
- [x] Set up background services (Cron job integration).

### Phase 6: OpenClaw and Ollama Integration
- [x] Add OpenClaw and Ollama modules to the system.
- [x] Update `install.sh` to install Ollama and OpenClaw locally.
- [x] Add logic to check for successful installation of the modules (including `ollama pull`).

### Phase 7: Obsidian & Apple Reminders Retrieval
- [x] Implement an agent to parse Obsidian for tasks and check their associated dates.
- [x] Create a script/module to retrieve tasks from Apple Reminders.
- [x] Add configuration support in `.config` to specify which Apple Reminders list to retrieve tasks from.
- [x] Ensure Reminders act as cross-category activities.
- [x] Implement LogSeq task scanning (Journals and Pages).
- [x] Support Linux (Ubuntu) environment.

### Phase 8: Daily Backlog & AI Assistant Workflow
- [x] Create an agent to process tasks from Obsidian and Apple Reminders into a unified backlog.
- [x] Develop AI assistant capability to manage the backlog daily.
- [x] Implement morning/evening suggestions: AI suggests tasks for the calendar, asks for time allocation, and verifies completion status.
- [x] Maintain a category-specific backlog with categories.
- [x] Implement logic for the AI to detect new uncategorized tasks from Obsidian and ask/suggest new categories.
- [x] Automatically schedule or track daily exercise and rest.
- [x] Support seamless launching through wrapper script and Makefile.
- [x] Support automated upgrades through install script.

### Phase 9: Automated Testing & Reporting
- [x] Create a `tests/` directory with unit and integration tests (using `pytest`).
- [ ] Implement mock objects for Google Calendar and Gemini API calls to allow offline testing.
- [x] Create a `Makefile` to automate test execution (`make test`) and environment setup.
- [ ] Implement a reporting mechanism (e.g., `pytest-html` or JSON reports) to capture and address errors.

### Phase 10: Documentation & Frontend
- [x] Create a `docs/` directory with comprehensive Markdown documentation.
- [x] Implement a CLI command (`python main.py --docs`) to render documentation in the terminal.
- [x] Develop a **Streamlit** (browser-based) dashboard for visual backlog management, schedule review, and manual overrides.
- [ ] Ensure the CLI remains the primary engine for background automation.

### Phase 11: Interactive CLI Chat & Slash Commands
- [x] Implement an interactive chat loop in the terminal (e.g., `python main.py --chat`).
- [x] Add support for slash commands:
    - `/sync`: Manually trigger a task sync.
    - `/backlog`: Display the current unified backlog.
    - `/plan`: Trigger a morning planning session.
    - `/review`: Trigger an evening review session.
    - `/ui`: Launch the Streamlit web interface from the CLI.
    - `/exit`: Quit the interactive session.
- [x] Integrate the AI orchestrator to answer questions about the schedule or backlog within the chat.
- [x] Ensure the CLI feels similar to `gemini-cli` or `claude-cli` for a consistent developer experience.

### Phase 12: Multi-LLM Support & Task Routing
- [x] Implement support for toggling active language models (Gemini, Ollama, OpenClaw) via the `.config` file.
- [x] Add CLI commands to enable/disable specific models on the fly (e.g., `/model enable ollama`).
- [x] Ensure local models (Ollama, OpenClaw) are always enabled by default if installed.
- [x] Create a routing mechanism in `ai_orchestration.py` to allow users to specify which LLM handles which specific tasks (e.g., local models for basic parsing, API models for complex scheduling).

### Phase 13: Dynamic Agent Creation Framework
- [x] Create a CLI command (e.g., `/create-agent <name>`) that scaffolds a new Python agent dynamically.
- [x] Implement backend code separation so user-defined agents are generated into an isolated directory structure (e.g., `custom_agents/`).
- [x] Support committing and pushing these user-defined agents into their own separate Git repositories, encouraging a modular and shareable agent ecosystem.
- [x] Enable the main assistant backend to discover and load these external agents dynamically at runtime.

### Phase 14: File System Agent & Action Capabilities
- [x] Implement a specialized "File System Agent" that can safely perform I/O operations (create folders, move files, generate new .md notes).
- [x] Update the CLI chat loop to support "Action Loops" where the AI can propose a file system change and wait for user confirmation.
- [x] Add support for "Reminders-to-Obsidian" migration: Automatically create a new Obsidian note from stored local JSON reminders.
- [x] Ensure all file operations are relative to the configured `WORKSPACE_DIR`.

### Phase 15: Gmail Snooze & Filter Agent
- [x] Implement a Gmail Agent to access the user's Gmail account via Google API.
- [x] Add capability to identify and retrieve emails that are currently "snoozed".
- [x] Implement a filtering mechanism based on user-defined search queries.
- [x] Create a CLI command to add/manage these filters (e.g., `/gmail-filter add "from:boss"`).
- [x] Store filters in a specialized skill or tool configuration file for persistence.
- [x] Integrate the Gmail Agent into the main orchestration loop to suggest tasks or reminders based on filtered emails.

### Phase 16: Deep Book Indexing & RAG
- [x] Implement a `BookAgent` to scan a user's library (`BOOKS_DIR`) for PDFs, EPUBs, and images.
- [x] Integrate `PyPDF2` and `EbookLib` for text extraction.
- [x] Implement a local vector database (ChromaDB) to index large books page by page.
- [x] Enable the AI to "read" specific sections of books and "search" for topics across the entire library.
- [x] Provide clickable (path-based) links to books within the AI's response.
- [x] Integrate book-level context into both the CLI chat and Streamlit UI.

### Phase 17: Travel Planning Agent
- [x] Implement a `TravelAgent` that utilizes Gemini's Google Search grounding.
- [x] Enable real-time search for flights, connecting flights, and holiday itineraries.
- [x] Provide direct URLs to booking sites for user reference.
- [x] Integrate travel planning into the AI Orchestrator as a tool-based action.
- [x] Support travel research in both CLI and Streamlit Mission Control.

### Phase 18: Local-First Refactor & Agent Specialisation
- [x] Implement `MonitoringAgent` to track health of local AI servers (Ollama/OpenClaw).
- [x] Create `CalendarAgent` for background sync to local YAML (`googlecalendar.yml`).
- [x] Implement `PlanningAgent` for atomic updates to Calendar and Obsidian.
- [x] Refine LogSeq parser to specifically target `LATER` tasks.
- [x] Add optional support for OpenAI and Claude APIs.
- [x] Update routing logic to prioritize local models with intelligent fallback.

## Summary of Planned Development
The system will act as a bridge between your local knowledge base and your schedule. 
1. **Watchdog** will monitor your markdown files for changes. 
2. **Parser** will extract tasks from these files. 
3. **Google Calendar API** will provide your current availability. 
4. **AI (Gemini/OpenAI)** will intelligently slot your tasks into your free time. 
5. **Sync** will update both your Google Calendar and your markdown file with the finalized daily plan.
