"""
Config for the Vietnamese Learning Agent
"""

from pathlib import Path
import os
import json
from dotenv import load_dotenv

load_dotenv()

POLL_INTERVAL_SECONDS = 10

CLAUDE_MODEL = "claude-sonnet-4-6"

GIT_USER_NAME = "James Stevens"
GIT_USER_EMAIL = "stevens@poolbegsolutions.com"

AGENT_CORE_DIR = Path("./agent-core")

GITHUB_USERNAME = "stevens-j-54"
AGENT_CORE_REPO = f"{GITHUB_USERNAME}/agent-core"

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_AUTHORIZED_IDS = json.loads(os.getenv("TELEGRAM_AUTHORIZED_IDS", "[]"))

# Dashboard (GitHub Pages)
DASHBOARD_REPO_NAME = f"{GITHUB_USERNAME}/{GITHUB_USERNAME}.github.io"
DASHBOARD_DIR = Path("./dashboard-repo")
