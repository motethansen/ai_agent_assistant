# 🤖 AI Agent Assistant: Your Privacy-First Markdown-to-Calendar OS

An automated, multi-agent AI assistant that bridges local Markdown notes (Obsidian/Logseq) and Apple Reminders with your Google Calendar. Designed for privacy, it prioritizes local models (Ollama/OpenClaw) and features a modular agent architecture.

## 🚀 Key Features

- **Local-First AI:** Built-in support for **Ollama** and **OpenClaw** to keep your data on your machine.
- **Bulk Task Management:** Select multiple tasks in the UI to batch-edit dates or re-categorize them.
- **Custom AI Commands:** Give specific instructions to the AI for selected tasks (e.g., "move all dev tasks to next Tuesday").
- **Intelligent Scheduling:** Automatically slots tasks from your notes into free gaps in your calendar.
- **Real-Time Search:** Research flights, itineraries, and travel plans with the **Travel Agent**.
- **Deep Research (RAG):** Index your entire note vault and book library (PDF/EPUB) for instant semantic search.
- **Background Sync:** A dedicated **Calendar Agent** keeps a local YAML cache of your schedule for lightning-fast responses.
- **LogSeq Integration:** Specifically extracts tasks marked with **LATER** from your journals.
- **Mission Control UI:** A modern Streamlit dashboard to manage your backlog, analytics, and chat history.

## 📈 Latest Updates (Progress Log)
- **2026-03-01:** Added **Bulk Task Management** and **Custom AI Commands** to the Mission Control.
- **2026-03-01:** Redesigned architecture to prioritize **Ollama/OpenClaw** with a **Monitoring Agent**.
- **2026-03-01:** Implemented **Priority-Based LLM Routing** (Ollama > OpenClaw > Cloud).
- **2026-03-04:** Added support for **Qwen 3.5-9B** and integrated **LangChain (ChatOllama)** for better agentic reasoning.
- **2026-03-01:** Added **Self-Repairing Installation** script with automatic model pulling.
- **2026-03-01:** Integrated **System Health & Update Tracking** in the Mission Control UI.

## 🚀 Quick Start

### 🖱️ One-Click Installer (Recommended)
If you have downloaded the project folder, simply double-click the installer:
- **Mac:** Double-click the `install.command` file.
- **Linux:** Double-click the `AI Assistant Installer` icon.
*This script will now automatically start local services (Ollama and OpenClaw via Docker), pull missing models, and verify AI functionality.*

**Note:** Ensure [Docker](https://www.docker.com/products/docker-desktop/) or [OrbStack](https://orbstack.dev/) is running before installation if you plan to use OpenClaw locally.

### ⚡ Quick Installation (Terminal)
```bash
./install.sh
```

## ⚙️ Configuration
The assistant is managed via the `.config` file or the `make setup` wizard:
- **`LLM_PRIORITY`**: Order of preference for models (e.g., `ollama, openclaw, gemini`).
- **`ROUTING_SCHEDULING`**: Task-specific override (e.g., `ollama`).
- **`ROUTING_CHAT`**: Task-specific override (e.g., `ollama`).
- **`OLLAMA_MODEL`**: The specific model to use (default: `llama3`).

## 3. Run the Assistant
- **Background Observer:** `make run`
- **Interactive Chat:** `make run-chat`
- **Web Dashboard:** `make run-ui`

## 📄 License
This project is open-source under the **MIT License**.

## ✍️ The Journey
Read the full story behind this project in the [BLOG_POST.md](BLOG_POST.md).
