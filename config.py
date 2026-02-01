"""
Config for the AI Agent
"""

from pathlib import Path
import os
import json
from dotenv import load_dotenv

load_dotenv()

POLL_INTERVAL_SECONDS = 10
WORKSPACE_DIR = Path("./workspace")

AUTHORIZED_SENDERS = json.loads(os.getenv("AUTHORIZED_SENDERS", "[]"))

CLAUDE_MODEL = "claude-sonnet-4-20250514"

GIT_USER_NAME = "James Stevens"
GIT_USER_EMAIL = "stevens@poolbegsolutions.com"

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
