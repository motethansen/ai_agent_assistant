# Development Plan: Markdown-Calendar-AI Bridge

**Goal:** Build an automated system that syncs local markdown tasks (from Obsidian/Logseq) with Google Calendar using an AI model to schedule free slots.

## Tasks & Phases

### Phase 1: Environment Foundation
- [ ] Initialize Python virtual environment.
- [ ] Install dependencies: `watchdog`, `google-api-python-client`, `google-auth-oauthlib`, and an AI SDK (e.g., `google-generativeai`).
- [ ] Create basic project structure.

### Phase 2: Local Observer Layer (Watchdog)
- [ ] Implement `watchdog` to monitor `.md` files in a specified directory.
- [ ] Create a parser to extract tasks from a `## Tasks` header in markdown files.
- [ ] Trigger an event when the file is modified.

### Phase 3: Calendar & Appointments Layer
- [ ] Set up Google Cloud Project and enable Calendar API.
- [ ] Handle OAuth 2.0 authentication (`credentials.json`, `token.json`).
- [ ] Write logic to fetch "Busy" blocks from Google Calendar for the current day.
- [ ] Calculate available free time slots.

### Phase 4: AI Orchestration
- [ ] Design a prompt that combines extracted tasks and available free slots.
- [ ] Call the AI API (e.g., Gemini) to generate a schedule in JSON format.
- [ ] Validate the AI's JSON output.

### Phase 5: Sync & Write-Back Loop
- [ ] Update Google Calendar with the AI-generated schedule.
- [ ] Write the finalized schedule back to the markdown file under a `## Today's Plan` header.
- [ ] (Optional) Set up background services (`launchd` for macOS).

## Summary of Planned Development
The system will act as a bridge between your local knowledge base and your schedule. 
1. **Watchdog** will monitor your markdown files for changes. 
2. **Parser** will extract tasks from these files. 
3. **Google Calendar API** will provide your current availability. 
4. **AI (Gemini/OpenAI)** will intelligently slot your tasks into your free time. 
5. **Sync** will update both your Google Calendar and your markdown file with the finalized daily plan.
