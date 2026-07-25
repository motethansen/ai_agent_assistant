"""
Obsidian integration — reads and writes to an Obsidian vault directly (no app needed).

Key concepts:
- Tasks use Obsidian Tasks plugin format: - [ ] text 📅 YYYY-MM-DD #tag
- Dashboard.md has named sections owned by agents (marked with HTML comments)
- Section writes are in-place — never stomp other sections
"""

import os
import re
import datetime
from pathlib import Path
from typing import Any
import config

# ── Task regex + metadata ─────────────────────────────────────────────────────

_TASK_RE = re.compile(r"^(\s*)-\s+\[([ xX])\]\s+(.*)")

PRIORITY_MAP = {
    "🔺": ("highest", 0),
    "⏫": ("high",    1),
    "🔼": ("medium",  2),
    "🔽": ("low",     3),
    "⏬": ("lowest",  4),
}

_DUE_RE       = re.compile(r'📅\s*(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?)')
_SCHEDULED_RE = re.compile(r'⏳\s*(\d{4}-\d{2}-\d{2})')
_DONE_RE      = re.compile(r'✅\s*(\d{4}-\d{2}-\d{2})')
_GCAL_RE      = re.compile(r'#' + re.escape(config.calendar.gcal_tag()) + r'\b')
_TAG_RE       = re.compile(r'#([\w/-]+)')

_EXCLUDE_DIRS = {
    ".obsidian", ".stfolder", ".claude", "assets", "Attachments",
    "990 Attachments", "910 PDF_PNG", "Clippings", "whiteboards", "export",
}


def _parse_date(m) -> datetime.date | None:
    if not m:
        return None
    try:
        return datetime.date.fromisoformat(m.group(1).split()[0])
    except ValueError:
        return None


def parse_task_metadata(raw_line: str) -> dict:
    """Parse an Obsidian task line. Returns rich metadata dict."""
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

    due_date = _parse_date(_DUE_RE.search(body))
    due_time_match = _DUE_RE.search(body)
    due_time = None
    if due_time_match and " " in due_time_match.group(1):
        due_time = due_time_match.group(1).split(" ", 1)[1]

    scheduled_date = _parse_date(_SCHEDULED_RE.search(body))
    gcal = bool(_GCAL_RE.search(body))
    tags = _TAG_RE.findall(body)

    text = body
    for pattern in (_DUE_RE, _SCHEDULED_RE, _DONE_RE):
        text = pattern.sub("", text)
    text = text.strip()

    return {
        "text": text,
        "priority": priority,
        "priority_weight": priority_weight,
        "due_date": due_date,
        "due_time": due_time,
        "scheduled_date": scheduled_date,
        "is_done": is_done,
        "gcal": gcal,
        "tags": tags,
    }


# ── Vault reader / writer ─────────────────────────────────────────────────────

# Module-level task-parse cache keyed by absolute file path. Shared across
# ObsidianVault instances (CLI commands and API requests each construct their
# own vault object). Entries are (mtime, tasks-including-done).
_PARSE_CACHE: dict[str, tuple[float, list[dict]]] = {}


class ObsidianVault:
    """
    Read and write to an Obsidian vault. The app does not need to be running.
    """

    def __init__(self, vault_dir: str | None = None):
        self.vault_dir = Path(vault_dir or config.paths.obsidian())

    # ── Reading ───────────────────────────────────────────────────────────────

    def get_tasks(
        self,
        include_done: bool = False,
        gcal_only: bool = False,
        subdirs: list[str] | None = None,
    ) -> list[dict]:
        """
        Scan vault for tasks. Returns list of dicts with file, line, metadata.
        subdirs: if set, only scan these subdirectories (relative to vault root).
        """
        if not self.vault_dir.is_dir():
            return []

        scan_roots = (
            [self.vault_dir / d for d in subdirs]
            if subdirs
            else [self.vault_dir]
        )

        tasks = []
        for root in scan_roots:
            for dirpath, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
                for fname in files:
                    if not fname.endswith(".md"):
                        continue
                    abs_path = Path(dirpath) / fname
                    rel_path = abs_path.relative_to(self.vault_dir)
                    tasks.extend(self._parse_file_cached(abs_path, rel_path, include_done))

        if gcal_only:
            tasks = [t for t in tasks if t.get("gcal")]
        return tasks

    def read_file(self, rel_path: str) -> str | None:
        path = self.vault_dir / rel_path
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def list_notes(
        self,
        subdir: str | None = None,
        with_frontmatter: bool = False,
    ) -> list[dict]:
        """
        Return a list of notes: {path, title, first_lines, tags}.
        Useful for the notes agent to decide folder moves and wikilinks.
        """
        root = self.vault_dir / subdir if subdir else self.vault_dir
        notes = []
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                abs_path = Path(dirpath) / fname
                rel = str(abs_path.relative_to(self.vault_dir))
                try:
                    text = abs_path.read_text(encoding="utf-8", errors="replace")
                    mtime = abs_path.stat().st_mtime
                except OSError:
                    continue
                lines = [l for l in text.splitlines() if l.strip()]
                first_lines = lines[:5]
                tags = _TAG_RE.findall(text[:2000])
                notes.append({
                    "path": rel,
                    "title": fname[:-3],
                    "first_lines": first_lines,
                    "tags": list(set(tags)),
                    "size": len(text),
                    "mtime": mtime,
                })
        return notes

    # ── Writing ───────────────────────────────────────────────────────────────

    def write_file(self, rel_path: str, content: str) -> Path:
        """Write (overwrite) a file in the vault. Creates parent dirs as needed."""
        path = self.vault_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        _PARSE_CACHE.pop(str(path), None)
        return path

    def append_to_file(self, rel_path: str, content: str) -> Path:
        """Append content to a file (creates it if missing)."""
        path = self.vault_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        _PARSE_CACHE.pop(str(path), None)
        return path

    def mark_task_done(self, task_text: str) -> bool:
        """Find the first matching - [ ] task by text and rewrite as - [x]."""
        if not self.vault_dir.is_dir():
            return False
        search = task_text.strip().lower()
        for dirpath, dirs, files in os.walk(self.vault_dir):
            dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                abs_path = Path(dirpath) / fname
                if self._mark_done_in_file(abs_path, search):
                    return True
        return False

    def update_task_date(self, task: dict, new_date: datetime.date) -> bool:
        """
        Rewrite the due-date emoji (📅 YYYY-MM-DD) on a specific task line,
        identified by task['file'] and task['line'] (1-based).
        Appends a due date if the task has none.
        """
        abs_path = self.vault_dir / task["file"]
        if not abs_path.exists():
            return False
        try:
            lines = abs_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        idx = task["line"] - 1
        if idx < 0 or idx >= len(lines):
            return False
        old = lines[idx]
        new_ds = new_date.isoformat()
        if _DUE_RE.search(old):
            lines[idx] = _DUE_RE.sub(f"📅 {new_ds}", old)
        else:
            lines[idx] = old.rstrip() + f" 📅 {new_ds}"
        abs_path.write_text("\n".join(lines), encoding="utf-8")
        _PARSE_CACHE.pop(str(abs_path), None)
        return True

    def set_deadline_by_text(self, text_match: str, new_date: datetime.date) -> str | None:
        """Set a due date (📅) on the first UNDATED open task whose text contains
        text_match — i.e. pull one backlog item into the active/dated list."""
        q = text_match.strip().lower()
        for t in self.get_tasks():
            if t.get("is_done") or t.get("due_date") or t.get("scheduled_date"):
                continue
            if q in t["text"].lower():
                return t["text"] if self.update_task_date(t, new_date) else None
        return None

    def set_deadline_by_category(self, category: str, new_date: datetime.date) -> int:
        """Set a due date (📅) on every UNDATED open task tagged #category. Returns count."""
        cat = category.lstrip("#").lower()
        n = 0
        for t in self.get_tasks():
            if t.get("is_done") or t.get("due_date") or t.get("scheduled_date"):
                continue
            if cat in [str(x).lstrip("#").lower() for x in (t.get("tags") or [])]:
                if self.update_task_date(t, new_date):
                    n += 1
        return n

    def move_file(self, from_rel: str, to_rel: str) -> bool:
        """Move a note to a new location within the vault. Creates dest dir."""
        src = self.vault_dir / from_rel
        dst = self.vault_dir / to_rel
        if not src.exists():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return True

    # ── Dashboard section management ──────────────────────────────────────────

    def read_section(self, section_name: str, file_rel: str | None = None) -> str:
        """Read the content of a named agent-managed section from Dashboard.md."""
        file_rel = file_rel or _dashboard_rel()
        content = self.read_file(file_rel) or ""
        start_marker = f"<!-- agent:{section_name}:start -->"
        end_marker = f"<!-- agent:{section_name}:end -->"
        start = content.find(start_marker)
        end = content.find(end_marker)
        if start == -1 or end == -1:
            return ""
        return content[start + len(start_marker):end].strip()

    def write_section(
        self,
        section_name: str,
        new_content: str,
        file_rel: str | None = None,
    ) -> bool:
        """
        Replace a named agent-managed section in Dashboard.md.
        If the section markers don't exist yet, appends them to the file.
        Never touches content outside the markers.
        """
        file_rel = file_rel or _dashboard_rel()
        path = self.vault_dir / file_rel

        start_marker = f"<!-- agent:{section_name}:start -->"
        end_marker = f"<!-- agent:{section_name}:end -->"

        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"{start_marker}\n{new_content}\n{end_marker}\n",
                encoding="utf-8",
            )
            _PARSE_CACHE.pop(str(path), None)
            return True

        current = path.read_text(encoding="utf-8")
        start_idx = current.find(start_marker)
        end_idx = current.find(end_marker)

        if start_idx == -1 or end_idx == -1:
            # Section doesn't exist yet — append
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n{start_marker}\n{new_content}\n{end_marker}\n")
            _PARSE_CACHE.pop(str(path), None)
            return True

        # Replace content between markers (markers themselves are preserved)
        before = current[: start_idx + len(start_marker)]
        after = current[end_idx:]
        path.write_text(f"{before}\n{new_content}\n{after}", encoding="utf-8")
        _PARSE_CACHE.pop(str(path), None)
        return True

    def create_daily_note(self, date: datetime.date | None = None) -> Path:
        """Create a daily note from template if it doesn't exist. Returns path."""
        date = date or datetime.date.today()
        rel = f"Daily/{date.isoformat()}.md"
        path = self.vault_dir / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f"# {date.strftime('%A, %B %d %Y')}\n\n## Tasks\n\n## Notes\n",
                encoding="utf-8",
            )
        return path

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _parse_file_cached(self, abs_path: Path, rel_path: Path, include_done: bool) -> list[dict]:
        """mtime-cached wrapper around _parse_file.

        Files are parsed with done tasks included so one cache entry serves
        both include_done modes; filtering happens on the way out. Unchanged
        files (~99% of a vault scan) skip the read+regex entirely.
        """
        key = str(abs_path)
        try:
            mtime = abs_path.stat().st_mtime
        except OSError:
            _PARSE_CACHE.pop(key, None)
            return []
        cached = _PARSE_CACHE.get(key)
        if cached is None or cached[0] != mtime:
            _PARSE_CACHE[key] = (mtime, self._parse_file(abs_path, rel_path, include_done=True))
        tasks = _PARSE_CACHE[key][1]
        if not include_done:
            tasks = [t for t in tasks if not t.get("done")]
        # Shallow-copy so callers can't mutate cached entries.
        return [dict(t) for t in tasks]

    def _parse_file(self, abs_path: Path, rel_path: Path, include_done: bool) -> list[dict]:
        tasks = []
        try:
            for line_num, raw_line in enumerate(
                abs_path.read_text(encoding="utf-8", errors="replace").splitlines(),
                start=1,
            ):
                m = _TASK_RE.match(raw_line)
                if not m:
                    continue
                is_done = m.group(2).lower() == "x"
                if is_done and not include_done:
                    continue
                meta = parse_task_metadata(raw_line)
                tasks.append({
                    "raw": raw_line.rstrip(),
                    "file": str(rel_path),
                    "line": line_num,
                    "done": is_done,
                    "text": meta.get("text", ""),
                    "priority": meta.get("priority"),
                    "priority_weight": meta.get("priority_weight", 99),
                    "due_date": meta.get("due_date"),
                    "due_time": meta.get("due_time"),
                    "scheduled_date": meta.get("scheduled_date"),
                    "gcal": meta.get("gcal", False),
                    "tags": meta.get("tags", []),
                })
        except OSError:
            pass
        return tasks

    def _mark_done_in_file(self, abs_path: Path, search: str) -> bool:
        try:
            lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return False
        for idx, raw_line in enumerate(lines):
            m = _TASK_RE.match(raw_line)
            if not m or m.group(2) != " ":
                continue
            if search in m.group(3).strip().lower():
                lines[idx] = f"{m.group(1)}- [x] {m.group(3)}"
                abs_path.write_text("\n".join(lines), encoding="utf-8")
                _PARSE_CACHE.pop(str(abs_path), None)
                return True
        return False


def _dashboard_rel() -> str:
    """Return the relative path of Dashboard.md from vault root."""
    full = config.paths.dashboard()
    vault = config.paths.obsidian()
    if full and vault and full.startswith(vault):
        return full[len(vault):].lstrip("/")
    return "Dashboard.md"
