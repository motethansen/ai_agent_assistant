# Dev Agent Task Prompt — T03-03

> **ACTION REQUIRED: You are a Claude Code agent with file-editing tools (Read, Edit, Write, Bash).**
> **READ the actual source files in the project, then APPLY all changes directly to disk using your tools.**
> **Do NOT output code as text blocks. Write changes to the actual files.**
> **Project root: /home/michaelhansen/Projects/github/ai_agent_assistant**

> Self-contained — no dependencies. Can run in parallel with T03-01 and T03-02.

---

## Identity & Role

You are a senior software developer on **AI Agent Assistant** — a personal CLI agent using local Ollama LLMs.

You are upgrading the evening review from a manual task-by-task confirmation into an automatic summary: scan today's completed tasks, generate a short LLM summary, print it, and optionally append it to the LogSeq journal.

---

## Relevant Existing Code

### main.py — current /review command handler (around line 721)

```python
elif command == "review":
    # Scans Obsidian and LogSeq for - [x] and DONE lines from today
    # Prints them as a list
    # Does NOT call LLM, does NOT append to journal
```

### main.py — current handle_evening_review() (around line 424)

```python
def handle_evening_review(obsidian_path):
    # Loops through unified tasks and asks "Did you complete X? (y/n)" for each
    # This is the old interactive approach — replace it
```

### main.py — --evening flag (line 1033)

```python
parser.add_argument("--evening", action="store_true", help="Start evening review mode")
# Wired to: handle_evening_review(args.file)  — replace with new function
```

### ai_orchestration.py — how to call LLM for a simple prompt

```python
def ollama_generate(prompt, model=None) -> str:
    """Sends a plain prompt to Ollama and returns the response string."""
```

### logseq_agent.py — write to journal

```python
class LogSeqAgent:
    def add_task(self, description: str, date_key: str = None) -> str:
        """Appends a LATER task line to a journal file."""
    # Use this pattern to append the summary — but write raw text, not a LATER task
    # (open the file directly with 'a' mode instead)
```

---

## Your Task

**Task ID**: T03-03
**Title**: Evening review agent with LLM summary
**Sprint**: Sprint-03
**Backlog item**: BLI-022

### Changes to make

**`main.py`** — replace `handle_evening_review()` with a new implementation:

```python
def handle_evening_review(obsidian_path):
    """Scans completed tasks from today, generates LLM summary, optionally saves to LogSeq."""
    print("🌙 Evening Review")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_logseq = datetime.datetime.now().strftime("%Y_%m_%d")
    done_tasks = []

    # 1. Scan Obsidian for - [x] lines in any .md file modified today
    workspace = get_config_value("WORKSPACE_DIR", None)
    if workspace and os.path.isdir(workspace):
        for root, _, files in os.walk(workspace):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, errors="ignore") as fh:
                    for line in fh:
                        if re.match(r"\s*- \[x\]", line):
                            task = re.sub(r"\s*- \[x\]\s*", "", line).strip()
                            if task:
                                done_tasks.append(f"[Obsidian] {task}")

    # 2. Scan LogSeq journal for DONE lines from today
    logseq_dir = get_config_value("LOGSEQ_DIR", None)
    if logseq_dir:
        jpath = os.path.join(logseq_dir, "journals", f"{today_logseq}.md")
        if os.path.exists(jpath):
            with open(jpath, errors="ignore") as fh:
                for line in fh:
                    if re.match(r"\s*- DONE", line):
                        task = re.sub(r"\s*- DONE\s*", "", line).strip()
                        if task:
                            done_tasks.append(f"[LogSeq] {task}")

    if not done_tasks:
        print("No tasks completed today.")
        return

    print(f"\n✅ {len(done_tasks)} tasks completed today:")
    for t in done_tasks:
        print(f"  • {t}")

    # 3. Generate LLM summary
    prompt = (
        f"Today is {today}. The user completed the following tasks:\n\n"
        + "\n".join(f"- {t}" for t in done_tasks)
        + "\n\nWrite a brief, encouraging 2-3 sentence daily summary. "
        "Mention the key themes of what was accomplished. Be concise and positive."
    )
    print("\n💬 Generating summary...")
    summary = ai_orchestration.ollama_generate(prompt)
    if summary:
        print(f"\n{summary}")

    # 4. Optionally append to LogSeq journal
    if logseq_dir and summary:
        try:
            save = input("\nAppend summary to today's LogSeq journal? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            save = "n"
        if save == "y":
            jpath = os.path.join(logseq_dir, "journals", f"{today_logseq}.md")
            os.makedirs(os.path.dirname(jpath), exist_ok=True)
            with open(jpath, "a", encoding="utf-8") as f:
                f.write(f"\n## Evening Review — {today}\n\n{summary}\n")
            print(f"✅ Saved to {jpath}")
```

**`main.py`** — update `/review` command handler to call `handle_evening_review()` instead of the inline scan:

```python
elif command == "review":
    handle_evening_review(obsidian_path)
```

**`main.py`** — ensure `--evening` wires to the same new function (it should already — confirm it does).

### Acceptance Criteria
- [ ] `/review` calls `handle_evening_review()` — no more inline scan block
- [ ] Scans Obsidian (`- [x]`) and LogSeq (`- DONE`) for today's completed tasks
- [ ] Calls `ai_orchestration.ollama_generate()` to produce a 2-3 sentence summary
- [ ] Summary printed to CLI
- [ ] If no tasks completed today: prints "No tasks completed today." and returns
- [ ] User prompted to append summary to LogSeq journal — writes if confirmed
- [ ] `--evening` flag triggers the same function
- [ ] Works non-interactively (cron): skips the "append?" prompt if no TTY, just prints

---

## Completion Report

### 1. Files modified
### 2. Acceptance criteria check (✅/❌ per item)
### 3. Any issues or deviations
