"""
Prompts package
"""

from .system import load_system_prompt
from .telegram import TELEGRAM_MESSAGE_TEMPLATE

__all__ = ["load_system_prompt", "TELEGRAM_MESSAGE_TEMPLATE"]
