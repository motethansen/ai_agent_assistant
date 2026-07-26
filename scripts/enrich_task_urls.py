#!/usr/bin/env python3
"""Enrich every vault TASK line containing a URL with the link's title.

For each `- [ ]` / `- [x]` line with an http(s) URL, fetch the page title (YouTube
oEmbed · HTML <title>/OG · LinkedIn slug fallback — reusing agents.sync_agent) and
rewrite `<url>` → `Title — <url>`, so the task reads clearly and stays clickable.
Idempotent: a line already carrying the title is left alone.

SAFE BY DEFAULT — dry-run mutates nothing (writes output/enrich_preview.md +
output/enrich_plan.json). --apply backs up touched files + writes a reversible log.

    python scripts/enrich_task_urls.py [--limit N]     # dry-run
    python scripts/enrich_task_urls.py --apply         # applies the saved plan
    python scripts/enrich_task_urls.py --revert output/enrich_urls_<ts>.json
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
from agents.sync_agent import (  # reuse the existing title machinery
    _fetch_url_title, _url_key, load_manual_titles, _apply_manual_titles, record_unfetchable,
)

_URL_RE = re.compile(r"(https?://\S+)", re.IGNORECASE)
OUT = Path(__file__).parent.parent / "output"
OUT.mkdir(exist_ok=True)

_title_cache: dict[str, str | None] = {}


def _title(url: str) -> str | None:
    k = _url_key(url)
    if k not in _title_cache:
        _title_cache[k] = _fetch_url_title(url)
    return _title_cache[k]


def enrich_line(raw: str, manual: dict, unfetchable: list) -> tuple[str, int]:
    """Return (new_line, n_changes). Mirrors scripts/enrich_inbox.py per-line logic."""
    line = raw
    changed = 0
    for url in _URL_RE.findall(line):
        if re.search(r" — " + re.escape(url), line):   # already "Title — url"
            continue
        title = _title(url)
        if not title:
            if _url_key(url) not in manual:
                unfetchable.append((url, raw.lstrip("- [].xX ")[:80]))
            continue
        text_no_urls = _URL_RE.sub("", line).lower()
        words = [w for w in title.lower().split()[:4] if len(w) > 3]
        if not all(w in text_no_urls for w in words):   # title not already in the text
            line = line.replace(url, f"{title} — {url}", 1)
            changed += 1
    line, n = _apply_manual_titles(line, manual)
    return line, changed + n


def build_plan(vault: ObsidianVault, limit: int | None) -> list[dict]:
    manual = load_manual_titles()
    unfetchable: list = []
    url_tasks = [t for t in vault.get_tasks(include_done=True) if _URL_RE.search(t.get("raw", ""))]
    print(f"▸ {len(url_tasks)} task lines contain a URL — fetching titles (cached)…")
    plan = []
    for t in url_tasks:
        if limit and len(plan) >= limit:
            break
        new, n = enrich_line(t["raw"], manual, unfetchable)
        if n and new != t["raw"]:
            plan.append({"file": t["file"], "line": t["line"], "old": t["raw"], "new": new})
    for u, ctx in unfetchable:
        record_unfetchable(u, ctx)
    print(f"▸ {len(plan)} lines to enrich · {len(set(_url_key(u) for u, _ in unfetchable))} URLs unfetchable "
          f"(logged for the manual worklist)")
    (OUT / "enrich_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    prev = ["# URL enrichment preview (nothing applied)", ""]
    for p in plan[:60]:
        prev += [f"- {p['file']}:{p['line']}", f"    − {p['old']}", f"    + {p['new']}", ""]
    (OUT / "enrich_preview.md").write_text("\n".join(prev), encoding="utf-8")
    print(f"▸ preview: {OUT/'enrich_preview.md'}")
    return plan


def apply(plan: list[dict], vault: ObsidianVault):
    ts = int(time.time())
    backup = OUT / f"enrich_backup_{ts}"
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
    log = OUT / f"enrich_urls_{ts}.json"
    log.write_text(json.dumps({"backup": str(backup), "plan": plan}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✓ enriched {len(plan)} lines · backup: {backup} · log: {log}")
    print("  revert with:  python scripts/enrich_task_urls.py --revert " + str(log))


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
    if args.apply and (OUT / "enrich_plan.json").exists():
        plan = json.loads((OUT / "enrich_plan.json").read_text(encoding="utf-8"))
        print(f"▸ applying saved plan ({len(plan)} lines)")
    else:
        plan = build_plan(vault, args.limit)
    if args.apply and plan:
        apply(plan, vault)
    elif not args.apply:
        print("\n(DRY-RUN — nothing changed. Re-run with --apply.)")


if __name__ == "__main__":
    main()
