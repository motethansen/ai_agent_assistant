"""
Retroactive inbox enrichment pass.

Reads the Dashboard ## inbox section, enriches each task line:
  - Fetches page title for bare URLs and inserts it before the URL
  - Copies any [[wikilink]] LogSeq pages to Obsidian 000 Inbox/LogSeq Pages/

Usage:
    python scripts/enrich_inbox.py [--dry-run] [--limit N]

Options:
    --dry-run   Print changes without writing
    --limit N   Only process first N tasks (useful for testing)
"""

import sys
import re
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from integrations.logseq import LogSeqReader
from integrations.obsidian import ObsidianVault
from agents.sync_agent import enrich_task_text

# Match a line like:
#   - [ ] TASK_TEXT  _(📅 2026-05-23 · journal/2026_05_23:1)_
#   - [ ] TASK_TEXT  _(from journal/2026_05_23:1)_
_TASK_LINE_RE = re.compile(
    r'^(- \[[ x]\] )(.*?)(\s{1,2}_\((?:📅 \d{4}-\d{2}-\d{2} · )?from (?:journal|page)/[^)]+\)_)$'
)
_ALREADY_ENRICHED_RE = re.compile(r' — https?://')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only process first N unenriched tasks")
    args = parser.parse_args()

    logseq = LogSeqReader()
    vault = ObsidianVault()
    synced_pages: set[str] = set()

    # Read current inbox section
    inbox = vault.read_section("inbox")
    if not inbox:
        print("Inbox section is empty or not found in Dashboard.")
        return

    lines = inbox.splitlines()
    updated_lines = []
    processed = 0
    url_enrichments = 0
    page_syncs = 0
    skipped = 0

    print(f"Processing {len(lines)} lines in inbox section...")
    print()

    for line in lines:
        m = _TASK_LINE_RE.match(line)
        if not m:
            updated_lines.append(line)
            continue

        prefix = m.group(1)     # "- [ ] "
        task_text = m.group(2)  # the actual task content
        suffix = m.group(3)     # "  _(📅 ... · journal/...)_"

        # Skip if already enriched
        if _ALREADY_ENRICHED_RE.search(task_text):
            skipped += 1
            updated_lines.append(line)
            continue

        # Limit check
        if args.limit and processed >= args.limit:
            updated_lines.append(line)
            continue

        # Enrich
        enriched_text, n_urls, n_pages = enrich_task_text(
            task_text, logseq, vault, synced_pages, fetch_titles=True
        )
        processed += 1
        url_enrichments += n_urls
        page_syncs += n_pages

        new_line = f"{prefix}{enriched_text}{suffix}"

        if enriched_text != task_text:
            short_old = task_text[:70]
            short_new = enriched_text[:70]
            print(f"  ✏  {short_old}")
            print(f"  →  {short_new}")
            if n_pages:
                print(f"     (+ {n_pages} page(s) copied to Obsidian)")
            print()

        updated_lines.append(new_line)

    # Write back
    if not args.dry_run:
        vault.write_section("inbox", "\n".join(updated_lines))
        print(f"\n✅ Done — {processed} tasks processed, "
              f"{url_enrichments} URLs enriched, "
              f"{page_syncs} pages synced to Obsidian, "
              f"{skipped} already enriched (skipped)")
    else:
        print(f"\n[DRY RUN] Would update {url_enrichments} URL titles, "
              f"sync {page_syncs} pages. "
              f"{skipped} already enriched.")


if __name__ == "__main__":
    main()
