"""
Tests for Agent.reset_telegram_sessions — must clear the in-memory session
dict AND persist the empty state, in that order, so a reset actually sticks
instead of getting silently resurrected by the next message's save.
"""

import json
import os
from unittest.mock import MagicMock

os.environ.setdefault("ANTHROPIC_API_KEY", "test")

from agent import Agent


def test_reset_clears_in_memory_sessions():
    a = Agent()
    a.agent_core = MagicMock()
    a.agent_core.upsert_file.return_value = {"success": True}
    a._telegram_sessions = {
        111: [{"role": "user", "content": "hi"}],
        222: [{"role": "assistant", "content": "yo"}],
    }
    result = a.reset_telegram_sessions()
    assert result["success"] is True
    assert a._telegram_sessions == {}


def test_reset_persists_empty_state():
    a = Agent()
    a.agent_core = MagicMock()
    a.agent_core.upsert_file.return_value = {"success": True}
    a._telegram_sessions = {111: [{"role": "user", "content": "hi"}]}
    a.reset_telegram_sessions()
    a.agent_core.upsert_file.assert_called_once()
    args, kwargs = a.agent_core.upsert_file.call_args
    persisted_content = args[1] if len(args) > 1 else kwargs.get("content")
    assert json.loads(persisted_content) == {}


def test_reset_on_already_empty_sessions_is_safe():
    a = Agent()
    a.agent_core = MagicMock()
    a.agent_core.upsert_file.return_value = {"success": True}
    a._telegram_sessions = {}
    result = a.reset_telegram_sessions()
    assert result["success"] is True
    assert a._telegram_sessions == {}
