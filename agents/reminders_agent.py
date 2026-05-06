"""
Reminders agent — on-demand Apple Reminders export to Obsidian.

Run manually with:  /sync-reminders  or  python agents/reminders_agent.py

Steps:
  1. Run AppleScript to export Apple Reminders → datainput/reminders.json
  2. Read uncompleted reminders
  3. Deduplicate against already-synced items
  4. Write new reminders to Dashboard.md inbox section
"""

import json
import subprocess
import hashlib
from pathlib import Path

from integrations.obsidian import ObsidianVault
import config

_REMINDERS_JSON = Path(__file__).parent.parent / "datainput" / "reminders.json"
_SYNCED_FILE    = Path(__file__).parent.parent / "output" / ".synced_reminders.json"

_APPLESCRIPT = """
tell application "Reminders"
    set output to ""
    repeat with reminderList in lists
        repeat with r in reminders of reminderList
            if completed of r is false then
                set output to output & name of r & "|||"
            end if
        end repeat
    end repeat
    return output
end tell
"""


def export_from_apple() -> list[dict]:
    """
    Run AppleScript to export incomplete Apple Reminders.
    Returns list of {task} dicts. Saves to reminders.json.
    macOS only — raises RuntimeError on other platforms.
    """
    import platform
    if platform.system() != "Darwin":
        raise RuntimeError("Apple Reminders export is macOS only")

    result = subprocess.run(
        ["osascript", "-e", _APPLESCRIPT],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript failed: {result.stderr.strip()}")

    raw = result.stdout.strip()
    # Names are delimited by ||| — encode in Python to avoid AppleScript JSON escaping issues
    names = [n.strip() for n in raw.split("|||") if n.strip()]
    reminders = [{"task": name} for name in names]

    _REMINDERS_JSON.parent.mkdir(parents=True, exist_ok=True)
    _REMINDERS_JSON.write_text(json.dumps(reminders, indent=2))
    return reminders


def load_from_file() -> list[dict]:
    """Load reminders from the last exported JSON (no AppleScript run)."""
    if not _REMINDERS_JSON.exists():
        return []
    try:
        return json.loads(_REMINDERS_JSON.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _load_synced() -> set[str]:
    try:
        return set(json.loads(_SYNCED_FILE.read_text()))
    except (OSError, json.JSONDecodeError):
        return set()


def _save_synced(hashes: set[str]) -> None:
    _SYNCED_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SYNCED_FILE.write_text(json.dumps(sorted(hashes), indent=2))


def _reminder_hash(reminder: dict) -> str:
    key = reminder.get("task", "").strip().lower()
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def run(export_first: bool = True) -> dict:
    """
    Sync Apple Reminders → Obsidian Dashboard inbox.

    export_first: if True, runs AppleScript export before syncing.
    Returns {exported, added, skipped, errors}.
    """
    stats = {"exported": 0, "added": 0, "skipped": 0, "errors": []}

    # Step 1: Export from Apple
    if export_first:
        try:
            reminders = export_from_apple()
            stats["exported"] = len(reminders)
        except Exception as e:
            stats["errors"].append(str(e))
            reminders = load_from_file()
            stats["exported"] = len(reminders)
    else:
        reminders = load_from_file()
        stats["exported"] = len(reminders)

    if not reminders:
        return stats

    # Step 2: Deduplicate
    synced = _load_synced()
    new_hashes = set()
    new_lines = []

    for r in reminders:
        h = _reminder_hash(r)
        if h in synced:
            stats["skipped"] += 1
            continue
        task = r.get("task", "").strip()
        if not task:
            continue
        new_lines.append(f"- [ ] {task}  _(from Apple Reminders)_")
        new_hashes.add(h)
        stats["added"] += 1

    # Step 3: Write to Dashboard inbox
    if new_lines:
        vault = ObsidianVault()
        existing = vault.read_section("inbox")
        content = "\n".join(new_lines)
        combined = (content + "\n\n" + existing).strip() if existing else content
        vault.write_section("inbox", combined)
        _save_synced(synced | new_hashes)

    return stats


if __name__ == "__main__":
    result = run(export_first=True)
    print(f"Reminders sync: {result['exported']} exported, {result['added']} added, {result['skipped']} skipped")
    if result["errors"]:
        for e in result["errors"]:
            print(f"  Error: {e}")
