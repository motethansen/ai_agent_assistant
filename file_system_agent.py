import os
import shutil
try:
    from obsidian_agent import ObsidianAgent
except ImportError:
    ObsidianAgent = None

class FileSystemAgent:
    def __init__(self, workspace_dir):
        self.workspace_dir = os.path.abspath(workspace_dir)
        if not os.path.exists(self.workspace_dir):
            os.makedirs(self.workspace_dir, exist_ok=True)
        self.obsidian = ObsidianAgent() if ObsidianAgent else None

    def _safe_path(self, relative_path):
        """Ensures the path is inside the workspace."""
        full_path = os.path.abspath(os.path.join(self.workspace_dir, relative_path))
        if not full_path.startswith(self.workspace_dir):
            raise PermissionError("Access denied: Path is outside of workspace.")
        return full_path

    def create_folder(self, folder_name):
        path = self._safe_path(folder_name)
        os.makedirs(path, exist_ok=True)
        return f"Created folder: {folder_name}"

    def read_file(self, file_name):
        path = self._safe_path(file_name)
        
        # Try Obsidian CLI first for better app integration
        if self.obsidian:
            content = self.obsidian.read_file(path)
            if content is not None:
                return content

        if not os.path.exists(path):
            return f"Error: File {file_name} not found."
        with open(path, "r") as f:
            return f.read()

    def write_file(self, file_name, content):
        path = self._safe_path(file_name)
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Try Obsidian CLI first
        if self.obsidian:
            # We use create_file with overwrite=True to simulate write_file
            result = self.obsidian.create_file(path, content=content, overwrite=True)
            if result is not None:
                return f"Wrote file via Obsidian CLI: {file_name}"

        with open(path, "w") as f:
            f.write(content)
        return f"Wrote file: {file_name}"

    def list_files(self, relative_path="."):
        path = self._safe_path(relative_path)
        items = os.listdir(path)
        return items

    def move_file(self, source, destination):
        src_path = self._safe_path(source)
        dst_path = self._safe_path(destination)
        
        if self.obsidian:
            # Obsidian CLI move command
            result = self.obsidian._run_command(["move", f"path={src_path}", f"to={dst_path}"])
            if result is not None:
                return f"Moved {source} to {destination} via Obsidian CLI"

        shutil.move(src_path, dst_path)
        return f"Moved {source} to {destination}"

