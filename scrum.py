#!/usr/bin/env python3
"""
scrum.py — Multi-project, multi-team Scrum orchestrator
Uses Claude Code CLI (and optionally other CLIs) via subprocess.
All agents are stateless — the .scrum/ filesystem is the shared brain.

Usage:
  python scrum.py <project> <command> [args] [--dry-run] [--model MODEL]

Commands:
  status                   Show sprint state — no LLM call
  chat   "<message>"       Free-form chat with Scrum Master (backlog grooming, Q&A)
  plan                     SM proposes sprint plan for PO approval
  task   <task-id>         Run one task prompt through its dev agent
  sprint-run               Run ALL pending tasks in current sprint (parallel)
  standup                  SM reviews task outputs and produces standup report
  review                   SM prepares sprint review doc for PO demo
  handoff [--to <team>]    SM writes team handoff doc for agent switch

Flags:
  --dry-run                Print the prompt that would be sent — no LLM call
  --model  MODEL           Override model: haiku / sonnet / opus
  --stagger SECONDS        Delay between parallel agent starts (default: 3)

Examples:
  python scrum.py demo status
  python scrum.py demo chat "Let's groom the backlog"
  python scrum.py demo plan --dry-run
  python scrum.py demo task T01-01
  python scrum.py demo sprint-run
  python scrum.py demo standup
  python scrum.py demo handoff --to claude
"""

import subprocess
import sys
import json
import argparse
import threading
import time
from pathlib import Path
from datetime import date


# ── Agent model assignments ───────────────────────────────────────────────────
# sm_model  : more reasoning needed → sonnet
# dev_model : change to "haiku" if you hit rate limits during sprint-run

AGENT_MODELS = {
    "claude-sm":  "sonnet",
    "claude-dev": "sonnet",   # swap to "haiku" for faster/cheaper dev tasks
}

# ── Project registry ──────────────────────────────────────────────────────────

PROJECTS = {
    "urbanlife": {
        "path": "projects/urbanlife",
        "sm_agent": "claude-sm",
        "dev_agents": {
            "dev-1": "claude-dev",
            "dev-2": "claude-dev",
            "dev-3": "claude-dev",
        },
    },
    "winedragons": {
        "path": "projects/winedragons",
        "sm_agent": "claude-sm",
        "dev_agents": {
            "dev-1": "claude-dev",
            "dev-2": "claude-dev",
        },
    },
    "cheersfriends": {
        "path": "projects/cheersfriends",
        "sm_agent": "claude-sm",
        "dev_agents": {
            "dev-1": "claude-dev",
            "dev-2": "claude-dev",
        },
    },
    # Minimal test project — use this first to verify everything works
    "demo": {
        "path": "projects/demo",
        "sm_agent": "claude-sm",
        "dev_agents": {
            "dev-1": "claude-dev",
        },
    },
    # AI Agent Assistant — root of this repo
    "agent": {
        "path": ".",
        "sm_agent": "claude-sm",
        "dev_agents": {
            "dev-1": "claude-dev",
            "dev-2": "claude-dev",
        },
    },
}


# ── Claude CLI invocation ─────────────────────────────────────────────────────

def build_claude_cmd(model: str) -> list[str]:
    """
    claude -p                         non-interactive print mode — exits after one response
    --model MODEL                     haiku | sonnet | opus
    --output-format text              plain text stdout — easiest to capture and save
    --dangerously-skip-permissions    allow all tool calls (file writes, bash, etc.)
                                      without prompting — required for unattended agents

    Prompt is always passed via stdin to avoid shell-escaping issues with
    long prompts. No API key needed — uses your Claude.ai login via claude auth.
    """
    return [
        "claude",
        "-p",
        "--model", model,
        "--output-format", "text",
        "--dangerously-skip-permissions",
    ]


# ── Core runner ───────────────────────────────────────────────────────────────

def run_agent(
    agent_profile: str,
    prompt: str,
    output_file: Path | None = None,
    label: str = "",
    dry_run: bool = False,
    model_override: str | None = None,
) -> str:
    model   = model_override or AGENT_MODELS.get(agent_profile, "sonnet")
    display = label or agent_profile

    if dry_run:
        separator = "=" * 60
        print(f"\n{separator}")
        print(f"🔍 DRY RUN — {display}  (model: {model})")
        print(separator)
        print(prompt[:3000])
        if len(prompt) > 3000:
            print(f"\n... [truncated — full prompt: {len(prompt)} chars]")
        print(f"{separator}\n")
        return "[dry-run — no output]"

    cmd = build_claude_cmd(model)
    print(f"\n🤖 [{display}]  claude -p --model {model} ...")

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print(f"⏱️  [{display}] timed out after 5 minutes")
        return "[error: timeout]"
    except FileNotFoundError:
        print("\n❌  'claude' command not found.")
        print("    Install : npm install -g @anthropic-ai/claude-code")
        print("    Auth    : claude   (opens browser on first run)")
        sys.exit(1)

    if result.returncode != 0:
        print(f"⚠️  [{display}] exit {result.returncode}")
        if result.stderr:
            print(f"    stderr: {result.stderr[:400]}")

    output = result.stdout.strip()

    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(output)
        print(f"💾 [{display}]  → {output_file}")

    return output


# ── Context helpers ───────────────────────────────────────────────────────────

def build_sm_context(scrum_dir: Path) -> str:
    """Read core .scrum files into a single context block for the SM."""
    core_files = [
        "SM-SYSTEM-PROMPT.md",
        "progress.md",
        "backlog.md",
        "decisions.md",
    ]

    current = find_current_sprint(scrum_dir)
    if current:
        core_files.append(f"sprints/{current}/plan.md")
        sprint_dir = scrum_dir / "sprints" / current
        for s in sorted(sprint_dir.glob("standup-*.md"))[-2:]:
            core_files.append(f"sprints/{current}/{s.name}")

    ctx = f"# Scrum Master Context — {date.today()}\n\n"
    for fname in core_files:
        p = scrum_dir / fname
        content = p.read_text() if p.exists() else "[not yet created]"
        ctx += f"\n{'─'*60}\n## {fname}\n\n{content}\n"
    return ctx


def find_current_sprint(scrum_dir: Path) -> str | None:
    sprints_dir = scrum_dir / "sprints"
    if not sprints_dir.exists():
        return None
    sprints = sorted([
        d.name for d in sprints_dir.iterdir()
        if d.is_dir() and d.name.startswith("sprint-") and d.name != "archive"
    ])
    return sprints[-1] if sprints else None


def next_sprint_name(scrum_dir: Path) -> str:
    current = find_current_sprint(scrum_dir)
    if not current:
        return "sprint-01"
    return f"sprint-{int(current.split('-')[1]) + 1:02d}"


def today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


def get_task_outputs(tasks_dir: Path) -> str:
    if not tasks_dir.exists():
        return "No task outputs found."
    outputs = sorted(tasks_dir.glob("*-output.md"))
    if not outputs:
        return "No task outputs yet."
    result = ""
    for f in outputs:
        result += f"\n\n{'─'*40}\n### {f.stem.replace('-output','')}\n\n{f.read_text()}"
    return result


def get_pending_tasks(tasks_dir: Path) -> list[Path]:
    """Prompt files without a matching output file."""
    if not tasks_dir.exists():
        return []
    return [
        p for p in sorted(tasks_dir.glob("*-prompt.md"))
        if not (tasks_dir / p.name.replace("-prompt", "-output")).exists()
    ]


def task_seq(task_id: str) -> int:
    """T01-02 → 1  (0-indexed, for round-robin dev assignment)."""
    try:
        return int(task_id.split("-")[-1]) - 1
    except (ValueError, IndexError):
        return 0


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_status(project, cfg, **_):
    scrum_dir = Path(cfg["path"]) / ".scrum"
    current   = find_current_sprint(scrum_dir)
    sep = "=" * 60

    print(f"\n{sep}")
    print(f"📊 {project}")
    print(f"   Path      : {cfg['path']}")
    print(f"   SM        : {cfg['sm_agent']}  (model: {AGENT_MODELS.get(cfg['sm_agent'],'?')})")
    devs = {slot: f"{a} ({AGENT_MODELS.get(a,'?')})" for slot, a in cfg['dev_agents'].items()}
    for slot, info in devs.items():
        print(f"   {slot}      : {info}")
    print(f"   Sprint    : {current or 'none — run plan first'}")

    if current:
        sprint_dir = scrum_dir / "sprints" / current
        tasks_dir  = sprint_dir / "tasks"
        prompts    = sorted(tasks_dir.glob("*-prompt.md")) if tasks_dir.exists() else []
        print(f"\n   Tasks ({len(prompts)}):")
        for p in prompts:
            tid = p.stem.replace("-prompt", "")
            done = (tasks_dir / f"{tid}-output.md").exists()
            print(f"     {'✅' if done else '⬜'}  {tid}")
        standups = list(sprint_dir.glob("standup-*.md"))
        print(f"\n   Standups : {len(standups)}")
        print(f"   Review   : {'✅' if (sprint_dir/'review.md').exists() else '—'}")
    print()


def cmd_chat(project, cfg, extra, dry_run, model_override, **_):
    if not extra:
        print("❌  python scrum.py <project> chat \"your message\"")
        sys.exit(1)
    scrum_dir = Path(cfg["path"]) / ".scrum"
    prompt = f"""{build_sm_context(scrum_dir)}

{'='*60}
## PRODUCT OWNER MESSAGE

{extra}

{'='*60}
Respond as Scrum Master. Be concise and structured.
"""
    out = run_agent(cfg["sm_agent"], prompt, label="SM", dry_run=dry_run, model_override=model_override)
    print("\n" + "="*60)
    print(out)


def cmd_plan(project, cfg, dry_run, model_override, **_):
    scrum_dir   = Path(cfg["path"]) / ".scrum"
    next_sprint = next_sprint_name(scrum_dir)
    prompt = f"""{build_sm_context(scrum_dir)}

{'='*60}
## YOUR TASK: Sprint Planning

Date        : {today_str()}
Next sprint : {next_sprint}
Dev agents  : {json.dumps(cfg['dev_agents'], indent=2)}

1. Review the backlog — pick the highest-priority items for a 1-week sprint
2. Write a one-sentence sprint goal
3. Break items into tasks (IDs like T{next_sprint.split('-')[1]}-01, -02 ...)
4. Assign each task to a dev slot
5. State clear acceptance criteria per task

Output a task table + per-task acceptance criteria.
End with: "Awaiting Product Owner approval."
"""
    sprint_dir = Path(cfg["path"]) / ".scrum" / "sprints" / next_sprint
    sprint_dir.mkdir(parents=True, exist_ok=True)
    out = run_agent(cfg["sm_agent"], prompt,
                    output_file=None if dry_run else sprint_dir / "plan-draft.md",
                    label="SM:plan", dry_run=dry_run, model_override=model_override)
    print("\n" + "="*60)
    print(out)
    if not dry_run:
        print(f"\n📝 Draft saved → {sprint_dir}/plan-draft.md")
        print(f"   Approve and save as: {sprint_dir}/plan.md")
        print(f"   Then add task prompts in: {sprint_dir}/tasks/")


def cmd_task(project, cfg, extra, dry_run, model_override, **_):
    if not extra:
        print("❌  python scrum.py <project> task T01-01")
        sys.exit(1)
    task_id   = extra
    scrum_dir = Path(cfg["path"]) / ".scrum"
    current   = find_current_sprint(scrum_dir)
    if not current:
        print("❌ No active sprint.")
        sys.exit(1)

    tasks_dir   = scrum_dir / "sprints" / current / "tasks"
    prompt_file = tasks_dir / f"{task_id}-prompt.md"
    if not prompt_file.exists():
        print(f"❌ Not found: {prompt_file}")
        print("   Create from TASK-TEMPLATE.md")
        sys.exit(1)

    dev_slots = list(cfg["dev_agents"].values())
    agent     = dev_slots[task_seq(task_id) % len(dev_slots)]

    print(f"📋 {task_id}  →  {agent} (model: {AGENT_MODELS.get(agent,'sonnet')})")
    out = run_agent(agent, prompt_file.read_text(),
                    output_file=tasks_dir / f"{task_id}-output.md",
                    label=f"dev:{task_id}", dry_run=dry_run, model_override=model_override)
    print("\n" + "="*60)
    print(out)


def cmd_sprint_run(project, cfg, dry_run, model_override, stagger, **_):
    scrum_dir = Path(cfg["path"]) / ".scrum"
    current   = find_current_sprint(scrum_dir)
    if not current:
        print("❌ No active sprint.")
        sys.exit(1)

    tasks_dir = scrum_dir / "sprints" / current / "tasks"
    pending   = get_pending_tasks(tasks_dir)

    if not pending:
        print(f"✅ All tasks complete.  Run: python scrum.py {project} standup")
        return

    dev_slots = list(cfg["dev_agents"].values())
    results   = {}
    lock      = threading.Lock()
    threads   = []

    print(f"\n🚀 sprint-run: {current}  —  {len(pending)} pending task(s)")
    print(f"   stagger: {stagger}s   dry-run: {dry_run}\n")

    def run_one(pf: Path, agent: str, idx: int):
        tid = pf.stem.replace("-prompt", "")
        out = run_agent(agent, pf.read_text(),
                        output_file=tasks_dir / f"{tid}-output.md",
                        label=f"dev-{idx+1}:{tid}",
                        dry_run=dry_run, model_override=model_override)
        with lock:
            results[tid] = "✅" if out and not out.startswith("[error") else "❌"

    for i, pf in enumerate(pending):
        tid   = pf.stem.replace("-prompt", "")
        agent = dev_slots[task_seq(tid) % len(dev_slots)]
        t     = threading.Thread(target=run_one, args=(pf, agent, i), daemon=True)
        threads.append(t)
        print(f"  ▶ {tid}  →  {agent}")
        t.start()
        if i < len(pending) - 1:
            time.sleep(stagger)

    print(f"\n⏳ Waiting for {len(threads)} agent(s)...")
    for t in threads:
        t.join()

    print(f"\n{'='*60}")
    for tid, status in results.items():
        print(f"  {status}  {tid}")
    print(f"\nNext:  python scrum.py {project} standup")


def cmd_standup(project, cfg, dry_run, model_override, **_):
    scrum_dir  = Path(cfg["path"]) / ".scrum"
    current    = find_current_sprint(scrum_dir)
    if not current:
        print("❌ No active sprint.")
        sys.exit(1)
    sprint_dir = scrum_dir / "sprints" / current
    prompt = f"""{build_sm_context(scrum_dir)}

{'='*60}
## YOUR TASK: Daily Standup — {today_str()}

Sprint: {current}

For each task: Status / Acceptance criteria met? / Blockers / Next action.
End with sprint health summary and any PO actions needed.

## Task Outputs
{get_task_outputs(sprint_dir / 'tasks')}
"""
    out = run_agent(cfg["sm_agent"], prompt,
                    output_file=sprint_dir / f"standup-{today_str()}.md",
                    label="SM:standup", dry_run=dry_run, model_override=model_override)
    print("\n" + "="*60)
    print(out)


def cmd_review(project, cfg, dry_run, model_override, **_):
    scrum_dir  = Path(cfg["path"]) / ".scrum"
    current    = find_current_sprint(scrum_dir)
    if not current:
        print("❌ No active sprint.")
        sys.exit(1)
    sprint_dir = scrum_dir / "sprints" / current
    prompt = f"""{build_sm_context(scrum_dir)}

{'='*60}
## YOUR TASK: Sprint Review — {current}

Date: {today_str()}

Produce the review.md document:
1. Was the sprint goal achieved?
2. Completed items
3. Deferred items + reason + backlog return
4. Demo summary for Product Owner
5. Sprint History entry for progress.md
6. Next sprint candidates

## All Task Outputs
{get_task_outputs(sprint_dir / 'tasks')}
"""
    out = run_agent(cfg["sm_agent"], prompt,
                    output_file=sprint_dir / "review.md",
                    label="SM:review", dry_run=dry_run, model_override=model_override)
    print("\n" + "="*60)
    print(out)


def cmd_handoff(project, cfg, to_team, dry_run, model_override, **_):
    scrum_dir = Path(cfg["path"]) / ".scrum"
    current   = find_current_sprint(scrum_dir)
    prompt = f"""{build_sm_context(scrum_dir)}

{'='*60}
## YOUR TASK: Team Handoff

Current team : {cfg['sm_agent']} SM + devs {list(cfg['dev_agents'].values())}
Incoming team: {to_team or 'any LLM team — write generically'}
Sprint       : {current or 'none yet'}
Date         : {today_str()}

Write a complete handoff document:
1. What works / what is incomplete / what was just completed
2. Critical things the incoming team must know
3. Files to read in order
4. Open questions
5. Ready-to-paste onboarding prompt for the incoming Scrum Master

Incoming team has ZERO prior context — be thorough.
"""
    sprint_label = current or "pre-sprint"
    out_path     = scrum_dir / f"handoff-{sprint_label}-{today_str()}.md"
    out = run_agent(cfg["sm_agent"], prompt,
                    output_file=None if dry_run else out_path,
                    label="SM:handoff", dry_run=dry_run, model_override=model_override)
    print("\n" + "="*60)
    print(out)
    if not dry_run:
        print(f"\n✅ Saved → {out_path}")
        print(f"\nTo switch teams:")
        print(f"  1. Edit PROJECTS['{project}'] sm_agent / dev_agents in scrum.py")
        print(f"  2. python scrum.py {project} chat \"[paste onboarding prompt]\"")


# ── CLI wiring ────────────────────────────────────────────────────────────────

COMMANDS = {
    "status":     cmd_status,
    "chat":       cmd_chat,
    "plan":       cmd_plan,
    "task":       cmd_task,
    "sprint-run": cmd_sprint_run,
    "standup":    cmd_standup,
    "review":     cmd_review,
    "handoff":    cmd_handoff,
}

def main():
    parser = argparse.ArgumentParser(
        description="AI Scrum orchestrator — Claude CLI multi-agent teams",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("project", help=f"Project: {list(PROJECTS.keys())}")
    parser.add_argument("command", choices=COMMANDS.keys())
    parser.add_argument("extra",   nargs="?", default="",
                        help="Task ID (task cmd) or quoted message (chat cmd)")
    parser.add_argument("--to",      dest="to_team", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print prompt, skip LLM call")
    parser.add_argument("--model",   dest="model_override", default=None,
                        choices=["haiku", "sonnet", "opus"])
    parser.add_argument("--stagger", type=float, default=3.0,
                        help="Seconds between parallel starts (sprint-run)")
    args = parser.parse_args()

    if args.project not in PROJECTS:
        print(f"❌ Unknown project '{args.project}'")
        print(f"   Available: {list(PROJECTS.keys())}")
        sys.exit(1)

    cfg = PROJECTS[args.project]

    # Auto-create project directory structure if missing
    scrum_dir = Path(cfg["path"]) / ".scrum"
    if not scrum_dir.exists():
        print(f"📁 Creating project structure at {cfg['path']} ...")
        (scrum_dir / "sprints" / "sprint-01" / "tasks").mkdir(parents=True)
        (Path(cfg["path"]) / "src").mkdir(exist_ok=True)
        (Path(cfg["path"]) / "tests").mkdir(exist_ok=True)
        print("   Done. Populate .scrum/ files from the template before running plan.")

    COMMANDS[args.command](
        project        = args.project,
        cfg            = cfg,
        extra          = args.extra,
        dry_run        = args.dry_run,
        model_override = args.model_override,
        to_team        = args.to_team,
        stagger        = args.stagger,
    )

if __name__ == "__main__":
    main()
