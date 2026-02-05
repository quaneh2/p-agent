"""
Services package
"""

from .git_repo import GitRepo
from .workspace import Workspace
from .email import EmailService
from .agent_core import AgentCore

__all__ = ["GitRepo", "Workspace", "EmailService", "AgentCore"]
