"""
Prompts package
"""

from .system import DEFAULT_SYSTEM_PROMPT, load_system_prompt
from .email import EMAIL_RECEIVED_TEMPLATE

__all__ = ["DEFAULT_SYSTEM_PROMPT", "load_system_prompt", "EMAIL_RECEIVED_TEMPLATE"]