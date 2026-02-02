"""
Workspace service - manages the local git workspace
"""

import os
import subprocess
from pathlib import Path

from config import GIT_USER_NAME, GIT_USER_EMAIL


class Workspace:
    """Manages the local git workspace."""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.repo_url = None

    def init(self):
        """Initialize the workspace by cloning or pulling the repo."""
        token = os.environ.get('GITHUB_TOKEN')
        repo_name = os.environ.get('GITHUB_REPO')

        if not token:
            raise ValueError("GITHUB_TOKEN environment variable not set")
        if not repo_name:
            raise ValueError("GITHUB_REPO environment variable not set (format: username/repo-name)")

        # Construct authenticated repo URL
        self.repo_url = f"https://{token}@github.com/{repo_name}.git"

        if self.workspace_dir.exists() and (self.workspace_dir / ".git").exists():
            # Workspace exists - update remote URL and pull latest
            print(f"Workspace exists at {self.workspace_dir}, pulling latest...")
            self._run_git(["remote", "set-url", "origin", self.repo_url])
            self._run_git(["pull"])
        else:
            # Clone fresh
            print(f"Cloning repository to {self.workspace_dir}...")
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", self.repo_url, str(self.workspace_dir)],
                check=True,
                capture_output=True
            )

        # Configure git user for commits
        self._run_git(["config", "user.email", GIT_USER_EMAIL])
        self._run_git(["config", "user.name", GIT_USER_NAME])

        print(f"Workspace ready: {self.workspace_dir}")
        return self

    def _run_git(self, args: list) -> subprocess.CompletedProcess:
        """Run a git command in the workspace directory."""
        return subprocess.run(
            ["git"] + args,
            cwd=self.workspace_dir,
            check=True,
            capture_output=True,
            text=True
        )

    def _resolve_safe_path(self, file_path: str) -> Path:
        """
        Resolve a path and ensure it's within the workspace.
        Raises ValueError if path escapes the workspace.
        """
        # Resolve to absolute path (handles .., symlinks, etc.)
        full_path = (self.workspace_dir / file_path).resolve()
        workspace_resolved = self.workspace_dir.resolve()

        # Ensure it's still within the workspace
        if not full_path.is_relative_to(workspace_resolved):
            raise ValueError(f"Path '{file_path}' is outside the workspace")

        # Prevent operations on .git directory
        try:
            relative = full_path.relative_to(workspace_resolved)
            if relative.parts and relative.parts[0] == ".git":
                raise ValueError("Cannot modify .git directory")
        except ValueError as e:
            if "outside the workspace" in str(e) or ".git" in str(e):
                raise
            # Other ValueError from relative_to means path issue
            raise ValueError(f"Invalid path: {file_path}")

        return full_path

    def save_document(self, file_path: str, content: str) -> dict:
        """Save a document to the workspace."""
        try:
            full_path = self._resolve_safe_path(file_path)

            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            full_path.write_text(content)

            # Stage the file
            self._run_git(["add", file_path])

            return {
                "success": True,
                "action": "saved",
                "path": file_path,
                "message": f"Document saved to workspace: {file_path}"
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
            
    def read_document(self, file_path: str) -> dict:
        """Read a document from the workspace."""
        try:
            full_path = self._resolve_safe_path(file_path)

            if not full_path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}"
                }

            if not full_path.is_file():
                return {
                    "success": False,
                    "error": f"Path is not a file: {file_path}"
                }

            content = full_path.read_text()

            return {
                "success": True,
                "path": file_path,
                "content": content
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def delete_document(self, file_path: str) -> dict:
        """Delete a document from the workspace."""
        try:
            full_path = self._resolve_safe_path(file_path)

            if not full_path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}"
                }

            if not full_path.is_file():
                return {
                    "success": False,
                    "error": f"Path is not a file: {file_path}"
                }

            # Delete the file
            full_path.unlink()

            # Stage the deletion
            self._run_git(["add", file_path])

            return {
                "success": True,
                "action": "deleted",
                "path": file_path,
                "message": f"Document deleted from workspace: {file_path}"
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def delete_folder(self, folder_path: str, force: bool = False) -> dict:
        """
        Delete a folder from the workspace.

        Args:
            folder_path: Path to the folder relative to workspace root
            force: If True, delete folder and all contents. If False, only delete if empty.
        """
        try:
            full_path = self._resolve_safe_path(folder_path)

            if not full_path.exists():
                return {
                    "success": False,
                    "error": f"Folder not found: {folder_path}"
                }

            if not full_path.is_dir():
                return {
                    "success": False,
                    "error": f"Path is not a folder: {folder_path}"
                }

            # Check if folder is empty (ignoring .git)
            contents = [f for f in full_path.iterdir() if f.name != ".git"]

            if contents and not force:
                return {
                    "success": False,
                    "error": f"Folder is not empty: {folder_path}. Use force=True to delete with contents.",
                    "contents": [str(f.relative_to(self.workspace_dir)) for f in contents]
                }

            if force and contents:
                # Delete all contents recursively
                import shutil
                shutil.rmtree(full_path)
            else:
                # Delete empty folder
                full_path.rmdir()

            # Stage the deletion (git add on deleted paths)
            self._run_git(["add", folder_path])

            return {
                "success": True,
                "action": "deleted",
                "path": folder_path,
                "message": f"Folder deleted from workspace: {folder_path}"
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def rename_document(self, old_path: str, new_path: str) -> dict:
        """Rename or move a document within the workspace."""
        try:
            old_full_path = self._resolve_safe_path(old_path)
            new_full_path = self._resolve_safe_path(new_path)

            if not old_full_path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {old_path}"
                }

            if not old_full_path.is_file():
                return {
                    "success": False,
                    "error": f"Path is not a file: {old_path}"
                }

            if new_full_path.exists():
                return {
                    "success": False,
                    "error": f"Destination already exists: {new_path}"
                }

            # Create parent directories for new path if needed
            new_full_path.parent.mkdir(parents=True, exist_ok=True)

            # Move the file
            old_full_path.rename(new_full_path)

            # Stage both the old (deleted) and new (added) paths
            self._run_git(["add", old_path, new_path])

            return {
                "success": True,
                "action": "renamed",
                "old_path": old_path,
                "new_path": new_path,
                "message": f"Document renamed from {old_path} to {new_path}"
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def create_folder(self, folder_path: str) -> dict:
        """Create a folder in the workspace."""
        try:
            full_path = self._resolve_safe_path(folder_path)

            if full_path.exists():
                return {
                    "success": False,
                    "error": f"Path already exists: {folder_path}"
                }

            # Create the folder (and any parent directories)
            full_path.mkdir(parents=True, exist_ok=True)

            # Git doesn't track empty directories, so we add a .gitkeep
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
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def commit_and_push(self, commit_message: str) -> dict:
        """Commit staged changes and push to remote."""
        try:
            # Check if there are changes to commit
            status = self._run_git(["status", "--porcelain"])

            if not status.stdout.strip():
                return {
                    "success": True,
                    "action": "no_changes",
                    "message": "No changes to commit."
                }

            # Commit
            self._run_git(["commit", "-m", commit_message])

            # Push
            self._run_git(["push"])

            return {
                "success": True,
                "action": "pushed",
                "message": f"Changes committed and pushed successfully."
            }
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"Git error: {e.stderr}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def examine_workspace(self) -> dict:
        """Examine the workspace structure, listing all files and folders."""
        try:
            files = []
            folders = set()

            for path in self.workspace_dir.rglob("*"):
                # Skip .git directory
                relative_path = path.relative_to(self.workspace_dir)
                if relative_path.parts and relative_path.parts[0] == ".git":
                    continue

                if path.is_file():
                    files.append(str(relative_path))
                    # Add all parent folders
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
            return {
                "success": False,
                "error": str(e)
            }
