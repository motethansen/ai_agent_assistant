# AI Agent Assistant

An automated, multi-agent AI assistant that bridges local Markdown notes (Obsidian/LogSeq) with your Google Calendar. Designed for privacy, it prioritises local models (Ollama) and falls back gracefully to cloud APIs (OpenAI, Claude, Gemini).

## Features

- **Local-First AI** — Ollama keeps your data on your machine.
- **Smart LLM Routing** — Complexity-based routing: simple tasks go local, complex tasks use the best available API.
- **4 LLM Backends** — Ollama, OpenAI, Claude, Gemini with automatic failover.
- **Rich Terminal Chat** — Streaming responses, Markdown rendering, and conversation history.
- **Intelligent Scheduling** — Slots tasks from your notes into free gaps in your calendar.
- **Deep Research (RAG)** — Index your entire note vault and book library (PDF/EPUB).
- **Background Sync** — A Calendar Agent keeps a local YAML cache for fast responses.
- **LogSeq Integration** — Extracts tasks marked with `LATER` from your journals.
- **Mission Control UI** — Streamlit dashboard for backlog, analytics, and chat history.

---

## Installation

### Requirements

- macOS or Linux
- Python 3.11+
- Git
- [Ollama](https://ollama.com) (primary local LLM)
- At least one cloud API key (optional — see below)

### Quick Start

```bash
git clone https://github.com/yourusername/ai_agent_assistant
cd ai_agent_assistant
./install.sh
```

The installer will:
1. Check and install Python dependencies
2. Set up a Python virtual environment
3. Install Ollama (if not present)
4. **Prompt you for API keys** (OpenAI, Gemini, Claude — all optional)
5. Set up an hourly cron job for background task sync
6. Verify everything is working

### Configuration

Copy the example config and fill in your paths:

```bash
cp config.example .config
# Edit .config with your Obsidian vault path, LogSeq path, and Ollama model
```

---

## API Key Setup

The assistant uses **Ollama** by default — no API keys required. Cloud APIs are optional fallbacks.

### OpenAI (Optional)

1. Get your key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. The installer will prompt: `OpenAI API Key (sk-proj-...)`

### Gemini (Optional)

1. Get your key at [aistudio.google.com](https://aistudio.google.com)
2. The installer will prompt: `Google Gemini API Key`

### Claude (Optional)

1. Get your key at [console.anthropic.com](https://console.anthropic.com)
2. The installer will prompt: `Anthropic Claude API Key`

### Updating Keys After Installation

```
/settings                              ← view all current keys and config
/settings set OPENAI_API_KEY sk-...   ← update OpenAI key
/settings set GEMINI_API_KEY AIza...  ← update Gemini key
/settings set CLAUDE_API_KEY sk-...   ← update Claude key
```

---

## Configuration

All settings live in `.config` (created from `config.template` during install). Key settings:

| Setting | Description | Default |
|---|---|---|
| `OLLAMA_MODEL` | Local Ollama model | `llama3` |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `LLM_PRIORITY` | Fallback order | `ollama,gemini,openai,claude` |
| `ROUTING_CHAT` | LLM for chat queries | `ollama` |
| `ROUTING_SCHEDULING` | LLM for scheduling | `ollama` |
| `OPENAI_API_KEY` | OpenAI API key (optional) | — |
| `GEMINI_API_KEY` | Gemini API key (optional) | — |
| `CLAUDE_API_KEY` | Anthropic API key (optional) | — |
| `WORKSPACE_DIR` | Path to Obsidian vault | — |
| `LOGSEQ_DIR` | Path to LogSeq graph | — |

**Do not commit `.config` to Git** — it contains your API keys. It is already in `.gitignore`.

---

## Running the Assistant

```bash
make run-chat    # Interactive terminal chat
make run-ui      # Streamlit web dashboard
make run         # Background observer (watches for Markdown changes)
```

### Chat Commands

| Command | Description |
|---|---|
| `/settings` | View and update API keys and LLM config |
| `/models` | Show which LLM backends are available |
| `/routing` | Show active routing configuration |
| `/services` | Check/start local AI services (Ollama) |
| `/model enable openai` | Enable a specific backend |
| `/sync` | Manually sync tasks from Obsidian and Reminders |
| `/plan` | Trigger morning planning session |
| `/backlog` | Display your unified task backlog |
| `/develop <prompt>` | AI code generation |
| `/commands` | Full command list |

---

## LLM Routing

The assistant automatically routes requests based on complexity:

- **Simple tasks** (chat, quick lookups) → Ollama (local, free)
- **Complex tasks** (scheduling, reasoning, code) → OpenAI/Claude/Gemini

Override routing in `.config`:
```
ROUTING_CHAT=ollama
ROUTING_SCHEDULING=openai
```

---

## Google Calendar Integration

1. Create a project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the Google Calendar API and Google Gmail API
3. Download `credentials.json` and place it in the project root
4. On first run, a browser window will open to authorise access

---

## License

MIT License

---

## Progress Log

- **2026-03-14:** Removed OpenClaw — Ollama is now the primary local LLM
- **2026-03-08:** `/settings` chat command for live API key management
- **2026-03-08:** Added Rich terminal chat UI with streaming, markdown rendering, and persistent conversation history
- **2026-03-08:** Implemented complexity-based LLM routing
- **2026-03-04:** Added Qwen 3.5-9B support and LangChain integration
- **2026-03-01:** Bulk Task Management and Custom AI Commands in Mission Control
- **2026-03-01:** Self-Repairing Installation script with automatic model pulling
