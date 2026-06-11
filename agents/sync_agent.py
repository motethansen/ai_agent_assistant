"""
Sync agent — pulls tasks and notes from LogSeq into Obsidian.

Runs automatically every 30 min via launchd (or cron_job.py).
Uses a hash file to track what has already been synced (no duplicates).

Enrichment pipeline (per task):
  1. URL title fetch  — inserts "Page Title — " before bare URLs
  2. Wikilink page sync — copies [[linked pages]] from LogSeq → Obsidian inbox
"""

import datetime
import hashlib
import json
import re
import urllib.request
import urllib.error
from html.parser import HTMLParser
from pathlib import Path

from integrations.logseq import LogSeqReader
from integrations.obsidian import ObsidianVault
import config

_HASH_FILE = Path(__file__).parent.parent / "output" / ".synced_hashes.json"

# ── Regexes ───────────────────────────────────────────────────────────────────
_URL_RE       = re.compile(r'(https?://\S+)', re.IGNORECASE)
_WIKILINK_RE  = re.compile(r'\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]')
_ENRICHED_RE  = re.compile(r' — https?://')  # already has title prefix


# ── URL title fetcher ─────────────────────────────────────────────────────────

class _MetaParser(HTMLParser):
    """Extracts <title> and og:title from an HTML snippet."""
    def __init__(self):
        super().__init__()
        self.title: str | None = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            prop = attrs_d.get("property", "").lower()
            name = attrs_d.get("name", "").lower()
            content = attrs_d.get("content", "").strip()
            if prop in ("og:title",) and content and not self.title:
                self.title = content

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and not self.title:
            t = data.strip()
            if t:
                self.title = t


def _fetch_url_title(url: str) -> str | None:
    """Fetch the <title> for a URL. Returns None on failure or timeout."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "html" not in ct:
                return None
            html = resp.read(50_000).decode("utf-8", errors="replace")
        parser = _MetaParser()
        parser.feed(html)
        title = (parser.title or "").strip()
        # Clean up common suffixes like " | LinkedIn", " | GitHub"
        title = re.sub(r'\s*[|·—–-]\s*(LinkedIn|GitHub|YouTube|Facebook|Twitter|X|Instagram|TikTok|Substack|Medium).*$', '', title, flags=re.IGNORECASE).strip()
        if title and len(title) > 4:
            return title[:120]
        return None
    except Exception:
        return None


# ── Wikilink page sync ────────────────────────────────────────────────────────

_LOGSEQ_PAGES_INBOX = "000 Inbox/LogSeq Pages"


def _sync_wikilink_page(
    page_name: str,
    logseq: LogSeqReader,
    vault: ObsidianVault,
    synced_pages: set[str],
) -> str | None:
    """
    Copy a LogSeq page to Obsidian inbox if it exists and hasn't been synced yet.
    Returns the Obsidian relative path on success, None otherwise.
    """
    key = page_name.strip().lower()
    if key in synced_pages:
        return None  # already processed this session

    # Case-insensitive search in LogSeq pages
    pages_dir = logseq.pages_dir
    if not pages_dir.exists():
        return None

    target_file: Path | None = None
    for f in pages_dir.iterdir():
        if f.suffix == ".md" and f.stem.lower() == key:
            target_file = f
            break

    if not target_file:
        return None  # not a real LogSeq page (just a tag/category ref)

    obs_rel = f"{_LOGSEQ_PAGES_INBOX}/{target_file.name}"
    obs_path = vault.vault_dir / obs_rel

    # Skip if already exists in Obsidian (don't overwrite manual edits)
    if obs_path.exists():
        synced_pages.add(key)
        return obs_rel

    content = target_file.read_text(encoding="utf-8", errors="replace")
    # Add a source header so the origin is clear
    header = f"> Synced from LogSeq page: `pages/{target_file.name}`  \n> Sync date: {datetime.date.today()}\n\n"
    vault.write_file(obs_rel, header + content)
    synced_pages.add(key)
    return obs_rel


# ── Task enrichment ───────────────────────────────────────────────────────────

def enrich_task_text(
    task_text: str,
    logseq: LogSeqReader,
    vault: ObsidianVault,
    synced_pages: set[str],
    fetch_titles: bool = True,
) -> tuple[str, int, int]:
    """
    Enrich a task text string:
      - URLs: fetch page title and insert "Title — " before the URL
      - [[Wikilinks]]: copy LogSeq page to Obsidian 000 Inbox/LogSeq Pages/

    Returns (enriched_text, url_enrichments, pages_synced).
    """
    url_count = 0
    page_count = 0
    text = task_text

    # ── 1. URL title enrichment ───────────────────────────────────────────────
    if fetch_titles:
        urls = _URL_RE.findall(text)
        for url in urls:
            # Skip if there's already a " — url" pattern (already enriched)
            if _ENRICHED_RE.search(text):
                continue
            title = _fetch_url_title(url)
            if title:
                # Check if a (possibly truncated) version of the title is already in text
                title_words = title.lower().split()[:4]
                already_there = all(w in text.lower() for w in title_words if len(w) > 3)
                if not already_there:
                    text = text.replace(url, f"{title} — {url}", 1)
                    url_count += 1

    # ── 2. Wikilink page sync ─────────────────────────────────────────────────
    wikilinks = _WIKILINK_RE.findall(text)
    for page_name in wikilinks:
        obs_rel = _sync_wikilink_page(page_name, logseq, vault, synced_pages)
        if obs_rel:
            page_count += 1

    return text, url_count, page_count


# ── Hash helpers ──────────────────────────────────────────────────────────────

def _load_hashes() -> set[str]:
    try:
        return set(json.loads(_HASH_FILE.read_text()))
    except (OSError, json.JSONDecodeError):
        return set()


def _save_hashes(hashes: set[str]) -> None:
    _HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    _HASH_FILE.write_text(json.dumps(sorted(hashes), indent=2))


def _task_hash(task: dict) -> str:
    key = f"{task['task']}|{task['source']}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


# ── Main run ──────────────────────────────────────────────────────────────────

def run(enrich: bool = True) -> dict:
    """
    Pull new LogSeq tasks and notes into Obsidian.
    Returns a summary dict: {tasks_added, notes_added, skipped, urls_enriched, pages_synced}.
    """
    logseq = LogSeqReader()
    vault = ObsidianVault()
    synced = _load_hashes()
    today = datetime.date.today()
    synced_pages: set[str] = set()

    stats = {"tasks_added": 0, "notes_added": 0, "skipped": 0,
             "urls_enriched": 0, "pages_synced": 0}

    # ── Tasks ─────────────────────────────────────────────────────────────────
    days = config.sync.logseq_journal_days()
    tasks = logseq.get_recent_tasks(days=days)
    page_tasks = logseq.get_all_page_tasks()
    all_tasks = tasks + page_tasks

    new_task_lines = []
    new_hashes = set()
    for t in all_tasks:
        h = _task_hash(t)
        if h in synced:
            stats["skipped"] += 1
            continue

        task_text = t["task"].strip()
        if not task_text:
            stats["skipped"] += 1
            continue

        # Enrich: fetch URL titles + sync wikilink pages
        if enrich:
            task_text, n_urls, n_pages = enrich_task_text(
                task_text, logseq, vault, synced_pages
            )
            stats["urls_enriched"] += n_urls
            stats["pages_synced"] += n_pages

        # Build the task line with date reference
        source = t.get("source", "")
        # Extract YYYY-MM-DD from source like "journal/2026_05_23:1"
        date_ref = ""
        dm = re.search(r"journal/(\d{4}_\d{2}_\d{2})", source)
        if dm:
            date_ref = dm.group(1).replace("_", "-")

        line = f"- [ ] {task_text}"
        if t.get("description"):
            line += f"  _{t['description']}_"
        line += f"  _(📅 {date_ref} · {source})_" if date_ref else f"  _(from {source})_"

        new_task_lines.append(line)
        new_hashes.add(h)
        stats["tasks_added"] += 1

    if new_task_lines:
        section_content = "\n".join(new_task_lines)
        existing = vault.read_section("inbox")
        combined = (section_content + "\n\n" + existing).strip() if existing else section_content
        vault.write_section("inbox", combined)

    # ── Notes (journal entries) ───────────────────────────────────────────────
    note_entries = logseq.get_recent_notes(days=days)
    new_note_lines = []
    for entry in note_entries:
        h = hashlib.sha1(entry["source"].encode()).hexdigest()[:12]
        if h in synced:
            continue
        new_note_lines.append(f"\n### {entry['date']}")
        for ln in entry["lines"]:
            new_note_lines.append(f"- {ln}")
        new_hashes.add(h)
        stats["notes_added"] += 1

    if new_note_lines:
        inbox_rel = f"000 Inbox/{today.isoformat()}-logseq.md"
        existing_dump = vault.read_file(inbox_rel) or ""
        dump_content = existing_dump + "\n".join(new_note_lines) + "\n"
        vault.write_file(inbox_rel, dump_content)

    # Persist hashes
    _save_hashes(synced | new_hashes)

    return stats


def reset_hashes() -> None:
    """Clear sync state — next run will re-sync everything. Use with caution."""
    if _HASH_FILE.exists():
        _HASH_FILE.unlink()


if __name__ == "__main__":
    result = run()
    print(
        f"Sync complete: {result['tasks_added']} tasks, "
        f"{result['notes_added']} note entries, "
        f"{result['skipped']} skipped, "
        f"{result['urls_enriched']} URLs enriched, "
        f"{result['pages_synced']} pages synced"
    )
