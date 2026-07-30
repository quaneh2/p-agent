# P. Agent — Vietnamese Learning Agent

An always-on AI agent, entirely dedicated to helping Hugh study Vietnamese and get from B1 to B2. It talks over Telegram as Minh — a guy in his mid-30s from Sài Gòn — sends proactive translation exercises and spontaneous chats on a randomised schedule, quizzes vocabulary, tracks a structured model of Hugh's progress and calibrates difficulty against it, and logs every word and session through structured tools rather than ad-hoc edits — so progress is never lost or malformed.

## What it does

- Polls a Telegram bot for messages from an authorised user and responds using Claude as its reasoning engine
- Proactively sends a Vietnamese translation exercise daily, and up to two spontaneous chats a day spread anywhere from ~7am to ~11pm Irish time — capped at two so it never floods, randomised so it's not trivially predictable
- Tracks a structured vocabulary list (`vietnamese_vocab.json`) with spaced-repetition review, written to exclusively through code tools — never free-form file edits
- Tracks a structured progress model (`vietnamese_progress.json`): estimated level, a 1–5 difficulty tier, strengths/struggles, and an audit trail of how that assessment has changed over time — exercises are calibrated against it instead of a fixed difficulty
- Runs a nightly review that reads recent sessions and deliberately updates that progress model (not reactively after every single exercise)
- Runs a weekly pacing review that separately tunes *how often* it reaches out, based on real engagement
- Logs every study session (exercise, conversation, quiz, or ad-hoc word lookup) to `exercises/`
- Publishes a live Vietnamese progress dashboard (streaks, heatmap, session history) to GitHub Pages
- Is aware of the current time in Ireland (computed fresh on every call) so it can judge whether a message is landing at a considerate hour
- Maintains persistent memory and a self-tunable identity/schedule
- Runs scheduled tasks (cron or one-time, with optional random jitter) via a lightweight scheduler

## Project structure

```
agent.py                  # Main agent loop and Agent class
config.py                 # Environment config and constants
pyproject.toml            # Project metadata and dependencies

utils/
  auth.py                 # is_authorized_telegram_user()
  telegram_formatting.py  # split_message_parts() — breaks one reply into multiple Telegram messages

prompts/
  system.py               # Composes system prompt from agent-core files + Vietnamese study workflow + live Ireland time
  telegram.py              # Telegram message template

services/
  telegram_service.py     # Telegram Bot API: long-polling, sending messages
  agent_core.py            # Agent-core repo management (identity, soul, memory, vocab, sessions, progress)
  git_repo.py              # Base class for git repository operations
  scheduler.py              # Task scheduling: persist, query due tasks, seed defaults, jitter, cron via croniter
  fetch_service.py          # HTTP fetch + HTML-to-text cleanup for article content

skills/
  vietnamese_study.py       # Fetches Vietnamese news section pages for exercise topic inspiration
  vietnamese_vocab.py       # Vocab spaced-repetition + atomic session/vocab save
  vietnamese_progress.py    # Structured progress snapshot: level, difficulty tier, strengths/struggles, history
  vietnamese_dashboard.py   # Vietnamese progress page: generate HTML, push to *.github.io repo
  dashboard.py               # Scheduled-task status page: generate HTML, push to *.github.io repo

tools/
  definitions.py            # Claude tool schemas
  handlers.py                # Tool dispatch table and handler functions

tests/
  test_scheduler.py            # Unit tests for SchedulerService (seeding, jitter, notify)
  test_vietnamese_progress.py  # Unit tests for VietnameseProgressSkill
  test_telegram_formatting.py  # Unit tests for markdown -> Telegram HTML conversion
  test_telegram_split.py       # Unit tests for split_message_parts()

docs/                       # Technical write-ups for significant features

agent-core/                  # Local clone of the agent's configuration repo
  IDENTITY.md                # Character and working style (editable by agent)
  SOUL.md                    # Values and principles (editable by agent)
  MEMORY.md                  # Persistent memory across conversations
  vietnamese_vocab.json      # Structured vocabulary list
  vietnamese_progress.json   # Structured progress snapshot (level, tier, strengths/struggles, history)
  exercises/                 # One JSON record per study session
  telegram_sessions.json     # Persisted Telegram conversation history
  SCHEDULES.json             # Persisted task schedule
```

## Agent configuration

The agent's behaviour is driven by files in its `agent-core` repository:

- **IDENTITY.md** — character, tone, and working style
- **SOUL.md** — values and principles that guide decisions
- **MEMORY.md** — episodic, semantic, and procedural memory written by the agent after each conversation
- **vietnamese_vocab.json** / **exercises/** — Hugh's structured learning data, written only via the `save_vietnamese_session` tool
- **vietnamese_progress.json** — the agent's structured assessment of Hugh's level and difficulty calibration, written only via the `update_vietnamese_progress` tool

These are loaded and composed into the system prompt on every message — live Telegram chat and scheduled tasks alike, since every call this agent makes is Vietnamese-study-relevant. The system prompt also includes the current time in Ireland, computed fresh on every call (not cached), so tone and timing judgement stay accurate. The agent can update its identity/soul/memory via tools, with changes committed and pushed to GitHub immediately.

## Tools available to the agent

**Vietnamese study**
- `fetch_vietnamese_articles` — pull headlines from VNExpress/Tuổi Trẻ/Thanh Niên for exercise topic inspiration
- `fetch_url` — fetch a specific article Hugh links
- `prepare_vietnamese_chat` / `prepare_vietnamese_quiz` — load vocab due for spaced-repetition review
- `get_vietnamese_progress` — load the current level/tier/strengths/struggles snapshot, used to calibrate exercises
- `update_vietnamese_progress` — the single reliable way to change the progress snapshot; auto-appends a history entry whenever level or tier actually changes
- `save_vietnamese_session` — the single, reliable code-based way to log a session and update the vocab list (exercise, conversation, quiz, or a quick "what does X mean?" lookup); writes structured JSON, never hand-edited

**Scheduling**
- `add_scheduled_task` — schedule a task on a cron expression or a specific future datetime; supports `jitter_minutes` (randomise timing) and `notify` (run silently)
- `remove_scheduled_task` — cancel a scheduled task by ID
- `list_scheduled_tasks` — list all tasks (active, paused, completed)

**Self-configuration**
- `list_agent_core`, `read_agent_core` — inspect configuration/data files
- `create_agent_core`, `update_agent_core` — modify identity, soul, or other config files
- `delete_agent_core_file`, `delete_agent_core_folder` — permanently remove a file/folder from agent-core (e.g. clearing exercises/ history); irreversible
- `update_memory` — update persistent memory
- `reset_telegram_memory` — clear Telegram conversation history immediately, both the live in-memory session and the persisted file (overwriting the file alone isn't enough while the process is running — the still-populated in-memory session would just get saved straight back over it on the next message)

## Proactive schedule

A fresh deployment seeds a sensible default schedule automatically (see `services/scheduler.py::DEFAULT_TASKS`):

| Task | Cadence | What happens |
|---|---|---|
| Vietnamese translation exercise | ~Daily 08:00 UTC, ±90 min jitter | Sends a fresh Vietnamese paragraph, calibrated to the current difficulty tier, to translate; corrected when Hugh replies |
| Vietnamese spontaneous chat (day) | ~10:00 UTC anchor, ±4h jitter (06:00-14:00 UTC) | An unprompted, genuine-sounding Vietnamese message — Minh has something to ask or share, not a "practice session" |
| Vietnamese spontaneous chat (evening) | ~18:00 UTC anchor, ±4h jitter (14:00-22:00 UTC) | Same as above, covering the other half of the day |
| Vietnamese nightly review | Daily 02:00 UTC (silent) | Reviews the last 1-3 days of activity and, only when there's a genuine multi-session signal, updates the progress snapshot (level, difficulty tier, strengths/struggles) |
| Vietnamese dashboard refresh | Daily 23:00 UTC (silent) | Regenerates the progress page |
| Vietnamese pacing review | Weekly, Sunday 12:00 UTC | Reviews the past week's engagement (replies, accuracy, dropped sessions) and adjusts the exercise/chat cadence and jitter to match Hugh's actual pace |

The two spontaneous-chat tasks' windows don't overlap, so together they cover roughly 7am-11pm Irish time (drifting ±1h with the season) without ever both landing close together — and two is a hard ceiling, never a third recurring chat task. If twice a day turns out to be too much, the fix is the pacing review removing one of the two tasks, not just shrinking both. The daily exercise cadence above is a deliberate starting point too, not a fixed target — the pacing review tunes *how often* over time based on real engagement, while the nightly review separately tunes *what level* to teach at. The `jitter_minutes` field on a recurring task randomises each computed run time within a window (implemented in the scheduler itself, not left to the model to remember) so proactive messages don't land at the exact same minute every day. The agent can also adjust cadence, timing, or content immediately whenever Hugh asks directly, e.g. "send exercises less often" or "switch check-ins to mornings."

## Environment variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GITHUB_TOKEN` | GitHub personal access token for the agent's account (used to read/write its own `agent-core` and dashboard repos) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (Telegram disabled if unset) |
| `TELEGRAM_AUTHORIZED_IDS` | JSON array of Telegram user IDs allowed to contact the agent. The first ID also receives proactive/scheduled messages. |

## Deployment

The agent is deployed on [Render](https://render.com) as a background worker. On startup it:

1. Initialises the Claude client
2. Clones (or pulls) the agent-core repo, seeding default identity/soul/memory if needed
3. Initialises the dashboard and Vietnamese study/vocab/progress skills
4. Loads the task schedule from `agent-core/SCHEDULES.json`, seeding a default schedule if missing
5. Initialises Telegram (if `TELEGRAM_BOT_TOKEN` is set), skipping any backlogged messages
6. Begins polling Telegram and the task schedule every 10 seconds

## Local development

```bash
python -m venv venv
source venv/bin/activate
pip install ".[dev]"

# Run the agent
python agent.py

# Run tests
pytest
```
