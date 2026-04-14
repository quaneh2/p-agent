"""
Telegram service — handles Telegram Bot API operations via long-polling.
"""

import html
import logging
import re

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"

_FENCED_CODE = re.compile(r"```(\w*)\n?(.*?)```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_STRIKETHROUGH = re.compile(r"~~(.+?)~~", re.DOTALL)
_BOLD_STAR = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BOLD_UNDER = re.compile(r"__(.+?)__", re.DOTALL)
_ITALIC_STAR = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_ITALIC_UNDER = re.compile(r"(?<![_\w])_(?!_)(.+?)(?<!_)_(?![_\w])")
_HEADER = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


def _markdown_to_html(text: str) -> str:
    """Convert common markdown to Telegram-compatible HTML."""
    code_blocks: list[str] = []
    inline_codes: list[str] = []

    def save_code_block(m: re.Match) -> str:
        body = html.escape(m.group(2))
        placeholder = f"\x00CODEBLOCK_{len(code_blocks)}\x00"
        code_blocks.append(f"<pre><code>{body}</code></pre>")
        return placeholder

    def save_inline_code(m: re.Match) -> str:
        body = html.escape(m.group(1))
        placeholder = f"\x00INLINE_{len(inline_codes)}\x00"
        inline_codes.append(f"<code>{body}</code>")
        return placeholder

    # 1. Stash code blocks before any other processing.
    text = _FENCED_CODE.sub(save_code_block, text)
    # 2. Stash inline code spans.
    text = _INLINE_CODE.sub(save_inline_code, text)
    # 3. Escape HTML special chars in remaining prose.
    text = html.escape(text)
    # 4. Apply inline markdown transforms.
    text = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    text = _STRIKETHROUGH.sub(r"<s>\1</s>", text)
    text = _BOLD_STAR.sub(r"<b>\1</b>", text)
    text = _BOLD_UNDER.sub(r"<b>\1</b>", text)
    text = _ITALIC_STAR.sub(r"<i>\1</i>", text)
    text = _ITALIC_UNDER.sub(r"<i>\1</i>", text)
    text = _HEADER.sub(r"<b>\1</b>", text)
    # 5. Restore stashed code.
    for i, block in enumerate(code_blocks):
        text = text.replace(f"\x00CODEBLOCK_{i}\x00", block)
    for i, code in enumerate(inline_codes):
        text = text.replace(f"\x00INLINE_{i}\x00", code)
    return text


class TelegramService:
    """Polls for Telegram updates and sends messages via the Bot API."""

    def __init__(self, token: str):
        self.token = token
        self._offset = 0

    def _url(self, method: str) -> str:
        return TELEGRAM_API_BASE.format(token=self.token, method=method)

    def skip_pending(self):
        """
        Advance the offset past any messages that arrived before startup.
        This prevents the agent from processing a backlog of old messages
        when it restarts. Messages sent during downtime are silently skipped.
        """
        updates = self._fetch_updates()
        if updates:
            logger.info("Skipped %d pending Telegram message(s) from before startup", len(updates))

    def get_updates(self) -> list:
        """Return new updates since the last call."""
        return self._fetch_updates()

    def _fetch_updates(self) -> list:
        try:
            resp = requests.get(
                self._url("getUpdates"),
                params={
                    "offset": self._offset,
                    "timeout": 0,
                    "allowed_updates": ["message"],
                },
                timeout=10,
            )
            resp.raise_for_status()
            updates = resp.json().get("result", [])
            if updates:
                self._offset = updates[-1]["update_id"] + 1
            return updates
        except Exception as e:
            logger.error("Failed to get Telegram updates: %s", e)
            return []

    def send_message(self, chat_id: int, text: str) -> dict:
        """Send a text message to a chat, rendering markdown as Telegram HTML."""
        try:
            html_text = _markdown_to_html(text)
            resp = requests.post(
                self._url("sendMessage"),
                json={"chat_id": chat_id, "text": html_text, "parse_mode": "HTML"},
                timeout=10,
            )
            # Telegram returns 400 with a description containing "parse" or "entities"
            # when the HTML is malformed. Fall back to plain text in that case only.
            if resp.status_code == 400:
                desc = resp.json().get("description", "").lower()
                if "parse" in desc or "entities" in desc:
                    logger.warning(
                        "HTML parse_mode rejected by Telegram, falling back to plain text: %s", desc
                    )
                    resp = requests.post(
                        self._url("sendMessage"),
                        json={"chat_id": chat_id, "text": text},
                        timeout=10,
                    )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("Failed to send Telegram message to %s: %s", chat_id, e)
            return None
