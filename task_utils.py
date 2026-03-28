import os
import re
from config_utils import get_config_value
from obsidian_agent import ObsidianAgent
from reminders_manager import get_apple_reminders


def get_unified_tasks(obsidian_path):
    """
    Merges tasks from Obsidian, LogSeq, and Apple Reminders.
    """
    # 1. Parse Obsidian tasks via direct file parsing (no Obsidian app needed)
    obsidian_tasks = []

    workspace_dir = get_config_value("WORKSPACE_DIR", None)
    if not workspace_dir:
        print("ℹ️  WORKSPACE_DIR not set — skipping Obsidian tasks")
    elif not os.path.isdir(workspace_dir):
        print(f"⚠️  WORKSPACE_DIR is set but does not exist: {workspace_dir}")
    else:
        try:
            agent = ObsidianAgent(workspace_dir=workspace_dir)
            raw_obs_tasks = agent.get_tasks(todo=True, done=False)

            for t in raw_obs_tasks:
                text = t.get("text", "")
                clean_text = re.sub(r"^\s*-\s+\[[ xX]\]\s+", "", text).strip()
                rel_file = t.get("file", "")
                line_num = t.get("line", "")

                task_data = {
                    "task": clean_text,
                    "category": "Uncategorized",
                    "due_date": None,
                    "source": f"obsidian:{rel_file}:{line_num}",
                    "file": rel_file,
                    "line": line_num,
                }

                # Extract #category
                cat_match = re.search(r"#([\w./-]+)", task_data["task"])
                if cat_match:
                    task_data["category"] = cat_match.group(1)
                    task_data["task"] = task_data["task"].replace(f"#{task_data['category']}", "").strip()

                # Extract 📅 YYYY-MM-DD
                date_match = re.search(r"📅\s*(\d{4}-\d{2}-\d{2})", task_data["task"])
                if date_match:
                    task_data["due_date"] = date_match.group(1)
                    task_data["task"] = task_data["task"].replace(f"📅 {task_data['due_date']}", "").strip()
                    task_data["task"] = task_data["task"].replace(f"📅{task_data['due_date']}", "").strip()

                # Also support ^YYYY-MM-DD
                if not task_data["due_date"]:
                    date_match = re.search(r"\^(\d{4}-\d{2}-\d{2})", task_data["task"])
                    if date_match:
                        task_data["due_date"] = date_match.group(1)
                        task_data["task"] = task_data["task"].replace(f"^{task_data['due_date']}", "").strip()

                obsidian_tasks.append(task_data)

            if obsidian_tasks:
                print(f"Extracted {len(obsidian_tasks)} tasks from Obsidian vault.")
        except Exception as e:
            print(f"⚠️ ObsidianAgent error: {e}")

    # 2. Parse LogSeq tasks if directory is provided
    logseq_tasks = []
    logseq_dir = get_config_value("LOGSEQ_DIR", None)
    if not logseq_dir:
        print("ℹ️  LOGSEQ_DIR not set — skipping LogSeq tasks. Set it in .env")
    elif not os.path.exists(logseq_dir):
        print(f"⚠️  LOGSEQ_DIR is set but does not exist: {logseq_dir}")
    else:
        from logseq_agent import LogSeqAgent
        ls_agent = LogSeqAgent(logseq_dir)
        ls_tasks = ls_agent.get_recent_tasks(days=14) + ls_agent.get_all_page_tasks()
        for t in ls_tasks:
            task_text = t["task"]
            if t.get("description"):
                task_text = f"{task_text} — {t['description']}"
            logseq_tasks.append({
                "task": task_text,
                "category": t["properties"].get("category", "Personal"),
                "due_date": t["properties"].get("deadline") or t["properties"].get("scheduled"),
                "source": t["source"],
            })
        if logseq_tasks:
            print(f"Extracted {len(logseq_tasks)} total tasks from LogSeq (journals + pages).")

    # 3. Get Apple Reminders
    reminders_list = get_config_value("APPLE_REMINDERS_LIST", "Reminders")
    apple_tasks = get_apple_reminders(reminders_list)

    # 4. Combine
    unified_backlog = obsidian_tasks + logseq_tasks + apple_tasks
    return unified_backlog
