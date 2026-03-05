import time
import os
import re
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

def parse_markdown_tasks(file_path):
    """
    Parses a markdown file to extract tasks with categories and dates.
    Format example: - [ ] #winedragons Review wireframes ^2026-02-24
    This improved version looks at the entire file but gives context to where tasks are found.
    """
    tasks = []
    if not file_path or not os.path.exists(file_path) or os.path.isdir(file_path):
        return []
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            # Match any task line: - [ ] Task description
            match = re.search(r"^\s*-\s+\[([ xX])\]\s+(.*)", line)
            if match:
                is_completed = match.group(1).lower() == 'x'
                if is_completed: continue # Skip completed tasks for the backlog
                
                raw_task = match.group(2).strip()
                task_data = {
                    "task": raw_task,
                    "category": "Uncategorized",
                    "due_date": None,
                    "source": "Obsidian",
                    "file": os.path.basename(file_path)
                }
                
                # Extract #category
                cat_match = re.search(r"#([\w.]+)", raw_task)
                if cat_match:
                    task_data["category"] = cat_match.group(1)
                    # Remove the tag from the task description
                    task_data["task"] = task_data["task"].replace(f"#{task_data['category']}", "").strip()
                
                # Extract ^YYYY-MM-DD
                date_match = re.search(r"\^(\d{4}-\d{2}-\d{2})", task_data["task"])
                if date_match:
                    task_data["due_date"] = date_match.group(1)
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
    This improved version captures block properties (like URLs) on subsequent lines.
    """
    tasks = []
    try:
        if not os.path.exists(file_path):
            return []
            
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        i = 0
        while i < len(lines):
            line = lines[i]
            # Support LogSeq-style LATER
            match = re.search(r"^\s*-\s+LATER\s+(.*)", line)
            if match:
                raw_task = match.group(1).strip()
                # Clean up LogSeq macros but try to keep URLs
                # Only strip if it's a known macro like {{renderer ...}} or {{query ...}}
                # But if it's a simple {{url}}, keep it or handle it.
                # For now, let's just be less aggressive.
                raw_task = re.sub(r"\{\{(?:renderer|query|clojure|embed|include)\s+.*?\}\}", "", raw_task).strip()
                
                task_data = {
                    "task": raw_task,
                    "category": "Uncategorized",
                    "due_date": None,
                    "source": "Logseq",
                    "properties": {}
                }

                # Look ahead for properties (indented lines below)
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    # If line is indented and contains a property :key: value
                    prop_match = re.search(r"^\s+:(.*?):\s*(.*)", next_line)
                    if prop_match:
                        prop_key = prop_match.group(1).lower()
                        prop_val = prop_match.group(2).strip()
                        task_data["properties"][prop_key] = prop_val
                        # If it's a URL property, append it to the task description if not already there
                        if prop_key == "url" and prop_val not in task_data["task"]:
                            task_data["task"] += f" ({prop_val})"
                        j += 1
                    elif next_line.strip() == "" or next_line.strip().startswith("- "):
                        # End of current block
                        break
                    else:
                        # Some other content in the block, maybe part of the description
                        # If it's indented, it might be a sub-bullet or note
                        if next_line.startswith("  "):
                             # If it's not a property, it's just a note. We can append it.
                             clean_note = next_line.strip()
                             if clean_note and not clean_note.startswith(":"):
                                 # Skip metadata lines like SCHEDULED: or DEADLINE: as they are handled later
                                 if not any(x in clean_note for x in ["SCHEDULED:", "DEADLINE:"]):
                                     task_data["task"] += " | " + clean_note
                        j += 1
                
                # Extract #category from the task or properties
                cat_match = re.search(r"#([\w.]+)", task_data["task"])
                if cat_match:
                    task_data["category"] = cat_match.group(1)
                    # Remove the tag from the task description
                    task_data["task"] = task_data["task"].replace(f"#{task_data['category']}", "").strip()
                
                # LogSeq scheduled/deadline parsing: SCHEDULED: <2026-02-28 Sat>
                # Check current line and next few lines for scheduling
                block_text = "".join(lines[i:j])
                date_match = re.search(r"(?:SCHEDULED|DEADLINE):\s*<(\d{4}-\d{2}-\d{2})", block_text)
                if date_match:
                    task_data["due_date"] = date_match.group(1)
                
                # Also support Obsidian/Logseq ^YYYY-MM-DD
                if not task_data["due_date"]:
                    obsidian_date = re.search(r"\^(\d{4}-\d{2}-\d{2})", task_data["task"])
                    if obsidian_date:
                        task_data["due_date"] = obsidian_date.group(1)
                        task_data["task"] = task_data["task"].replace(f"^{task_data['due_date']}", "").strip()

                tasks.append(task_data)
                i = j - 1 # Skip the lines we already processed
            i += 1
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
        # Try to use ObsidianAgent for better integration with the app
        try:
            from obsidian_agent import ObsidianAgent
            agent = ObsidianAgent()
            content = agent.read_file(file_path)
            use_agent = True if content is not None else False
        except ImportError:
            use_agent = False
            content = None

        # Sort schedule by start time
        schedule = sorted(schedule, key=lambda x: x['start'])

        if not content:
            with open(file_path, 'r') as f:
                content = f.read()

        plan_text = "## Today's Plan\n"
        for item in schedule:
            # Clean up the ISO time for better readability
            start_time = item['start'].split('T')[1][:5] if 'T' in item['start'] else item['start']
            end_time = item['end'].split('T')[1][:5] if 'T' in item['end'] else item['end']
            plan_text += f"- **{start_time} - {end_time}**: {item['task']}\n"
        
        # Replace the section using regex
        pattern = r"## Today's Plan.*?(?=\n##|$)"
        new_content = re.sub(pattern, plan_text, content, flags=re.DOTALL)

        # If ## Today's Plan doesn't exist, append it
        if new_content == content:
            new_content = content + "\n\n" + plan_text

        if use_agent:
            # Use CLI to overwrite - handles app sync better
            # Note: We don't need to manually escape for subprocess.run(list)
            agent.create_file(file_path, content=new_content, overwrite=True)
        else:
            with open(file_path, 'w') as f:
                f.write(new_content)
        
        print(f"Updated {os.path.basename(file_path)} with Today's Plan.")
    except Exception as e:
        print(f"Error updating markdown file: {e}")

