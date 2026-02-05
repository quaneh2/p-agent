"""
Workspace service - manages the local git workspace
"""

import shutil
from pathlib import Path

from config import WORKSPACE_REPO

from .git_repo import GitRepo


class Workspace(GitRepo):
    """Manages the local git workspace with path security validation."""

    def __init__(self, workspace_dir: Path):
        super().__init__(workspace_dir, WORKSPACE_REPO)
        # Alias for backwards compatibility
        self.workspace_dir = self.repo_dir

    def _resolve_safe_path(self, file_path: str) -> Path:
        """
        Resolve a path and ensure it's within the workspace.
        Raises ValueError if path escapes the workspace.
        """
        full_path = (self.repo_dir / file_path).resolve()
        repo_resolved = self.repo_dir.resolve()

        if not full_path.is_relative_to(repo_resolved):
            raise ValueError(f"Path '{file_path}' is outside the workspace")

        try:
            relative = full_path.relative_to(repo_resolved)
            if relative.parts and relative.parts[0] == ".git":
                raise ValueError("Cannot modify .git directory")
        except ValueError as e:
            if "outside the workspace" in str(e) or ".git" in str(e):
                raise
            raise ValueError(f"Invalid path: {file_path}")

        return full_path

    def save_document(self, file_path: str, content: str) -> dict:
        """Save a document to the workspace."""
        try:
            full_path = self._resolve_safe_path(file_path)

            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            self._run_git(["add", file_path])

            return {
                "success": True,
                "action": "saved",
                "path": file_path,
                "message": f"Document saved to workspace: {file_path}"
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_document(self, file_path: str) -> dict:
        """Read a document from the workspace."""
        try:
            full_path = self._resolve_safe_path(file_path)

            if not full_path.exists():
                return {"success": False, "error": f"File not found: {file_path}"}

            if not full_path.is_file():
                return {"success": False, "error": f"Path is not a file: {file_path}"}

            content = full_path.read_text()

            return {
                "success": True,
                "path": file_path,
                "content": content
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_document(self, file_path: str) -> dict:
        """Delete a document from the workspace."""
        try:
            full_path = self._resolve_safe_path(file_path)

            if not full_path.exists():
                return {"success": False, "error": f"File not found: {file_path}"}

            if not full_path.is_file():
                return {"success": False, "error": f"Path is not a file: {file_path}"}

            full_path.unlink()
            self._run_git(["add", file_path])

            return {
                "success": True,
                "action": "deleted",
                "path": file_path,
                "message": f"Document deleted from workspace: {file_path}"
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_folder(self, folder_path: str, force: bool = False) -> dict:
        """Delete a folder from the workspace."""
        try:
            full_path = self._resolve_safe_path(folder_path)

            if not full_path.exists():
                return {"success": False, "error": f"Folder not found: {folder_path}"}

            if not full_path.is_dir():
                return {"success": False, "error": f"Path is not a folder: {folder_path}"}

            contents = [f for f in full_path.iterdir() if f.name != ".git"]

            if contents and not force:
                return {
                    "success": False,
                    "error": f"Folder is not empty: {folder_path}. Use force=True to delete with contents.",
                    "contents": [str(f.relative_to(self.repo_dir)) for f in contents]
                }

            if force and contents:
                shutil.rmtree(full_path)
            else:
                full_path.rmdir()

            self._run_git(["add", folder_path])

            return {
                "success": True,
                "action": "deleted",
                "path": folder_path,
                "message": f"Folder deleted from workspace: {folder_path}"
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rename_document(self, old_path: str, new_path: str) -> dict:
        """Rename or move a document within the workspace."""
        try:
            old_full_path = self._resolve_safe_path(old_path)
            new_full_path = self._resolve_safe_path(new_path)

            if not old_full_path.exists():
                return {"success": False, "error": f"File not found: {old_path}"}

            if not old_full_path.is_file():
                return {"success": False, "error": f"Path is not a file: {old_path}"}

            if new_full_path.exists():
                return {"success": False, "error": f"Destination already exists: {new_path}"}

            new_full_path.parent.mkdir(parents=True, exist_ok=True)
            old_full_path.rename(new_full_path)
            self._run_git(["add", old_path, new_path])

            return {
                "success": True,
                "action": "renamed",
                "old_path": old_path,
                "new_path": new_path,
                "message": f"Document renamed from {old_path} to {new_path}"
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_folder(self, folder_path: str) -> dict:
        """Create a folder in the workspace."""
        try:
            full_path = self._resolve_safe_path(folder_path)

            if full_path.exists():
                return {"success": False, "error": f"Path already exists: {folder_path}"}

            full_path.mkdir(parents=True, exist_ok=True)

            gitkeep = full_path / ".gitkeep"
            gitkeep.touch()
            self._run_git(["add", str(Path(folder_path) / ".gitkeep")])

            return {
                "success": True,
                "action": "created",
                "path": folder_path,
                "message": f"Folder created in workspace: {folder_path}"
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def examine_workspace(self) -> dict:
        """Examine the workspace structure, listing all files and folders."""
        try:
            files = []
            folders = set()

            for path in self.repo_dir.rglob("*"):
                relative_path = path.relative_to(self.repo_dir)
                if relative_path.parts and relative_path.parts[0] == ".git":
                    continue

                if path.is_file():
                    files.append(str(relative_path))
                    for parent in relative_path.parents:
                        if parent != Path("."):
                            folders.add(str(parent))
                elif path.is_dir():
                    folders.add(str(relative_path))

            return {
                "success": True,
                "files": sorted(files),
                "folders": sorted(folders)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
