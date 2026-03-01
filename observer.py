import time
import os
import re
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

def parse_markdown_tasks(file_path):
    """
    Parses a markdown file to extract tasks with categories and dates.
    Format example: - [ ] #winedragons Review wireframes ^2026-02-24
    """
    tasks = []
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Regex to find the ## Tasks section and its content
        pattern = r"## Tasks\s*(.*?)(?=##|$)"
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            tasks_content = match.group(1).strip()
            # Extract individual task lines with metadata
            # - [ ] #category Task Description ^YYYY-MM-DD
            task_lines = re.findall(r"- \[[ xX]\] (.*)", tasks_content)
            for raw_task in task_lines:
                task_data = {
                    "task": raw_task,
                    "category": "Uncategorized",
                    "due_date": None,
                    "source": "Obsidian"
                }
                
                # Extract #category
                cat_match = re.search(r"#([\w.]+)", raw_task)
                if cat_match:
                    task_data["category"] = cat_match.group(1)
                    # Remove the tag from the task description
                    task_data["task"] = raw_task.replace(f"#{task_data['category']}", "").strip()
                
                # Extract ^YYYY-MM-DD (Obsidian/Logseq convention)
                date_match = re.search(r"\^(\d{4}-\d{2}-\d{2})", task_data["task"])
                if date_match:
                    task_data["due_date"] = date_match.group(1)
                    # Clean up the task description
                    task_data["task"] = task_data["task"].replace(f"^{task_data['due_date']}", "").strip()
                
                tasks.append(task_data)
        
        return tasks
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

def parse_logseq_tasks(file_path):
    """
    Parses a LogSeq markdown file to extract tasks.
    User specifies: "I will mark tasks with LATER on each line to identify a task."
    """
    tasks = []
    try:
        if not os.path.exists(file_path):
            return []
            
        with open(file_path, 'r') as f:
            for line in f:
                # Support LogSeq-style LATER and checkboxes
                match = re.search(r"^\s*-\s+LATER\s+(.*)", line)
                if match:
                    raw_task = match.group(1).strip()
                    # Clean up LogSeq properties if they exist on the same line (unlikely but safe)
                    raw_task = re.sub(r"\s+\{\{.*\}\}", "", raw_task)
                    
                    task_data = {
                        "task": raw_task,
                        "category": "Uncategorized",
                        "due_date": None,
                        "source": "Logseq"
                    }

                    # Extract #category
                    cat_match = re.search(r"#([\w.]+)", raw_task)
                    if cat_match:
                        task_data["category"] = cat_match.group(1)
                        # Remove the tag from the task description
                        task_data["task"] = raw_task.replace(f"#{task_data['category']}", "").strip()
                    
                    # LogSeq scheduled/deadline parsing: SCHEDULED: <2026-02-28 Sat>
                    # Sometimes on the next line, but sometimes the AI can see the context.
                    # For simplicity, if it's on the same line or we find it in the file.
                    # Actually LogSeq tasks usually have metadata on the line below.
                    # We'll skip complex multiline for now and look for same-line or ^ date.
                    
                    date_match = re.search(r"(?:SCHEDULED|DEADLINE):\s*<(\d{4}-\d{2}-\d{2})", line)
                    if date_match:
                        task_data["due_date"] = date_match.group(1)
                    
                    # Also support Obsidian/Logseq ^YYYY-MM-DD
                    if not task_data["due_date"]:
                        obsidian_date = re.search(r"\^(\d{4}-\d{2}-\d{2})", raw_task)
                        if obsidian_date:
                            task_data["due_date"] = obsidian_date.group(1)
                            task_data["task"] = raw_task.replace(f"^{task_data['due_date']}", "").strip()

                    tasks.append(task_data)
        return tasks
    except Exception as e:
        print(f"Error reading Logseq file {file_path}: {e}")
        return []


class MarkdownEventHandler(PatternMatchingEventHandler):
    patterns = ["*.md"]

    def on_modified(self, event):
        # Prevent double triggers (some editors save twice)
        if hasattr(self, 'last_triggered') and time.time() - self.last_triggered < 1:
            return
        self.last_triggered = time.time()
        
        print(f"Detected change in: {event.src_path}")
        tasks = parse_markdown_tasks(event.src_path)
        if tasks:
            print(f"Extracted Tasks from {os.path.basename(event.src_path)}:")
            for i, task in enumerate(tasks, 1):
                print(f"  {i}. {task}")
        else:
            print(f"No tasks found in the '## Tasks' section of {os.path.basename(event.src_path)}")

if __name__ == "__main__":
    path = "."  # Current directory
    event_handler = MarkdownEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=False)
    
    print(f"Monitoring for .md file changes in {os.path.abspath(path)}...")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def update_markdown_plan(file_path, schedule):
    """
    Overwrites the '## Today's Plan' section with the AI-generated schedule.
    """
    if not schedule:
        return

    try:
        # Sort schedule by start time
        schedule = sorted(schedule, key=lambda x: x['start'])

        with open(file_path, 'r') as f:
            content = f.read()

        plan_text = "## Today's Plan\n"
        for item in schedule:
            # Clean up the ISO time for better readability
            start_time = item['start'].split('T')[1][:5]
            end_time = item['end'].split('T')[1][:5]
            plan_text += f"- **{start_time} - {end_time}**: {item['task']}\n"
        
        # Replace the section using regex
        pattern = r"## Today's Plan.*?(?=\n##|$)"
        new_content = re.sub(pattern, plan_text, content, flags=re.DOTALL)

        # If ## Today's Plan doesn't exist, append it
        if new_content == content:
            new_content = content + "\n\n" + plan_text

        with open(file_path, 'w') as f:
            f.write(new_content)
        print(f"Updated {os.path.basename(file_path)} with Today's Plan.")
    except Exception as e:
        print(f"Error updating markdown file: {e}")
