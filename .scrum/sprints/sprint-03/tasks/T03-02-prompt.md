# Dev Agent Task Prompt — T03-02

> **ACTION REQUIRED: You are a Claude Code agent with file-editing tools (Read, Edit, Write, Bash).**
> **READ the actual source files in the project, then APPLY all changes directly to disk using your tools.**
> **Do NOT output code as text blocks. Write changes to the actual files.**
> **Project root: /home/michaelhansen/Projects/github/ai_agent_assistant**

> Self-contained — no dependencies. Can run in parallel with T03-01 and T03-03.

---

## Identity & Role

You are a senior software developer on **AI Agent Assistant** — a personal CLI agent using local Ollama LLMs.

You are creating `config.example` — a clean, well-commented starter config file for new users — and updating `README.md` to reference it.

---

## Relevant Existing Code

### config.template (current full contents — read the actual file at config.template)

The `config.template` file is the authoritative reference. `config.example` should be a trimmed-down, friendlier version of it — only the settings a new user needs, all others commented out.

### .gitignore

```
.config        ← gitignored (user's real config)
.env           ← gitignored
```

`config.example` must NOT be gitignored — it is a template committed to the repo.

### README.md — current Getting Started section (read the actual file to find it)

---

## Your Task

**Task ID**: T03-02
**Title**: config.example with sane defaults
**Sprint**: Sprint-03
**Backlog item**: BLI-021

### Changes to make

**Create `config.example`** at the project root:

Include only these settings (in this order), each with a one-line comment:

```
# Copy this file to .config and fill in your paths.
# Cloud API keys are optional — Ollama runs fully locally.

# Ollama (required — install from https://ollama.com)
OLLAMA_MODEL=llama3:latest
OLLAMA_HOST=http://localhost:11434

# Your notes directories
WORKSPACE_DIR=/path/to/your/obsidian/vault
LOGSEQ_DIR=/path/to/your/logseq/graph

# Google Calendar (optional — needs credentials.json from Google Cloud Console)
CALENDAR_ID=primary

# LLM routing — which model handles each task type
ROUTING_CHAT=ollama
ROUTING_SCHEDULING=ollama
ROUTING_PARSING=ollama

# Fallback order if Ollama is unavailable
LLM_PRIORITY=ollama,gemini,openai,claude

# Cloud API keys (optional — uncomment and fill in if you want cloud fallback)
# GEMINI_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here
# CLAUDE_API_KEY=your_key_here

# Enable cloud providers (all off by default — Ollama only)
ENABLE_OLLAMA=true
ENABLE_GEMINI=false
ENABLE_OPENAI=false
ENABLE_CLAUDE=false

# Webhook server for n8n integration (optional)
# WEBHOOK_PORT=5678
# N8N_PORT=5679
```

**`README.md`** — find the Getting Started or Installation section and add:

```markdown
### Configuration

Copy the example config and fill in your paths:

```bash
cp config.example .config
# Edit .config with your Obsidian vault path, LogSeq path, and Ollama model
```
```

### Acceptance Criteria
- [ ] `config.example` created at project root
- [ ] Contains only essential settings — no obscure or advanced options at the top level
- [ ] Every setting has a one-line comment
- [ ] Cloud API keys present but commented out
- [ ] No OpenClaw references anywhere
- [ ] `README.md` references `config.example` in setup instructions
- [ ] `config.example` is NOT listed in `.gitignore` (it should be committed)

---

## Completion Report

### 1. Files created/modified
### 2. Acceptance criteria check (✅/❌ per item)
### 3. Any issues or deviations
