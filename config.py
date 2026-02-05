"""
Config for the AI Agent
"""

from pathlib import Path
import os
import json
from dotenv import load_dotenv

load_dotenv()

POLL_INTERVAL_SECONDS = 10

AUTHORIZED_SENDERS = json.loads(os.getenv("AUTHORIZED_SENDERS", "[]"))

CLAUDE_MODEL = "claude-sonnet-4-20250514"

GIT_USER_NAME = "James Stevens"
GIT_USER_EMAIL = "stevens@poolbegsolutions.com"

WORKSPACE_DIR = Path("./workspace")
AGENT_CORE_DIR = Path("./agent-core")

GITHUB_USERNAME = "stevens-j-54"
WORKSPACE_REPO = f"{GITHUB_USERNAME}/workspace"
AGENT_CORE_REPO = f"{GITHUB_USERNAME}/agent-core"

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
