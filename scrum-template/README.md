# AI Scrum Team — Setup Guide

Multi-agent, multi-project Scrum system where the filesystem is the shared brain.
Any LLM team can pick up any project at any point.

---

## Key Principle

**The filesystem is the real Scrum Master.**
The LLMs just animate it each session.
Any agent that can read markdown and write code can join any team at any time.

---

## How It Works

`scrum.py` orchestrates multiple AI agents via the Claude CLI (`claude -p`).
Agents are stateless — all shared context lives in `.scrum/` markdown files.

**Two agent roles:**
- **Scrum Master (SM)** — reads all context files, facilitates ceremonies, produces plans and reports
- **Dev agents** — receive a self-contained task prompt file, output code and notes to a matching output file

**What writes to files automatically vs what you manage:**

| Command | Writes to |
|---|---|
| `plan` | `plan-draft.md` (you rename to `plan.md` to activate) |
| `task` / `sprint-run` | `T0x-xx-output.md` per task |
| `standup` | `standup-YYYY-MM-DD.md` |
| `review` | `review.md` |
| `handoff` | `handoff-sprint-XX-date.md` |
| `chat` | stdout only — no file written |

`backlog.md`, `decisions.md`, and `progress.md` are read by agents but **never written automatically**.
Use `chat` to ask the SM to produce updated content, then paste the output into the file yourself.

---

## Quick Start

### 1. Copy this template for each project

```bash
cp -r scrum-template projects/myproject
```

### 2. Register your project in scrum.py

```python
PROJECTS = {
    "myproject": {
        "path": "projects/myproject",
        "sm_agent": "claude-sm",
        "dev_agents": {
            "dev-1": "claude-dev",
            "dev-2": "claude-dev",
        },
    },
}
```

### 3. Fill in the core context files

Edit these files in `projects/myproject/.scrum/` before running any agent:

| File | What to fill in |
|---|---|
| `SM-SYSTEM-PROMPT.md` | Replace `[PROJECT NAME]` with your project name |
| `backlog.md` | Add your user stories as BLI-001, BLI-002, etc. |
| `progress.md` | Fill in project name, repo path, Product Owner name |
| `decisions.md` | Leave blank initially — SM populates as work progresses |

### 4. Verify the setup

```bash
python scrum.py myproject status   # no LLM call — just reads filesystem
```

---

## Updating the Backlog with the SM Agent

The SM reads `backlog.md` as context on every call. To update it, ask the SM to produce new content via `chat`, then paste the output into the file.

**Grooming new stories:**

```bash
python scrum.py myproject chat "Add these stories to the backlog and re-prioritize:
- As a user I want X so that Y
- As an admin I want Z so that W
Output the full updated backlog.md content."
```

Copy the SM's output and save it:

```bash
python scrum.py myproject chat "..." > /tmp/backlog-draft.md
# Review it, then:
cp /tmp/backlog-draft.md projects/myproject/.scrum/backlog.md
```

**Closing or deferring items after a sprint:**

```bash
python scrum.py myproject chat "Mark BLI-001 and BLI-002 as Done.
Move BLI-003 to Deferred with reason: 'deprioritized by PO'.
Output the full updated backlog.md."
```

---

## Sprint Lifecycle

### Sprint Planning

```bash
# SM reads backlog and proposes a sprint plan
python scrum.py myproject plan

# Review the draft
cat projects/myproject/.scrum/sprints/sprint-01/plan-draft.md

# Approve it by saving as plan.md
cp projects/myproject/.scrum/sprints/sprint-01/plan-draft.md \
   projects/myproject/.scrum/sprints/sprint-01/plan.md
```

### Creating Task Prompt Files

For each task the SM planned, copy and fill in the template:

```bash
cp projects/myproject/.scrum/sprints/sprint-01/tasks/TASK-TEMPLATE.md \
   projects/myproject/.scrum/sprints/sprint-01/tasks/T01-01-prompt.md
```

Edit `T01-01-prompt.md` and fill in:
- **Project Stack** — your tech (Python/FastAPI, PostgreSQL, etc.)
- **Relevant Existing Code** — paste the files the dev agent needs to read
- **Task Description** — exactly what to build
- **Acceptance Criteria** — what done looks like
- **Out of Scope** — explicitly prevent scope creep

Task prompts must be **fully self-contained** — dev agents receive zero other context.

### Running Tasks

```bash
# Dry-run first to see what prompt gets sent (no LLM call)
python scrum.py myproject task T01-01 --dry-run

# Run a single task
python scrum.py myproject task T01-01

# Run all pending tasks in parallel
python scrum.py myproject sprint-run

# Control parallel start delay (default 3s)
python scrum.py myproject sprint-run --stagger 5
```

Task outputs are saved to `tasks/T01-01-output.md` automatically.

### Daily Standup

```bash
# SM reviews all task outputs and produces a standup report
python scrum.py myproject standup
```

Output saved to `standup-YYYY-MM-DD.md`. Review it, then update `progress.md` if needed:

```bash
python scrum.py myproject chat "Update progress.md to reflect today's standup.
Output the full updated file content."
# paste output into projects/myproject/.scrum/progress.md
```

### Sprint Review

```bash
python scrum.py myproject review
```

SM reads all task outputs and produces `review.md`. After reviewing, update `progress.md` and `backlog.md` to reflect completed and deferred items.

---

## Updating Progress and Decisions

These files are updated manually after agent calls. Use `chat` to generate content.

**After a sprint ends:**

```bash
python scrum.py myproject chat "Update progress.md with sprint-01 results.
Completed: T01-01, T01-02. Deferred: T01-03 (reason: blocked on design).
Output the full updated file."
```

**After a significant architecture decision:**

```bash
python scrum.py myproject chat "Add an ADR to decisions.md for the following decision:
We chose SQLite over PostgreSQL for simplicity in the MVP.
Output the full updated decisions.md."
```

---

## Daily Workflow

```
Morning:
  python scrum.py <project> standup          # SM reviews task outputs

During the day:
  python scrum.py <project> task T01-02      # Run a dev agent task
  python scrum.py <project> chat "..."       # Backlog questions, grooming, decisions
  # → copy SM output → paste into backlog.md / decisions.md as needed

End of sprint:
  python scrum.py <project> review           # SM prepares sprint review
  # → review and approve output
  python scrum.py <project> chat "Update progress.md with sprint results..."
  # → paste into progress.md
  python scrum.py <project> chat "Update backlog.md — mark done items, return deferred..."
  # → paste into backlog.md
  python scrum.py <project> handoff          # If switching teams
```

---

## Switching Agent Teams

### Step 1 — Generate handoff doc (outgoing team)

```bash
python scrum.py myproject handoff --to claude
```

Writes `.scrum/handoff-sprint-XX-[date].md` with a copy-paste onboarding prompt.

### Step 2 — Update config in scrum.py

```python
# Before
"myproject": {"sm_agent": "claude-sm", "dev_agents": {"dev-1": "codex-dev"}}

# After
"myproject": {"sm_agent": "claude-sm", "dev_agents": {"dev-1": "claude-dev"}}
```

### Step 3 — Onboard new team

```bash
python scrum.py myproject chat "[paste onboarding prompt from handoff doc]"
```

The new SM reads all context files and confirms understanding before starting.

---

## File Reference

```
.scrum/
├── SM-SYSTEM-PROMPT.md     # Scrum Master role definition (agent-agnostic)
├── backlog.md              # Product backlog — you + SM maintain this
├── decisions.md            # Architecture decisions — NEVER skip updating this
├── progress.md             # Master handoff document — sprint history
└── sprints/
    ├── sprint-01/
    │   ├── plan-draft.md   # SM-generated plan awaiting PO approval
    │   ├── plan.md         # Approved sprint plan (rename from plan-draft.md)
    │   ├── standup-*.md    # Daily standup reports (auto-written)
    │   ├── review.md       # Sprint review (auto-written)
    │   ├── handoff.md      # Team handoff doc if team changed (auto-written)
    │   └── tasks/
    │       ├── TASK-TEMPLATE.md      # Copy this for each task
    │       ├── T01-01-prompt.md      # Input to dev agent (you fill this in)
    │       └── T01-01-output.md      # Dev agent response (auto-written)
    └── archive/            # Move completed sprint folders here
```

---

## Agent CLI Setup

`scrum.py` currently uses the Claude CLI for all agents. Requires:

```bash
npm install -g @anthropic-ai/claude-code
claude   # opens browser auth on first run
```

To use different CLIs per agent, modify `build_claude_cmd()` in `scrum.py`.

| Agent | Install | Notes |
|-------|---------|-------|
| Claude | `npm install -g @anthropic-ai/claude-code` | Default — used for all roles |
| Gemini | Google CLI | Modify `build_claude_cmd()` to branch by agent profile |
| Codex | OpenAI CLI | Same — pass prompt via stdin |

---

## Command Reference

```
python scrum.py <project> status                  # Show sprint state — no LLM call
python scrum.py <project> chat "<message>"        # Free-form chat with Scrum Master
python scrum.py <project> plan                    # SM proposes sprint plan
python scrum.py <project> task <task-id>          # Run one task through dev agent
python scrum.py <project> sprint-run              # Run all pending tasks in parallel
python scrum.py <project> standup                 # SM reviews outputs, produces report
python scrum.py <project> review                  # SM prepares sprint review doc
python scrum.py <project> handoff [--to <team>]   # SM writes team handoff doc

Flags:
  --dry-run          Print prompt, skip LLM call
  --model haiku|sonnet|opus   Override model
  --stagger SECONDS  Delay between parallel starts (default: 3)
```
