"""
Prompts package
"""

from .system import load_system_prompt
from .email import EMAIL_RECEIVED_TEMPLATE

__all__ = ["load_system_prompt", "EMAIL_RECEIVED_TEMPLATE"]