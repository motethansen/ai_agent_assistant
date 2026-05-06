"""
Evernote web-clip archiver — moves detected web clips to a disposal folder.

A "web clip" is an Evernote note that captured a web page rather than original
writing. They typically contain scraped navigation menus, embedded resource
images, and external links — low signal for a knowledge base.

Detection uses a scoring system (threshold ≥ 3):
  +3  References ./_resources/ or ./Note.resources/ (Evernote clip image dirs)
  +2  Contains navigation markers ("Main Menu", "Back To", "Subscribe")
  +2  First 50 lines have >5 distinct external HTTP links
  +1  Contains ad/social markers (advertisement, disqus, share buttons)
  +1  Title looks like a scraped page title (long, has | or — separators)

Clips are moved to:
  900 Archive/Evernote Web Clips Disposal/<original notebook>/

Usage:
    python scripts/archive_evernote_clips.py          # dry-run (safe)
    python scripts/archive_evernote_clips.py --execute # actually move files
    python scripts/archive_evernote_clips.py --notebook Archive  # one notebook
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

# ── Detection patterns ────────────────────────────────────────────────────────

_RESOURCES_RE  = re.compile(r'!\[\[\./_resources/|!\[\[\./[^/\]]+\.resources/')
_NAV_RE        = re.compile(
    r'##?\s*Main Menu|Back To\s+\[|##?\s*Navigation|##?\s*Site Map'
    r'|\[Skip to|##?\s*Table of Contents\n.*\n.*\[',
    re.IGNORECASE,
)
_SOCIAL_RE     = re.compile(
    r'advertisement|#disqus_thread|disqus\.com|addthis\.com'
    r'|share this|tweet this|follow us|subscribe (now|today|free)',
    re.IGNORECASE,
)
_EXTERNAL_LINK_RE = re.compile(r'\[.+?\]\(https?://([^)]+)\)')
_TITLE_JUNK_RE    = re.compile(r'[|–—]\s*(Home|Blog|Official|Wikipedia|YouTube)', re.IGNORECASE)


def _score_note(abs_path: Path) -> int:
    try:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0

    score = 0

    if _RESOURCES_RE.search(text):
        score += 3

    preview = "\n".join(text.splitlines()[:50])
    if _NAV_RE.search(preview):
        score += 2

    domains = set(m.group(1).split("/")[0] for m in _EXTERNAL_LINK_RE.finditer(preview))
    if len(domains) > 5:
        score += 2

    if _SOCIAL_RE.search(text[:6000]):
        score += 1

    if _TITLE_JUNK_RE.search(abs_path.stem):
        score += 1

    return score


CLIP_THRESHOLD = 3


# ── Move logic ────────────────────────────────────────────────────────────────

def _resources_dir(note_path: Path) -> Path | None:
    """Return the _resources dir for this note if it exists."""
    # Evernote exports resources as ./Note_Title.resources/ or ./_resources/
    stem = note_path.stem
    candidates = [
        note_path.parent / f"{stem}.resources",
        note_path.parent / "_resources",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def archive_clips(
    vault_dir: Path,
    evernote_root: Path,
    disposal_root: Path,
    notebook_filter: str | None = None,
    dry_run: bool = True,
) -> dict:
    stats = {"scanned": 0, "clips": 0, "moved": 0, "errors": []}
    moves: list[tuple[Path, Path]] = []

    for notebook_dir in sorted(evernote_root.iterdir()):
        if not notebook_dir.is_dir() or notebook_dir.name.startswith("_"):
            continue
        if notebook_filter and notebook_dir.name != notebook_filter:
            continue

        dest_notebook = disposal_root / notebook_dir.name

        for note_path in sorted(notebook_dir.rglob("*.md")):
            # Skip notes inside _resources dirs
            if "_resources" in note_path.parts:
                continue
            stats["scanned"] += 1
            score = _score_note(note_path)
            if score < CLIP_THRESHOLD:
                continue

            stats["clips"] += 1
            rel = note_path.relative_to(notebook_dir)
            dest_note = dest_notebook / rel
            moves.append((note_path, dest_note, score))

    # Sort by notebook then title for readable output
    moves.sort(key=lambda x: (x[0].parent.name, x[0].stem.lower()))

    print(f"\nScanned {stats['scanned']} notes — {len(moves)} web clips detected\n")
    print(f"{'Score':<7} {'Notebook':<35} {'Note title'}")
    print("-" * 80)

    notebooks_seen: set = set()
    for note_path, dest_note, score in moves:
        notebook = note_path.parent.name if note_path.parent != evernote_root else "—"
        # Use the immediate notebook subdir name
        for part in note_path.relative_to(evernote_root).parts[:-1]:
            if not part.startswith("_"):
                notebook = part
                break
        title = note_path.stem[:50]
        print(f"  [{score}]   {notebook:<35} {title}")
        notebooks_seen.add(notebook)

    print(f"\n{len(notebooks_seen)} notebooks affected.")
    if dry_run:
        print("\n[DRY RUN] No files moved. Pass --execute to move them.")
        return stats

    print(f"\nMoving {len(moves)} files to {disposal_root.relative_to(vault_dir)} ...")
    for note_path, dest_note, score in moves:
        try:
            dest_note.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(note_path), str(dest_note))
            stats["moved"] += 1

            # Move associated resources dir if it co-locates with the note
            res = _resources_dir(note_path)
            if res and res.is_dir():
                dest_res = dest_note.parent / res.name
                shutil.move(str(res), str(dest_res))
        except Exception as e:
            stats["errors"].append(f"{note_path}: {e}")

    print(f"Moved {stats['moved']} clips. Errors: {len(stats['errors'])}")
    for e in stats["errors"]:
        print(f"  ERROR: {e}")
    return stats


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Archive Evernote web clips")
    parser.add_argument("--execute", action="store_true",
                        help="Actually move files (default is dry-run)")
    parser.add_argument("--notebook", metavar="NAME",
                        help="Process only this notebook subfolder")
    args = parser.parse_args()

    vault = Path(config.paths.obsidian())
    evernote_root = (
        vault
        / "900 Archive"
        / "Imported Evernote"
        / "transfer_notes_to update"
        / "Bucket"
        / "Evernote"
    )
    disposal_root = vault / "900 Archive" / "Evernote Web Clips Disposal"

    if not evernote_root.is_dir():
        print(f"Evernote root not found: {evernote_root}")
        sys.exit(1)

    archive_clips(
        vault_dir=vault,
        evernote_root=evernote_root,
        disposal_root=disposal_root,
        notebook_filter=args.notebook,
        dry_run=not args.execute,
    )
