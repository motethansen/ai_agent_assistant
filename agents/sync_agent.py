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
import urllib.parse
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


_YOUTUBE_RE = re.compile(
    r'(?:youtube\.com/(?:watch\?|.*[?&]v=)|youtu\.be/|youtube\.com/(?:shorts|embed)/)',
    re.IGNORECASE,
)


def _fetch_youtube_title(url: str) -> str | None:
    """Fetch a YouTube video title via the oEmbed API (no auth, returns JSON)."""
    try:
        oembed = "https://www.youtube.com/oembed?url=" + urllib.parse.quote(url, safe="") + "&format=json"
        req = urllib.request.Request(oembed, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read(20_000).decode("utf-8", errors="replace"))
        title = " ".join((data.get("title") or "").split())
        if title and len(title) > 4:
            return title[:120]
    except Exception:
        pass
    return None


def _fetch_url_title(url: str) -> str | None:
    """Fetch the <title> for a URL. Returns None on failure or timeout."""
    # YouTube blocks scrapers / serves a consent wall — use oEmbed instead.
    if _YOUTUBE_RE.search(url):
        yt = _fetch_youtube_title(url)
        if yt:
            return yt
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
        title = " ".join((parser.title or "").split())  # collapse whitespace / newlines
        # Strip " | Site Name" and " | Author Name, Credentials" suffixes
        title = re.sub(
            r'\s*[|·—–-]\s*(LinkedIn|GitHub|YouTube|Facebook|Twitter|X|Instagram|TikTok|Substack|Medium).*$',
            '', title, flags=re.IGNORECASE,
        ).strip()
        # Strip any remaining " | short suffix" (≤40 chars) — catches author bylines
        title = re.sub(r'\s*\|\s*.{1,40}$', '', title).strip()
        if title and len(title) > 4:
            return title[:120]
        return None
    except Exception:
        pass

    # Fallback: derive a readable title from the URL slug for login-walled sites
    # LinkedIn pattern: /posts/<author>_<content-slug>-ugcPost-<id> or -share-<id>
    if 'linkedin.com/posts/' in url:
        m = re.search(r'linkedin\.com/posts/[^_/]+_(.+?)(?:-ugcPost|-share)-\d', url)
        if m:
            slug = m.group(1).replace('-', ' ').strip()
            if len(slug) > 4:
                title = slug[:100].rsplit(' ', 1)[0] if len(slug) > 100 else slug
                return f"{title.capitalize()} [LinkedIn]"

    return None


# ── Wikilink page sync ────────────────────────────────────────────────────────

_LOGSEQ_PAGES_INBOX = "000 Inbox/LogSeq Pages"
_MAX_SUBPAGE_DEPTH = 3  # how deep to follow [[sub-page]] chains


def _find_page_file(logseq: LogSeqReader, key: str) -> Path | None:
    """Case-insensitive lookup of a LogSeq page file by name (without extension)."""
    pages_dir = logseq.pages_dir
    if not pages_dir.exists():
        return None
    for f in pages_dir.iterdir():
        if f.suffix == ".md" and f.stem.lower() == key:
            return f
    return None


def _sync_wikilink_page(
    page_name: str,
    logseq: LogSeqReader,
    vault: ObsidianVault,
    synced_pages: set[str],
    _depth: int = 0,
) -> int:
    """
    Copy a LogSeq page to Obsidian inbox, then recursively copy any sub-pages it
    links to via [[...]] (up to _MAX_SUBPAGE_DEPTH). `synced_pages` doubles as a
    cycle/duplicate guard. Returns the number of new Obsidian files written
    (this page plus its descendants).
    """
    key = page_name.strip().lower()
    if key in synced_pages:
        return 0  # already processed this session (also breaks link cycles)

    target_file = _find_page_file(logseq, key)
    if not target_file:
        return 0  # not a real LogSeq page (just a tag/category ref)

    # Mark before recursing so a page that links back to us doesn't loop.
    synced_pages.add(key)

    content = target_file.read_text(encoding="utf-8", errors="replace")

    written = 0
    obs_rel = f"{_LOGSEQ_PAGES_INBOX}/{target_file.name}"
    obs_path = vault.vault_dir / obs_rel
    # Skip the write if it already exists (don't clobber manual edits), but still
    # recurse into its sub-pages — they may not have been extracted yet.
    if not obs_path.exists():
        header = f"> Synced from LogSeq page: `pages/{target_file.name}`  \n> Sync date: {datetime.date.today()}\n\n"
        vault.write_file(obs_rel, header + content)
        written = 1

    # ── Recurse into linked sub-pages ─────────────────────────────────────────
    if _depth < _MAX_SUBPAGE_DEPTH:
        for sub_name in _WIKILINK_RE.findall(content):
            written += _sync_wikilink_page(
                sub_name, logseq, vault, synced_pages, _depth + 1
            )

    return written


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
            # Skip this specific URL if it already has a " — <url>" prefix
            if re.search(r' — ' + re.escape(url), text):
                continue
            title = _fetch_url_title(url)
            if title:
                # Check in text-without-URLs so slug words in the URL don't
                # fool us into thinking the title is already visible to the user
                text_no_urls = _URL_RE.sub('', text)
                title_words = title.lower().split()[:4]
                already_there = all(w in text_no_urls.lower() for w in title_words if len(w) > 3)
                if not already_there:
                    text = text.replace(url, f"{title} — {url}", 1)
                    url_count += 1

    # ── 2. Wikilink page sync ─────────────────────────────────────────────────
    wikilinks = _WIKILINK_RE.findall(text)
    for page_name in wikilinks:
        page_count += _sync_wikilink_page(page_name, logseq, vault, synced_pages)

    return text, url_count, page_count


# ── Task line builder ─────────────────────────────────────────────────────────

_DATE_NORM_RE = re.compile(r'(\d{4})[/_-](\d{1,2})[/_-](\d{1,2})')


def _normalise_date(raw: str) -> str | None:
    """Return 'YYYY-MM-DD' from various date formats, or None if unparseable."""
    m = _DATE_NORM_RE.search(raw.strip())
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return None


def _build_task_line(task_text: str, task: dict, date_ref: str) -> str:
    """
    Compose a full Obsidian Tasks-plugin-compatible checkbox line.

    Format:
      - [ ] <text>  _<description>_  _(📅 journal-date · source)_  📅 deadline  ⏳ scheduled  #tag1 #tag2
    """
    props = task.get("properties", {})

    line = f"- [ ] {task_text}"

    if task.get("description"):
        line += f"  _{task['description']}_"

    line += f"  _(📅 {date_ref} · {task.get('source', '')})_" if date_ref else f"  _(from {task.get('source', '')})_"

    # Obsidian Tasks: due date
    if "deadline" in props:
        d = _normalise_date(props["deadline"])
        if d:
            line += f" 📅 {d}"

    # Obsidian Tasks: scheduled date
    if "scheduled" in props:
        s = _normalise_date(props["scheduled"])
        if s:
            line += f" ⏳ {s}"

    # Tags: LogSeq `:tags: foo, bar` → `#foo #bar`
    if "tags" in props:
        raw_tags = props["tags"]
        tags = [t.strip().lstrip("#").replace(" ", "-") for t in raw_tags.split(",") if t.strip()]
        if tags:
            line += "  " + " ".join(f"#{t}" for t in tags)

    return line


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

        # Build the task line with date reference + LogSeq properties
        source = t.get("source", "")
        date_ref = ""
        dm = re.search(r"journal/(\d{4}_\d{2}_\d{2})", source)
        if dm:
            date_ref = dm.group(1).replace("_", "-")

        line = _build_task_line(task_text, t, date_ref)

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

    # ── Kanban refresh — push new inbox tasks to Queued column ────────────────
    try:
        from agents.kanban_agent import run as kanban_run
        k = kanban_run(push_inbox=True, push_due=True)
        stats["kanban_added"] = k.get("added", 0)
    except Exception:
        stats["kanban_added"] = 0

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
