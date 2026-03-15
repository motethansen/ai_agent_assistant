import os
import re

from config_utils import get_config_value

_TASK_RE = re.compile(r"^(\s*)-\s+\[([ xX])\]\s+(.*)")


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

    def get_tasks(self, todo=True, done=False, format="dict"):
        """Scan all .md files under workspace_dir and return matching tasks.

        Returns a list of dicts:
            {"text": str, "file": str (relative path), "line": int (1-indexed), "done": bool}
        """
        if not self.workspace_dir or not os.path.isdir(self.workspace_dir):
            return []

        tasks = []
        for root, _, files in os.walk(self.workspace_dir):
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
                    tasks.append({
                        "text": raw_line.rstrip(),
                        "file": rel_path,
                        "line": line_num,
                        "done": is_done,
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
