"""
Unit tests for VietnameseProgressSkill.

Uses a lightweight mock for agent_core so no git operations are performed.
Loaded directly from its module file to avoid triggering skills/__init__.py,
which pulls in the full skills package (and therefore PyGithub-backed modules).
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

_spec = importlib.util.spec_from_file_location(
    "skills.vietnamese_progress",
    Path(__file__).parent.parent / "skills" / "vietnamese_progress.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["skills.vietnamese_progress"] = _mod
_spec.loader.exec_module(_mod)
VietnameseProgressSkill = _mod.VietnameseProgressSkill


def _make_skill(existing: dict = None):
    """Return a VietnameseProgressSkill with a mocked agent_core."""
    agent_core = MagicMock()
    if existing is None:
        agent_core.read_file.return_value = {"success": False, "error": "not found"}
    else:
        agent_core.read_file.return_value = {
            "success": True,
            "content": json.dumps(existing),
        }
    agent_core.upsert_file.return_value = {"success": True}
    return VietnameseProgressSkill(agent_core), agent_core


def test_get_snapshot_seeds_defaults_on_first_read():
    skill, agent_core = _make_skill()
    result = skill.get_snapshot()
    assert result["success"] is True
    progress = result["progress"]
    assert progress["journey_started"] is not None
    assert progress["difficulty_tier"] == 1
    assert progress["target_level"] == "B2"
    # Seeding should have persisted the file.
    agent_core.upsert_file.assert_called_once()


def test_get_snapshot_does_not_reseed_existing_file():
    existing = {
        "version": 1,
        "target_level": "B2",
        "journey_started": "2026-01-01",
        "estimated_level": "B1 (solid)",
        "difficulty_tier": 2,
        "last_updated": "2026-01-05T00:00:00Z",
        "strengths": ["listening"],
        "struggles": ["subjunctive"],
        "notes": "doing fine",
        "history": [],
    }
    skill, agent_core = _make_skill(existing)
    result = skill.get_snapshot()
    assert result["success"] is True
    assert result["progress"]["journey_started"] == "2026-01-01"
    assert result["progress"]["difficulty_tier"] == 2
    agent_core.upsert_file.assert_not_called()


def test_update_snapshot_changes_only_provided_fields():
    existing = {
        "version": 1,
        "target_level": "B2",
        "journey_started": "2026-01-01",
        "estimated_level": "B1 (low)",
        "difficulty_tier": 1,
        "last_updated": "2026-01-01T00:00:00Z",
        "strengths": [],
        "struggles": [],
        "notes": "starting out",
        "history": [],
    }
    skill, agent_core = _make_skill(existing)
    result = skill.update_snapshot(struggles=["classifiers"])
    assert result["success"] is True
    progress = result["progress"]
    assert progress["struggles"] == ["classifiers"]
    # Untouched fields preserved.
    assert progress["estimated_level"] == "B1 (low)"
    assert progress["difficulty_tier"] == 1
    assert progress["notes"] == "starting out"


def test_update_snapshot_appends_history_on_tier_change():
    existing = {
        "version": 1,
        "target_level": "B2",
        "journey_started": "2026-01-01",
        "estimated_level": "B1 (low)",
        "difficulty_tier": 1,
        "last_updated": "2026-01-01T00:00:00Z",
        "strengths": [],
        "struggles": [],
        "notes": "starting out",
        "history": [],
    }
    skill, agent_core = _make_skill(existing)
    result = skill.update_snapshot(
        difficulty_tier=2,
        reason="Three strong sessions in a row.",
    )
    assert result["success"] is True
    history = result["progress"]["history"]
    assert len(history) == 1
    assert history[0]["difficulty_tier"] == 2
    assert history[0]["reason"] == "Three strong sessions in a row."


def test_update_snapshot_no_history_entry_without_change():
    existing = {
        "version": 1,
        "target_level": "B2",
        "journey_started": "2026-01-01",
        "estimated_level": "B1 (low)",
        "difficulty_tier": 1,
        "last_updated": "2026-01-01T00:00:00Z",
        "strengths": [],
        "struggles": [],
        "notes": "starting out",
        "history": [],
    }
    skill, agent_core = _make_skill(existing)
    result = skill.update_snapshot(notes="still starting out, no change in level")
    assert result["progress"]["history"] == []


def test_update_snapshot_default_reason_when_missing():
    existing = {
        "version": 1,
        "target_level": "B2",
        "journey_started": "2026-01-01",
        "estimated_level": "B1 (low)",
        "difficulty_tier": 1,
        "last_updated": "2026-01-01T00:00:00Z",
        "strengths": [],
        "struggles": [],
        "notes": "",
        "history": [],
    }
    skill, agent_core = _make_skill(existing)
    result = skill.update_snapshot(difficulty_tier=2)
    assert result["progress"]["history"][0]["reason"] == "No reason given."
