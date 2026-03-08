"""
LogSeq Agent — reads journals and pages from a LogSeq graph directory.

Journal files: journals/YYYY_MM_DD.md
Pages files:   pages/<name>.md

Tasks are identified by lines starting with "- LATER".
"""
import os
import re
import datetime


MONTHS = {
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'may': '05', 'june': '06', 'july': '07', 'august': '08',
    'september': '09', 'october': '10', 'november': '11', 'december': '12'
}


class LogSeqAgent:
    def __init__(self, logseq_dir):
        self.logseq_dir = logseq_dir
        self.journals_dir = os.path.join(logseq_dir, "journals")
        self.pages_dir = os.path.join(logseq_dir, "pages")

    # ── File helpers ─────────────────────────────────────────────────────

    def _journal_path(self, date_key):
        """Return the full path for a journal file given 'YYYY_MM_DD'."""
        return os.path.join(self.journals_dir, f"{date_key}.md")

    def _read(self, path):
        if not os.path.exists(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    # ── Task parsing ──────────────────────────────────────────────────────

    def parse_later_tasks(self, text, source=""):
        """
        Extract LATER tasks from raw LogSeq markdown text.
        Returns list of dicts: {task, source, properties}
        """
        tasks = []
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            m = re.match(r"^\s*-\s+LATER\s+(.*)", lines[i])
            if m:
                raw = m.group(1).strip()
                # Strip LogSeq macros but keep URLs and plain text
                raw = re.sub(r"\{\{(?:renderer|query|clojure|embed|include)\s+.*?\}\}", "", raw).strip()
                # Strip bold markers (**) and unwanted timestamps like **11:23**
                raw = re.sub(r"\*\*\d{1,2}:\d{2}\*\*\s*", "", raw).strip()
                # Strip [[quick capture]]: prefix
                raw = re.sub(r"\[\[.*?\]\]:\s*", "", raw).strip()

                task = {"task": raw, "source": source, "properties": {}}

                # Collect indented property lines
                j = i + 1
                while j < len(lines):
                    nxt = lines[j]
                    prop = re.match(r"^\s+:([\w-]+):\s*(.*)", nxt)
                    if prop:
                        k, v = prop.group(1).lower(), prop.group(2).strip()
                        task["properties"][k] = v
                        if k == "url" and v not in task["task"]:
                            task["task"] += f" ({v})"
                        j += 1
                    elif nxt.strip() == "" or re.match(r"^\s*-\s", nxt):
                        break
                    else:
                        j += 1
                i = j
                tasks.append(task)
            else:
                i += 1
        return tasks

    # ── Journal access ────────────────────────────────────────────────────

    def get_tasks_for_date(self, date_key):
        """
        Return LATER tasks for a specific journal date ('YYYY_MM_DD').
        """
        path = self._journal_path(date_key)
        text = self._read(path)
        if not text:
            return None, []       # None = file not found
        tasks = self.parse_later_tasks(text, source=f"journal/{date_key}")
        return text, tasks

    def get_recent_tasks(self, days=7):
        """
        Return LATER tasks from the most recent N journal files.
        """
        all_tasks = []
        if not os.path.exists(self.journals_dir):
            return all_tasks
        files = sorted(
            [f for f in os.listdir(self.journals_dir) if re.match(r"\d{4}_\d{2}_\d{2}\.md$", f)],
            reverse=True
        )
        for fname in files[:days]:
            date_key = fname[:-3]
            path = os.path.join(self.journals_dir, fname)
            text = self._read(path)
            tasks = self.parse_later_tasks(text, source=f"journal/{date_key}")
            all_tasks.extend(tasks)
        return all_tasks

    def list_journal_dates(self):
        """Return sorted list of all journal date keys (newest first)."""
        if not os.path.exists(self.journals_dir):
            return []
        return sorted(
            [f[:-3] for f in os.listdir(self.journals_dir)
             if re.match(r"\d{4}_\d{2}_\d{2}\.md$", f)],
            reverse=True
        )

    # ── Pages access ──────────────────────────────────────────────────────

    def get_page(self, name):
        """Read a named page (case-insensitive partial match)."""
        if not os.path.exists(self.pages_dir):
            return None, ""
        name_lower = name.lower()
        for fname in os.listdir(self.pages_dir):
            if fname.lower().endswith(".md") and name_lower in fname.lower()[:-3]:
                path = os.path.join(self.pages_dir, fname)
                return fname, self._read(path)
        return None, ""

    def get_all_page_tasks(self):
        """Return LATER tasks from all pages."""
        all_tasks = []
        if not os.path.exists(self.pages_dir):
            return all_tasks
        for fname in os.listdir(self.pages_dir):
            if fname.endswith(".md"):
                path = os.path.join(self.pages_dir, fname)
                text = self._read(path)
                tasks = self.parse_later_tasks(text, source=f"page/{fname[:-3]}")
                all_tasks.extend(tasks)
        return all_tasks

    def search_pages(self, query, max_results=5):
        """
        Search pages for lines containing any word from the query.
        Returns list of (page_name, matching_lines).
        """
        if not os.path.exists(self.pages_dir):
            return []
        keywords = [w.lower() for w in query.split() if len(w) > 3]
        results = []
        for fname in os.listdir(self.pages_dir):
            if not fname.endswith(".md"):
                continue
            path = os.path.join(self.pages_dir, fname)
            text = self._read(path)
            hits = [ln.strip() for ln in text.splitlines()
                    if any(kw in ln.lower() for kw in keywords) and ln.strip()]
            if hits:
                results.append((fname[:-3], hits[:10]))
            if len(results) >= max_results:
                break
        return results

    # ── Formatted context for LLM ─────────────────────────────────────────

    def format_tasks(self, tasks):
        """Format task list as a numbered markdown list."""
        if not tasks:
            return "No LATER tasks found."
        lines = []
        for i, t in enumerate(tasks, 1):
            lines.append(f"{i}. {t['task']}  _(source: {t['source']})_")
        return "\n".join(lines)

    def context_for_date(self, date_key):
        """Return a formatted context string for a specific journal date."""
        _, tasks = self.get_tasks_for_date(date_key)
        header = f"LogSeq journal {date_key} — LATER tasks ({len(tasks)} found):"
        return f"{header}\n{self.format_tasks(tasks)}"

    def context_for_recent(self, days=7):
        """Return formatted context for recent journal tasks."""
        tasks = self.get_recent_tasks(days)
        header = f"LogSeq recent journals (last {days} days) — LATER tasks ({len(tasks)} found):"
        return f"{header}\n{self.format_tasks(tasks)}"

    def context_for_all_page_tasks(self):
        """Return formatted context for all page tasks."""
        tasks = self.get_all_page_tasks()
        header = f"LogSeq pages — LATER tasks ({len(tasks)} found):"
        return f"{header}\n{self.format_tasks(tasks)}"


# ── Date parsing helper ────────────────────────────────────────────────────

def parse_date_from_text(text):
    """
    Extract a date from natural language text.
    Returns 'YYYY_MM_DD' string or None.
    Handles: "March 6 2026", "March 6, 2026", "2026-03-06", "2026/03/06", "today", "yesterday"
    """
    text_lower = text.lower()

    if "today" in text_lower:
        return datetime.datetime.now().strftime("%Y_%m_%d")
    if "yesterday" in text_lower:
        d = datetime.datetime.now() - datetime.timedelta(days=1)
        return d.strftime("%Y_%m_%d")

    # Numeric: 2026-03-06 or 2026/03/06
    m = re.search(r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b', text)
    if m:
        return f"{m.group(1)}_{m.group(2).zfill(2)}_{m.group(3).zfill(2)}"

    # Month name: "March 6 2026" or "March 6, 2026"
    m = re.search(
        r'\b(january|february|march|april|may|june|july|august|'
        r'september|october|november|december)\s+(\d{1,2})[,\s]+(\d{4})\b',
        text_lower
    )
    if m:
        month = MONTHS[m.group(1)]
        day = m.group(2).zfill(2)
        year = m.group(3)
        return f"{year}_{month}_{day}"

    return None
