import os
import re
import datetime

from config_utils import get_config_value

_TASK_RE = re.compile(r"^(\s*)-\s+\[([ xX])\]\s+(.*)")

# ---------------------------------------------------------------------------
# Obsidian Tasks plugin — emoji metadata markers
# ---------------------------------------------------------------------------

# Priority: emoji → (label, sort weight — lower = more urgent)
PRIORITY_MAP = {
    "🔺": ("highest", 0),
    "⏫": ("high",    1),
    "🔼": ("medium",  2),
    "🔽": ("low",     3),
    "⏬": ("lowest",  4),
}

_DUE_RE       = re.compile(r'📅\s*(\d{4}-\d{2}-\d{2})')
_SCHEDULED_RE = re.compile(r'⏳\s*(\d{4}-\d{2}-\d{2})')
_START_RE     = re.compile(r'🛫\s*(\d{4}-\d{2}-\d{2})')
_CREATED_RE   = re.compile(r'➕\s*(\d{4}-\d{2}-\d{2})')
_DONE_RE      = re.compile(r'✅\s*(\d{4}-\d{2}-\d{2})')


def _parse_date(m) -> "datetime.date | None":
    if not m:
        return None
    try:
        return datetime.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def parse_task_metadata(raw_line: str) -> dict:
    """
    Parse an Obsidian task line and return a rich metadata dict:
      text          — task body with emoji markers stripped
      priority      — 'highest' | 'high' | 'medium' | 'low' | 'lowest' | None
      priority_weight — int sort key (0=highest urgency, 4=lowest, 99=none)
      due_date      — datetime.date or None
      scheduled_date — datetime.date or None  (⏳)
      start_date    — datetime.date or None   (🛫)
      created_date  — datetime.date or None   (➕)
      is_done       — bool
    """
    m = _TASK_RE.match(raw_line)
    if not m:
        return {}

    is_done = m.group(2).lower() == "x"
    body = m.group(3)

    priority = None
    priority_weight = 99
    for emoji, (label, weight) in PRIORITY_MAP.items():
        if emoji in body:
            priority = label
            priority_weight = weight
            body = body.replace(emoji, "", 1)
            break

    due_date       = _parse_date(_DUE_RE.search(body))
    scheduled_date = _parse_date(_SCHEDULED_RE.search(body))
    start_date     = _parse_date(_START_RE.search(body))
    created_date   = _parse_date(_CREATED_RE.search(body))

    # Strip date markers from display text
    text = body
    for pattern in (_DUE_RE, _SCHEDULED_RE, _START_RE, _CREATED_RE, _DONE_RE):
        text = pattern.sub("", text)
    text = text.strip()

    return {
        "text": text,
        "priority": priority,
        "priority_weight": priority_weight,
        "due_date": due_date,
        "scheduled_date": scheduled_date,
        "start_date": start_date,
        "created_date": created_date,
        "is_done": is_done,
    }


class ObsidianAgent:
    """
    Reads and writes Obsidian tasks directly from markdown files.
    The Obsidian app does NOT need to be running.
    """

    def __init__(self, workspace_dir=None):
        self.workspace_dir = workspace_dir or get_config_value("WORKSPACE_DIR", None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # Default directories to skip — templates, archives, attachments, etc.
    DEFAULT_EXCLUDE_DIRS = {
        "950 Templates", "900 Archive", "990 Attachments", "910 PDF_PNG",
        "Clippings", "export", "whiteboards", "assets",
        ".obsidian", ".stfolder", ".claude",
    }

    def get_tasks(self, todo=True, done=False, format="dict"):
        """Scan .md files under workspace_dir and return matching tasks.

        Directories listed in OBSIDIAN_EXCLUDE_DIRS (comma-separated in .config)
        are skipped. Defaults exclude Templates, Archive, Attachments, etc.

        Returns a list of dicts:
            {"text": str, "file": str (relative path), "line": int (1-indexed), "done": bool}
        """
        if not self.workspace_dir or not os.path.isdir(self.workspace_dir):
            return []

        raw_exclude = get_config_value("OBSIDIAN_EXCLUDE_DIRS", "")
        if raw_exclude:
            exclude_dirs = {d.strip() for d in raw_exclude.split(",") if d.strip()}
        else:
            exclude_dirs = self.DEFAULT_EXCLUDE_DIRS

        tasks = []
        for root, dirs, files in os.walk(self.workspace_dir):
            # Prune excluded directories in-place so os.walk won't descend into them
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for filename in files:
                if not filename.endswith(".md"):
                    continue
                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, self.workspace_dir)
                tasks.extend(self._parse_file(abs_path, rel_path, todo=todo, done=done))

        return tasks

    def get_all_tasks(self, include_done=False):
        """Convenience wrapper — returns all incomplete tasks (or all tasks if include_done=True)."""
        return self.get_tasks(todo=True, done=include_done)

    def mark_done(self, task_text: str) -> bool:
        """Find the first matching - [ ] task by text and rewrite it as - [x].

        Returns True if a task was found and updated, False otherwise.
        """
        if not self.workspace_dir or not os.path.isdir(self.workspace_dir):
            return False

        task_text_lower = task_text.strip().lower()

        for root, _, files in os.walk(self.workspace_dir):
            for filename in files:
                if not filename.endswith(".md"):
                    continue
                abs_path = os.path.join(root, filename)
                if self._mark_done_in_file(abs_path, task_text_lower):
                    return True

        return False

    def update_task(self, path: str, line: int, action: str = "done"):
        """Mark the task at the given file path and 1-indexed line number as done.

        Only 'done' is currently supported as an action.
        """
        if not os.path.isabs(path):
            path = os.path.join(self.workspace_dir, path)

        if not os.path.isfile(path):
            return

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        idx = line - 1  # convert to 0-indexed
        if idx < 0 or idx >= len(lines):
            return

        m = _TASK_RE.match(lines[idx])
        if m and m.group(2) == " " and action == "done":
            indent = m.group(1)
            task_body = m.group(3)
            lines[idx] = f"{indent}- [x] {task_body}\n"
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)

    def read_file(self, file_path):
        """Reads and returns the content of a markdown file."""
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def create_file(self, file_path, content="", overwrite=False):
        """Creates a markdown file with the given content."""
        if os.path.exists(file_path) and not overwrite:
            return False
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_file(self, abs_path: str, rel_path: str, todo: bool, done: bool) -> list:
        tasks = []
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                for line_num, raw_line in enumerate(f, start=1):
                    m = _TASK_RE.match(raw_line)
                    if not m:
                        continue
                    is_done = m.group(2).lower() == "x"
                    if is_done and not done:
                        continue
                    if not is_done and not todo:
                        continue
                    meta = parse_task_metadata(raw_line)
                    tasks.append({
                        "text": raw_line.rstrip(),
                        "file": rel_path,
                        "line": line_num,
                        "done": is_done,
                        # rich metadata
                        "priority": meta.get("priority"),
                        "priority_weight": meta.get("priority_weight", 99),
                        "due_date": meta.get("due_date"),
                        "scheduled_date": meta.get("scheduled_date"),
                        "start_date": meta.get("start_date"),
                        "clean_text": meta.get("text", ""),
                    })
        except OSError:
            pass
        return tasks

    def _mark_done_in_file(self, abs_path: str, task_text_lower: str) -> bool:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            return False

        for idx, raw_line in enumerate(lines):
            m = _TASK_RE.match(raw_line)
            if not m or m.group(2) != " ":
                continue
            task_body = m.group(3).strip().lower()
            if task_text_lower in task_body or task_body in task_text_lower:
                indent = m.group(1)
                original_body = m.group(3)
                lines[idx] = f"{indent}- [x] {original_body}\n"
                try:
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    return True
                except OSError:
                    return False

        return False


if __name__ == "__main__":
    agent = ObsidianAgent()
    tasks = agent.get_tasks(todo=True, done=False)
    print(f"Found {len(tasks)} incomplete tasks")
    for t in tasks[:5]:
        print(f"  [{t['file']}:{t['line']}] {t['text']}")
