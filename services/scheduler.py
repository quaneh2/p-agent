"""
SchedulerService — persists and evaluates scheduled tasks.

Tasks are stored as JSON in agent-core/SCHEDULES.json (same pattern as
telegram_sessions.json). Two task types are supported:

  recurring  — fires on a standard 5-field UTC cron expression
  one_time   — fires once at a specific ISO 8601 UTC datetime

Two instruction types are supported:

  skill            — calls a registered Python skill directly (no Claude API call)
  natural_language — runs a text instruction through Claude with a lean prompt
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from croniter import croniter, CroniterBadCronError

logger = logging.getLogger(__name__)

SCHEDULES_FILE = "SCHEDULES.json"

# Seeded into a fresh agent-core on first run, so Hugh gets proactive
# messages from day one without having to ask for a schedule to be set up.
# All times are UTC; adjust cadence/timing anytime via add/remove_scheduled_task.
DEFAULT_TASKS = [
    {
        "name": "Vietnamese translation exercise",
        "type": "recurring",
        "cron": "0 8 * * 1,3,5",  # Mon/Wed/Fri 08:00 UTC
        "instruction_type": "natural_language",
        "instruction": (
            "Run a Vietnamese translation exercise for Hugh (B1 working towards B2). "
            "Follow steps 1-3 of the Translation Exercise Workflow only: call "
            "prepare_vietnamese_chat, write the paragraph, and present the exercise. "
            "Do not correct or save the session yet — that happens once Hugh replies "
            "with his translation in a later message."
        ),
    },
    {
        "name": "Vietnamese conversation check-in",
        "type": "recurring",
        "cron": "0 17 * * 2,6",  # Tue/Sat 17:00 UTC
        "instruction_type": "natural_language",
        "instruction": (
            "Start a casual Vietnamese conversation practice session with Hugh. "
            "Follow steps 1-2 of the Conversation Practice Workflow only: call "
            "prepare_vietnamese_chat, then open the conversation. Keep it light and "
            "low-pressure — this should feel like a check-in, not a test."
        ),
    },
    {
        "name": "Vietnamese dashboard refresh",
        "type": "recurring",
        "cron": "0 23 * * *",  # daily 23:00 UTC
        "instruction_type": "skill",
        "instruction": "update_vietnamese_dashboard",
    },
]


class SchedulerService:
    def __init__(self, agent_core, skills: dict):
        self.agent_core = agent_core
        self._skills = skills  # live reference — reflects skills added after init
        self._tasks: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_tasks(self) -> list[dict]:
        """Load tasks from agent-core/SCHEDULES.json. Seeds defaults if missing."""
        result = self.agent_core.read_file(SCHEDULES_FILE)
        if not result.get("success"):
            logger.info("SCHEDULES.json not found — seeding default schedule")
            self._tasks = []
            self._seed_defaults()
        else:
            try:
                data = json.loads(result["content"])
                self._tasks = data.get("tasks", [])
                logger.info("Loaded %d scheduled task(s)", len(self._tasks))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Could not parse SCHEDULES.json (%s) — starting fresh", e)
                self._tasks = []
        return self._tasks

    def list_tasks(self) -> list[dict]:
        return list(self._tasks)

    def get_due_tasks(self) -> list[dict]:
        """Return active tasks whose next_run is at or before now (UTC)."""
        now = datetime.now(timezone.utc)
        due = []
        for task in self._tasks:
            if task.get("status") != "active":
                continue
            next_run_str = task.get("next_run")
            if not next_run_str:
                continue
            try:
                next_run = datetime.fromisoformat(next_run_str)
                # Ensure timezone-aware for comparison
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=timezone.utc)
                if next_run <= now:
                    due.append(task)
            except ValueError:
                logger.warning("Task %s has invalid next_run: %s", task.get("id"), next_run_str)
        return due

    def add_task(self, task_input: dict) -> dict:
        """Validate, assign metadata, calculate next_run, and persist."""
        name = task_input.get("name", "").strip()
        task_type = task_input.get("type")
        instruction = task_input.get("instruction", "").strip()
        instruction_type = task_input.get("instruction_type")

        # Basic validation
        if not name:
            return {"success": False, "error": "name is required"}
        if task_type not in ("recurring", "one_time"):
            return {"success": False, "error": "type must be 'recurring' or 'one_time'"}
        if not instruction:
            return {"success": False, "error": "instruction is required"}
        if instruction_type not in ("skill", "natural_language"):
            return {"success": False, "error": "instruction_type must be 'skill' or 'natural_language'"}
        if instruction_type == "skill" and instruction not in self._skills:
            known = sorted(self._skills.keys())
            return {"success": False, "error": f"Unknown skill '{instruction}'. Known skills: {known}"}

        task: dict = {
            "id": str(uuid.uuid4()),
            "name": name,
            "type": task_type,
            "cron": task_input.get("cron") or None,
            "run_at": task_input.get("run_at") or None,
            "instruction": instruction,
            "instruction_type": instruction_type,
            "next_run": None,
            "last_run": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }

        next_run = self._calculate_next_run(task)
        if next_run is None:
            if task_type == "recurring":
                return {"success": False, "error": "recurring tasks require a valid 'cron' expression"}
            return {"success": False, "error": "one_time tasks require a valid 'run_at' datetime"}
        task["next_run"] = next_run

        self._tasks.append(task)
        self._persist(f"Add scheduled task: {name}")
        logger.info("Scheduled task added: %s (id=%s, next_run=%s)", name, task["id"], next_run)
        return {"success": True, "task": task}

    def remove_task(self, task_id: str) -> dict:
        """Remove a task by ID and persist."""
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if t["id"] != task_id]
        if len(self._tasks) == before:
            return {"success": False, "error": f"No task found with id: {task_id}"}
        self._persist(f"Remove scheduled task {task_id}")
        logger.info("Scheduled task removed: %s", task_id)
        return {"success": True}

    def mark_task_complete(self, task_id: str) -> None:
        """
        Update a task after it has run.
        - recurring: advance next_run via croniter from now
        - one_time:  set status=completed
        """
        now = datetime.now(timezone.utc)
        for task in self._tasks:
            if task["id"] != task_id:
                continue
            task["last_run"] = now.isoformat()
            if task["type"] == "recurring":
                cron = task.get("cron", "")
                try:
                    task["next_run"] = croniter(cron, now).get_next(datetime).isoformat()
                except (CroniterBadCronError, ValueError) as e:
                    logger.error("Cannot advance next_run for task %s: %s", task_id, e)
            else:
                task["status"] = "completed"
            break
        self._persist(f"Update task after run: {task_id}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _seed_defaults(self) -> None:
        """Populate a fresh schedule with DEFAULT_TASKS (each persisted via add_task)."""
        for task_input in DEFAULT_TASKS:
            result = self.add_task(task_input)
            if not result.get("success"):
                logger.warning(
                    "Failed to seed default task '%s': %s",
                    task_input.get("name"), result.get("error")
                )
        if not self._tasks:
            self._persist("Initialise task schedule")

    def _calculate_next_run(self, task: dict) -> str | None:
        """Return the next scheduled run time as an ISO 8601 string, or None on error."""
        if task["type"] == "recurring":
            cron = task.get("cron")
            if not cron:
                return None
            try:
                now = datetime.now(timezone.utc)
                return croniter(cron, now).get_next(datetime).isoformat()
            except (CroniterBadCronError, ValueError) as e:
                logger.warning("Invalid cron '%s': %s", cron, e)
                return None
        else:
            run_at = task.get("run_at")
            if not run_at:
                return None
            try:
                dt = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except ValueError as e:
                logger.warning("Invalid run_at '%s': %s", run_at, e)
                return None

    def _persist(self, commit_message: str) -> None:
        """Write current task list to agent-core and commit."""
        content = json.dumps({"tasks": self._tasks}, indent=2)
        result = self.agent_core.upsert_file(SCHEDULES_FILE, content, commit_message)
        if not result.get("success"):
            logger.error("Failed to persist schedule: %s", result.get("error"))
