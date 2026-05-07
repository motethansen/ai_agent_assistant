"""
Project planning agent — groups tasks by project folder, enriches URL-only tasks,
and writes a per-project _plan.md with categorised tasks and a suggested next action.

Usage:
    from agents.project_agent import run
    stats = run(subdir="400 Projects")

    /organise-projects [subdir]
"""

import datetime
import re
from html.parser import HTMLParser
from pathlib import Path

import requests

from integrations.obsidian import ObsidianVault
from llm import router

_URL_RE = re.compile(r'^https?://\S+$')

_SYSTEM_PROMPT = (
    "You are a personal productivity assistant. "
    "Be concise. Plain text only — no JSON, no markdown headers."
)


# ── URL enrichment ────────────────────────────────────────────────────────────

class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            d = dict(attrs)
            name = d.get("name", "").lower()
            prop = d.get("property", "").lower()
            if name in ("description",) or prop in ("og:description",):
                if not self.description:
                    self.description = d.get("content", "")

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title = data.strip()

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False


def fetch_url_metadata(url: str) -> dict:
    """Return {title, description} for a URL. Falls back to bare URL on any error."""
    try:
        r = requests.get(
            url,
            timeout=5,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
            allow_redirects=True,
        )
        content_type = r.headers.get("content-type", "")
        if not r.ok or "text/html" not in content_type:
            return {"title": url, "description": ""}
        parser = _MetaParser()
        parser.feed(r.text[:50_000])
        return {
            "title": parser.title.strip() or url,
            "description": parser.description[:200].strip(),
        }
    except Exception:
        return {"title": url, "description": ""}


def is_url_only(task: dict) -> bool:
    return bool(_URL_RE.match(task.get("text", "").strip()))


def enrich_tasks(tasks: list[dict]) -> tuple[list[dict], int]:
    """
    Fetch metadata for URL-only tasks. Adds url_title + url_description fields.
    Returns (enriched_tasks, count_fetched).
    """
    enriched = []
    fetched = 0
    for t in tasks:
        if is_url_only(t):
            meta = fetch_url_metadata(t["text"].strip())
            t = {**t, "url_title": meta["title"], "url_description": meta["description"]}
            fetched += 1
        enriched.append(t)
    return enriched, fetched


# ── Task categorisation ───────────────────────────────────────────────────────

_PRIORITY_EMOJI = {
    "highest": "🔺",
    "high":    "⏫",
    "medium":  "🔼",
    "low":     "🔽",
    "lowest":  "⏬",
}

# Tags that are structural markers, not real categories
_SKIP_TAGS = {"later", "todo", "gcal", "done"}


def categorise_tasks(tasks: list[dict]) -> dict:
    """
    Sort tasks into overdue / due_today / due_soon / backlog buckets.
    Backlog is further split by primary tag. Each bucket is sorted by
    (priority_weight, due_date).
    """
    today = datetime.date.today()
    overdue, due_today, due_soon, backlog = [], [], [], []

    for t in tasks:
        d = t.get("due_date")
        if d:
            if d < today:
                overdue.append(t)
            elif d == today:
                due_today.append(t)
            elif d <= today + datetime.timedelta(days=7):
                due_soon.append(t)
            else:
                backlog.append(t)
        else:
            backlog.append(t)

    def _sort_key(t):
        return (t.get("priority_weight", 99), t.get("due_date") or datetime.date.max)

    # Group backlog by primary meaningful tag
    tags_map: dict[str, list] = {}
    untagged: list[dict] = []
    for t in sorted(backlog, key=_sort_key):
        meaningful = [tag for tag in t.get("tags", []) if tag.lower() not in _SKIP_TAGS]
        if meaningful:
            bucket = meaningful[0]
            tags_map.setdefault(bucket, []).append(t)
        else:
            untagged.append(t)

    return {
        "overdue":          sorted(overdue,   key=_sort_key),
        "due_today":        sorted(due_today, key=_sort_key),
        "due_soon":         sorted(due_soon,  key=_sort_key),
        "backlog_by_tag":   tags_map,
        "backlog_untagged": untagged,
    }


# ── Plan rendering ────────────────────────────────────────────────────────────

def _fmt_task(t: dict) -> str:
    """Format one task line for the plan note."""
    display = t.get("url_title") or t["text"]
    p_emoji = _PRIORITY_EMOJI.get(t.get("priority", ""), "")
    due = f" 📅 {t['due_date']}" if t.get("due_date") else ""
    line = f"- [ ] {p_emoji}{display}{due}"

    # For URL tasks: show URL and description as block-quotes beneath
    if is_url_only(t):
        url = t["text"].strip()
        if url != display:
            line += f"\n  > <{url}>"
        if t.get("url_description"):
            line += f"\n  > {t['url_description']}"

    return line


def _suggest_next_action(project_name: str, tasks: list[dict]) -> str:
    task_lines = "\n".join(
        f"  - {t.get('url_title', t['text'])}"
        + (f" [due {t['due_date']}]" if t.get("due_date") else "")
        + (f" [{t['priority']}]" if t.get("priority") else "")
        for t in tasks[:15]
    )
    prompt = (
        f"Project: {project_name}\n\nOpen tasks:\n{task_lines}\n\n"
        "What is the single most important next action for this project right now?\n"
        "One sentence. Start with a verb. Be specific."
    )
    try:
        return router.ask(prompt, task="quick", system=_SYSTEM_PROMPT)
    except Exception:
        return "(Could not generate — check /status)"


def render_project_plan(project_name: str, tasks: list[dict], next_action: str) -> str:
    cats = categorise_tasks(tasks)
    today = datetime.date.today()

    lines: list[str] = [
        f"# Project Plan — {project_name}",
        f"_Updated {today.isoformat()} · {len(tasks)} open task(s)_",
        "",
        "## Next Action",
        f"> {next_action}",
        "",
    ]

    def section(title, task_list):
        if not task_list:
            return
        lines.append(f"## {title}")
        lines.append("")
        lines.extend(_fmt_task(t) for t in task_list)
        lines.append("")

    section("⚠️ Overdue", cats["overdue"])
    section("Today", cats["due_today"])
    section("Due This Week", cats["due_soon"])

    if cats["backlog_by_tag"] or cats["backlog_untagged"]:
        lines.append("## Backlog")
        lines.append("")
        for tag, tagged in sorted(cats["backlog_by_tag"].items()):
            lines.append(f"### #{tag}")
            lines.extend(_fmt_task(t) for t in tagged)
            lines.append("")
        if cats["backlog_untagged"]:
            if cats["backlog_by_tag"]:
                lines.append("### Unsorted")
            lines.extend(_fmt_task(t) for t in cats["backlog_untagged"])
            lines.append("")

    n_ov = len(cats["overdue"])
    n_td = len(cats["due_today"])
    n_sn = len(cats["due_soon"])
    n_bl = (
        sum(len(v) for v in cats["backlog_by_tag"].values())
        + len(cats["backlog_untagged"])
    )
    lines += [
        "---",
        f"_Overdue: {n_ov} · Today: {n_td} · This week: {n_sn} · Backlog: {n_bl}_",
    ]
    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

def run(subdir: str | None = None) -> dict:
    """
    Scan tasks in subdir (default: whole vault), group by project folder,
    enrich URL-only tasks, write _plan.md per project.

    Returns {projects_updated, tasks_enriched, url_tasks, skipped, errors}.
    """
    vault = ObsidianVault()
    subdirs = [subdir] if subdir else None
    all_tasks = vault.get_tasks(subdirs=subdirs)

    # Group open tasks by their containing folder (= project)
    projects: dict[str, list] = {}
    for t in all_tasks:
        if t.get("done"):
            continue
        folder = str(Path(t["file"]).parent)
        if folder in ("", "."):
            folder = "Root"
        projects.setdefault(folder, []).append(t)

    stats = {
        "projects_updated": 0,
        "tasks_enriched": 0,
        "url_tasks": 0,
        "skipped": 0,
        "errors": [],
    }

    for project_name, tasks in sorted(projects.items()):
        url_count = sum(1 for t in tasks if is_url_only(t))
        tasks, fetched = enrich_tasks(tasks)
        stats["url_tasks"] += url_count
        stats["tasks_enriched"] += fetched

        next_action = _suggest_next_action(project_name, tasks)
        plan_md = render_project_plan(project_name, tasks, next_action)

        plan_rel = str(Path(project_name) / "_plan.md")
        try:
            vault.write_file(plan_rel, plan_md)
            stats["projects_updated"] += 1
        except Exception as e:
            stats["errors"].append(f"{project_name}: {e}")
            stats["skipped"] += 1

    return stats
