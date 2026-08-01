"""
Tests for Agent._run_claude's tool-use loop — text Claude writes in a turn
that also calls a tool (e.g. explaining a word before logging it via
save_vietnamese_session) must make it into the reply, not just the final
turn's text after the tool call resolves.
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "test")

from agent import Agent


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(name, tool_input, tool_id="tool_1"):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=tool_id)


def _response(content, stop_reason):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


def test_text_alongside_tool_call_is_kept_in_reply():
    a = Agent()
    a.claude = MagicMock()

    first_response = _response(
        content=[
            _text_block('"nét" means a stroke/line, or by extension a feature or trait.'),
            _tool_use_block("save_vietnamese_session", {}),
        ],
        stop_reason="tool_use",
    )
    second_response = _response(
        content=[_text_block("Added to your vocab list.")],
        stop_reason="end_turn",
    )
    a.claude.messages.create.side_effect = [first_response, second_response]

    with patch("agent.handle_tool_call", return_value="ok"):
        reply = a._run_claude([{"role": "user", "content": "hi"}], "system prompt")

    assert "nét" in reply
    assert "Added to your vocab list." in reply


def test_reply_is_just_final_text_when_no_tool_call():
    a = Agent()
    a.claude = MagicMock()
    a.claude.messages.create.return_value = _response(
        content=[_text_block("just chatting, no tools needed")],
        stop_reason="end_turn",
    )

    reply = a._run_claude([{"role": "user", "content": "hi"}], "system prompt")

    assert reply == "just chatting, no tools needed"
