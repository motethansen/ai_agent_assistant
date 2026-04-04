# Installation Guide

## Quick Start

```bash
python main.py          # Launch interactive CLI chat
python main.py --backlog # Print task list and exit
python main.py --plan    # Run calendar planning session
python main.py --plan --dry-run  # Preview plan without booking
```

This project requires setting up a few local and cloud components to function as an AI agent assistant.

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) installed locally.
- [Docker](https://www.docker.com/) (to run n8n for calendar/automation).

## Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd ai_agent_assistant
    ```

2.  **Run the Self-Repairing Installation Script:**
    We provide a robust `install.sh` script to automate your setup.
    ```bash
    chmod +x install.sh
    ./install.sh
    ```
    This script will:
    - **Verify Dependencies:** Ensure Python 3.11+, Git, and Ollama are present.
    - **Prepare Environment:** Create `.venv` and install all required libraries.
    - **Manage Services:** Start Ollama and automatically pull the configured `OLLAMA_MODEL` (default: `llama3`).
    - **Configure System:** Guide you through `.config` creation (API keys, paths).
    - **Warming & Verification:** Pre-load the AI model and run a full diagnostic to ensure the assistant is working.

3.  **Local Services (Ollama):**
    - The system is **Local-First**. It will always try to use your local Ollama instance before hitting cloud APIs.
    - You can manually manage services using: `./scripts/manage_services.sh {start|check}`.

4.  **Configure `.config`:**
    Open `.config` (managed by the installer) and refine your settings:
    - `LLM_PRIORITY`: Set your preferred model order (e.g., `ollama,gemini,openai,claude`).
    - `OLLAMA_MODEL`: The local model to use (e.g., `llama3`, `mistral`, `qwen2.5:14b`).
    - `GEMINI_API_KEY`: Optional cloud fallback.
    - `CALENDAR_ID`: Usually 'primary' or a specific ID.

5. **Google Calendar, Tasks, and Gmail (via n8n):**
    Google credentials live in n8n's credential store — no `token.json` or
    `credentials.json` files are needed in the Python project.
    See **[docs/GOOGLE_SETUP.md](docs/GOOGLE_SETUP.md)** for the full step-by-step guide:
    - Create a Google Cloud project and enable the required APIs
    - Configure the OAuth consent screen and create OAuth 2.0 credentials
    - Add credentials in n8n and wire them into workflows
    - Set `ENABLE_GOOGLE_TASKS=true` and/or `ENABLE_GMAIL=true` in `.config`


## LogSeq Setup

If you use [LogSeq](https://logseq.com/) for note-taking, the assistant can read your pending tasks directly from your graph.

### 1. Find your graph path

Your LogSeq graph is a folder on disk that contains `journals/` and `pages/` subdirectories.

| Platform | Typical location |
|----------|-----------------|
| Linux    | `/home/yourname/logseq/my-graph` |
| macOS    | `/Users/yourname/Documents/LogSeq/my-graph` |
| Windows  | `C:\Users\yourname\Documents\LogSeq\my-graph` |

Open LogSeq → **Settings → Graphs** to see the exact path.

### 2. Set LOGSEQ_DIR in .env / .config

```
# LOGSEQ_DIR: Path to your LogSeq graph folder (the one containing journals/ and pages/).
# Linux example:  LOGSEQ_DIR=/home/yourname/logseq/my-graph
# Mac example:    LOGSEQ_DIR=/Users/yourname/Documents/LogSeq/my-graph
LOGSEQ_DIR=/home/yourname/logseq/my-graph
```

### 3. Task format

The assistant parses tasks that start with `- LATER` or `- TODO` (standard LogSeq task markers):

```markdown
- LATER Write sprint retrospective notes
- TODO Review pull request #42
  :category: dev
  :url: https://github.com/...
```

Optional indented properties (`:category:`, `:url:`, etc.) are picked up automatically.

### 4. View your backlog

```bash
python3 main.py --backlog
```

This merges tasks from LogSeq journals (last 14 days), LogSeq pages, Obsidian, and Apple Reminders into one list.

## Scheduled Planning (cron / systemd)

### cron

Add to your crontab (`crontab -e`):

```
0 8 * * 1-5 cd /home/michaelhansen/Projects/github/ai_agent_assistant && python main.py --plan >> /tmp/ai-plan.log 2>&1
```

### systemd timer

Create `/etc/systemd/user/ai-plan.service`:

```ini
[Unit]
Description=AI Agent morning planning

[Service]
Type=oneshot
WorkingDirectory=/home/michaelhansen/Projects/github/ai_agent_assistant
ExecStart=/home/michaelhansen/Projects/github/ai_agent_assistant/.venv/bin/python main.py --plan
```

Create `/etc/systemd/user/ai-plan.timer`:

```ini
[Unit]
Description=Run AI planning daily at 08:00

[Timer]
OnCalendar=Mon-Fri 08:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable: `systemctl --user enable --now ai-plan.timer`


## Obsidian Setup

If you use [Obsidian](https://obsidian.md/) for note-taking, the assistant can read and update your tasks directly from your vault's markdown files — **the Obsidian app does not need to be running**.

### 1. Find your vault path

Your Obsidian vault is a folder on disk that contains `.md` files (and optionally subdirectories).

| Platform | Typical location |
|----------|-----------------|
| Linux    | `/home/yourname/Documents/Obsidian` |
| macOS    | `/Users/yourname/Documents/Obsidian` |

Open Obsidian → **Settings → About** → **Vault path** to see the exact path.

### 2. Set WORKSPACE_DIR in .config

```
# WORKSPACE_DIR: Path to your Obsidian vault directory (contains .md files).
# The Obsidian app does NOT need to be running — tasks are read directly from disk.
# Linux example: WORKSPACE_DIR=/home/yourname/Documents/Obsidian
# Mac example:   WORKSPACE_DIR=/Users/yourname/Documents/Obsidian
WORKSPACE_DIR=/home/yourname/Documents/Obsidian
```

### 3. Supported task formats

The assistant parses standard Obsidian/markdown checkbox syntax:

```markdown
- [ ] Incomplete task
- [x] Completed task
- [ ] Task with category #dev
- [ ] Task with due date 📅 2026-04-01
```

### 4. View your backlog

```bash
python3 main.py --backlog
```

Obsidian tasks appear alongside LogSeq and Apple Reminders, grouped by source file.

### 5. Mark a task done

In the interactive chat, use:

```
/done <partial task text>
```

The assistant checks LogSeq first, then Obsidian. It will report which system the task was marked done in.

## Terminal Reminders

Set a one-off reminder from the terminal:

    python scripts/remind.py "Call dentist" "14:30"

This will:
- Schedule a macOS notification at the given time (macOS only, requires `at` command)
- Log the reminder to `logs/reminders.log`
- Send a webhook event to n8n if `N8N_WEBHOOK_URL` is configured

To enable the `at` command on macOS:

    sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.atrun.plist

## Calendar Sync

The local calendar is stored at `datainput/local_calendar.ics` in RFC 5545 `.ics` format.

Export from the CLI:

```text
/export-calendar
/export-calendar ~/myfile.ics
```

Import the exported file into other calendar apps:

- Google Calendar: Settings → Import → select the `.ics` file
- Apple Calendar: File → Import → select the `.ics` file

To pull events from Google Calendar into the local calendar, first export the calendar from Google as an `.ics` file, then import it in the assistant:

```text
/import-calendar
/import-calendar ~/Downloads/google-calendar.ics
```

## LM Studio

[LM Studio](https://lmstudio.ai/) is an optional second local inference backend alongside Ollama.

### 1. Download and install

Download LM Studio from [lmstudio.ai](https://lmstudio.ai/) and install it for your platform.

### 2. Load a model

Open LM Studio, browse the model catalogue, and download a model (e.g. `mistral-7b-instruct`).

### 3. Enable the local server

In LM Studio, open the **Local Server** tab (the `<->` icon) and click **Start Server**. It listens on port `1234` by default.

### 4. Set config keys

In your `.config` file:

```
ENABLE_LM_STUDIO=true
LM_STUDIO_MODEL=mistral-7b-instruct-v0.3
```

LM Studio appears between Ollama and Gemini in the default fallback chain, so it is tried automatically when Ollama is unavailable.

### 5. Headless use (Linux server)

For Linux servers without a GUI, the LM Studio inference engine can run headlessly:

```bash
lms daemon start
```

This starts the inference engine without the GUI. You must have run the LM Studio GUI on the machine at least once first to register the `lms` CLI and accept the licence.

### 6. Verify

```bash
python scripts/status.py
```

Look for `lm_studio: ok` in the output.

## n8n Setup (workflow automation)

n8n runs as a Docker container and handles event-driven workflows between your
local data sources and external services (calendar, tasks, morning plans).

### 1. Start n8n

```bash
docker compose up -d n8n
```

UI: http://localhost:5679 (port controlled by `N8N_PORT` in `.config`)

### 2. Import workflows

1. Open http://localhost:5679
2. Top-right menu → **Import from file**
3. Import each file from `n8n-workflows/`:
   - `morning-planning.json`
   - `add-task.json`
   - `backlog-digest.json`
   - `universal_task_sync.json`
   - `google_tasks_sync.json`
4. Open each imported workflow → toggle **Active** (top-right switch)

### 3. Start the Python API server (n8n callback target)

```bash
python api_server.py
```

Listens on port 5678 (`WEBHOOK_PORT` in `.config`). n8n workflows call back to
this server to add tasks, fetch the backlog, and trigger planning.

### 4. Verify

```bash
./run.sh
/sync-universal
```

n8n logs should show: `POST /webhook/task-sync received`

Check service health:

```bash
python scripts/status.py
```

### 5. Persistent service

```bash
./service.sh install   # macOS launchd / Linux systemd unit
```

The daemon starts the API server and keeps it running across reboots.

---

## NanoClaw Setup (optional — containerised agent isolation)

NanoClaw runs ObsidianAgent inside an isolated Docker container so it can only access the Obsidian vault directory — nothing else on the host filesystem.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed and running (`docker info` should succeed)
- `WORKSPACE_DIR` in `.config` must be an absolute path on the host

### Enable NanoClaw

Add to `.config`:
```
NANOCLAW_ENABLED=true
```

When `NANOCLAW_ENABLED=false` (the default), all existing code runs unchanged — zero Docker dependency.

### Build the Skill image

```bash
docker compose --profile nanoclaw build
```

Only needs to be re-run when `obsidian_agent.py` changes.

### Test the Skill manually

```bash
# List all .md files in your vault
docker compose run --rm \
  --volume "${WORKSPACE_DIR}:/vault:ro" \
  obsidian_skill list_files

# Find all incomplete tasks
docker compose run --rm \
  --volume "${WORKSPACE_DIR}:/vault:ro" \
  obsidian_skill find_tasks
```

You should see JSON output. If the container is not built yet, run the `build` step above first.

### Notes

- The container can only access `WORKSPACE_DIR` — it cannot reach any other host path
- Mutation actions (`create_file`, `update_file`) require `write=True` in the Python call, which switches the mount to `:rw`
- The `obsidian_skill` service uses `profiles: [nanoclaw]` — it is **not** started by `docker compose up`

---

## Running the Assistant

```bash
python3 main.py
```
