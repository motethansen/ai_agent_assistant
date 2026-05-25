"""
One-off backfill: sync ALL LogSeq journal files into Obsidian.

Usage:
    python scripts/backfill_logseq.py [--dry-run] [--days N]

Options:
    --dry-run   Print what would be added without writing anything
    --days N    Only go back N days (default: all files)
"""

import sys
import argparse
import hashlib
import json
import datetime
from pathlib import Path

# make sure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from integrations.logseq import LogSeqReader
from integrations.obsidian import ObsidianVault
import config

_HASH_FILE = Path(__file__).parent.parent / "output" / ".synced_hashes.json"


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days", type=int, default=None,
                        help="Limit to N most recent journal files (default: all)")
    args = parser.parse_args()

    logseq = LogSeqReader()
    vault = ObsidianVault()
    synced = _load_hashes()
    new_hashes = set()

    journals_dir = logseq.journals_dir
    import re
    all_files = sorted(
        [f for f in journals_dir.iterdir()
         if re.match(r"\d{4}_\d{2}_\d{2}\.md$", f.name)],
        key=lambda f: f.name,
        reverse=True,
    )

    if args.days:
        all_files = all_files[:args.days]

    print(f"Found {len(all_files)} journal files to scan")
    print(f"Already synced: {len(synced)} task hashes")
    print()

    total_new = 0
    total_skip = 0

    for f in reversed(all_files):  # oldest first so inbox order is chronological
        tasks = logseq.parse_tasks(logseq._read(f), source=f"journal/{f.stem}")
        if not tasks:
            continue

        new_lines = []
        for t in tasks:
            h = _task_hash(t)
            if h in synced or h in new_hashes:
                total_skip += 1
                continue
            task_text = t["task"].strip()
            if not task_text:
                total_skip += 1
                continue
            line = f"- [ ] {task_text}  _(from {t['source']})_"
            new_lines.append(line)
            new_hashes.add(h)
            total_new += 1

        if new_lines:
            date_label = f.stem.replace("_", "-")
            print(f"  {date_label}: {len(new_lines)} new task(s)")
            for ln in new_lines:
                print(f"    {ln[:90]}")
            print()

            if not args.dry_run:
                existing = vault.read_section("inbox") or ""
                header = f"\n<!-- {date_label} -->\n"
                combined = header + "\n".join(new_lines) + "\n" + existing
                vault.write_section("inbox", combined)

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Done — {total_new} new tasks, {total_skip} skipped")

    if not args.dry_run and new_hashes:
        _save_hashes(synced | new_hashes)
        print(f"Hash file updated ({len(synced) + len(new_hashes)} total entries)")


if __name__ == "__main__":
    main()
