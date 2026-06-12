"""
Kanban agent — writes today's focus tasks into the Queued column of Today Kanban.md.

Rules:
  - Never touches In Progress, Blocked, or Done columns.
  - Deduplicates against ALL columns (won't re-add a card you've moved).
  - Sources: tasks due today/overdue from Task Categories + new LogSeq inbox tasks.

Kanban file: 010 Planning/Today Kanban.md
"""

import re
import datetime
from pathlib import Path

from integrations.obsidian import ObsidianVault
import config

_KANBAN_REL    = "010 Planning/Today Kanban.md"
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


if __name__ == "__main__":
    result = run()
    print(f"Kanban refresh: {result.get('added', 0)} added, {result.get('skipped', 0)} skipped")
