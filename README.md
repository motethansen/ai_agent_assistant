# 🤖 AI Agent Assistant: Your Markdown-to-Calendar Sync & File System Manager

An automated AI assistant that bridges local Markdown notes (Obsidian/Logseq) and Apple Reminders with your Google Calendar. It features intelligent scheduling, multi-LLM support, and full file system agency to organize your digital life.

## 🚀 Key Features

- **Intelligent Scheduling:** Automatically slots tasks from your notes and reminders into free gaps in your Google Calendar using Gemini or local models.
- **File System Agency:** The AI can create folders, move files, and migrate tasks directly within your Obsidian vault (upon your confirmation).
- **Multi-Source Backlog:** Unifies tasks from local `.md` files and Apple Reminders into a single, deduplicated backlog.
- **Multi-LLM Routing:** Toggle between Google Gemini (for complex reasoning) and Ollama (for local, private processing).
- **Interactive CLI & Dashboard:** Manage everything via a chat-like terminal interface with `/` commands or a modern Streamlit web dashboard.
- **Modular & Extensible:** Scaffold your own custom agents with `/create-agent` and manage them in separate Git repositories.

## 🛠️ Quick Start

### 1. Installation
```bash
git clone https://github.com/motethansen/ai_agent_assistant.git
cd ai_agent_assistant
make install
```
The installation script will set up your virtual environment and guide you through creating your `.config` file.

### 2. Configuration
Update your `.config` file with your specific paths and keys:
- **`WORKSPACE_DIR`**: Path to your Obsidian vault.
- **`CALENDAR_ID`**: Your Google Calendar ID.
- **`GEMINI_API_KEY`**: Your Google Gemini API key.

### 3. Run the Assistant
- **Passive Sync:** `python main.py` (Watches for file changes)
- **Interactive Chat:** `python main.py --chat`
- **Web Dashboard:** `make run-ui`

## 🧪 Testing & Docs
- **Run Tests:** `make test`
- **View Docs:** `make docs`

## 📄 License
This project is open-source and available under the **MIT License**. See the [LICENSE](LICENSE) file for details.

## ✍️ The Journey
Read the full story behind this project in the [BLOG_POST.md](BLOG_POST.md).
