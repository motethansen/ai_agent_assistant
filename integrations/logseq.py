"""
LogSeq integration — reads journals and pages from a LogSeq graph directory.

Journal files: journals/YYYY_MM_DD.md
Pages files:   pages/<name>.md

Tasks are identified by lines starting with "- LATER" or "- TODO".
"""

import os
import re
import datetime
from pathlib import Path
import config

_MONTHS = {
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'may': '05', 'june': '06', 'july': '07', 'august': '08',
    'september': '09', 'october': '10', 'november': '11', 'december': '12',
}


class LogSeqReader:
    def __init__(self, logseq_dir: str | None = None):
        self.logseq_dir = Path(logseq_dir or config.paths.logseq())
        self.journals_dir = self.logseq_dir / "journals"
        self.pages_dir = self.logseq_dir / "pages"

    # ── File helpers ──────────────────────────────────────────────────────────

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    # ── Task parsing ──────────────────────────────────────────────────────────

    def parse_tasks(self, text: str, source: str = "") -> list[dict]:
        """
        Extract LATER and TODO tasks from raw LogSeq markdown.
        Returns list of dicts: {task, source, properties, description}
        """
        tasks = []
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            m = re.match(r"^\s*-\s+(LATER|TODO)\s+(.*)", lines[i])
            if m:
                raw = m.group(2).strip()
                raw = re.sub(r"\{\{(?:renderer|query|clojure|embed|include)\s+.*?\}\}", "", raw).strip()
                raw = re.sub(r"\*\*\d{1,2}:\d{2}\*\*\s*", "", raw).strip()
                raw = re.sub(r"\[\[.*?\]\]:\s*", "", raw).strip()

                task_indent = len(re.match(r"^(\s*)", lines[i]).group(1))
                task = {
                    "task": raw,
                    "source": f"{source}:{i + 1}",
                    "properties": {},
                    "description": "",
                }

                j = i + 1
                desc_parts = []
                while j < len(lines):
                    nxt = lines[j]
                    if not nxt.strip():
                        break
                    if len(re.match(r"^(\s*)", nxt).group(1)) <= task_indent:
                        break
                    prop = re.match(r"^\s+:([\w-]+):\s*(.*)", nxt)
                    if prop:
                        k, v = prop.group(1).lower(), prop.group(2).strip()
                        task["properties"][k] = v
                        if k == "url" and v not in task["task"]:
                            task["task"] += f" ({v})"
                    else:
                        desc_text = re.sub(r"^\s*-\s+", "", nxt).strip()
                        if desc_text:
                            desc_parts.append(desc_text)
                    j += 1

                if desc_parts:
                    task["description"] = " | ".join(desc_parts)
                tasks.append(task)
                i = j
            else:
                i += 1
        return tasks

    # ── Journal access ────────────────────────────────────────────────────────

    def get_recent_tasks(self, days: int | None = None) -> list[dict]:
        """Return LATER/TODO tasks from the most recent N journal files."""
        days = days or config.sync.logseq_journal_days()
        if not self.journals_dir.exists():
            return []
        files = sorted(
            [f for f in self.journals_dir.iterdir()
             if re.match(r"\d{4}_\d{2}_\d{2}\.md$", f.name)],
            key=lambda f: f.name,
            reverse=True,
        )
        tasks = []
        for f in files[:days]:
            date_key = f.stem
            tasks.extend(self.parse_tasks(self._read(f), source=f"journal/{date_key}"))
        return tasks

    def get_recent_notes(self, days: int | None = None) -> list[dict]:
        """
        Return raw journal entries (non-task lines) from recent journal files.
        Each entry: {date, lines: [str], source}
        """
        days = days or config.sync.logseq_journal_days()
        if not self.journals_dir.exists():
            return []
        files = sorted(
            [f for f in self.journals_dir.iterdir()
             if re.match(r"\d{4}_\d{2}_\d{2}\.md$", f.name)],
            key=lambda f: f.name,
            reverse=True,
        )
        entries = []
        for f in files[:days]:
            date_key = f.stem
            text = self._read(f)
            note_lines = [
                ln.strip() for ln in text.splitlines()
                if ln.strip()
                and not re.match(r"^\s*-\s+(LATER|TODO|DONE|NOW|WAITING)\s+", ln)
            ]
            if note_lines:
                entries.append({
                    "date": date_key.replace("_", "-"),
                    "lines": note_lines,
                    "source": f"journal/{date_key}",
                })
        return entries

    def list_journal_dates(self) -> list[str]:
        """Return all journal date keys (YYYY_MM_DD), newest first."""
        if not self.journals_dir.exists():
            return []
        return sorted(
            [f.stem for f in self.journals_dir.iterdir()
             if re.match(r"\d{4}_\d{2}_\d{2}\.md$", f.name)],
            reverse=True,
        )

    # ── Pages access ──────────────────────────────────────────────────────────

    def get_all_page_tasks(self) -> list[dict]:
        """Return LATER/TODO tasks from all pages."""
        if not self.pages_dir.exists():
            return []
        tasks = []
        for f in self.pages_dir.iterdir():
            if f.suffix == ".md":
                tasks.extend(self.parse_tasks(self._read(f), source=f"page/{f.stem}"))
        return tasks

    def search_pages(self, query: str, max_results: int = 5) -> list[tuple]:
        """Search pages for lines matching any word in query. Returns [(name, lines)]."""
        if not self.pages_dir.exists():
            return []
        keywords = [w.lower() for w in query.split() if len(w) > 3]
        results = []
        for f in self.pages_dir.iterdir():
            if f.suffix != ".md":
                continue
            hits = [
                ln.strip() for ln in self._read(f).splitlines()
                if ln.strip() and any(kw in ln.lower() for kw in keywords)
            ]
            if hits:
                results.append((f.stem, hits[:10]))
            if len(results) >= max_results:
                break
        return results

    # ── Write ─────────────────────────────────────────────────────────────────

    def add_task(self, description: str, date_key: str | None = None) -> Path:
        """Append a LATER task to a journal file. Returns the path written to."""
        if date_key is None:
            date_key = datetime.datetime.now().strftime("%Y_%m_%d")
        path = self.journals_dir / f"{date_key}.md"
        self.journals_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n- LATER {description}\n")
        return path

    def mark_done(self, task_text: str, days_back: int = 14) -> bool:
        """Find and mark a LATER/TODO task DONE in recent journals. Returns True on success."""
        if not self.journals_dir.exists():
            return False
        files = sorted(
            [f for f in self.journals_dir.iterdir()
             if re.match(r"\d{4}_\d{2}_\d{2}\.md$", f.name)],
            key=lambda f: f.name,
            reverse=True,
        )
        search = task_text.lower().strip()
        for f in files[:days_back]:
            text = self._read(f)
            lines = text.splitlines()
            new_lines, changed = [], False
            for line in lines:
                m = re.match(r"^(\s*-\s+)(LATER|TODO)(\s+.*)", line)
                if m and search in m.group(3).lower():
                    new_lines.append(f"{m.group(1)}DONE{m.group(3)}")
                    changed = True
                else:
                    new_lines.append(line)
            if changed:
                f.write_text("\n".join(new_lines), encoding="utf-8")
                return True
        return False


# ── Date parsing helper ────────────────────────────────────────────────────────

def parse_date_from_text(text: str) -> str | None:
    """
    Extract a date from natural language. Returns 'YYYY_MM_DD' or None.
    Handles: 'March 6 2026', '2026-03-06', 'today', 'yesterday'.
    """
    text_lower = text.lower()
    if "today" in text_lower:
        return datetime.datetime.now().strftime("%Y_%m_%d")
    if "yesterday" in text_lower:
        return (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y_%m_%d")
    m = re.search(r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b', text)
    if m:
        return f"{m.group(1)}_{m.group(2).zfill(2)}_{m.group(3).zfill(2)}"
    m = re.search(
        r'\b(january|february|march|april|may|june|july|august|'
        r'september|october|november|december)\s+(\d{1,2})[,\s]+(\d{4})\b',
        text_lower,
    )
    if m:
        return f"{m.group(3)}_{_MONTHS[m.group(1)]}_{m.group(2).zfill(2)}"
    return None
