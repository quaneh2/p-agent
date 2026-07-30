"""
Unit tests for SchedulerService.

Uses a lightweight mock for agent_core so no git operations are performed.
SchedulerService is loaded directly from its module file to avoid triggering
services/__init__.py, which imports PyGithub-backed modules.
"""

import importlib.util
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock

# Load scheduler module without triggering services/__init__.py
_spec = importlib.util.spec_from_file_location(
    "services.scheduler",
    Path(__file__).parent.parent / "services" / "scheduler.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["services.scheduler"] = _mod
_spec.loader.exec_module(_mod)
SchedulerService = _mod.SchedulerService
DEFAULT_TASKS = _mod.DEFAULT_TASKS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal stub — only the key matters for skill-task validation.
_FAKE_SKILLS = {"update_vietnamese_dashboard": object()}


def _make_scheduler(tasks=None):
    """
    Return a SchedulerService with a mocked agent_core.

    Pass tasks=[] (not the default None) to get a genuinely empty, unseeded
    schedule — None simulates a missing SCHEDULES.json, which triggers
    default-task seeding, same as a fresh deploy.
    """
    agent_core = MagicMock()
    if tasks is None:
        agent_core.read_file.return_value = {"success": False, "error": "not found"}
    else:
        agent_core.read_file.return_value = {
            "success": True,
            "content": json.dumps({"tasks": tasks}),
        }
    agent_core.upsert_file.return_value = {"success": True}
    sched = SchedulerService(agent_core, _FAKE_SKILLS)
    sched.load_tasks()
    return sched


def _past_dt(seconds=60):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _future_dt(seconds=3600):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def test_missing_schedule_seeds_defaults():
    sched = _make_scheduler()  # tasks=None -> simulates missing SCHEDULES.json
    tasks = sched.list_tasks()
    assert len(tasks) == len(DEFAULT_TASKS)
    assert {t["name"] for t in tasks} == {t["name"] for t in DEFAULT_TASKS}
    for t in tasks:
        assert t["next_run"] is not None
        assert t["status"] == "active"


def test_existing_schedule_is_not_reseeded():
    sched = _make_scheduler(tasks=[])
    assert sched.list_tasks() == []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_get_due_tasks_returns_overdue():
    task = {
        "id": "aaa",
        "name": "Past task",
        "type": "recurring",
        "cron": "* * * * *",
        "run_at": None,
        "instruction": "update_vietnamese_dashboard",
        "instruction_type": "skill",
        "next_run": _past_dt(120),
        "last_run": None,
        "created_at": _past_dt(3600),
        "status": "active",
    }
    sched = _make_scheduler([task])
    due = sched.get_due_tasks()
    assert len(due) == 1
    assert due[0]["id"] == "aaa"


def test_get_due_tasks_skips_future():
    task = {
        "id": "bbb",
        "name": "Future task",
        "type": "one_time",
        "cron": None,
        "run_at": _future_dt(7200),
        "instruction": "send me a report",
        "instruction_type": "natural_language",
        "next_run": _future_dt(7200),
        "last_run": None,
        "created_at": _past_dt(60),
        "status": "active",
    }
    sched = _make_scheduler([task])
    due = sched.get_due_tasks()
    assert due == []


def test_get_due_tasks_skips_completed():
    task = {
        "id": "ccc",
        "name": "Done task",
        "type": "one_time",
        "cron": None,
        "run_at": _past_dt(3600),
        "instruction": "do something",
        "instruction_type": "natural_language",
        "next_run": _past_dt(3600),
        "last_run": _past_dt(3600),
        "created_at": _past_dt(7200),
        "status": "completed",
    }
    sched = _make_scheduler([task])
    due = sched.get_due_tasks()
    assert due == []


def test_mark_complete_recurring_advances_next_run():
    task = {
        "id": "ddd",
        "name": "Recurring",
        "type": "recurring",
        "cron": "0 9 * * *",
        "run_at": None,
        "instruction": "update_vietnamese_dashboard",
        "instruction_type": "skill",
        "next_run": _past_dt(60),
        "last_run": None,
        "created_at": _past_dt(3600),
        "status": "active",
    }
    sched = _make_scheduler([task])
    before_next = sched.list_tasks()[0]["next_run"]
    sched.mark_task_complete("ddd")
    after = sched.list_tasks()[0]
    # Status stays active for recurring tasks
    assert after["status"] == "active"
    # last_run should now be set
    assert after["last_run"] is not None
    # next_run should have moved forward
    assert after["next_run"] != before_next
    # next_run should be in the future
    next_dt = datetime.fromisoformat(after["next_run"])
    assert next_dt > datetime.now(timezone.utc)


def test_mark_complete_one_time_sets_completed():
    task = {
        "id": "eee",
        "name": "One-time",
        "type": "one_time",
        "cron": None,
        "run_at": _past_dt(60),
        "instruction": "write me a haiku",
        "instruction_type": "natural_language",
        "next_run": _past_dt(60),
        "last_run": None,
        "created_at": _past_dt(3600),
        "status": "active",
    }
    sched = _make_scheduler([task])
    sched.mark_task_complete("eee")
    after = sched.list_tasks()[0]
    assert after["status"] == "completed"
    assert after["last_run"] is not None


def test_add_task_assigns_id_and_next_run():
    sched = _make_scheduler(tasks=[])
    result = sched.add_task({
        "name": "Daily digest",
        "type": "recurring",
        "cron": "0 9 * * 1-5",
        "instruction": "update_vietnamese_dashboard",
        "instruction_type": "skill",
    })
    assert result["success"] is True
    task = result["task"]
    assert task["id"]  # non-empty UUID
    assert task["next_run"]  # calculated
    next_dt = datetime.fromisoformat(task["next_run"])
    assert next_dt > datetime.now(timezone.utc)
    assert len(sched.list_tasks()) == 1


def test_add_task_one_time_requires_run_at():
    sched = _make_scheduler(tasks=[])
    result = sched.add_task({
        "name": "Missing run_at",
        "type": "one_time",
        "instruction": "do something",
        "instruction_type": "natural_language",
        # run_at intentionally omitted
    })
    assert result["success"] is False
    assert "run_at" in result["error"]


def test_add_task_recurring_requires_cron():
    sched = _make_scheduler(tasks=[])
    result = sched.add_task({
        "name": "Missing cron",
        "type": "recurring",
        "instruction": "update_vietnamese_dashboard",
        "instruction_type": "skill",
        # cron intentionally omitted
    })
    assert result["success"] is False
    assert "cron" in result["error"]


def test_remove_task():
    task = {
        "id": "fff",
        "name": "To remove",
        "type": "one_time",
        "cron": None,
        "run_at": _future_dt(3600),
        "instruction": "do nothing",
        "instruction_type": "natural_language",
        "next_run": _future_dt(3600),
        "last_run": None,
        "created_at": _past_dt(60),
        "status": "active",
    }
    sched = _make_scheduler([task])
    assert len(sched.list_tasks()) == 1
    result = sched.remove_task("fff")
    assert result["success"] is True
    assert len(sched.list_tasks()) == 0


def test_remove_task_not_found():
    sched = _make_scheduler(tasks=[])
    result = sched.remove_task("nonexistent-id")
    assert result["success"] is False
    assert "No task found" in result["error"]


# ---------------------------------------------------------------------------
# Jitter
# ---------------------------------------------------------------------------

def test_jitter_keeps_next_run_within_window_on_create():
    sched = _make_scheduler(tasks=[])
    now = datetime.now(timezone.utc)
    result = sched.add_task({
        "name": "Jittered daily",
        "type": "recurring",
        "cron": "0 8 * * *",
        "jitter_minutes": 90,
        "instruction": "update_vietnamese_dashboard",
        "instruction_type": "skill",
    })
    assert result["success"] is True
    next_dt = datetime.fromisoformat(result["task"]["next_run"])
    # Base cron next-run is <=24h out; a 90-minute jitter can't push it past ~26h.
    assert now < next_dt < now + timedelta(hours=26)


def test_jitter_zero_is_deterministic():
    sched = _make_scheduler(tasks=[])
    from croniter import croniter
    now_before = datetime.now(timezone.utc)
    result = sched.add_task({
        "name": "No jitter",
        "type": "recurring",
        "cron": "0 8 * * *",
        "instruction": "update_vietnamese_dashboard",
        "instruction_type": "skill",
    })
    expected = croniter("0 8 * * *", now_before).get_next(datetime)
    actual = datetime.fromisoformat(result["task"]["next_run"])
    # Without jitter, next_run should match the raw cron computation (within a
    # second of slack for the two croniter calls happening a moment apart).
    assert abs((actual - expected).total_seconds()) < 2


def test_jitter_applied_on_mark_complete():
    task = {
        "id": "jjj",
        "name": "Jittered recurring",
        "type": "recurring",
        "cron": "0 9 * * *",
        "jitter_minutes": 60,
        "run_at": None,
        "instruction": "update_vietnamese_dashboard",
        "instruction_type": "skill",
        "next_run": _past_dt(60),
        "last_run": None,
        "created_at": _past_dt(3600),
        "status": "active",
    }
    sched = _make_scheduler([task])
    from croniter import croniter
    now = datetime.now(timezone.utc)
    base_next = croniter("0 9 * * *", now).get_next(datetime)
    sched.mark_task_complete("jjj")
    after = sched.list_tasks()[0]
    next_dt = datetime.fromisoformat(after["next_run"])
    assert abs((next_dt - base_next).total_seconds()) <= 60 * 60 + 5


def test_negative_jitter_input_clamped_to_zero():
    sched = _make_scheduler(tasks=[])
    result = sched.add_task({
        "name": "Bad jitter",
        "type": "recurring",
        "cron": "0 8 * * *",
        "jitter_minutes": -50,
        "instruction": "update_vietnamese_dashboard",
        "instruction_type": "skill",
    })
    assert result["success"] is True
    assert result["task"]["jitter_minutes"] == 0


# ---------------------------------------------------------------------------
# Notify
# ---------------------------------------------------------------------------

def test_notify_defaults_true_for_natural_language():
    sched = _make_scheduler(tasks=[])
    result = sched.add_task({
        "name": "Chatty task",
        "type": "one_time",
        "run_at": _future_dt(3600),
        "instruction": "say hello",
        "instruction_type": "natural_language",
    })
    assert result["task"]["notify"] is True


def test_notify_can_be_set_false():
    sched = _make_scheduler(tasks=[])
    result = sched.add_task({
        "name": "Silent task",
        "type": "one_time",
        "run_at": _future_dt(3600),
        "instruction": "do internal housekeeping",
        "instruction_type": "natural_language",
        "notify": False,
    })
    assert result["task"]["notify"] is False


def test_default_tasks_have_expected_notify_flags():
    by_name = {t["name"]: t for t in DEFAULT_TASKS}
    assert by_name["Vietnamese translation exercise"].get("notify", True) is True
    assert by_name["Vietnamese spontaneous chat (day)"].get("notify", True) is True
    assert by_name["Vietnamese spontaneous chat (evening)"].get("notify", True) is True
    assert by_name["Vietnamese nightly review"]["notify"] is False


def test_default_chat_tasks_capped_at_two_and_non_overlapping():
    chat_tasks = [t for t in DEFAULT_TASKS if "spontaneous chat" in t["name"]]
    assert len(chat_tasks) == 2
    for t in chat_tasks:
        assert t["jitter_minutes"] > 0
    # Windows (anchor +/- jitter) should not overlap, so the two chats stay spread out.
    from croniter import croniter
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    windows = []
    for t in chat_tasks:
        anchor = croniter(t["cron"], now).get_next(datetime)
        j = timedelta(minutes=t["jitter_minutes"])
        windows.append((anchor - j, anchor + j))
    windows.sort()
    assert windows[0][1] <= windows[1][0]
