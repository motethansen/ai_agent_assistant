import subprocess
import json
import os

class ObsidianAgent:
    """
    An agent that interacts with Obsidian via its Command Line Interface (CLI).
    Requires Obsidian 1.12+ and CLI enabled in settings.
    """

    def __init__(self, vault=None):
        self.vault = vault

    def _run_command(self, command_args):
        """Runs an obsidian CLI command and returns the output."""
        cmd = ["obsidian"] + command_args
        if self.vault:
            cmd.append(f"vault={self.vault}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            # Remove the "Loading updated app package..." and "Your Obsidian installer is out of date..." messages
            output = result.stdout
            clean_output = []
            for line in output.splitlines():
                if "Loading updated app package" in line or "Your Obsidian installer is out of date" in line:
                    continue
                clean_output.append(line)
            return "\n".join(clean_output).strip()
        except subprocess.CalledProcessError as e:
            print(f"Error running Obsidian CLI: {e.stderr}")
            return None

    def get_tasks(self, todo=True, done=False, daily=False, format="json"):
        """Lists tasks from the vault."""
        args = ["tasks"]
        if todo: args.append("todo")
        if done: args.append("done")
        if daily: args.append("daily")
        args.append(f"format={format}")
        
        output = self._run_command(args)
        if output and format == "json":
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return []
        return output

    def update_task(self, path=None, line=None, ref=None, action="toggle"):
        """Updates a specific task's status."""
        args = ["task"]
        if ref:
            args.append(f"ref={ref}")
        elif path and line:
            args.append(f"path={path}")
            args.append(f"line={line}")
        else:
            raise ValueError("Must provide either 'ref' or 'path' and 'line'")
        
        if action in ["toggle", "done", "todo"]:
            args.append(action)
        else:
            args.append(f"status={action}")
            
        return self._run_command(args)

    def read_file(self, path):
        """Reads the content of a file."""
        return self._run_command(["read", f"path={path}"])

    def create_file(self, path, content="", template=None, overwrite=False, open_file=False):
        """Creates a new file."""
        args = ["create", f"path={path}", f"content={content}"]
        if template: args.append(f"template={template}")
        if overwrite: args.append("overwrite")
        if open_file: args.append("open")
        return self._run_command(args)

    def append_to_file(self, path, content, inline=False):
        """Appends content to a file."""
        args = ["append", f"path={path}", f"content={content}"]
        if inline: args.append("inline")
        return self._run_command(args)

    def prepend_to_file(self, path, content, inline=False):
        """Prepends content to a file."""
        args = ["prepend", f"path={path}", f"content={content}"]
        if inline: args.append("inline")
        return self._run_command(args)

    def get_daily_note_path(self):
        """Returns the path to today's daily note."""
        return self._run_command(["daily:path"])

    def read_daily_note(self):
        """Reads today's daily note."""
        return self._run_command(["daily:read"])

    def append_to_daily_note(self, content, inline=False, open_file=False):
        """Appends content to today's daily note."""
        args = ["daily:append", f"content={content}"]
        if inline: args.append("inline")
        if open_file: args.append("open")
        return self._run_command(args)

    def prepend_to_daily_note(self, content, inline=False, open_file=False):
        """Prepends content to today's daily note."""
        args = ["daily:prepend", f"content={content}"]
        if inline: args.append("inline")
        if open_file: args.append("open")
        return self._run_command(args)

    def set_property(self, path, name, value, property_type=None):
        """Sets a property on a file."""
        args = ["property:set", f"path={path}", f"name={name}", f"value={value}"]
        if property_type: args.append(f"type={property_type}")
        return self._run_command(args)

    def read_property(self, path, name):
        """Reads a property value from a file."""
        return self._run_command(["property:read", f"path={path}", f"name={name}"])

    def search(self, query, path=None, limit=None, context=False):
        """Searches the vault."""
        args = ["search:context" if context else "search", f"query={query}"]
        if path: args.append(f"path={path}")
        if limit: args.append(f"limit={limit}")
        args.append("format=json")
        
        output = self._run_command(args)
        if output:
            try:
                return json.loads(output)
            except json.JSONDecodeError:
                return []
        return []

if __name__ == "__main__":
    # Simple test
    agent = ObsidianAgent()
    print("Tasks (JSON):")
    tasks = agent.get_tasks()
    if tasks:
        print(json.dumps(tasks[:3], indent=2))
    
    print("\nDaily Note Path:")
    print(agent.get_daily_note_path())
