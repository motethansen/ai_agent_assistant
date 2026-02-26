# Project Overview

This AI Agent Assistant synchronizes tasks from local Markdown files (like Obsidian) and Apple Reminders to your Google Calendar, using the Gemini AI model as an intelligent scheduler.

## Key Features

- **Real-time Monitoring:** Listens for changes in your Markdown files.
- **AI Scheduling:** Uses Gemini to intelligently slot tasks into your free time.
- **Unified Backlog:** Merges tasks from multiple sources (Obsidian, Apple Reminders).
- **Category Management:** Tracks tasks across various projects and suggests new categories as needed.

## Setup

1.  Run `make install` to set up the environment.
2.  Follow the interactive prompts to configure your API keys in the `.config` file.
3.  Place your `credentials.json` from Google Cloud in the root directory.

## Running

- **CLI Mode:** `source .venv/bin/activate && python main.py`
- **Docs:** `make docs`
- **Tests:** `make test`
- **Frontend (Coming Soon):** `streamlit run app.py`
