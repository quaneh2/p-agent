"""
Pure helpers for splitting a single agent response into multiple Telegram
messages. A reply with genuinely distinct parts (e.g. an exercise paragraph
and its glossary) reads better as separate messages than one long block —
the model marks the break with TELEGRAM_PART_SEPARATOR and each part is
delivered as its own Telegram message.
"""

# Keep this literal string in sync with the Message Formatting section of
# prompts/system.py::CAPABILITIES, which is where the model is told to use it.
TELEGRAM_PART_SEPARATOR = "<<<telegram-message-break>>>"


def split_message_parts(text: str) -> list[str]:
    """Split text on TELEGRAM_PART_SEPARATOR, stripping whitespace and dropping empty parts."""
    return [part.strip() for part in text.split(TELEGRAM_PART_SEPARATOR) if part.strip()]
