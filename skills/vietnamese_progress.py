"""
Vietnamese Progress Skill

Maintains a compact, structured snapshot of Hugh's B1->B2 journey — distinct
from the full session log in exercises/ and the vocab list in
vietnamese_vocab.json. Those record *what happened*; this records the
agent's current *assessment*: estimated level, a 1-5 difficulty tier, and
recent strengths/struggles. A new exercise reads this once (cheap) instead
of re-deriving a level estimate from scratch every session.

Updated deliberately — typically by the nightly review, or when a single
session reveals something significant — rather than after every exercise,
so the difficulty tier doesn't thrash on single-session noise. Every change
to estimated_level or difficulty_tier is appended to an audit trail
(history) with a reason, so the journey is legible over time.
"""

import json
import logging
from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)

PROGRESS_FILE = "vietnamese_progress.json"

DEFAULT_SNAPSHOT = {
    "version": 1,
    "target_level": "B2",
    "journey_started": None,  # stamped with today's date on first read
    "estimated_level": "B1 (low, resuming after a break)",
    "difficulty_tier": 1,
    "last_updated": None,
    "strengths": [],
    "struggles": [],
    "notes": (
        "Journey restarted after an extended break from study. Starting "
        "conservatively at tier 1 rather than assuming prior B1 fluency "
        "carried over — early sessions should rebuild confidence before "
        "difficulty increases."
    ),
    "history": [],
}


class VietnameseProgressSkill:
    """
    Reads/writes agent-core/vietnamese_progress.json.

    Depends on:
      - agent_core: AgentCore — for reading/writing the progress file
    """

    def __init__(self, agent_core):
        self.agent_core = agent_core

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_snapshot(self) -> dict:
        """Load the progress snapshot, seeding defaults on first-ever read."""
        try:
            snapshot = self._load()
            if snapshot.get("journey_started") is None:
                snapshot["journey_started"] = date.today().isoformat()
                snapshot["last_updated"] = _now_iso()
                self._save(snapshot, "Seed Vietnamese progress tracking")
            return {"success": True, "progress": snapshot}
        except Exception as e:
            logger.error("get_snapshot failed: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}

    def update_snapshot(
        self,
        estimated_level: str = None,
        difficulty_tier: int = None,
        strengths: list = None,
        struggles: list = None,
        notes: str = None,
        reason: str = None,
    ) -> dict:
        """
        Update the progress snapshot. Only fields provided are changed.
        Appends a history entry (with reason) whenever estimated_level or
        difficulty_tier actually changes.
        """
        try:
            snapshot = self._load()
            if snapshot.get("journey_started") is None:
                snapshot["journey_started"] = date.today().isoformat()

            level_changed = estimated_level is not None and estimated_level != snapshot.get("estimated_level")
            tier_changed = difficulty_tier is not None and difficulty_tier != snapshot.get("difficulty_tier")

            if estimated_level is not None:
                snapshot["estimated_level"] = estimated_level
            if difficulty_tier is not None:
                snapshot["difficulty_tier"] = difficulty_tier
            if strengths is not None:
                snapshot["strengths"] = strengths
            if struggles is not None:
                snapshot["struggles"] = struggles
            if notes is not None:
                snapshot["notes"] = notes

            if level_changed or tier_changed:
                snapshot.setdefault("history", []).append({
                    "date": date.today().isoformat(),
                    "estimated_level": snapshot["estimated_level"],
                    "difficulty_tier": snapshot["difficulty_tier"],
                    "reason": reason or "No reason given.",
                })

            snapshot["last_updated"] = _now_iso()
            self._save(snapshot, f"Update Vietnamese progress: {reason or 'routine update'}")
            return {"success": True, "progress": snapshot}
        except Exception as e:
            logger.error("update_snapshot failed: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        result = self.agent_core.read_file(PROGRESS_FILE)
        if not result.get("success") or not result.get("content"):
            return json.loads(json.dumps(DEFAULT_SNAPSHOT))  # deep copy
        try:
            return json.loads(result["content"])
        except (json.JSONDecodeError, KeyError):
            return json.loads(json.dumps(DEFAULT_SNAPSHOT))

    def _save(self, snapshot: dict, commit_message: str) -> None:
        content = json.dumps(snapshot, ensure_ascii=False, indent=2)
        result = self.agent_core.upsert_file(PROGRESS_FILE, content, commit_message)
        if not result.get("success"):
            raise RuntimeError(f"Failed to save progress: {result.get('error')}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
