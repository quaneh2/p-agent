"""
AgentCore service - manages the agent's personality and configuration repo
"""

import os
import subprocess

from github import Github
from github.GithubException import GithubException

from config import AGENT_CORE_DIR, AGENT_CORE_REPO
from prompts import DEFAULT_SYSTEM_PROMPT

from .git_repo import GitRepo


class AgentCore(GitRepo):
    """Manages the agent-core repository containing personality and config."""

    def __init__(self):
        super().__init__(AGENT_CORE_DIR, AGENT_CORE_REPO)
        self.github = None
        self.repo = None
        # Alias for backwards compatibility
        self.core_dir = self.repo_dir

    def init(self):
        """
        Initialize agent-core repo.
        - Create repo if it doesn't exist
        - Clone/pull the repo
        - Seed with IDENTITY.md if missing
        """
        token = os.environ.get('GITHUB_TOKEN')

        if not token:
            raise ValueError("GITHUB_TOKEN environment variable not set")
        if not self.repo_name:
            raise ValueError("GITHUB_USERNAME not configured")

        # Initialize GitHub client and ensure repo exists
        self.github = Github(token)
        self._ensure_repo_exists()

        # Now do the standard git init (clone/pull)
        super().init()

        # Seed with default identity if IDENTITY.md doesn't exist
        self._seed_if_needed()

        return self

    def _ensure_repo_exists(self):
        """Create the repo if it doesn't exist."""
        try:
            self.repo = self.github.get_repo(self.repo_name)
            print(f"Agent core repo exists: {self.repo_name}")
        except GithubException as e:
            if e.status == 404:
                print(f"Creating agent-core repo: {self.repo_name}")
                user = self.github.get_user()
                just_repo_name = self.repo_name.split("/")[-1]
                self.repo = user.create_repo(
                    just_repo_name,
                    description="Agent personality and configuration",
                    private=True,
                    auto_init=True
                )
                print(f"Created repo: {self.repo_name}")
            else:
                raise

    def _seed_if_needed(self):
        """If IDENTITY.md doesn't exist, create it from default."""
        identity_file = self.repo_dir / "IDENTITY.md"

        if not identity_file.exists():
            print("Seeding agent-core with default identity...")

            identity_file.write_text(DEFAULT_SYSTEM_PROMPT)

            self._run_git(["add", "."])
            self._run_git(["commit", "-m", "Initial setup: seed with default identity"])
            self._run_git(["push"])

            print("Agent core seeded successfully.")

    def create_file(self, file_path: str, content: str, commit_message: str) -> dict:
        """Create a new file in agent-core, commit, and push."""
        try:
            full_path = self.repo_dir / file_path

            if full_path.exists():
                return {
                    "success": False,
                    "error": f"File already exists: {file_path}. Use update_file to modify it."
                }

            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

            self._run_git(["add", file_path])
            self._run_git(["commit", "-m", commit_message])
            self._run_git(["push"])

            return {
                "success": True,
                "action": "created",
                "path": file_path,
                "message": f"Created and pushed: {file_path}"
            }
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Git error: {e.stderr}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_file(self, file_path: str, content: str, commit_message: str) -> dict:
        """Update an existing file in agent-core, commit, and push."""
        try:
            full_path = self.repo_dir / file_path

            if not full_path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}. Use create_file for new files."
                }

            full_path.write_text(content)

            self._run_git(["add", file_path])
            self._run_git(["commit", "-m", commit_message])
            self._run_git(["push"])

            return {
                "success": True,
                "action": "updated",
                "path": file_path,
                "message": f"Updated and pushed: {file_path}"
            }
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": f"Git error: {e.stderr}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
