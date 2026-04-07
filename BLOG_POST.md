# Building a Local-First AI Productivity Agent: Lessons from a Year in the Terminal

## The Problem I Was Trying to Solve

I have three places my work lives: **Obsidian** (long-form notes and projects), **LogSeq** (daily journals and quick capture), and a **calendar**. Every Monday I was spending 20 minutes manually copying tasks between them, figuring out what was overdue, and trying to build a plan for the week.

What I actually wanted was simple: a system that reads everything, knows what's overdue, and helps me decide what to do today — without sending my private notes to a cloud service.

This post documents how I built that, what I learned, and what you need to install before it'll work on your machine.

---

## What the System Does Today

- Reads `LATER` and `TODO` tasks from LogSeq journals and pages
- Syncs Apple Reminders into an Obsidian planner file
- Detects overdue tasks (Python date comparison, not LLM guesswork) and surfaces them at the top of the planner under `## 🚨 Overdue`
- Categorises tasks by your focus areas using an LLM
- Generates a day-by-day AI weekly plan using your calendar and pending tasks
- Pushes events to your local ICS calendar and optionally to Apple Calendar via `osascript`
- Runs all of this hourly via a cron job
- Exposes a terminal chat interface with 40+ slash commands

All processing runs locally by default via LM Studio. No notes leave your machine.

---

## What You Need to Install First

This section is the one I wish existed when I started. Nothing in `requirements.txt` tells you that you need a running LLM before the whole thing makes sense.

### 1. Python 3.11 or later

The project uses `match` statements and `datetime.date.fromisoformat()` features that require 3.11+.

```bash
# macOS
brew install python@3.12

# Ubuntu / Debian
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.12 python3.12-venv
```

### 2. A Local LLM — LM Studio (recommended) or Ollama

This is the non-obvious one. The agent doesn't work without an LLM backend. You have two choices:

**LM Studio** (what I use on macOS):
- Download from [lmstudio.ai](https://lmstudio.ai)
- Open the app, search for a model (I use `qwen2.5-coder-7b-instruct-mlx` on Apple Silicon)
- Click Load, then go to Local Server → Start Server
- The server runs on `http://localhost:1234`
- Set `ENABLE_LM_STUDIO=true` and `LM_STUDIO_MODEL=<your model name>` in `.config`

**Ollama** (better for Linux / headless servers):
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:14b      # or any model you prefer
```
- Set `ENABLE_OLLAMA=true`, `OLLAMA_MODEL=qwen2.5:14b` in `.config`

You can also configure cloud LLMs (Gemini, OpenAI, Claude) as fallbacks. If you hit a free-tier rate limit, the CLI will tell you clearly and suggest switching providers rather than dumping a JSON error blob.

### 3. Your Notes Folders

The agent reads Obsidian and LogSeq as plain markdown files — neither app needs to be running. You just need the folders to exist.

Set these in `.config`:
```
WORKSPACE_DIR=/path/to/your/obsidian/vault
LOGSEQ_DIR=/path/to/your/logseq/graph
```

On macOS with iCloud sync, these are typically deep inside `~/Library/Mobile Documents/`. The `config.example` file shows the exact path format.

### 4. Docker or OrbStack (optional, for automation)

The n8n workflow engine handles scheduled automation and the Google Calendar/Tasks connector. It runs as a Docker container.

On macOS I recommend [OrbStack](https://orbstack.dev) — it's faster and lighter than Docker Desktop, and the `docker` CLI works identically.

```bash
# Once Docker/OrbStack is running:
docker compose up -d n8n      # starts n8n at http://localhost:5679
python api_server.py           # starts the Python webhook server on port 5678
```

### 5. Apple Calendar access (macOS only, optional)

The `/add-event` command can push events directly into Apple Calendar via `osascript`. You need to grant Terminal access:

**System Settings → Privacy & Security → Automation → Terminal → Calendar: on**

The first time `/add-event` runs it will launch Calendar.app and prompt for approval if not already granted.

---

## Architecture: How the Pieces Fit Together

```
LogSeq journals ──┐
Apple Reminders ──┼──► cron_job.py ──► Planner.md (Obsidian)
Google Tasks ─────┘         │
                            ▼
                   LM Studio (local LLM)
                   - re-organises planner
                   - detects overdue tasks
                   - generates weekly plan
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
       local ICS      Apple Calendar    datainput/
       calendar       (osascript)      calendar_suggestions.md
              │
              ▼
         n8n (Docker)
         - morning planning cron
         - Google Calendar connector
         - Universal Task Sync
```

The terminal chat (`./run.sh`) sits in front of all of this. You can inspect any layer, run agents on demand, or just ask the LLM a question in plain English.

---

## Lessons Learned

### Lesson 1: Don't trust the LLM for date arithmetic

My first overdue-task detector sent the whole planner to the LLM and asked it to figure out what was overdue. It was unreliable — models would miss tasks or hallucinate dates.

The fix was to scan for `📅 YYYY-MM-DD` patterns in Python before touching the LLM:

```python
def _find_overdue_tasks(content):
    today = datetime.date.today()
    overdue = []
    date_pattern = re.compile(r'📅\s*(\d{4}-\d{2}-\d{2})')
    for line in content.splitlines():
        if not re.match(r'\s*-\s*\[ \]', line):  # open tasks only
            continue
        m = date_pattern.search(line)
        if m:
            due = datetime.date.fromisoformat(m.group(1))
            if due < today:
                overdue.append((line.strip(), m.group(1)))
    return overdue
```

The LLM then receives a reliable list: "these 3 tasks are overdue — put them in `## 🚨 Overdue` at the top." It just has to format and categorise, not reason about dates.

### Lesson 2: Free tier rate limits are invisible until they hit

I was using Gemini as a fallback and it worked great — until it didn't. When the free-tier quota runs out mid-session, the raw API error is 400 lines of JSON. I wrapped the error handler to catch `429`/`RESOURCE_EXHAUSTED` and surface one line:

```
⚠  gemini/gemini-2.0-flash: rate-limit / quota exceeded.
   Try /ask lmstudio <query> or switch to gemini-1.5-flash in .config.
```

The lesson: cloud APIs are useful fallbacks but not reliable primaries if you're on a free tier. Run a local LLM first.

### Lesson 3: The Calendar app needs to be running to receive events

`osascript` can create Apple Calendar events, but if Calendar.app isn't open you get a cryptic `-600` error. The fix is to launch the app first and wait:

```python
subprocess.run(["open", "-a", "Calendar"])
time.sleep(2)  # let it initialise
# now run the osascript
```

### Lesson 4: `install.sh` on re-runs used to add duplicate cron jobs

The original install script always appended a new cron line on every run. After two installs you'd have two cron jobs firing simultaneously and corrupting the planner. The fix was to check for an existing entry first:

```bash
EXISTING_CRON=$(crontab -l 2>/dev/null | grep "cron_job.py" || true)
if [ -n "$EXISTING_CRON" ]; then
    # show it, ask to keep or replace
fi
```

### Lesson 5: The virtual environment is not optional

If you're syncing your vault via iCloud or Syncthing, do **not** sync the `.venv` folder. Keep it local and recreate it from `requirements.txt` on each machine. Otherwise you end up with binary conflicts and path errors that are very hard to debug.

Add `.venv/` to your `.gitignore` (it already is in this repo) and to your sync exclusion list.

### Lesson 6: Per-task LLM routing matters

Sending every request to the same model is wasteful. Task parsing (extract bullet points from markdown) is simple — a small fast model handles it fine. Weekly plan generation needs more reasoning — a larger model does better.

The `.config` routing keys let you send different task types to different models:
```
ROUTING_PARSING=lmstudio       # fast, local
ROUTING_PLANNING=lmstudio      # same model, but could be gemini for heavier reasoning
ROUTING_CHAT=lmstudio
```

And `/ask <provider> <query>` lets you route a single question to any provider without changing the config.

---

## The Stack Today

| Layer | Technology |
|---|---|
| Local LLM | LM Studio (`qwen2.5-coder-7b-instruct-mlx`) |
| LLM fallback | Gemini → OpenAI → Claude |
| Notes | Obsidian + LogSeq (plain `.md` files) |
| Calendar | Local ICS file + Apple Calendar (`osascript`) |
| Task sync | Python agents + n8n workflows |
| Automation | cron + n8n (Docker) |
| Vector search | ChromaDB (for RAG over notes and books) |
| Container agents | NanoClaw (Docker-isolated skills for Obsidian/LogSeq) |
| Terminal UI | Rich library + custom chat loop |

---

## What's Next

The project is now at a stable base. Remaining work:

- **Sprint 07**: Migrate Google Calendar and Tasks OAuth out of Python and into n8n's credential store — so no `token.json` or `credentials.json` lives in the project folder
- **LM Studio SDK**: Replace the OpenAI-compat HTTP calls with the official `lmstudio` Python SDK for streaming and proper timeout handling

If you want to run this yourself, clone the repo, read the **Dependencies** section in `README.md`, copy `config.example` to `.config`, fill in your paths and model name, and run `./install.sh`.

The system is genuinely useful once it's running. The morning cron fires, the planner gets updated, overdue tasks bubble to the top, and the day has a shape before I've opened a browser.

---

*Full source: [github.com/yourusername/ai_agent_assistant](https://github.com/yourusername/ai_agent_assistant)*
