"""
Tool Handlers
"""

import json
import logging

logger = logging.getLogger(__name__)


# --- Fetch handler ---

def handle_fetch_url(fetch, url: str) -> str:
    logger.info("Fetching URL: %s", url)
    result = fetch.fetch_url(url=url)
    if not result.get("success"):
        logger.error("Fetch error: %s", result.get('error'))
    return json.dumps(result)


# --- Skills handlers ---

def handle_fetch_vietnamese_articles(skills, topic: str = None) -> str:
    logger.info("Fetching Vietnamese articles (topic=%s)", topic or "all")
    result = skills["vietnamese_study"].run(topic=topic)
    if not result.get("success"):
        logger.error("Vietnamese article fetch failed: %s", result.get('error'))
    return json.dumps(result)


def handle_prepare_vietnamese_chat(skills) -> str:
    logger.info("Preparing Vietnamese chat (loading vocab due for review)")
    result = skills["vietnamese_vocab"].prepare_chat()
    if not result.get("success"):
        logger.error("Vietnamese chat prep failed: %s", result.get('error'))
    return json.dumps(result)


def handle_prepare_vietnamese_quiz(skills, max_words: int = 10) -> str:
    logger.info("Preparing Vietnamese quiz (max_words=%d)", max_words)
    result = skills["vietnamese_vocab"].prepare_quiz(max_words=max_words)
    if not result.get("success"):
        logger.error("Vietnamese quiz prep failed: %s", result.get('error'))
    return json.dumps(result)


def handle_get_vietnamese_progress(skills) -> str:
    logger.info("Loading Vietnamese progress snapshot")
    result = skills["vietnamese_progress"].get_snapshot()
    if not result.get("success"):
        logger.error("Vietnamese progress load failed: %s", result.get('error'))
    return json.dumps(result)


def handle_update_vietnamese_progress(skills, **kwargs) -> str:
    logger.info("Updating Vietnamese progress (reason=%s)", kwargs.get("reason", "?"))
    result = skills["vietnamese_progress"].update_snapshot(**kwargs)
    if not result.get("success"):
        logger.error("Vietnamese progress update failed: %s", result.get('error'))
    return json.dumps(result)


def handle_save_vietnamese_session(
    skills,
    session_record: dict,
    words_practiced: list,
    new_entries: list,
) -> str:
    logger.info("Saving Vietnamese session (mode=%s, topic=%s)",
                session_record.get("mode", "?"), session_record.get("topic", "?"))
    result = skills["vietnamese_vocab"].save_session(
        session_record=session_record,
        words_practiced=words_practiced,
        new_entries=new_entries,
    )
    if result.get("success"):
        vd = skills.get("update_vietnamese_dashboard")
        if vd:
            vd.update()
    else:
        logger.error("Vietnamese session save failed: %s", result.get('error'))
    return json.dumps(result)


# --- Scheduling handlers ---

def handle_add_scheduled_task(scheduler, dashboard, tool_input: dict) -> str:
    result = scheduler.add_task(tool_input)
    if result.get("success"):
        logger.info("Task added: %s — updating dashboard", result["task"]["name"])
        dashboard.update()
    else:
        logger.error("Failed to add task: %s", result.get("error"))
    return json.dumps(result)


def handle_remove_scheduled_task(scheduler, dashboard, task_id: str) -> str:
    result = scheduler.remove_task(task_id)
    if result.get("success"):
        logger.info("Task removed: %s — updating dashboard", task_id)
        dashboard.update()
    else:
        logger.error("Failed to remove task: %s", result.get("error"))
    return json.dumps(result)


def handle_list_scheduled_tasks(scheduler) -> str:
    tasks = scheduler.list_tasks()
    return json.dumps({"success": True, "tasks": tasks, "count": len(tasks)})


# --- Agent-core handlers ---

def handle_list_agent_core(agent_core) -> str:
    logger.info("Listing agent-core files")
    result = agent_core.list_files()
    return json.dumps(result)


def handle_read_agent_core(agent_core, file_path: str) -> str:
    logger.info("Reading agent-core file: %s", file_path)
    result = agent_core.read_file(file_path)
    return json.dumps(result)


def handle_create_agent_core(agent_core, file_path: str, content: str, commit_message: str) -> str:
    logger.info("Creating agent-core file: %s", file_path)
    result = agent_core.upsert_file(file_path=file_path, content=content, commit_message=commit_message)
    return json.dumps(result)


def handle_update_memory(agent_core, content: str, commit_message: str) -> str:
    logger.info("Updating memory: %s", commit_message)
    result = agent_core.upsert_file(file_path="MEMORY.md", content=content, commit_message=commit_message)
    return json.dumps(result)


def handle_update_agent_core(agent_core, file_path: str, content: str, commit_message: str) -> str:
    logger.info("Updating agent-core file: %s", file_path)
    result = agent_core.upsert_file(file_path=file_path, content=content, commit_message=commit_message)
    return json.dumps(result)


# --- Router ---

def handle_tool_call(tool_name: str, tool_input: dict, services: dict) -> str:
    """Route a tool call to its handler via dispatch table."""
    ac = services.get("agent_core")
    ft = services.get("fetch")
    sk = services.get("skills", {})
    sc = services.get("scheduler")
    db = services.get("dashboard")

    dispatch = {
        # Fetch
        "fetch_url":        lambda: handle_fetch_url(ft, tool_input["url"]),
        # Skills
        "fetch_vietnamese_articles": lambda: handle_fetch_vietnamese_articles(sk, tool_input.get("topic")),
        "prepare_vietnamese_chat": lambda: handle_prepare_vietnamese_chat(sk),
        "prepare_vietnamese_quiz": lambda: handle_prepare_vietnamese_quiz(sk, tool_input.get("max_words", 10)),
        "get_vietnamese_progress": lambda: handle_get_vietnamese_progress(sk),
        "update_vietnamese_progress": lambda: handle_update_vietnamese_progress(
            sk,
            estimated_level=tool_input.get("estimated_level"),
            difficulty_tier=tool_input.get("difficulty_tier"),
            strengths=tool_input.get("strengths"),
            struggles=tool_input.get("struggles"),
            notes=tool_input.get("notes"),
            reason=tool_input.get("reason"),
        ),
        "save_vietnamese_session": lambda: handle_save_vietnamese_session(
            sk,
            tool_input.get("session_record", {}),
            tool_input.get("words_practiced", []),
            tool_input.get("new_entries", []),
        ),
        # Scheduling
        "add_scheduled_task":    lambda: handle_add_scheduled_task(sc, db, tool_input),
        "remove_scheduled_task": lambda: handle_remove_scheduled_task(sc, db, tool_input["task_id"]),
        "list_scheduled_tasks":  lambda: handle_list_scheduled_tasks(sc),
        # Agent-core
        "list_agent_core":  lambda: handle_list_agent_core(ac),
        "read_agent_core":  lambda: handle_read_agent_core(ac, tool_input["file_path"]),
        "create_agent_core": lambda: handle_create_agent_core(ac, tool_input["file_path"], tool_input["content"], tool_input["commit_message"]),
        "update_memory":    lambda: handle_update_memory(ac, tool_input["content"], tool_input["commit_message"]),
        "update_agent_core": lambda: handle_update_agent_core(ac, tool_input["file_path"], tool_input["content"], tool_input["commit_message"]),
    }

    handler = dispatch.get(tool_name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    return handler()
