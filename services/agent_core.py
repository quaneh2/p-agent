"""
AgentCore service - manages the agent's personality and configuration repo
"""

import logging
import os
import subprocess

from github import Github
from github.GithubException import GithubException

from config import AGENT_CORE_DIR, AGENT_CORE_REPO
from prompts.system import DEFAULT_IDENTITY, DEFAULT_SOUL, DEFAULT_MEMORY

from .git_repo import GitRepo

logger = logging.getLogger(__name__)


class AgentCore(GitRepo):
    """Manages the agent-core repository containing personality and config."""

    def __init__(self):
        super().__init__(AGENT_CORE_DIR, AGENT_CORE_REPO)
        self.github = None
        self.repo = None
        self.core_dir = self.repo_dir

    def init(self):
        """
        Initialize agent-core repo.
        - Create repo if it doesn't exist
        - Clone/pull the repo
        - Seed with default files if missing
        """
        token = os.environ.get('GITHUB_TOKEN')

        if not token:
            raise ValueError("GITHUB_TOKEN environment variable not set")
        if not self.repo_name:
            raise ValueError("GITHUB_USERNAME not configured")

        self.github = Github(token)
        self._ensure_repo_exists()
        super().init()
        self._seed_if_needed()

        return self

    def _ensure_repo_exists(self):
        """Create the repo if it doesn't exist."""
        try:
            self.repo = self.github.get_repo(self.repo_name)
            logger.info("Agent-core repo exists: %s", self.repo_name)
        except GithubException as e:
            if e.status == 404:
                logger.info("Creating agent-core repo: %s", self.repo_name)
                user = self.github.get_user()
                just_repo_name = self.repo_name.split("/")[-1]
                self.repo = user.create_repo(
                    just_repo_name,
                    description="Agent personality and configuration",
                    private=True,
                    auto_init=True
                )
                logger.info("Agent-core repo created: %s", self.repo_name)
            else:
                raise

    def _seed_if_needed(self):
        """Seed any missing agent-core files with defaults."""
        seeds = {
            "IDENTITY.md": DEFAULT_IDENTITY,
            "SOUL.md": DEFAULT_SOUL,
            "MEMORY.md": f"# Memory\n\n{DEFAULT_MEMORY}",
        }

        missing = {f: c for f, c in seeds.items() if not (self.repo_dir / f).exists()}

        if missing:
            logger.info("Seeding agent-core with missing files: %s", ", ".join(missing))
            for filename, content in missing.items():
                (self.repo_dir / filename).write_text(content)

            self._run_git(["add", "."])
            self._run_git(["commit", "-m", "Initial setup: seed default identity, soul, and memory"])
            self._run_git(["push"])
            logger.info("Agent-core seeded successfully")

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
            logger.error("Git error creating %s: %s", file_path, e.stderr)
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
            logger.error("Git error updating %s: %s", file_path, e.stderr)
            return {"success": False, "error": f"Git error: {e.stderr}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
