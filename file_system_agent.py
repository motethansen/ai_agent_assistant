import os
import shutil

class FileSystemAgent:
    def __init__(self, workspace_dir):
        self.workspace_dir = os.path.abspath(workspace_dir)
        if not os.path.exists(self.workspace_dir):
            os.makedirs(self.workspace_dir, exist_ok=True)

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

    def write_file(self, file_name, content):
        path = self._safe_path(file_name)
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
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
        shutil.move(src_path, dst_path)
        return f"Moved {source} to {destination}"
