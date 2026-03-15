# Dev Agent Task Prompt — T01-05

> **ACTION REQUIRED: You are a Claude Code agent with file-editing tools (Read, Edit, Write, Bash).**
> **READ the actual source files in the project, then APPLY all changes directly to disk using your tools.**
> **Do NOT output code as text blocks. Write changes to the actual files.**
> **Project root: /home/michaelhansen/Projects/github/ai_agent_assistant**
>
> Self-contained — you have no other context. Read everything here carefully before acting.
> PREREQUISITE: T01-04 must be complete (logseq_agent.py must have working parse_tasks()).

---

## Identity & Role

You are a senior software developer working on **AI Agent Assistant** — a personal CLI agent that uses local LLMs (Ollama) to manage tasks from LogSeq and Obsidian and interact with Google Calendar.

You are adding **write-back capability** to the LogSeq integration: the user should be able to add new tasks and mark tasks done directly from the CLI, with changes written to the LogSeq markdown files.

---

## Project Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| Task storage | LogSeq markdown files (direct file writes — no LogSeq app required) |
| Journal format | `journals/YYYY_MM_DD.md` |
| Task markers | `- LATER`, `- TODO`, `- DONE` |
| CLI | Rich library, existing chat loop in `main.py` |
| Config | `.env` via `config_utils.get_config_value()` |

---

## Relevant Existing Code

### logseq_agent.py — current write methods (NONE — add these)

The current `LogSeqAgent` class in `logseq_agent.py` only reads. After T01-04 it will have:
- `parse_tasks(text, source="")` — parses both LATER and TODO lines
- `get_recent_tasks(days=7)` — reads last N journal files
- `get_all_page_tasks()` — reads all pages

You need to add write methods to this class.

### main.py — chat command handler pattern

The CLI chat loop in `main.py` handles commands like this (simplified):

```python
# Inside the main chat loop
while True:
    user_input = console.input("[bold cyan]You:[/bold cyan] ").strip()

    if user_input.startswith("/"):
        cmd_parts = user_input[1:].split(" ", 1)
        cmd = cmd_parts[0].lower()
        args = cmd_parts[1] if len(cmd_parts) > 1 else ""

        if cmd == "backlog":
            # show tasks
            ...
        elif cmd == "sync":
            # sync calendar
            ...
        elif cmd == "models":
            # T01-03: show ollama models
            ...
        # ... other commands ...
        else:
            console.print(f"[yellow]Unknown command: /{cmd}[/yellow]")
        continue

    # Otherwise: send to LLM
    ...
```

---

## Your Task

**Task ID**: T01-05
**Title**: Add `/add-task` and `/done` CLI commands writing to LogSeq journal
**Sprint**: Sprint-01
**Backlog item**: BLI-005

### Description

Add two methods to `LogSeqAgent` for writing tasks, and wire them to `/add-task` and `/done` commands in the `main.py` chat loop.

### Changes to make

**`logseq_agent.py`** — add these two methods to the `LogSeqAgent` class:

```python
def add_task(self, description: str, date_key: str = None) -> str:
    """
    Append a LATER task to a journal file.
    date_key: 'YYYY_MM_DD' — defaults to today.
    Returns the path of the file written to.
    """
    if date_key is None:
        date_key = datetime.datetime.now().strftime("%Y_%m_%d")
    path = self._journal_path(date_key)
    os.makedirs(self.journals_dir, exist_ok=True)
    entry = f"\n- LATER {description}\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    return path

def mark_done(self, task_text: str, days_back: int = 14) -> bool:
    """
    Find a LATER/TODO task matching task_text in recent journals and mark it DONE.
    Searches the last days_back journal files.
    Returns True if a match was found and updated, False otherwise.
    """
    if not os.path.exists(self.journals_dir):
        return False
    files = sorted(
        [f for f in os.listdir(self.journals_dir) if re.match(r"\d{4}_\d{2}_\d{2}\.md$", f)],
        reverse=True
    )
    search = task_text.lower().strip()
    for fname in files[:days_back]:
        path = os.path.join(self.journals_dir, fname)
        text = self._read(path)
        lines = text.splitlines()
        changed = False
        new_lines = []
        for line in lines:
            m = re.match(r"^(\s*-\s+)(LATER|TODO)(\s+.*)", line)
            if m and search in m.group(3).lower():
                new_lines.append(f"{m.group(1)}DONE{m.group(3)}")
                changed = True
            else:
                new_lines.append(line)
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines))
            return True
    return False
```

**`main.py`** — add to the command handler:

```python
elif cmd == "add-task":
    if not args:
        console.print("[yellow]Usage: /add-task <task description>[/yellow]")
    else:
        logseq_dir = get_config_value("LOGSEQ_DIR", None)
        if not logseq_dir:
            console.print("[red]LOGSEQ_DIR not set in .env[/red]")
        else:
            from logseq_agent import LogSeqAgent
            ls = LogSeqAgent(logseq_dir)
            path = ls.add_task(args)
            console.print(f"[green]✅ Added to LogSeq:[/green] {args}")
            console.print(f"   → {path}")

elif cmd == "done":
    if not args:
        console.print("[yellow]Usage: /done <task text or partial match>[/yellow]")
    else:
        logseq_dir = get_config_value("LOGSEQ_DIR", None)
        if not logseq_dir:
            console.print("[red]LOGSEQ_DIR not set in .env[/red]")
        else:
            from logseq_agent import LogSeqAgent
            ls = LogSeqAgent(logseq_dir)
            found = ls.mark_done(args)
            if found:
                console.print(f"[green]✅ Marked DONE:[/green] {args}")
            else:
                console.print(f"[yellow]No matching LATER/TODO task found for:[/yellow] {args}")
```

Also update the `/help` command output (or wherever commands are listed) to include:
```
/add-task <description>   Add a LATER task to today's LogSeq journal
/done <text>              Mark a matching task as DONE in LogSeq journals
```

### Acceptance Criteria
- [ ] `LogSeqAgent.add_task(description)` appends `- LATER <description>` to today's journal file
- [ ] Creates the journal file if it does not exist
- [ ] Creates the `journals/` directory if it does not exist
- [ ] `/add-task <description>` in the CLI calls `add_task()` and confirms the file written
- [ ] `LogSeqAgent.mark_done(task_text)` finds a matching LATER/TODO task in recent journals and rewrites the line as `DONE`
- [ ] `/done <text>` in the CLI calls `mark_done()` and reports success or "not found"
- [ ] No LogSeq app needs to be running for either command
- [ ] `/help` output lists both new commands

### Out of Scope
- Do NOT implement page write-back (journals only for now)
- Do NOT implement task editing — only add and mark-done
- Do NOT add LogSeq → Obsidian sync — that is BLI-011 in sprint 2

---

## Completion Report

After applying all changes to the actual files, write a brief report covering:

### 1. Files modified
List each file you edited/created.

### 2. Acceptance criteria check
Go through each AC item and confirm ✅ or ❌ with a one-line note.

### 3. Integration notes for Sprint-02
What sprint-02 tasks need to know about the logseq_agent write API.

### 4. Any issues or deviations
Note anything you couldn't apply and why.
