# AI Scrum Team — Setup Guide

Multi-agent, multi-project Scrum system where the filesystem is the shared brain.
Any LLM team can pick up any project at any point.

---

## Quick Start

### 1. Copy this template for each project

```bash
cp -r scrum-template projects/urbanlife
cp -r scrum-template projects/winedragons
```

### 2. Configure your projects in scrum.py

```python
PROJECTS = {
    "urbanlife": {
        "path": "projects/urbanlife",
        "sm_agent": "claude",        # LLM acting as Scrum Master
        "dev_agents": {
            "dev-1": "codex",
            "dev-2": "gemini",
            "dev-3": "claude",
        },
    },
}
```

### 3. Initialise the project backlog (with your SM)

```bash
python scrum.py urbanlife chat "Let's do backlog grooming. Here are my initial user stories: ..."
```

### 4. Run sprint planning

```bash
python scrum.py urbanlife plan
```

### 5. Create task prompt files

Copy `.scrum/sprints/sprint-01/tasks/TASK-TEMPLATE.md` for each task.
Fill in the relevant code context, then run:

```bash
python scrum.py urbanlife task T01-01
python scrum.py urbanlife task T01-02
```

### 6. Daily standup

```bash
python scrum.py urbanlife standup
```

### 7. Sprint review

```bash
python scrum.py urbanlife review
```

---

## Switching Agent Teams

### Step 1 — Generate handoff doc (outgoing team)

```bash
python scrum.py urbanlife handoff --to claude
```

This writes `.scrum/handoff-sprint-XX-[date].md` with a copy-paste onboarding prompt.

### Step 2 — Update config

```python
# Before
"urbanlife": {"sm_agent": "codex", "dev_agents": {"dev-1": "gemini", ...}}

# After
"urbanlife": {"sm_agent": "claude", "dev_agents": {"dev-1": "claude", ...}}
```

### Step 3 — Onboard new team

Copy the onboarding prompt from the handoff doc and run:

```bash
python scrum.py urbanlife chat "[paste onboarding prompt here]"
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
├── sprints/
│   ├── sprint-01/
│   │   ├── plan.md         # Sprint plan — SM produces, PO approves
│   │   ├── standup-*.md    # Daily standups
│   │   ├── review.md       # Sprint review + PO approval
│   │   ├── handoff.md      # Team handoff doc (if team changed)
│   │   └── tasks/
│   │       ├── TASK-TEMPLATE.md      # Copy this for each task
│   │       ├── T01-01-prompt.md      # Input to dev agent
│   │       └── T01-01-output.md      # Dev agent response
│   └── archive/            # Completed sprints moved here
```

---

## Daily Workflow

```
Morning:
  python scrum.py <project> standup          # SM reviews overnight outputs

During day:
  python scrum.py <project> task T01-02      # Run a dev agent task
  python scrum.py <project> chat "..."       # Backlog questions, decisions

End of sprint:
  python scrum.py <project> review           # SM prepares demo
  [you review and approve in chat]
  python scrum.py <project> handoff          # If switching teams
```

---

## Agent CLI Setup

Adjust `get_agent_command()` in `scrum.py` to match your installed CLI tools:

| Agent | Install | CLI invocation |
|-------|---------|---------------|
| Claude | `npm install -g @anthropic-ai/claude-cli` | `claude --print --file prompt.md` |
| Gemini | Google CLI | `gemini -f prompt.md` |
| Codex | OpenAI CLI | `codex --file prompt.md` |
| Cursor | Cursor IDE | Check cursor docs for headless mode |

---

## Key Principle

**The filesystem is the real Scrum Master.**
The LLMs just animate it each session.
Any agent that can read markdown and write code can join any team at any time.
