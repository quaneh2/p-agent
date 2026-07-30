"""
Pure authorization helpers.
"""

import logging

from config import TELEGRAM_AUTHORIZED_IDS

logger = logging.getLogger(__name__)


def is_authorized_telegram_user(user_id: int) -> bool:
    """Check if a Telegram user ID is in the authorized list."""
    if not TELEGRAM_AUTHORIZED_IDS:
        logger.error("No authorized Telegram users configured — rejecting all messages")
        return False
    return user_id in TELEGRAM_AUTHORIZED_IDS
