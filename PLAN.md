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
- [ ] (Optional) Set up background services (`launchd` for macOS).

### Phase 6: OpenClaw and Ollama Integration
- [ ] Add OpenClaw and Ollama modules to the system.
- [ ] Update `install.sh` to install Ollama and OpenClaw locally.
- [ ] Add logic to check for successful installation of the modules.

### Phase 7: Obsidian & Apple Reminders Retrieval
- [x] Implement an agent to parse Obsidian for tasks and check their associated dates.
- [x] Create a script/module to retrieve tasks from Apple Reminders.
- [x] Add configuration support in `.config` to specify which Apple Reminders list to retrieve tasks from.
- [x] Ensure Reminders act as cross-category activities.

### Phase 8: Daily Backlog & AI Assistant Workflow
- [ ] Create an agent to process tasks from Obsidian and Apple Reminders into a unified backlog.
- [ ] Develop AI assistant capability to manage the backlog daily.
- [ ] Implement morning/evening suggestions: AI suggests tasks for the calendar, asks for time allocation, and verifies completion status.
- [ ] Maintain a category-specific backlog with categories.
- [ ] Implement logic for the AI to detect new uncategorized tasks from Obsidian and ask/suggest new categories.
- [ ] Automatically schedule or track daily exercise and rest.

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

## Summary of Planned Development
The system will act as a bridge between your local knowledge base and your schedule. 
1. **Watchdog** will monitor your markdown files for changes. 
2. **Parser** will extract tasks from these files. 
3. **Google Calendar API** will provide your current availability. 
4. **AI (Gemini/OpenAI)** will intelligently slot your tasks into your free time. 
5. **Sync** will update both your Google Calendar and your markdown file with the finalized daily plan.
