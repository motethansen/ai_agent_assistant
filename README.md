# AI Agent Assistant

An automated, multi-agent AI assistant that bridges local Markdown notes (Obsidian/Logseq) and Apple Reminders with your Google Calendar. Designed for privacy, it prioritises local models (Ollama/OpenClaw) and falls back gracefully to cloud APIs (OpenAI, Claude, Gemini).

## Features

- **Local-First AI** — Ollama and OpenClaw keep your data on your machine.
- **Smart LLM Routing** — Complexity-based routing: simple tasks go local, complex tasks use the best available API.
- **5 LLM Backends** — Ollama, OpenClaw, OpenAI, Claude, Gemini with automatic failover.
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
- Node.js 22+ (for OpenClaw)
- [Ollama](https://ollama.com) (optional, for local models)
- At least one API key (see below)

### Quick Start

```bash
git clone https://github.com/yourusername/ai_agent_assistant
cd ai_agent_assistant
./install.sh
```

The installer will:
1. Check and install Python/Node dependencies
2. Set up a Python virtual environment
3. Install Ollama and OpenClaw (if not present)
4. **Prompt you for API keys** (OpenAI, Gemini, Claude — see below)
5. Register OpenClaw as a background service so it survives reboots
6. Set up an hourly cron job for background task sync
7. Verify everything is working

---

## API Key Setup

The assistant routes AI requests through **OpenClaw**, which acts as a local gateway supporting multiple providers. You need at least one API key.

### OpenAI (Recommended)

1. Get your key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. The installer will prompt: `OpenAI API Key (sk-proj-...)`
3. Paste it in — the installer configures both `.config` and the OpenClaw gateway automatically.

The default model is `gpt-4o-mini` (fast, cheap, capable). To use `gpt-4o` instead, edit `.config`:
```
OPENCLAW_MODEL=openai/gpt-4o
```

### Gemini (Optional)

1. Get your key at [aistudio.google.com](https://aistudio.google.com)
2. The installer will prompt: `Google Gemini API Key`

### Claude (Optional)

1. Get your key at [console.anthropic.com](https://console.anthropic.com)
2. The installer will prompt: `Anthropic Claude API Key`

### Updating Keys After Installation

You can add or update any API key at any time from within the chat interface:

```
/settings                              ← view all current keys and config
/settings set OPENAI_API_KEY sk-...   ← update OpenAI key
/settings set GEMINI_API_KEY AIza...  ← update Gemini key
/settings set CLAUDE_API_KEY sk-...   ← update Claude key
```

Changes take effect immediately (no restart needed for most keys).

---

## Configuration

All settings live in `.config` (created from `config.template` during install). Key settings:

| Setting | Description | Default |
|---|---|---|
| `OPENCLAW_MODEL` | Model used by OpenClaw gateway | `openai/gpt-4o-mini` |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `GEMINI_API_KEY` | Gemini API key | — |
| `CLAUDE_API_KEY` | Anthropic API key | — |
| `OLLAMA_MODEL` | Local Ollama model | `llama3` |
| `LLM_PRIORITY` | Fallback order | `openclaw,ollama,gemini` |
| `ROUTING_CHAT` | LLM for chat queries | `openclaw` |
| `ROUTING_SCHEDULING` | LLM for scheduling | `openclaw` |
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
| `/services` | Check/start local AI services (Ollama, OpenClaw) |
| `/model enable openai` | Enable a specific backend |
| `/sync` | Manually sync tasks from Obsidian and Reminders |
| `/plan` | Trigger morning planning session |
| `/backlog` | Display your unified task backlog |
| `/develop <prompt>` | AI code generation |
| `/commands` | Full command list |

---

## LLM Routing

The assistant automatically routes requests based on complexity:

- **Simple tasks** (chat, quick lookups) → Ollama (local, free) or OpenClaw
- **Complex tasks** (scheduling, reasoning, code) → OpenClaw → OpenAI/Claude/Gemini

Override routing in `.config`:
```
ROUTING_CHAT=ollama
ROUTING_SCHEDULING=openai
```

---

## OpenClaw Gateway

OpenClaw runs as a persistent background service (macOS LaunchAgent / Linux systemd) and provides a unified OpenAI-compatible API endpoint for all configured providers. This means:

- One local endpoint (`http://localhost:18789/v1`) routes to any provider
- Dashboard available at `http://127.0.0.1:18789`
- Survives machine restarts

To check status: `openclaw gateway status`
To restart: `openclaw gateway restart`

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

- **2026-03-08:** OpenAI via OpenClaw gateway — working end-to-end with `gpt-4o-mini`
- **2026-03-08:** `/settings` chat command for live API key management
- **2026-03-08:** `install.sh` now prompts for API keys and auto-configures OpenClaw
- **2026-03-08:** OpenClaw installed as persistent macOS LaunchAgent
- **2026-03-08:** Fixed `is_openclaw_running()` — `/v1/models` returns HTML (SPA), probe via `/v1/chat/completions`
- **2026-03-08:** Added Rich terminal chat UI with streaming, markdown rendering, and persistent conversation history
- **2026-03-08:** Implemented complexity-based LLM routing
- **2026-03-04:** Added Qwen 3.5-9B support and LangChain integration
- **2026-03-01:** Bulk Task Management and Custom AI Commands in Mission Control
- **2026-03-01:** Priority-Based LLM Routing (Ollama > OpenClaw > Cloud)
- **2026-03-01:** Self-Repairing Installation script with automatic model pulling
