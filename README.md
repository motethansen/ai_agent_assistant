# 🤖 AI Agent Assistant: Your Privacy-First Markdown-to-Calendar OS

An automated, multi-agent AI assistant that bridges local Markdown notes (Obsidian/Logseq) and Apple Reminders with your Google Calendar. Designed for privacy, it prioritizes local models (Ollama/OpenClaw) and features a modular agent architecture.

## 🚀 Key Features

- **Local-First AI:** Built-in support for **Ollama** and **OpenClaw** to keep your data on your machine.
- **Intelligent Scheduling:** Automatically slots tasks from your notes into free gaps in your calendar.
- **Real-Time Search:** Research flights, itineraries, and travel plans with the **Travel Agent**.
- **Deep Research (RAG):** Index your entire note vault and book library (PDF/EPUB) for instant semantic search.
- **Background Sync:** A dedicated **Calendar Agent** keeps a local YAML cache of your schedule for lightning-fast responses.
- **LogSeq Integration:** Specifically extracts tasks marked with **LATER** from your journals.
- **Mission Control UI:** A modern Streamlit dashboard to manage your backlog, analytics, and chat history.

## 📈 Latest Updates (Progress Log)
- **2026-03-01:** Redesigned architecture to prioritize **Ollama/OpenClaw** with a **Monitoring Agent**.
- **2026-03-01:** Implemented **Background Calendar Sync** to `datainput/googlecalendar.yml`.
- **2026-03-01:** Added **Planning Agent** to handle atomic updates to Calendar and Obsidian.
- **2026-03-01:** Enhanced **LogSeq Agent** to pull tasks specifically marked with `LATER`.
- **2026-03-01:** Launched **Web Setup Wizard** for seamless, non-technical configuration.

## 🚀 Quick Start

### 🖱️ One-Click Installer (Recommended)
If you have downloaded the project folder, simply double-click the installer:
- **Mac:** Double-click the `install.command` file.
- **Linux:** Double-click the `AI Assistant Installer` icon.
*This will prepare the environment (Python 3.11+) and launch the **Web Setup Wizard**.*

### ⚡ Quick Installation (Terminal)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/motethansen/ai_agent_assistant/main/install.sh)"
```

## ⚙️ Configuration
The assistant is managed via the `.config` file or the `make setup` wizard:
- **`ROUTING_SCHEDULING`**: Default model for planning (e.g., `openclaw`).
- **`ROUTING_CHAT`**: Default model for chat (e.g., `ollama`).
- **`ENABLE_GEMINI/OPENAI/CLAUDE`**: Optional cloud fallback flags.

## 3. Run the Assistant
- **Background Observer:** `make run`
- **Interactive Chat:** `make run-chat`
- **Web Dashboard:** `make run-ui`

## 📄 License
This project is open-source under the **MIT License**.

## ✍️ The Journey
Read the full story behind this project in the [BLOG_POST.md](BLOG_POST.md).
