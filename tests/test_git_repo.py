"""
Tests for GitRepo.delete_file / delete_folder against a real scratch git repo
(local-only — no remote, no push). AgentCore.remove_file / remove_folder are
thin commit-wrapped calls to these, tested separately below with mocks since
AgentCore's constructor is hardcoded to the real agent-core path.
"""

import subprocess
from unittest.mock import MagicMock

import pytest

from services.git_repo import GitRepo


@pytest.fixture
def repo(tmp_path):
    repo_dir = tmp_path / "scratch-repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True, capture_output=True)
    return GitRepo(repo_dir, "test/scratch-repo")


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------

def test_delete_file_removes_file(repo):
    repo.write_file("a.txt", "hello")
    assert (repo.repo_dir / "a.txt").exists()
    result = repo.delete_file("a.txt")
    assert result["success"] is True
    assert not (repo.repo_dir / "a.txt").exists()


def test_delete_file_not_found(repo):
    result = repo.delete_file("missing.txt")
    assert result["success"] is False
    assert "not found" in result["error"].lower()


def test_delete_file_rejects_directory(repo):
    (repo.repo_dir / "somedir").mkdir()
    result = repo.delete_file("somedir")
    assert result["success"] is False


def test_delete_file_stages_removal(repo):
    repo.write_file("a.txt", "hello")
    subprocess.run(["git", "commit", "-m", "add a.txt"], cwd=repo.repo_dir, check=True, capture_output=True)
    repo.delete_file("a.txt")
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo.repo_dir, check=True, capture_output=True, text=True
    )
    assert status.stdout.strip().endswith("a.txt")
    assert status.stdout.strip().startswith("D")


# ---------------------------------------------------------------------------
# delete_folder
# ---------------------------------------------------------------------------

def test_delete_folder_removes_contents(repo):
    repo.write_file("sessions/one.json", "{}")
    repo.write_file("sessions/two.json", "{}")
    assert (repo.repo_dir / "sessions").exists()
    result = repo.delete_folder("sessions")
    assert result["success"] is True
    assert not (repo.repo_dir / "sessions").exists()


def test_delete_folder_not_found(repo):
    result = repo.delete_folder("missing")
    assert result["success"] is False


def test_delete_folder_rejects_file(repo):
    repo.write_file("a.txt", "hello")
    result = repo.delete_folder("a.txt")
    assert result["success"] is False


# ---------------------------------------------------------------------------
# AgentCore.remove_file / remove_folder — mock the inherited GitRepo methods
# so we can test the wrapper logic without touching the real agent-core path.
# ---------------------------------------------------------------------------

def _bare_agent_core():
    from services.agent_core import AgentCore
    return AgentCore.__new__(AgentCore)  # bypass __init__ (hardcoded to real paths)


def test_remove_file_short_circuits_on_delete_failure():
    ac = _bare_agent_core()
    ac.delete_file = MagicMock(return_value={"success": False, "error": "not found"})
    ac.commit_and_push = MagicMock()
    result = ac.remove_file("x.json", "remove x")
    assert result["success"] is False
    ac.commit_and_push.assert_not_called()


def test_remove_file_commits_on_delete_success():
    ac = _bare_agent_core()
    ac.delete_file = MagicMock(return_value={"success": True, "path": "x.json"})
    ac.commit_and_push = MagicMock(return_value={"success": True, "action": "pushed"})
    result = ac.remove_file("x.json", "remove x")
    assert result["success"] is True
    ac.commit_and_push.assert_called_once_with("remove x")


def test_remove_folder_short_circuits_on_delete_failure():
    ac = _bare_agent_core()
    ac.delete_folder = MagicMock(return_value={"success": False, "error": "not found"})
    ac.commit_and_push = MagicMock()
    result = ac.remove_folder("exercises", "clear exercises")
    assert result["success"] is False
    ac.commit_and_push.assert_not_called()


def test_remove_folder_commits_on_delete_success():
    ac = _bare_agent_core()
    ac.delete_folder = MagicMock(return_value={"success": True, "path": "exercises"})
    ac.commit_and_push = MagicMock(return_value={"success": True, "action": "pushed"})
    result = ac.remove_folder("exercises", "clear exercises")
    assert result["success"] is True
    ac.commit_and_push.assert_called_once_with("clear exercises")
