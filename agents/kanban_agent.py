"""
Kanban agent — the board is a two-way surface between the user and the agents.

Outbound (agent → board): run() writes today's focus tasks into the Queued
column. Never touches In Progress, Blocked, or Done; dedupes across ALL columns.

Inbound (board → agent): process_board() reads user cards from Queued and acts:
  /command …    → run the command (plan, sync, done), reply in 🤖 Agent column
  ends with "?" → answer via LLM with task context, reply in 🤖 Agent column
Processed cards are removed from Queued and tracked by hash in
output/.kanban_processed.json so each fires exactly once.

Kanban file: 010 Planning/Today Kanban.md
"""

import re
import json
import hashlib
import datetime
from pathlib import Path

from integrations.obsidian import ObsidianVault
import config

_KANBAN_REL    = config.paths.kanban_board()
_CATEGORIES_REL = "010 Planning/Task Categories.md"
_PLANNER_REL   = "010 Planning/Planner.md"

# Matches a task checkbox line anywhere in the kanban file
_TASK_RE = re.compile(r'^\s*- \[[ x]\] (.+)', re.IGNORECASE)
# Matches a column heading
_COL_RE  = re.compile(r'^## (.+)')
# Obsidian Tasks due-date emoji
_DUE_RE  = re.compile(r'📅\s*(\d{4}-\d{2}-\d{2})')


def _fingerprint(text: str) -> str:
    """Short case-insensitive key for dedup — first 60 non-emoji chars."""
    clean = re.sub(r'[^\w\s]', '', text.lower())
    return ' '.join(clean.split())[:60]


def _parse_kanban(content: str) -> dict[str, list[str]]:
    """
    Parse kanban file into {column_name: [raw_lines]}.
    Preserves blank lines inside a column.
    """
    cols: dict[str, list[str]] = {}
    current = None
    for line in content.splitlines():
        m = _COL_RE.match(line)
        if m:
            current = m.group(1).strip()
            cols[current] = []
        elif current is not None and not line.startswith('%%') and not line.startswith('```'):
            cols[current].append(line)
    return cols


def _all_existing_fingerprints(cols: dict[str, list[str]]) -> set[str]:
    fps = set()
    for lines in cols.values():
        for l in lines:
            m = _TASK_RE.match(l)
            if m:
                fps.add(_fingerprint(m.group(1)))
    return fps


def _rewrite_kanban(content: str, new_queued_lines: list[str]) -> str:
    """
    Replace the Queued column body with new_queued_lines.
    Everything else (frontmatter, other columns, settings block) is preserved.
    """
    queued_col_re = re.compile(r'^## 📥 Queued\s*$', re.MULTILINE)
    next_col_re   = re.compile(r'^## ', re.MULTILINE)

    m = queued_col_re.search(content)
    if not m:
        return content  # column not found — don't corrupt the file

    after_heading = content[m.end():]
    # Find where the next column starts
    nxt = next_col_re.search(after_heading)
    if nxt:
        rest = after_heading[nxt.start():]
    else:
        rest = ""

    queued_body = "\n".join(new_queued_lines) + "\n\n" if new_queued_lines else "\n"
    return content[:m.end()] + "\n\n" + queued_body + rest


def _collect_due_tasks(vault: ObsidianVault, today: datetime.date) -> list[str]:
    """Pull overdue + today tasks from Task Categories and Planner."""
    tasks = []
    for rel in [_CATEGORIES_REL, _PLANNER_REL]:
        text = vault.read_file(rel) or ""
        for line in text.splitlines():
            if not re.match(r'\s*- \[ \]', line):
                continue
            m = _DUE_RE.search(line)
            if not m:
                continue
            due = datetime.date.fromisoformat(m.group(1))
            if due <= today:
                # Strip leading whitespace/dash to normalise
                clean = re.sub(r'^\s*- \[ \]\s*', '', line).strip()
                tasks.append(f"- [ ] {clean}")
    return tasks


def _collect_inbox_tasks(vault: ObsidianVault) -> list[str]:
    """
    Pull tagged inbox tasks from the agent:inbox section.
    Only includes tasks that carry an explicit #kanban tag — avoids
    dumping every research link onto the board.
    """
    inbox = vault.read_section("inbox") or ""
    lines = []
    for line in inbox.splitlines():
        if re.match(r'\s*- \[ \]', line) and '#kanban' in line.lower():
            lines.append(line.strip())
    return lines


def run(push_inbox: bool = True, push_due: bool = True) -> dict:
    """
    Refresh the Queued column with today's tasks.
    Returns {'added': N, 'skipped': N}.
    """
    vault  = ObsidianVault()
    today  = datetime.date.today()

    kanban_path = vault.vault_dir / _KANBAN_REL
    if not kanban_path.exists():
        return {"error": f"{_KANBAN_REL} not found in vault"}

    content = kanban_path.read_text(encoding="utf-8")
    cols    = _parse_kanban(content)
    existing_fps = _all_existing_fingerprints(cols)

    candidates: list[str] = []
    if push_due:
        candidates += _collect_due_tasks(vault, today)
    if push_inbox:
        candidates += _collect_inbox_tasks(vault)

    added, skipped = 0, 0
    new_lines = list(cols.get("📥 Queued", []))
    # Drop blank trailing lines before appending
    while new_lines and not new_lines[-1].strip():
        new_lines.pop()

    for line in candidates:
        m = _TASK_RE.match(line)
        if not m:
            continue
        fp = _fingerprint(m.group(1))
        if fp in existing_fps:
            skipped += 1
            continue
        new_lines.append(line)
        existing_fps.add(fp)
        added += 1

    if added:
        new_content = _rewrite_kanban(content, new_lines)
        kanban_path.write_text(new_content, encoding="utf-8")

    return {"added": added, "skipped": skipped}


def add_task(task_text: str) -> bool:
    """
    Add a single task card to the Queued column immediately.
    Returns True on success.
    """
    vault = ObsidianVault()
    kanban_path = vault.vault_dir / _KANBAN_REL
    if not kanban_path.exists():
        return False

    content = kanban_path.read_text(encoding="utf-8")
    cols    = _parse_kanban(content)
    existing_fps = _all_existing_fingerprints(cols)

    fp = _fingerprint(task_text)
    if fp in existing_fps:
        return False  # already there

    new_lines = list(cols.get("📥 Queued", []))
    while new_lines and not new_lines[-1].strip():
        new_lines.pop()
    new_lines.append(f"- [ ] {task_text.strip()}")

    new_content = _rewrite_kanban(content, new_lines)
    kanban_path.write_text(new_content, encoding="utf-8")
    return True


# ── Inbound: board → agent ────────────────────────────────────────────────────

_AGENT_COL = "🤖 Agent"
_STATE_FILE = Path(config.paths.output()) / ".kanban_processed.json"
_MAX_HASHES = 2000


def _load_processed() -> set[str]:
    try:
        return set(json.loads(_STATE_FILE.read_text()))
    except (OSError, ValueError):
        return set()


def _save_processed(hashes: set[str]) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(sorted(hashes)[-_MAX_HASHES:]))


def _card_hash(text: str) -> str:
    return hashlib.sha1(text.strip().lower().encode()).hexdigest()[:12]


def _stamp() -> str:
    return datetime.datetime.now().strftime("%m-%d %H:%M")


def _rewrite_column(content: str, column: str, new_lines: list[str]) -> str:
    """Replace one column's body, preserving everything else."""
    col_re = re.compile(rf'^## {re.escape(column)}\s*$', re.MULTILINE)
    m = col_re.search(content)
    if not m:
        # Column missing — insert it before the settings block (or append).
        body = f"\n\n## {column}\n\n" + "\n".join(new_lines) + "\n"
        settings = content.find("%% kanban:settings")
        if settings != -1:
            return content[:settings] + body + "\n" + content[settings:]
        return content + body
    after = content[m.end():]
    nxt = re.search(r'^## |^%% kanban', after, re.MULTILINE)
    rest = after[nxt.start():] if nxt else ""
    body = "\n".join(new_lines) + "\n\n" if new_lines else "\n"
    return content[:m.end()] + "\n\n" + body + rest


def _run_board_command(cmd_line: str) -> str:
    """Execute a safe subset of slash commands from a board card."""
    parts = cmd_line[1:].split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "plan":
        from agents import planning_agent
        mode = "week" if arg.strip() == "week" else "today"
        planning_agent.run(mode)
        return f"{mode} plan written to Planner"
    if cmd == "sync":
        from agents import sync_agent
        r = sync_agent.run()
        return f"sync done — {r.get('tasks_added', 0)} tasks, {r.get('notes_added', 0)} notes"
    if cmd == "done":
        ok = ObsidianVault().mark_task_done(arg)
        return f"marked done: {arg}" if ok else f"no task matched: {arg}"
    if cmd == "kanban":
        r = run()
        return f"board refreshed — {r.get('added', 0)} added"
    return f"unsupported board command: /{cmd} (try /plan, /sync, /done, /kanban)"


def _answer_question(question: str) -> str:
    from llm import router
    today = datetime.date.today()
    soon = today + datetime.timedelta(days=7)
    tasks = [
        t for t in ObsidianVault().get_tasks()
        if t.get("due_date") and t["due_date"] <= soon
    ]
    tasks.sort(key=lambda t: (t["due_date"], t.get("priority_weight", 99)))
    lines = [
        f"- {t['text']} (due {t['due_date']}, {t.get('priority') or 'no priority'})"
        for t in tasks[:40]
    ]
    prompt = (
        f"Today is {today.isoformat()}.\n"
        f"Due/overdue/upcoming tasks:\n" + ("\n".join(lines) or "(none)") + "\n\n"
        f"Question from the user's kanban board — answer in ONE short line, "
        f"max 250 chars, no headers: {question}"
    )
    return router.ask(prompt, task="quick").strip().replace("\n", " ")


def process_board() -> dict:
    """Act on user command/question cards in Queued. Returns counts."""
    vault = ObsidianVault()
    kanban_path = vault.vault_dir / _KANBAN_REL
    if not kanban_path.exists():
        return {"error": f"{_KANBAN_REL} not found in vault"}

    content = kanban_path.read_text(encoding="utf-8")
    cols = _parse_kanban(content)
    queued = cols.get("📥 Queued", [])
    processed = _load_processed()

    replies: list[str] = []
    remaining: list[str] = []
    handled = 0
    for line in queued:
        m = _TASK_RE.match(line)
        card = m.group(1).strip() if m else ""
        is_actionable = card.startswith("/") or card.rstrip().endswith("?")
        h = _card_hash(card) if card else ""
        if not (m and is_actionable) or h in processed:
            remaining.append(line)
            continue
        if card.startswith("/"):
            try:
                result = _run_board_command(card)
            except Exception as exc:  # never corrupt the board on a failed command
                result = f"error: {exc}"
            replies.append(f"- [ ] 🤖 {_stamp()} · `{card}` → {result}")
        else:
            try:
                answer = _answer_question(card)
            except Exception as exc:
                answer = f"error: {exc}"
            replies.append(f"- [ ] 💬 {_stamp()} · {card} → {answer}")
        processed.add(h)
        handled += 1

    if handled:
        content = _rewrite_column(content, "📥 Queued", remaining)
        agent_lines = replies + [
            l for l in _parse_kanban(content).get(_AGENT_COL, []) if l.strip()
        ][:20]  # keep the agent column short — newest on top
        content = _rewrite_column(content, _AGENT_COL, agent_lines)
        kanban_path.write_text(content, encoding="utf-8")
        _save_processed(processed)

    return {"handled": handled}


def post_focus_card() -> str | None:
    """Post a 'top 3 focus' card to the 🤖 Agent column (morning cron)."""
    from llm import router
    today = datetime.date.today()
    tasks = [
        t for t in ObsidianVault().get_tasks()
        if t.get("due_date") and t["due_date"] <= today
    ]
    if not tasks:
        return None
    tasks.sort(key=lambda t: (t.get("priority_weight", 99), t["due_date"]))
    lines = [f"- {t['text']} (due {t['due_date']})" for t in tasks[:20]]
    prompt = (
        f"Today is {today.isoformat()}. From these due/overdue tasks pick the "
        f"TOP 3 to focus on, one short line each, max 300 chars total, plain text:\n"
        + "\n".join(lines)
    )
    focus = router.ask(prompt, task="quick").strip().replace("\n", " · ")

    vault = ObsidianVault()
    kanban_path = vault.vault_dir / _KANBAN_REL
    if not kanban_path.exists():
        return None
    content = kanban_path.read_text(encoding="utf-8")
    agent_lines = [f"- [ ] 🎯 {_stamp()} · Focus: {focus}"] + [
        l for l in _parse_kanban(content).get(_AGENT_COL, []) if l.strip()
    ][:20]
    kanban_path.write_text(_rewrite_column(content, _AGENT_COL, agent_lines), encoding="utf-8")
    return focus


if __name__ == "__main__":
    result = run()
    print(f"Kanban refresh: {result.get('added', 0)} added, {result.get('skipped', 0)} skipped")
    result = process_board()
    print(f"Board commands: {result.get('handled', 0)} handled")
