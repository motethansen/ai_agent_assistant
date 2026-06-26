"""
Retroactive inbox enrichment pass.

Reads the Dashboard agent:inbox section, enriches each task line:
  - Fetches page title for bare URLs and inserts "Title — " before the URL
  - Falls back to URL-slug extraction for login-walled sites (LinkedIn)
  - Copies any [[wikilink]] LogSeq pages to Obsidian 000 Inbox/LogSeq Pages/

Usage:
    python scripts/enrich_inbox.py [--dry-run] [--limit N]

Options:
    --dry-run   Print changes without writing
    --limit N   Only enrich first N bare-URL tasks (useful for testing)
"""

import sys
import re
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from integrations.logseq import LogSeqReader
from integrations.obsidian import ObsidianVault
from agents.sync_agent import (
    _fetch_url_title, _sync_wikilink_page,
    _apply_manual_titles, _url_key,
    load_manual_titles, record_unfetchable,
)

_URL_RE      = re.compile(r'(https?://\S+)', re.IGNORECASE)
_WIKILINK_RE = re.compile(r'\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]')


def _enrich_line(line: str, logseq: LogSeqReader, vault: ObsidianVault,
                 synced_pages: set, limit_hit: bool,
                 manual_titles: dict, unfetchable: list) -> tuple[str, int, int]:
    """Enrich a single task line. Returns (new_line, url_enrichments, page_syncs)."""
    if not line.startswith('- ['):
        return line, 0, 0

    url_count = 0
    page_count = 0
    enriched = line

    # ── URL title enrichment ──────────────────────────────────────────────────
    if not limit_hit:
        for url in _URL_RE.findall(enriched):
            # Already has a "Title — <url>" prefix for this specific URL?
            if re.search(r' — ' + re.escape(url), enriched):
                continue
            title = _fetch_url_title(url)
            if not title:
                # Can't auto-fetch — flag for the manual worklist unless a
                # user-supplied title already covers it (applied just below).
                if _url_key(url) not in manual_titles:
                    unfetchable.append((url, line.lstrip('- [].x ')[:80]))
                continue
            # Strip URLs before checking so slug words don't give false positives
            text_no_urls = _URL_RE.sub('', enriched)
            title_words = title.lower().split()[:4]
            already_there = all(w in text_no_urls.lower() for w in title_words if len(w) > 3)
            if not already_there:
                enriched = enriched.replace(url, f"{title} — {url}", 1)
                url_count += 1

    # ── Manual title overrides (user-filled, beats auto-fetch) ─────────────────
    enriched, n_manual = _apply_manual_titles(enriched, manual_titles)
    url_count += n_manual

    # ── Wikilink page sync (recurses into linked sub-pages) ────────────────────
    for page_name in _WIKILINK_RE.findall(enriched):
        page_count += _sync_wikilink_page(page_name, logseq, vault, synced_pages)

    return enriched, url_count, page_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only enrich first N bare-URL tasks")
    args = parser.parse_args()

    logseq = LogSeqReader()
    vault = ObsidianVault()
    synced_pages: set[str] = set()

    # User-filled titles for links that can't be auto-fetched (read once)
    manual_titles = load_manual_titles(vault)
    unfetchable: list[tuple[str, str]] = []
    if manual_titles:
        print(f"Loaded {len(manual_titles)} manual title(s) from "
              f"'000 Inbox/Manual link titles needed.md'\n")

    inbox = vault.read_section("inbox")
    if not inbox:
        print("Inbox section is empty or not found in Dashboard.")
        return

    lines = inbox.splitlines()
    updated_lines = []
    total_url = 0
    total_pages = 0
    tasks_changed = 0
    tasks_enriched = 0  # counts tasks where at least one URL was enriched

    print(f"Scanning {len(lines)} lines in the inbox section...\n")

    for line in lines:
        limit_hit = args.limit is not None and tasks_enriched >= args.limit
        new_line, n_urls, n_pages = _enrich_line(
            line, logseq, vault, synced_pages, limit_hit,
            manual_titles, unfetchable
        )

        if new_line != line:
            tasks_changed += 1
            if n_urls:
                tasks_enriched += 1
            print(f"  ✏  {line[:90]}")
            print(f"  →  {new_line[:90]}")
            if n_pages:
                print(f"     (+ {n_pages} page(s) synced to Obsidian)")
            print()

        total_url += n_urls
        total_pages += n_pages
        updated_lines.append(new_line)

    if not args.dry_run:
        vault.write_section("inbox", "\n".join(updated_lines))
        stubs = record_unfetchable(vault, unfetchable)
        print(f"✅ Done — {tasks_changed} lines updated, "
              f"{total_url} URLs enriched, "
              f"{total_pages} pages synced to Obsidian")
        if stubs:
            print(f"   📝 {stubs} un-fetchable link(s) added to the manual-titles "
                  f"note — fill in a Title: and re-run to apply.")
    else:
        unique_new = len({_url_key(u) for u, _ in unfetchable})
        print(f"[DRY RUN] Would update {tasks_changed} lines, "
              f"enrich {total_url} URLs, sync {total_pages} pages, "
              f"flag {unique_new} un-fetchable link(s) for manual titling.")


if __name__ == "__main__":
    main()
