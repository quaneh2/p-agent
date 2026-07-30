"""
Vietnamese Learning Agent
==========================================
An always-on agent that helps Hugh study Vietnamese (B1 → B2) over Telegram:
proactive translation exercises, conversation practice, vocab quizzes, and
structured vocabulary tracking.
"""

import json
import logging
import os
import time

import anthropic

from config import (
    POLL_INTERVAL_SECONDS,
    CLAUDE_MODEL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_AUTHORIZED_IDS,
    AGENT_CORE_DIR,
)
from prompts import load_system_prompt, TELEGRAM_MESSAGE_TEMPLATE
from tools import TOOLS, handle_tool_call
from services import AgentCore, TelegramService, FetchService, SchedulerService
from skills import (
    DashboardSkill,
    VietnameseStudySkill,
    VietnameseVocabSkill,
    VietnameseDashboardSkill,
    VietnameseProgressSkill,
)
from utils import is_authorized_telegram_user, split_message_parts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

MAX_TELEGRAM_HISTORY = 20  # message turns to keep per chat session

# Anthropic rate-limit + burst control.
# Keep this in-process (per agent instance) to avoid immediate back-to-back
# calls causing repeated 429 → sleep → success → 429 patterns during tool loops.
ANTHROPIC_MIN_REQUEST_INTERVAL_SECONDS = 0.5
ANTHROPIC_MAX_RETRIES = 10
ANTHROPIC_BACKOFF_INITIAL_SECONDS = 1.0
# 529 "Overloaded" is server-side and clears much more slowly than a network
# hiccup.  Starting the backoff at 1 s wastes the first several retries.
ANTHROPIC_OVERLOAD_BACKOFF_INITIAL_SECONDS = 5.0
ANTHROPIC_BACKOFF_MAX_SECONDS = 60.0



class Agent:
    def __init__(self):
        self.telegram_service = None
        self.claude = None
        self._telegram_sessions: dict[int, list] = {}
        self.agent_core = None
        self.fetch_service = FetchService()
        self._anthropic_next_allowed_ts = 0.0
        self._anthropic_last_call_ts = 0.0
        self._skills: dict = {}
        self.scheduler: SchedulerService | None = None
        self.dashboard_skill: DashboardSkill | None = None

    @property
    def services(self):
        return {
            "agent_core": self.agent_core,
            "fetch": self.fetch_service,
            "skills": self._skills,
            "scheduler": self.scheduler,
            "dashboard": self.dashboard_skill,
            "reset_telegram_sessions": self.reset_telegram_sessions,
        }

    def init_claude(self):
        """Initialize Claude client."""
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        # Disable SDK-level retries so we can apply a shared, cross-call limiter.
        self.claude = anthropic.Anthropic(api_key=api_key, max_retries=0)
        logger.info("Claude client initialised (model: %s)", CLAUDE_MODEL)
        return self

    def _extract_retry_after_seconds(self, exc: Exception):
        """
        Best-effort extraction of retry delay from Anthropic/HTTPX exceptions.
        Handles common shapes without depending on SDK internals.
        """
        response = getattr(exc, "response", None)
        if response is None:
            return None
        status_code = getattr(response, "status_code", None)
        if status_code != 429:
            return None
        headers = getattr(response, "headers", None) or {}

        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after is not None:
            try:
                return float(retry_after)
            except Exception:
                return None

        # Some APIs return a unix timestamp reset. If present, convert to seconds.
        reset = (
            headers.get("x-ratelimit-reset")
            or headers.get("X-RateLimit-Reset")
            or headers.get("anthropic-ratelimit-reset")
            or headers.get("Anthropic-RateLimit-Reset")
        )
        if reset is not None:
            try:
                reset_ts = float(reset)
                now = time.time()
                return max(0.0, reset_ts - now)
            except Exception:
                return None

        return None

    def _sleep_for_anthropic_throttle(self):
        now = time.time()
        # Burst control: ensure a minimum interval between calls.
        since_last = now - self._anthropic_last_call_ts
        if since_last < ANTHROPIC_MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(ANTHROPIC_MIN_REQUEST_INTERVAL_SECONDS - since_last)
            now = time.time()
        # Shared cooldown: if we've been told to wait until a certain time, respect it.
        if now < self._anthropic_next_allowed_ts:
            time.sleep(self._anthropic_next_allowed_ts - now)

    def _claude_messages_create(self, *, model: str, max_tokens: int, system: str, tools, messages):
        """
        Wrapper around Anthropic messages.create with shared throttling and retries.
        This avoids immediate follow-on calls after a successful retry window reset.
        """
        attempt = 0
        backoff = ANTHROPIC_BACKOFF_INITIAL_SECONDS
        while True:
            self._sleep_for_anthropic_throttle()
            self._anthropic_last_call_ts = time.time()
            try:
                return self.claude.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    tools=tools,
                    messages=messages
                )
            except Exception as e:
                retry_after = self._extract_retry_after_seconds(e)
                if retry_after is not None:
                    # 429: the API told us how long to wait.  Add a small cushion.
                    delay = max(0.0, retry_after) + 0.25
                    self._anthropic_next_allowed_ts = max(self._anthropic_next_allowed_ts, time.time() + delay)
                    logger.info("Anthropic 429 — retrying in %.3f seconds", delay)
                else:
                    # 529 Overloaded or other transient: exponential backoff.
                    # For 529 specifically, bump the floor on the very first attempt —
                    # server overload clears in seconds-to-minutes, not milliseconds,
                    # so starting at 1 s wastes early retries.
                    status_code = getattr(getattr(e, "response", None), "status_code", None)
                    if status_code == 529 and backoff == ANTHROPIC_BACKOFF_INITIAL_SECONDS:
                        backoff = ANTHROPIC_OVERLOAD_BACKOFF_INITIAL_SECONDS
                    delay = min(backoff, ANTHROPIC_BACKOFF_MAX_SECONDS)
                    self._anthropic_next_allowed_ts = max(self._anthropic_next_allowed_ts, time.time() + delay)
                    if status_code == 529:
                        logger.info("Anthropic API overloaded (529) — retrying in %.3f seconds", delay)
                    else:
                        logger.info("Anthropic request failed — retrying in %.3f seconds (%s)", delay, type(e).__name__)
                    backoff = min(backoff * 2.0, ANTHROPIC_BACKOFF_MAX_SECONDS)

                attempt += 1
                if attempt > ANTHROPIC_MAX_RETRIES:
                    raise

    def init_agent_core(self):
        """Initialize the agent-core configuration repo."""
        self.agent_core = AgentCore()
        self.agent_core.init()
        return self

    def init_skills(self):
        """Initialize skills, wiring in required services."""
        self._skills["vietnamese_study"] = VietnameseStudySkill(
            fetch_service=self.fetch_service,
        )
        self._skills["vietnamese_vocab"] = VietnameseVocabSkill(
            agent_core=self.agent_core,
        )
        self._skills["update_vietnamese_dashboard"] = VietnameseDashboardSkill(
            dashboard_skill=self.dashboard_skill,
        )
        self._skills["vietnamese_progress"] = VietnameseProgressSkill(
            agent_core=self.agent_core,
        )
        logger.info("Skills initialised: %s", list(self._skills.keys()))
        return self

    def init_scheduler(self):
        """Initialize the task scheduler, loading (or seeding) persisted tasks from agent-core."""
        self.scheduler = SchedulerService(self.agent_core, self._skills)
        self.scheduler.load_tasks()
        logger.info("Scheduler initialised with %d task(s)", len(self.scheduler.list_tasks()))
        return self

    def init_dashboard(self):
        """Initialize the dashboard skill (does not clone repo yet — lazy on first update)."""
        self.dashboard_skill = DashboardSkill(
            agent_core=self.agent_core,
        )
        logger.info("Dashboard skill initialised")
        return self

    def execute_scheduled_task(self, task: dict) -> str:
        """
        Execute a scheduled task.
        - skill tasks: call the Python skill directly (no Claude API call)
        - natural_language tasks: call Claude with the full system prompt
        """
        if task["instruction_type"] == "skill":
            skill = self._skills.get(task["instruction"])
            if not skill:
                return f"Unknown skill: {task['instruction']}"
            result = skill.run()
            return json.dumps(result)
        else:
            system_prompt = load_system_prompt()
            messages = [{"role": "user", "content": task["instruction"]}]
            return self._run_claude(messages, system_prompt)

    def init_telegram(self):
        """Initialize Telegram service if a bot token is configured."""
        if not TELEGRAM_BOT_TOKEN:
            logger.info("No TELEGRAM_BOT_TOKEN configured — Telegram disabled")
            return self
        self._telegram_sessions = self._load_telegram_sessions()
        self.telegram_service = TelegramService(TELEGRAM_BOT_TOKEN)
        self.telegram_service.skip_pending()
        logger.info("Telegram service initialised")
        return self

    def _load_telegram_sessions(self) -> dict:
        """Load persisted Telegram session histories from agent-core."""
        sessions_path = AGENT_CORE_DIR / "telegram_sessions.json"
        if not sessions_path.exists():
            return {}
        try:
            data = json.loads(sessions_path.read_text())
            # JSON keys are always strings; convert back to int chat IDs
            return {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.warning("Could not load Telegram sessions (%s) — starting fresh", e)
            return {}

    def _save_telegram_sessions(self):
        """Persist Telegram session histories to agent-core, committing and pushing."""
        result = self.agent_core.upsert_file(
            "telegram_sessions.json",
            json.dumps(self._telegram_sessions, indent=2),
            "Update Telegram session history",
        )
        if not result.get("success"):
            logger.error("Failed to save Telegram sessions: %s", result.get("error"))

    def _run_claude(self, messages: list, system_prompt: str) -> str:
        """
        Core Claude tool-use loop. Runs until Claude stops requesting tools,
        then returns the final text response.
        """
        messages = list(messages)  # own the defensive copy; callers' lists are not mutated
        try:
            response = self._claude_messages_create(
                model=CLAUDE_MODEL,
                max_tokens=16384,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )

            while response.stop_reason == "tool_use":
                tool_calls = [block for block in response.content if block.type == "tool_use"]
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for tool_call in tool_calls:
                    result = handle_tool_call(tool_call.name, tool_call.input, self.services)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": result
                    })

                messages.append({"role": "user", "content": tool_results})

                response = self._claude_messages_create(
                    model=CLAUDE_MODEL,
                    max_tokens=16384,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages,
                )

            text_blocks = [block.text for block in response.content if hasattr(block, 'text')]
            return "\n".join(text_blocks)

        except Exception as e:
            logger.error("Claude API error: %s", e)
            return f"Something went wrong on my end. Please try again.\n\n(Error: {str(e)[:100]})"

    def process_telegram_update(self, update: dict) -> str:
        """
        Process a Telegram message using Claude with tool support.

        Maintains an in-memory conversation history per chat ID so the agent
        has multi-turn context within a session. History resets on restart
        (but is also persisted to agent-core, so a redeploy recovers it).
        """
        message = update['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')

        user = message.get('from', {})
        sender_name = user.get('first_name', 'User')
        if user.get('last_name'):
            sender_name += f" {user['last_name']}"

        self.agent_core.pull_latest()
        system_prompt = load_system_prompt()

        # Get or create session history for this chat
        history = self._telegram_sessions.setdefault(chat_id, [])

        user_content = TELEGRAM_MESSAGE_TEMPLATE.format(
            sender_name=sender_name,
            text=text,
        )
        history.append({"role": "user", "content": user_content})

        response = self._run_claude(history, system_prompt)

        history.append({"role": "assistant", "content": response})
        self._trim_and_save_session(chat_id)
        return response

    def _record_scheduled_message(self, chat_id: int, task: dict, response: str):
        """
        Append a scheduled task's outgoing message to the chat's session history,
        so that a follow-up reply (e.g. a translation) has the exercise in context.
        A synthetic user turn keeps role alternation valid.
        """
        history = self._telegram_sessions.setdefault(chat_id, [])
        history.append({
            "role": "user",
            "content": f"(scheduled task: {task['name']}) {task['instruction']}",
        })
        history.append({"role": "assistant", "content": response})
        self._trim_and_save_session(chat_id)

    def _trim_and_save_session(self, chat_id: int):
        history = self._telegram_sessions.get(chat_id, [])
        if len(history) > MAX_TELEGRAM_HISTORY:
            self._telegram_sessions[chat_id] = history[-MAX_TELEGRAM_HISTORY:]
        self._save_telegram_sessions()

    def reset_telegram_sessions(self) -> dict:
        """
        Clear all in-memory Telegram conversation history and persist the empty
        state immediately. Clearing the file alone isn't enough while the process
        is running — the next message would just re-save the still-populated
        in-memory history straight back over it. This clears both, in the same
        request that triggered it, so the reset actually takes effect right away
        with no restart required.
        """
        self._telegram_sessions.clear()
        self._save_telegram_sessions()
        return {"success": True, "message": "Telegram conversation memory cleared."}


def send_telegram_response(telegram_service: TelegramService, chat_id: int, response: str):
    """
    Send a Claude response to Telegram, splitting it into multiple messages
    wherever the model marked a break (see TELEGRAM_PART_SEPARATOR) — e.g. an
    exercise paragraph and its glossary arrive as two separate messages
    instead of one long block. The full, unsplit response is still what gets
    recorded in session history — only delivery is split.
    """
    for part in split_message_parts(response):
        telegram_service.send_message(chat_id, part)


def run_agent():
    """Main agent loop."""
    logger.info("=" * 50)
    logger.info("Vietnamese Learning Agent starting up")
    logger.info("=" * 50)

    agent = Agent()
    agent.init_claude()
    agent.init_agent_core()
    agent.init_dashboard()
    agent.init_skills()
    agent.init_scheduler()
    agent.init_telegram()

    logger.info("Polling interval: %ss | Authorized Telegram users: %s",
                POLL_INTERVAL_SECONDS, TELEGRAM_AUTHORIZED_IDS or "NONE (not configured)")
    logger.info("Agent is running")

    while True:
        try:
            # --- Telegram ---
            if agent.telegram_service:
                logger.debug("Checking for Telegram messages...")
                updates = agent.telegram_service.get_updates()

                if updates:
                    logger.info("Found %d Telegram update(s)", len(updates))

                for update in updates:
                    if 'message' not in update:
                        continue

                    message = update['message']
                    if 'text' not in message:
                        continue

                    user_id = message.get('from', {}).get('id')
                    chat_id = message['chat']['id']

                    if not is_authorized_telegram_user(user_id):
                        logger.warning("Skipping unauthorized Telegram user: %s", user_id)
                        continue

                    logger.info("Processing Telegram message from user %s...", user_id)
                    response = agent.process_telegram_update(update)

                    send_telegram_response(agent.telegram_service, chat_id, response)
                    logger.info("Telegram reply sent")

            # --- Scheduler ---
            if agent.scheduler:
                due_tasks = agent.scheduler.get_due_tasks()
                completed_any = False
                for task in due_tasks:
                    logger.info("Running scheduled task: %s (id=%s)", task["name"], task["id"])
                    try:
                        result = agent.execute_scheduled_task(task)
                        agent.scheduler.mark_task_complete(task["id"])
                        completed_any = True
                        # Only natural-language tasks are ever chat-worthy — skill tasks
                        # (e.g. dashboard refresh) return raw data, not something to send.
                        # Within natural-language tasks, notify defaults to True but can be
                        # set False for tasks meant to run silently (e.g. the nightly review).
                        should_notify = (
                            task["instruction_type"] == "natural_language"
                            and task.get("notify", True)
                        )
                        if (
                            should_notify
                            and TELEGRAM_AUTHORIZED_IDS
                            and agent.telegram_service
                        ):
                            # For direct (private) Telegram chats, chat_id == user_id,
                            # so the first authorized ID doubles as the notification target.
                            owner_chat_id = TELEGRAM_AUTHORIZED_IDS[0]
                            send_telegram_response(agent.telegram_service, owner_chat_id, result)
                            agent._record_scheduled_message(owner_chat_id, task, result)
                        logger.info("Scheduled task done: %s", task["name"])
                    except Exception as task_err:
                        logger.error(
                            "Scheduled task '%s' failed: %s", task["name"], task_err, exc_info=True
                        )
                # Push dashboard once after all due tasks have run, not once per task
                if completed_any:
                    agent.dashboard_skill.update()

            time.sleep(POLL_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            logger.info("Agent stopped by user")
            break
        except Exception as e:
            logger.error("Error in main loop: %s", e, exc_info=True)
            logger.info("Retrying in %ss...", POLL_INTERVAL_SECONDS)
            time.sleep(POLL_INTERVAL_SECONDS)


def main():
    run_agent()


if __name__ == '__main__':
    main()
