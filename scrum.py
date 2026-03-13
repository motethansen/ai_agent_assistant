#!/usr/bin/env python3
"""
scrum.py — Multi-project, multi-team Scrum orchestrator

Usage:
  python scrum.py <project> <command> [options]

Commands:
  standup              Run daily standup (SM reads task outputs, reports status)
  plan                 Start sprint planning session with SM
  task <task-id>       Run a specific task against its assigned dev agent
  review               Prepare sprint review
  handoff              Generate handoff doc for team switch
  chat                 Open free-form chat with SM (for backlog grooming etc.)
  status               Show current sprint status (no LLM call)

Examples:
  python scrum.py urbanlife standup
  python scrum.py urbanlife task T01-02
  python scrum.py winedragons plan
  python scrum.py urbanlife handoff --to claude
"""

import subprocess
import sys
import json
import argparse
from pathlib import Path
from datetime import date, datetime


# ── Project registry ──────────────────────────────────────────────────────────
# Add your projects here. sm_agent is the LLM for the Scrum Master.
# dev_agents maps logical dev slots to LLM CLI tools.

PROJECTS = {
    "urbanlife": {
        "path": "projects/urbanlife",
        "sm_agent": "claude",
        "dev_agents": {
            "dev-1": "codex",
            "dev-2": "gemini",
            "dev-3": "claude",
        },
    },
    "winedragons": {
        "path": "projects/winedragons",
        "sm_agent": "gemini",
        "dev_agents": {
            "dev-1": "claude",
            "dev-2": "codex",
        },
    },
    "cheersfriends": {
        "path": "projects/cheersfriends",
        "sm_agent": "claude",
        "dev_agents": {
            "dev-1": "claude",
            "dev-2": "gemini",
        },
    },
}

# ── Agent CLI commands ─────────────────────────────────────────────────────────
# Adjust these to match how your CLI tools actually accept input.
# Each should accept a file path and return output to stdout.

def get_agent_command(agent: str, prompt_file: str) -> list[str]:
    commands = {
        "claude":  ["claude", "--print", "--file", prompt_file],
        "gemini":  ["gemini", "-f", prompt_file],
        "codex":   ["codex", "--file", prompt_file],
        "cursor":  ["cursor", "--headless", prompt_file],  # if cursor supports CLI
    }
    if agent not in commands:
        raise ValueError(f"Unknown agent: {agent}. Add it to get_agent_command().")
    return commands[agent]


# ── Core runner ───────────────────────────────────────────────────────────────

def run_agent(agent: str, prompt_file: Path, output_file: Path | None = None) -> str:
    """Run a prompt file against an agent CLI. Optionally save output."""
    print(f"\n🤖 Running {agent} with {prompt_file.name}...")
    
    cmd = get_agent_command(agent, str(prompt_file))
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    output = result.stdout
    if result.returncode != 0:
        print(f"⚠️  Agent returned error:\n{result.stderr}")
    
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(output)
        print(f"💾 Output saved to {output_file}")
    
    return output


def build_sm_context(scrum_dir: Path, extra_files: list[str] = []) -> str:
    """Build context string from core scrum files for SM prompt."""
    core_files = [
        "SM-SYSTEM-PROMPT.md",
        "progress.md",
        "backlog.md",
        "decisions.md",
    ]
    
    # Add current sprint plan if it exists
    current_sprint = find_current_sprint(scrum_dir)
    if current_sprint:
        core_files.append(f"sprints/{current_sprint}/plan.md")
    
    context = f"# Scrum Master Context — {date.today()}\n\n"
    
    for fname in core_files + extra_files:
        p = scrum_dir / fname
        if p.exists():
            context += f"\n\n---\n## {fname}\n\n{p.read_text()}"
        else:
            context += f"\n\n---\n## {fname}\n\n[File not yet created]\n"
    
    return context


def find_current_sprint(scrum_dir: Path) -> str | None:
    """Find the most recent non-archived sprint."""
    sprints_dir = scrum_dir / "sprints"
    if not sprints_dir.exists():
        return None
    
    sprints = sorted([
        d.name for d in sprints_dir.iterdir()
        if d.is_dir() and d.name.startswith("sprint-") and d.name != "archive"
    ])
    return sprints[-1] if sprints else None


def today_str() -> str:
    return date.today().strftime("%Y-%m-%d")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_standup(project: str, cfg: dict):
    """Run daily standup — SM reviews task outputs and reports."""
    scrum_dir = Path(cfg["path"]) / ".scrum"
    current_sprint = find_current_sprint(scrum_dir)
    
    if not current_sprint:
        print("❌ No active sprint found. Run 'plan' first.")
        return
    
    sprint_dir = scrum_dir / "sprints" / current_sprint
    
    # Gather task output files for SM to review
    task_outputs = ""
    tasks_dir = sprint_dir / "tasks"
    if tasks_dir.exists():
        for output_file in sorted(tasks_dir.glob("*-output.md")):
            task_id = output_file.stem.replace("-output", "")
            task_outputs += f"\n\n## Output: {task_id}\n{output_file.read_text()}"
    
    context = build_sm_context(scrum_dir)
    prompt = f"""{context}

---
## Your Task: Daily Standup

Today's date: {today_str()}
Sprint: {current_sprint}

Review the task outputs below and produce a standup report.
Save your report — it will be written to sprints/{current_sprint}/standup-{today_str()}.md

{task_outputs if task_outputs else "No task outputs found yet."}

Produce the standup report now in the format specified in SM-SYSTEM-PROMPT.md.
"""
    
    prompt_file = scrum_dir / "_tmp_standup_prompt.md"
    prompt_file.write_text(prompt)
    
    output_file = sprint_dir / f"standup-{today_str()}.md"
    output = run_agent(cfg["sm_agent"], prompt_file, output_file)
    
    prompt_file.unlink()  # clean up temp file
    print("\n" + "="*60)
    print(output)


def cmd_task(project: str, cfg: dict, task_id: str):
    """Run a specific task prompt against its assigned dev agent."""
    scrum_dir = Path(cfg["path"]) / ".scrum"
    current_sprint = find_current_sprint(scrum_dir)
    
    if not current_sprint:
        print("❌ No active sprint found.")
        return
    
    tasks_dir = scrum_dir / "sprints" / current_sprint / "tasks"
    prompt_file = tasks_dir / f"{task_id}-prompt.md"
    
    if not prompt_file.exists():
        print(f"❌ Prompt file not found: {prompt_file}")
        print(f"   Create it first using the TASK-TEMPLATE.md")
        return
    
    # Determine which agent runs this task (from plan.md or ask user)
    plan_file = scrum_dir / "sprints" / current_sprint / "plan.md"
    agent = infer_agent_for_task(task_id, plan_file, cfg["dev_agents"])
    
    print(f"📋 Task: {task_id}")
    print(f"🤖 Agent: {agent}")
    
    output_file = tasks_dir / f"{task_id}-output.md"
    output = run_agent(agent, prompt_file, output_file)
    
    print("\n" + "="*60)
    print(output)


def infer_agent_for_task(task_id: str, plan_file: Path, dev_agents: dict) -> str:
    """Try to read agent assignment from plan.md, fall back to dev-1."""
    if plan_file.exists():
        content = plan_file.read_text()
        for line in content.splitlines():
            if task_id in line:
                for slot, agent in dev_agents.items():
                    if slot in line or agent in line:
                        return agent
    return dev_agents.get("dev-1", "claude")


def cmd_plan(project: str, cfg: dict):
    """Start sprint planning — interactive session with SM."""
    scrum_dir = Path(cfg["path"]) / ".scrum"
    context = build_sm_context(scrum_dir)
    
    prompt = f"""{context}

---
## Your Task: Sprint Planning

Today's date: {today_str()}

You are starting a new sprint planning session with the Product Owner.

1. Review the backlog and identify candidate items
2. Propose a sprint goal
3. Select items that fit the sprint
4. Break items into concrete tasks
5. Propose the sprint plan for Product Owner approval

Available dev agents: {json.dumps(cfg['dev_agents'], indent=2)}

Begin by proposing the sprint goal and candidate items.
Wait for Product Owner approval before finalizing.
"""
    
    prompt_file = scrum_dir / "_tmp_plan_prompt.md"
    prompt_file.write_text(prompt)
    
    output = run_agent(cfg["sm_agent"], prompt_file)
    prompt_file.unlink()
    
    print("\n" + "="*60)
    print(output)
    print("\n" + "="*60)
    print("📝 Review the plan above, then manually create:")
    print(f"   {scrum_dir}/sprints/sprint-XX/plan.md")
    print("   and the task prompt files in tasks/")


def cmd_review(project: str, cfg: dict):
    """Prepare sprint review."""
    scrum_dir = Path(cfg["path"]) / ".scrum"
    current_sprint = find_current_sprint(scrum_dir)
    
    if not current_sprint:
        print("❌ No active sprint found.")
        return
    
    sprint_dir = scrum_dir / "sprints" / current_sprint
    
    # Collect all task outputs
    task_outputs = ""
    tasks_dir = sprint_dir / "tasks"
    if tasks_dir.exists():
        for output_file in sorted(tasks_dir.glob("*-output.md")):
            task_id = output_file.stem.replace("-output", "")
            task_outputs += f"\n\n## {task_id} Output\n{output_file.read_text()}"
    
    context = build_sm_context(scrum_dir)
    prompt = f"""{context}

---
## Your Task: Sprint Review Preparation

Sprint: {current_sprint}
Date: {today_str()}

Review all task outputs and produce:
1. A sprint review document (completed vs planned, demo summary)
2. A list of items to return to backlog
3. Updated progress.md content
4. Recommended candidates for next sprint

Task outputs:
{task_outputs if task_outputs else "No task outputs found."}

Format your response as the review.md document.
"""
    
    prompt_file = scrum_dir / "_tmp_review_prompt.md"
    prompt_file.write_text(prompt)
    
    output_file = sprint_dir / "review.md"
    output = run_agent(cfg["sm_agent"], prompt_file, output_file)
    prompt_file.unlink()
    
    print("\n" + "="*60)
    print(output)


def cmd_handoff(project: str, cfg: dict, to_agent: str | None = None):
    """Generate handoff document for team switch."""
    scrum_dir = Path(cfg["path"]) / ".scrum"
    current_sprint = find_current_sprint(scrum_dir)
    
    context = build_sm_context(scrum_dir)
    prompt = f"""{context}

---
## Your Task: Generate Team Handoff

Current team: {cfg['sm_agent']} (SM), {cfg['dev_agents']}
Incoming team: {to_agent or 'unspecified — write generically'}
Sprint: {current_sprint}
Date: {today_str()}

Generate a complete handoff document following the format in sprints/sprint-01/handoff.md.
Include the copy-paste onboarding prompt for the incoming Scrum Master.
Be thorough — the incoming team has no context beyond what you write.
"""
    
    prompt_file = scrum_dir / "_tmp_handoff_prompt.md"
    prompt_file.write_text(prompt)
    
    sprint_label = current_sprint or "latest"
    output_file = scrum_dir / f"handoff-{sprint_label}-{today_str()}.md"
    output = run_agent(cfg["sm_agent"], prompt_file, output_file)
    prompt_file.unlink()
    
    print("\n" + "="*60)
    print(output)
    print(f"\n✅ Handoff doc saved to: {output_file}")
    print("   Update PROJECTS config to switch the team, then run:")
    print(f"   python scrum.py {project} chat")


def cmd_chat(project: str, cfg: dict, message: str):
    """Free-form chat with SM (backlog grooming, questions, etc.)."""
    scrum_dir = Path(cfg["path"]) / ".scrum"
    context = build_sm_context(scrum_dir)
    
    prompt = f"""{context}

---
## Product Owner Message

{message}

Respond as Scrum Master.
"""
    
    prompt_file = scrum_dir / "_tmp_chat_prompt.md"
    prompt_file.write_text(prompt)
    
    output = run_agent(cfg["sm_agent"], prompt_file)
    prompt_file.unlink()
    
    print("\n" + "="*60)
    print(output)


def cmd_status(project: str, cfg: dict):
    """Show current sprint status without calling any LLM."""
    scrum_dir = Path(cfg["path"]) / ".scrum"
    current_sprint = find_current_sprint(scrum_dir)
    
    print(f"\n📊 Project: {project}")
    print(f"   Path: {cfg['path']}")
    print(f"   SM Agent: {cfg['sm_agent']}")
    print(f"   Dev Agents: {cfg['dev_agents']}")
    print(f"   Current Sprint: {current_sprint or 'None'}")
    
    if current_sprint:
        sprint_dir = scrum_dir / "sprints" / current_sprint
        tasks_dir = sprint_dir / "tasks"
        
        if tasks_dir.exists():
            prompts = list(tasks_dir.glob("*-prompt.md"))
            outputs = list(tasks_dir.glob("*-output.md"))
            print(f"\n   Tasks with prompts: {len(prompts)}")
            print(f"   Tasks with outputs: {len(outputs)}")
            
            for p in sorted(prompts):
                task_id = p.stem.replace("-prompt", "")
                has_output = (tasks_dir / f"{task_id}-output.md").exists()
                icon = "✅" if has_output else "⬜"
                print(f"     {icon} {task_id}")
        
        standups = sorted(sprint_dir.glob("standup-*.md"))
        print(f"\n   Standups logged: {len(standups)}")


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrum orchestrator for multi-agent LLM teams")
    parser.add_argument("project", help="Project name (must be in PROJECTS)")
    parser.add_argument("command", choices=["standup", "plan", "task", "review", "handoff", "chat", "status"])
    parser.add_argument("extra", nargs="?", help="Extra arg: task ID for 'task', message for 'chat'")
    parser.add_argument("--to", help="Target agent team for handoff command")
    
    args = parser.parse_args()
    
    if args.project not in PROJECTS:
        print(f"❌ Unknown project: {args.project}")
        print(f"   Available: {list(PROJECTS.keys())}")
        sys.exit(1)
    
    cfg = PROJECTS[args.project]
    
    match args.command:
        case "standup":  cmd_standup(args.project, cfg)
        case "plan":     cmd_plan(args.project, cfg)
        case "review":   cmd_review(args.project, cfg)
        case "status":   cmd_status(args.project, cfg)
        case "handoff":  cmd_handoff(args.project, cfg, args.to)
        case "task":
            if not args.extra:
                print("❌ Provide task ID: python scrum.py <project> task T01-01")
                sys.exit(1)
            cmd_task(args.project, cfg, args.extra)
        case "chat":
            if not args.extra:
                print("❌ Provide message: python scrum.py <project> chat \"your message\"")
                sys.exit(1)
            cmd_chat(args.project, cfg, args.extra)


if __name__ == "__main__":
    main()
