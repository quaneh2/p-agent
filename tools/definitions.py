"""
Tool definitions
"""

TOOLS = [
    # --- Fetch tool ---
    {
        "name": "fetch_url",
        "description": (
            "Fetch the content of a URL and return it as clean plain text. "
            "Use this to read a specific article the user shares a link to (e.g. "
            "'translate this: <url>'), or any other public web page. "
            "HTML tags and boilerplate are stripped; the result is readable prose. "
            "Content is capped at 50,000 characters to protect context window size."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch, e.g. 'https://vnexpress.net/...'"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "fetch_vietnamese_articles",
        "description": (
            "Fetch recent article listings from Vietnamese news sites (VNExpress, Tuổi Trẻ, "
            "Thanh Niên) for topic and theme inspiration for a Vietnamese study exercise. "
            "Returns best-effort plain-text content from 1–3 section pages. "
            "Fetching is resilient — partial or sparse results are normal and still useful. "
            "Use the returned content for INSPIRATION ONLY: read the headlines/snippets to "
            "understand what topics are current, then WRITE YOUR OWN Vietnamese paragraph "
            "at the correct B1→B2 level. Do not copy-paste from the fetched content. "
            "See the Vietnamese Language Study section of your instructions for the full "
            "exercise workflow, including how to incorporate vocab review words. "
            "Use the topic parameter to match the user's interests."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": ["current_affairs", "nature", "food", "travel"],
                    "description": (
                        "Optional topic filter. "
                        "current_affairs = world/domestic news (thế giới / thời sự), "
                        "nature = science and environment (khoa học), "
                        "food = cuisine and recipes (ẩm thực), "
                        "travel = travel and tourism (du lịch). "
                        "Omit to fetch from all sections."
                    )
                }
            },
            "required": []
        }
    },
    {
        "name": "prepare_vietnamese_chat",
        "description": (
            "Load vocab entries due for spaced-repetition review. "
            "Call this at the start of any Vietnamese study session before choosing a topic. "
            "Returns due_for_review: up to 3 vocab entries sorted by review priority "
            "(never-practiced first, then oldest last_practiced). "
            "Use the returned words to choose a topic where they arise naturally — "
            "do NOT pick a topic first and then force the words in."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "prepare_vietnamese_quiz",
        "description": (
            "Load vocab entries due for an Anki-style quiz session. "
            "Returns up to max_words due entries (default 10) — more than prepare_vietnamese_chat "
            "which caps at 3. Call once at the start of a quiz session. "
            "Returns due_for_review sorted by review priority (never-practiced first, "
            "then oldest last_practiced)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "max_words": {
                    "type": "integer",
                    "description": "Maximum number of words to include in the quiz. Default 10.",
                }
            },
            "required": []
        }
    },
    {
        "name": "get_vietnamese_progress",
        "description": (
            "Load Hugh's current Vietnamese progress snapshot: target_level, estimated_level, "
            "difficulty_tier (1-5, see the Difficulty Tiers guide in your instructions), "
            "journey_started, strengths, struggles, notes, and an audit-trail history of past "
            "changes. Call this at the start of any translation exercise or conversation session "
            "(alongside prepare_vietnamese_chat) to calibrate difficulty and tone. Cheap — reads "
            "a single small file. Self-seeds sensible defaults on first-ever call."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "update_vietnamese_progress",
        "description": (
            "Update Hugh's Vietnamese progress snapshot. Only the fields you pass are changed. "
            "This is a deliberate, occasional action — typically once during the nightly review, "
            "not after every exercise — since the difficulty tier should reflect a genuine trend "
            "across several sessions, not react to one data point. Whenever you pass "
            "estimated_level or difficulty_tier and the value actually changes, a history entry "
            "is appended automatically — always include reason in that case so the change is "
            "explainable later. The single reliable way to update progress; never hand-edit "
            "vietnamese_progress.json via create_agent_core/update_agent_core."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "estimated_level": {
                    "type": "string",
                    "description": "e.g. 'B1 (low)', 'B1 (solid)', 'B1→B2 transition', 'B2 (emerging)', 'B2 (confident)'."
                },
                "difficulty_tier": {
                    "type": "integer",
                    "description": "1-5. See the Difficulty Tiers guide in your instructions for what each tier means."
                },
                "strengths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Replaces the current strengths list entirely — read the existing snapshot first if you want to keep prior entries."
                },
                "struggles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Replaces the current struggles list entirely — read the existing snapshot first if you want to keep prior entries."
                },
                "notes": {
                    "type": "string",
                    "description": "Free-text context for how Hugh is doing and how to teach him right now. Replaces the current notes entirely."
                },
                "reason": {
                    "type": "string",
                    "description": "Why this update — required (in spirit) whenever estimated_level or difficulty_tier changes; recorded in history."
                }
            },
            "required": []
        }
    },
    {
        "name": "save_vietnamese_session",
        "description": (
            "Atomically save a completed Vietnamese study session and update the vocab list. "
            "This is the ONLY reliable way to record a session or add/update vocabulary — "
            "it writes directly to the structured vietnamese_vocab.json and exercises/ data "
            "files via code, so entries are never lost, malformed, or duplicated. "
            "Handles translation exercises (mode='exercise'), conversation sessions "
            "(mode='conversation'), Anki-style quiz sessions (mode='quiz'), and ad-hoc "
            "vocabulary lookups (mode='lookup', for when the user just asks what a word means). "
            "Must be called at the end of every study session, and immediately after every "
            "ad-hoc 'what does X mean?' question. "
            "Saves the session record to exercises/ in agent-core, increments practice_count "
            "and sets last_practiced for each word in words_practiced, and appends any new_entries "
            "to the vocab list (duplicates are silently skipped)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_record": {
                    "type": "object",
                    "description": (
                        "Full session JSON. Required fields: date (YYYY-MM-DD), mode ('exercise', "
                        "'conversation', 'quiz', or 'lookup'), topic. "
                        "For exercise mode also include: paragraph_vi, vocab_reviewed, "
                        "vocab_new_introduced, user_translation, correction_notes, "
                        "vocab_added_to_list, inspiration_source. "
                        "For conversation mode also include: conversation_summary, vocab_reviewed, "
                        "vocab_new_introduced, correction_notes, vocab_added_to_list, inspiration_source. "
                        "For quiz mode also include: cards_presented, correct_count, incorrect_count, "
                        "vocab_reviewed, correction_notes, vocab_added_to_list. "
                        "For lookup mode, topic should be 'direct lookup' — no other fields required."
                    )
                },
                "words_practiced": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Vietnamese words (strings) from the vocab list that were genuinely reviewed "
                        "during this session. practice_count will be incremented and last_practiced "
                        "set to today for each."
                    )
                },
                "new_entries": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": (
                        "New vocab entries to add to the list. Each must follow the vocab entry schema: "
                        "vietnamese, english, word_type, source, sample_sentences (3 vi/en pairs). "
                        "Duplicates (same vietnamese + same English meaning) are silently skipped."
                    )
                }
            },
            "required": ["session_record"]
        }
    },
    # --- Scheduling tools ---
    {
        "name": "add_scheduled_task",
        "description": (
            "Schedule a task to run once at a future datetime or on a recurring cron schedule. "
            "Use instruction_type='skill' to run a registered skill (e.g. 'update_vietnamese_dashboard') "
            "directly — no extra Claude credits are used at runtime. "
            "Use instruction_type='natural_language' to run a text instruction via Claude when the task "
            "fires — the instruction's final response text is sent to Hugh directly via Telegram, so "
            "this is how proactive articles, exercises, reminders, and check-in chats get delivered. "
            "cron uses standard 5-field UTC syntax, e.g. '0 9 * * 1-5' for weekday 09:00 UTC. "
            "run_at uses ISO 8601 UTC, e.g. '2027-04-13T09:00:00Z'. "
            "The dashboard at https://stevens-j-54.github.io is auto-updated after adding."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Short human-readable task name, e.g. 'Friday translation exercise'."
                },
                "type": {
                    "type": "string",
                    "enum": ["recurring", "one_time"],
                    "description": "'recurring' fires on a cron schedule; 'one_time' fires at a specific datetime."
                },
                "cron": {
                    "type": "string",
                    "description": (
                        "Required for recurring tasks. Standard 5-field cron in UTC. "
                        "Examples: '0 8 * * 1,3,5' (Mon/Wed/Fri 08:00), '0 17 * * 2,6' (Tue/Sat 17:00)."
                    )
                },
                "run_at": {
                    "type": "string",
                    "description": (
                        "Required for one_time tasks. ISO 8601 UTC datetime. "
                        "Example: '2027-04-13T09:00:00Z'."
                    )
                },
                "instruction": {
                    "type": "string",
                    "description": (
                        "What to do when the task fires. "
                        "For instruction_type='skill': the skill name, e.g. 'update_vietnamese_dashboard'. "
                        "For instruction_type='natural_language': a plain-English instruction."
                    )
                },
                "instruction_type": {
                    "type": "string",
                    "enum": ["skill", "natural_language"],
                    "description": (
                        "'skill' calls a Python skill directly (zero extra credits, always silent — "
                        "use for background maintenance like dashboard refreshes). "
                        "'natural_language' runs the instruction through Claude; the result is sent "
                        "to Hugh via Telegram unless notify=false."
                    )
                },
                "jitter_minutes": {
                    "type": "integer",
                    "description": (
                        "Recurring tasks only. Randomises each computed next_run by up to +/- this "
                        "many minutes, so e.g. a 'daily 08:00' task actually lands anywhere in "
                        "06:30-09:30 — not the exact same time every day. Omit or 0 for exact timing "
                        "(use that for anything precision matters for, like the nightly review)."
                    )
                },
                "notify": {
                    "type": "boolean",
                    "description": (
                        "natural_language tasks only, default true. Set false for a task that should "
                        "run silently in the background — e.g. one that only updates internal files "
                        "(progress, memory) rather than saying something to Hugh. Has no effect on "
                        "instruction_type='skill' tasks, which are always silent."
                    )
                }
            },
            "required": ["name", "type", "instruction", "instruction_type"]
        }
    },
    {
        "name": "remove_scheduled_task",
        "description": (
            "Remove a scheduled task by its ID. "
            "Use list_scheduled_tasks first to find the task ID. "
            "The dashboard is auto-updated after removal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The UUID of the task to remove."
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "name": "list_scheduled_tasks",
        "description": "List all scheduled tasks, including active, paused, and recently completed ones.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    # --- Agent-core tools ---
    {
        "name": "list_agent_core",
        "description": "List all files in your agent-core configuration repository (identity, memory, vocab list, session history, schedule).",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "read_agent_core",
        "description": "Read the contents of a file in your agent-core configuration repository, e.g. 'IDENTITY.md' or 'vietnamese_vocab.json'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read, e.g., 'IDENTITY.md'"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "create_agent_core",
        "description": "Create a new file in your agent-core configuration repository. Changes are committed and pushed immediately.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path for the new file, e.g., 'preferences.md'"
                },
                "content": {
                    "type": "string",
                    "description": "The content for the new file"
                },
                "commit_message": {
                    "type": "string",
                    "description": "A clear commit message describing what this file is for"
                }
            },
            "required": ["file_path", "content", "commit_message"]
        }
    },
    {
        "name": "update_agent_core",
        "description": "Update an existing file in your agent-core configuration repository. Always read the current file first before updating.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to update, e.g., 'IDENTITY.md'"
                },
                "content": {
                    "type": "string",
                    "description": "The complete new content for the file"
                },
                "commit_message": {
                    "type": "string",
                    "description": "A clear commit message describing what changed and why"
                }
            },
            "required": ["file_path", "content", "commit_message"]
        }
    },
    {
        "name": "update_memory",
        "description": "Update your persistent memory (MEMORY.md). Always call this at the end of every conversation unless the message was purely trivial. Memory has three sections: Episodic (one-line log per message: [date] task — outcome, keep last 20), Semantic (persistent facts about Hugh — his level, interests, recurring struggles, preferences — the most important section), Procedural (what approaches work or fail: 'When asked to X, do Y'). Read the current MEMORY.md first, then write the full updated content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The full updated content for MEMORY.md."
                },
                "commit_message": {
                    "type": "string",
                    "description": "A brief commit message describing what was added or changed."
                }
            },
            "required": ["content", "commit_message"]
        }
    },
    {
        "name": "delete_agent_core_file",
        "description": (
            "Permanently delete a single file from your agent-core configuration "
            "repository. Irreversible — think before calling. Use this rather than "
            "overwriting with empty content when a file shouldn't exist at all anymore."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to delete, e.g. 'exercises/2026-07-30T0800.json'"
                },
                "commit_message": {
                    "type": "string",
                    "description": "A clear commit message describing what was deleted and why"
                }
            },
            "required": ["file_path", "commit_message"]
        }
    },
    {
        "name": "delete_agent_core_folder",
        "description": (
            "Permanently delete a folder and everything under it from your agent-core "
            "configuration repository. Irreversible — think before calling. Used for "
            "e.g. clearing all of exercises/ when Hugh asks to wipe his session history."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_path": {
                    "type": "string",
                    "description": "Path to the folder to delete, e.g. 'exercises'"
                },
                "commit_message": {
                    "type": "string",
                    "description": "A clear commit message describing what was deleted and why"
                }
            },
            "required": ["folder_path", "commit_message"]
        }
    },
    {
        "name": "reset_telegram_memory",
        "description": (
            "Clear all Telegram conversation history immediately — both the live "
            "in-memory session and the persisted telegram_sessions.json file. Use only "
            "when Hugh explicitly asks to forget past conversations or start fresh. "
            "Irreversible, and affects every authorized chat, not just the current one. "
            "Overwriting telegram_sessions.json yourself via update_agent_core is NOT "
            "sufficient while the process is running — the still-populated in-memory "
            "session would just get saved straight back over it on the next message. "
            "This tool clears both at once, so the reset actually sticks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]
