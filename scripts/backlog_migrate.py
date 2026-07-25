#!/usr/bin/env python3
"""Backlog migration — move every DATED Obsidian task into an undated, categorised backlog.

The vault carries hundreds of long-overdue tasks. This strips the 📅/⏳ deadline from each
dated task (IN PLACE) and tags it with an AI-derived #category, so "undated" = the backlog.
Set a new deadline later via the API (POST /tasks/deadline or POST /categories/deadline).

SAFE BY DEFAULT — dry-run mutates nothing: it writes a preview (output/Backlog_preview.md +
output/backlog_plan.json) and prints a summary. Use --apply to edit the vault; it backs up
every touched file and writes a reversible migration log first.

    python scripts/backlog_migrate.py                 # dry-run (default)
    python scripts/backlog_migrate.py --apply
    python scripts/backlog_migrate.py --revert output/backlog_migration_<ts>.json
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from integrations.obsidian import ObsidianVault
from llm import router

_DATE_RE = re.compile(r"\s*(?:📅|⏳)\s*\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?")
_URL_RE = re.compile(r"https?://\S+")
OUT = Path(__file__).parent.parent / "output"
OUT.mkdir(exist_ok=True)

# Clean scope: skip the assistant's own generated / capture files and reading-link junk.
_EXCLUDE_FILE_PREFIXES = ("010 Planning/",)
_EXCLUDE_FILES = {"000 Inbox/Reading List.md", "000 Inbox/Reminders Backlog.md"}


def _excluded_file(f: str) -> bool:
    # generated files: 010 Planning/*, the inbox capture files, and per-folder _plan.md
    return (f in _EXCLUDE_FILES
            or any(f.startswith(p) for p in _EXCLUDE_FILE_PREFIXES)
            or Path(f).name == "_plan.md")


def _reason_to_skip(t: dict) -> str | None:
    """Return why a dated task should be skipped, or None to keep it."""
    txt = (t.get("text") or "").strip()
    if not txt:
        return "empty"
    if _URL_RE.search(txt):
        return "reading-link"
    if _excluded_file(t["file"]):
        return "generated-file"
    return None


# ── LLM helpers (robust JSON extraction) ─────────────────────────────────────
def _json_slice(raw: str, open_ch: str, close_ch: str):
    i, j = raw.find(open_ch), raw.rfind(close_ch)
    if i == -1 or j == -1 or j < i:
        return None
    try:
        return json.loads(raw[i:j + 1])
    except json.JSONDecodeError:
        return None


def propose_categories(samples: list[str]) -> list[str]:
    listing = "\n".join(f"- {s[:140]}" for s in samples[:80])
    prompt = (
        f"Here is a sample of my to-do tasks:\n\n{listing}\n\n"
        "Propose 8–12 concise lowercase single-word categories that together organise ALL such "
        "tasks (examples: finance, dev, writing, learning, admin, health, reading, errands, home). "
        "Return ONLY a JSON array of category slugs."
    )
    got = _json_slice(router.ask(prompt, task="planning", system="You output only valid JSON."), "[", "]")
    cats = [str(c).lower().strip() for c in got] if isinstance(got, list) else []
    cats = [c for c in cats if c.isascii() and c.replace("-", "").isalnum()]
    if "uncategorized" not in cats:
        cats.append("uncategorized")
    return cats or ["dev", "writing", "learning", "finance", "admin", "personal", "reading", "errands", "uncategorized"]


def classify(tasks: list[dict], cats: list[str]) -> dict[int, str]:
    cset = set(cats)
    out: dict[int, str] = {}
    B = 40
    for i in range(0, len(tasks), B):
        batch = tasks[i:i + B]
        listing = "\n".join(f"{j}: {t['text'][:160]}" for j, t in enumerate(batch))
        prompt = (
            f"Categories: {', '.join(cats)}.\n\n"
            f"Assign each task to exactly ONE category (use 'uncategorized' if none fit):\n\n{listing}\n\n"
            'Return ONLY a JSON object mapping the number to the category, e.g. {"0":"dev","1":"finance"}.'
        )
        m = _json_slice(router.ask(prompt, task="planning", system="You output only valid JSON."), "{", "}") or {}
        for j, t in enumerate(batch):
            c = str(m.get(str(j), "uncategorized")).lower().strip()
            out[i + j] = c if c in cset else "uncategorized"
    return out


# ── line transform ───────────────────────────────────────────────────────────
def strip_and_tag(raw: str, category: str) -> str:
    line = _DATE_RE.sub("", raw)
    line = re.sub(r"  +", " ", line).rstrip()
    tag = f"#{category}"
    if category != "uncategorized" and tag not in line.split():
        line = f"{line} {tag}"
    return line


# ── main ─────────────────────────────────────────────────────────────────────
def build_plan(vault: ObsidianVault) -> list[dict]:
    dated = [t for t in vault.get_tasks() if (t.get("due_date") or t.get("scheduled_date")) and not t.get("is_done")]
    # clean scope: drop empty / reading-link / generated-file tasks
    skipped = Counter()
    tasks = []
    for t in dated:
        r = _reason_to_skip(t)
        if r:
            skipped[r] += 1
        else:
            tasks.append(t)
    print(f"▸ {len(dated)} dated tasks · kept {len(tasks)} · skipped {sum(skipped.values())} "
          f"({', '.join(f'{k}:{v}' for k, v in skipped.most_common())})")
    if not tasks:
        return []
    print("▸ proposing categories…")
    cats = propose_categories([t["text"] for t in tasks])
    print(f"  categories: {', '.join(cats)}")
    print("▸ classifying (batched)…")
    assigned = classify(tasks, cats)
    plan = []
    for idx, t in enumerate(tasks):
        cat = assigned.get(idx, "uncategorized")
        old_date = str(t.get("due_date") or t.get("scheduled_date"))
        plan.append({
            "file": t["file"], "line": t["line"], "old": t["raw"],
            "new": strip_and_tag(t["raw"], cat), "category": cat,
            "old_date": old_date, "text": t["text"],
        })
    return plan


def write_preview(plan: list[dict]):
    by_cat = defaultdict(list)
    for p in plan:
        by_cat[p["category"]].append(p)
    counts = Counter(p["category"] for p in plan)
    lines = ["# Backlog (preview — nothing applied yet)", "",
             f"> {len(plan)} dated tasks → undated + categorised. Review, then run with `--apply`.", ""]
    for cat, items in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"## {cat}  ({len(items)})")
        for p in sorted(items, key=lambda x: x["text"].lower()):
            lines.append(f"- [ ] {p['text']}  ·  _(was 📅 {p['old_date']}, in {p['file']})_")
        lines.append("")
    (OUT / "Backlog_preview.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "backlog_plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n▸ category distribution:")
    for cat, n in counts.most_common():
        print(f"    {cat:16} {n}")
    print(f"\n▸ preview written: {OUT/'Backlog_preview.md'}  ({len(plan)} tasks)")


def apply(plan: list[dict], vault: ObsidianVault):
    import time
    ts = int(vault.vault_dir.stat().st_mtime)  # deterministic-ish; avoid Date in workflows only
    ts = int(time.time())
    backup = OUT / f"vault_backup_{ts}"
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
        # backup
        bpath = backup / rel
        bpath.parent.mkdir(parents=True, exist_ok=True)
        bpath.write_text(content, encoding="utf-8")
        lines = content.splitlines()
        for p in items:
            i = p["line"] - 1
            if 0 <= i < len(lines) and lines[i].rstrip() == p["old"]:
                lines[i] = p["new"]
            else:
                print(f"  ! line drift in {rel}:{p['line']} — skipped (content changed)")
        abs_path.write_text("\n".join(lines) + ("\n" if content.endswith("\n") else ""), encoding="utf-8")

    log = OUT / f"backlog_migration_{ts}.json"
    log.write_text(json.dumps({"backup": str(backup), "plan": plan}, indent=2, ensure_ascii=False), encoding="utf-8")
    write_backlog_index(plan, vault)
    print(f"\n✓ applied {len(plan)} tasks · backup: {backup} · log: {log}")
    print("  revert with:  python scripts/backlog_migrate.py --revert " + str(log))


def write_backlog_index(plan: list[dict], vault: ObsidianVault):
    by_cat: dict[str, dict[str, dict]] = defaultdict(dict)   # cat → {norm_text: task}  (deduped)
    for p in plan:
        by_cat[p["category"]].setdefault(p["text"].strip().lower(), p)
    lines = ["# Backlog", "", "> Undated tasks by category. Set a deadline on a task or a whole",
             "> category via the assistant API (`POST /tasks/deadline`, `POST /categories/deadline`).", ""]
    for cat, items in sorted(by_cat.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"## {cat}  ({len(items)})")
        for p in sorted(items.values(), key=lambda x: x["text"].lower()):
            lines.append(f"- [ ] {p['text']} #{cat}")
        lines.append("")
    (vault.vault_dir / "Backlog.md").write_text("\n".join(lines), encoding="utf-8")


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
    ap.add_argument("--apply", action="store_true", help="edit the vault (default: dry-run)")
    ap.add_argument("--revert", metavar="LOG", help="restore files from a migration log's backup")
    args = ap.parse_args()
    vault = ObsidianVault()

    if args.revert:
        revert(args.revert, vault)
        return
    if args.apply and (OUT / "backlog_plan.json").exists():
        plan = json.loads((OUT / "backlog_plan.json").read_text(encoding="utf-8"))
        print(f"▸ applying saved plan ({len(plan)} tasks) from output/backlog_plan.json")
    else:
        plan = build_plan(vault)
        write_preview(plan)
    if args.apply and plan:
        apply(plan, vault)
    elif not args.apply:
        print("\n(DRY-RUN — nothing changed. Re-run with --apply to migrate.)")


if __name__ == "__main__":
    main()
