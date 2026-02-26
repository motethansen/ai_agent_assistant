import time
import os
import re
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

def parse_markdown_tasks(file_path):
    """
    Parses a markdown file to extract tasks from the '## Tasks' section.
    """
    tasks = []
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Regex to find the ## Tasks section and its content until the next header or end of file
        pattern = r"## Tasks\s*(.*?)(?=##|$)"
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            tasks_content = match.group(1).strip()
            # Extract individual task lines (e.g., - [ ] or - [x])
            task_lines = re.findall(r"- \[[ xX]\] (.*)", tasks_content)
            for task in task_lines:
                # We can refine this later to distinguish between [ ] and [x]
                tasks.append(task)
        
        return tasks
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
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
