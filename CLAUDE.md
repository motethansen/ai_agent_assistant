# ai_agent_assistant — Claude Code Guide

> Read this at session start. It tells Claude what this project is, how to run it, and how to log progress into the user's Obsidian vault.

## What this project is

A **local-first personal AI assistant** that bridges Markdown notes (Obsidian + LogSeq), Apple Calendar, and task lists — all from the terminal, powered by local LLMs. Optimized for headless, low-memory operation on Apple Silicon and Linux.

- **Reads** tasks from Obsidian + LogSeq (`LATER` / `TODO` markers), Apple Reminders
- **Writes** schedule into Apple Calendar, daily plans back into Obsidian
- **Runs** offline by default; cloud LLMs are fallback only
- **Triggers** the full planning pipeline from n8n on weekdays at 08:00

**Primary LLM:** Ollama (local, headless).
**Fallback chain:** Ollama → Groq → Gemini → OpenAI → Claude.

## Key entry points

```bash
./run.sh            # main planning pipeline (reads notes, generates plan, writes back)
./install.sh        # idempotent install (creates venv, pulls Ollama models, wires cron)
python main.py      # bypass run.sh wrapper
pytest              # full test suite
```

Config lives in `.config` (env-var style — see `config.example` and `config.template`). Key vars: `WORKSPACE_DIR`, `LOGSEQ_DIR`, `OBSIDIAN_API_KEY`, `OLLAMA_MODEL`, plus optional cloud keys.

## Project layout

```
agents/             # one-purpose agents (calendar, obsidian, reminders, planner, …)
llm/                # provider adapters + fallback chain orchestration
integrations/       # Apple Calendar (AppleScript), Reminders (AppleScript), n8n (HTTP)
ui/                 # terminal UI — month-grid calendar view, task list
datainput/          # cached snapshots (reminders.json, …)
output/             # generated plans, summaries
projects/           # project-specific outputs (per-project digests live here)
scripts/            # one-off ops scripts
docs/               # PROJECT_OVERVIEW.md, GOOGLE_SETUP.md
PLAN.md             # phased dev plan (Phase 1–7 done; later phases in flight)
```

## Conventions

- **Local-first.** Any feature that requires a cloud key must work without one (degraded but functional).
- **No silent network calls.** Every outbound call (Ollama, Groq, Gemini, n8n, Obsidian REST API) logs to `output/run.log` with provider, model, latency, status.
- **Time zone: user's local.** Apple Calendar uses local time; never serialize as UTC into a markdown plan.
- **Markdown is the source of truth.** When state changes, the obsidian/logseq files are updated last — they're the durable record.

## Vault logging — Obsidian as second brain

This project's purpose **is** to be the second-brain plumbing, so the logging contract is doubly important here. After each meaningful unit of work, write a progress entry into the vault.

**Vault root:** `/Users/michaelhansen/Library/Mobile Documents/iCloud~md~obsidian/Documents/`

**Project home in vault:**
- Hub note: `400 Projects/Coding/ai_agent_assistant/ai_agent_assistant.md` (index)
- Progress log: `400 Projects/Coding/ai_agent_assistant/progress.md` (rolling, append-only)
- Daily journal: `150 Journal/<YYYY-MM-DD>-<Weekday>.md` (e.g. `2026-04-30-Thursday.md`)

### When to write a progress entry

Append to `progress.md` after:
- Adding or renaming an agent in `agents/`
- Adding a new LLM provider to the fallback chain
- Changing the planning prompt (record the **why** — these prompts are load-bearing)
- A new integration (Apple Reminders, n8n trigger, Obsidian REST API endpoint, etc.)
- Any cron / n8n schedule change
- Resolving a quota / rate-limit issue with a cloud provider

Skip for typos, formatter passes, `pip install` upgrades without behaviour change.

### Entry format

```markdown
## 2026-04-30 — short title

What changed (1–2 sentences). Why it mattered (1 sentence). Next step or open question (1 sentence).

**Phase:** Phase 7 (Obsidian round-trip) · **Module:** agents/ / llm/ / integrations/ · **Branch/PR:** `branch-name` (#42)
```

Then a one-line bullet in today's daily journal:

```markdown
- 🤖 ai_agent_assistant — short title — see [[ai_agent_assistant/progress|progress]]
```

### How to actually write it

**Preferred — via the obsidian MCP server** (or directly via the Obsidian Local REST API, which this project already integrates):

```python
# pseudo — use the project's existing obsidian agent
from agents.obsidian import append
append(
    "400 Projects/Coding/ai_agent_assistant/progress.md",
    "\n\n## 2026-04-30 — short title\n\n…body…\n",
)
append(
    f"150 Journal/{today}-{weekday}.md",
    f"\n- 🤖 ai_agent_assistant — short title — see [[ai_agent_assistant/progress|progress]]\n",
    create_if_missing=True,
)
```

**Fallback — direct file write** under `/Users/michaelhansen/Library/Mobile Documents/iCloud~md~obsidian/Documents/`.

### What not to put in the vault

- API keys (OpenAI, Groq, Gemini, HuggingFace, Claude, Cloudflare) — those live in `400 Projects/Credentials/AI Assistant.md` only
- Apple ID credentials — never log
- The full text of a private journal page being processed — log only metadata (path, line count, agent run)

### Special: this project's own digest agent

[[Development insights 2026-04|Development insights]] mentions a planned "second-brain digest" agent that walks the user's project repos every morning at 08:00 and writes summaries into `150 Journal/`. When that agent ships, **its first action on each run is to write into the same `progress.md` files described above** — so the contract here is what the digest agent will follow.

## End-of-session checkpoint

Before wrapping a Claude Code session, glance at `400 Projects/Coding/ai_agent_assistant/progress.md` and confirm a new entry exists if the session did anything meaningful.
