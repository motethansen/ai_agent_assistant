# 🤖 AI Agent Assistant: Your Markdown-to-Calendar Sync & File System Manager

An automated AI assistant that bridges local Markdown notes (Obsidian/Logseq) and Apple Reminders with your Google Calendar. It features intelligent scheduling, multi-LLM support, and full file system agency to organize your digital life.

## 🚀 Key Features

- **Intelligent Scheduling:** Automatically slots tasks from your notes and reminders into free gaps in your Google Calendar using Gemini or local models.
- **File System Agency:** The AI can create folders, move files, and migrate tasks directly within your Obsidian vault (upon your confirmation).
- **Multi-Source Backlog:** Unifies tasks from local `.md` files and Apple Reminders into a single, deduplicated backlog.
- **Multi-LLM Routing:** Toggle between Google Gemini (for complex reasoning) and Ollama (for local, private processing).
- **Interactive CLI & Dashboard:** Manage everything via a chat-like terminal interface with `/` commands or a modern Streamlit web dashboard.
- **Modular & Extensible:** Scaffold your own custom agents with `/create-agent` and manage them in separate Git repositories.

## 🚀 Quick Start

### ⚡ Quick Installation (One-Click/Terminal)
For a one-step installation on **macOS** or **Linux (Ubuntu)**, run the following command in your terminal:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/motethansen/ai_agent_assistant/main/install.sh)"
```
*This will clone the repository, set up a virtual environment, install dependencies (including Ollama), and guide you through configuration.*

### 🛠️ Manual Installation
If you prefer to install manually:
```bash
git clone https://github.com/motethansen/ai_agent_assistant.git
cd ai_agent_assistant
./install.sh
```

### 🔄 Background Sync (Cron Job)
To set up an automated hourly sync that checks your tasks and updates your calendar:
```bash
./install.sh cron
```

### 🆙 Upgrading
To pull the latest code and update dependencies at any time:
```bash
./install.sh upgrade
```

## 🐧 Linux (Ubuntu) Support
This solution is fully compatible with Linux. 
- **Apple Reminders:** The Apple Reminders sync feature is disabled on Linux (as it requires macOS `osascript`).
- **Obsidian & LogSeq:** Full support for scanning your Markdown vaults and journals on Linux.
- **Dependencies:** The installer automatically handles Linux-specific Python requirements.

## ⚙️ Configuration
Update your `.config` file with your specific paths and keys:
- **`WORKSPACE_DIR`**: Path to your Obsidian vault.
- **`LOGSEQ_DIR`**: Path to your LogSeq graph folder.
- **`CALENDAR_ID`**: Your Google Calendar ID (usually `primary`).
- **`GEMINI_API_KEY`**: Your Google Gemini API key.

### 3. Run the Assistant (Seamlessly)
You can run the assistant using the `./assistant` wrapper script or `make` commands. Both will automatically use the virtual environment for you.

- **Background Observer:** `./assistant` (or `make run`)
- **Interactive Chat:** `./assistant --chat` (or `make run-chat`)
- **Web Dashboard:** `./assistant --ui` (or `make run-ui`)
- **Manual Sync:** `./assistant --sync`

## 🧪 Testing & Docs
- **Run Tests:** `make test`
- **View Docs:** `make docs`

## 📄 License
This project is open-source and available under the **MIT License**. See the [LICENSE](LICENSE) file for details.

## ✍️ The Journey
Read the full story behind this project in the [BLOG_POST.md](BLOG_POST.md).
