#!/usr/bin/env python3
"""Convert enriched `Title — URL` task lines into Markdown links `[Title](URL)`.

Runs after enrich_task_urls.py: turns every `<title> — <url>` in a task line into a
proper Obsidian markdown link, so the reading view shows a clean clickable title.
Pure text transform (no network). Idempotent — lines already containing a
`](http…)` markdown link are skipped.

SAFE BY DEFAULT — dry-run mutates nothing (writes output/mdlink_preview.md).
--apply backs up touched files + writes a reversible log. --revert restores.

    python scripts/mdlink_tasks.py [--limit N]     # dry-run
    python scripts/mdlink_tasks.py --apply
    python scripts/mdlink_tasks.py --revert output/mdlink_<ts>.json
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from integrations.obsidian import ObsidianVault

OUT = Path(__file__).parent.parent / "output"
OUT.mkdir(exist_ok=True)

_PREFIX = re.compile(r"^(\s*- \[[ xX]\]\s*)(.*)$")
# "<title> — <url>"  →  the title is the run of text up to the em-dash before the URL
_TM = re.compile(r"(.+?)\s+—\s+(https?://\S+)")


def convert(raw: str) -> str:
    m = _PREFIX.match(raw)
    if not m:
        return raw
    prefix, content = m.group(1), m.group(2)
    if "](http" in content:              # already has a markdown link → leave the line alone
        return raw

    def repl(mm: re.Match) -> str:
        title = mm.group(1).strip().strip("*").replace("[", "").replace("]", "").strip()
        return f"[{title}]({mm.group(2)})" if title else mm.group(0)

    return prefix + _TM.sub(repl, content)


def build_plan(vault: ObsidianVault, limit: int | None) -> list[dict]:
    plan = []
    for t in vault.get_tasks(include_done=True):
        raw = t.get("raw", "")
        if " — http" not in raw:         # only lines with the "Title — url" pattern
            continue
        new = convert(raw)
        if new != raw:
            plan.append({"file": t["file"], "line": t["line"], "old": raw, "new": new})
            if limit and len(plan) >= limit:
                break
    (OUT / "mdlink_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    prev = ["# Markdown-link conversion preview (nothing applied)", ""]
    for p in plan[:60]:
        prev += [f"- {p['file']}:{p['line']}", f"    − {p['old']}", f"    + {p['new']}", ""]
    (OUT / "mdlink_preview.md").write_text("\n".join(prev), encoding="utf-8")
    print(f"▸ {len(plan)} task lines to convert to markdown links · preview: {OUT/'mdlink_preview.md'}")
    return plan


def apply(plan: list[dict], vault: ObsidianVault):
    ts = int(time.time())
    backup = OUT / f"mdlink_backup_{ts}"
    by_file = defaultdict(list)
    for p in plan:
        by_file[p["file"]].append(p)
    for rel, items in by_file.items():
        abs_path = vault.vault_dir / rel
        try:
            content = abs_path.read_text(encoding="utf-8")
        except OSError:
            print(f"  ! skip unreadable {rel}")
            continue
        b = backup / rel
        b.parent.mkdir(parents=True, exist_ok=True)
        b.write_text(content, encoding="utf-8")
        lines = content.splitlines()
        for p in items:
            i = p["line"] - 1
            if 0 <= i < len(lines) and lines[i].rstrip() == p["old"]:
                lines[i] = p["new"]
            else:
                print(f"  ! line drift {rel}:{p['line']} — skipped")
        abs_path.write_text("\n".join(lines) + ("\n" if content.endswith("\n") else ""), encoding="utf-8")
    log = OUT / f"mdlink_{ts}.json"
    log.write_text(json.dumps({"backup": str(backup), "plan": plan}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✓ converted {len(plan)} lines · backup: {backup} · log: {log}")
    print("  revert with:  python scripts/mdlink_tasks.py --revert " + str(log))


def revert(log_path: str, vault: ObsidianVault):
    data = json.loads(Path(log_path).read_text(encoding="utf-8"))
    backup = Path(data["backup"])
    n = 0
    for rel in {p["file"] for p in data["plan"]}:
        b = backup / rel
        if b.exists():
            shutil.copy2(b, vault.vault_dir / rel)
            n += 1
    print(f"✓ reverted {n} files from {backup}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--revert", metavar="LOG")
    args = ap.parse_args()
    vault = ObsidianVault()
    if args.revert:
        revert(args.revert, vault)
        return
    if args.apply and (OUT / "mdlink_plan.json").exists():
        plan = json.loads((OUT / "mdlink_plan.json").read_text(encoding="utf-8"))
        print(f"▸ applying saved plan ({len(plan)} lines)")
    else:
        plan = build_plan(vault, args.limit)
    if args.apply and plan:
        apply(plan, vault)
    elif not args.apply:
        print("\n(DRY-RUN — nothing changed. Re-run with --apply.)")


if __name__ == "__main__":
    main()
