# P. Agent

An always-on AI agent with a persistent identity, memory, and the ability to administer its own GitHub repositories. The agent monitors a Gmail inbox and responds to emails using Claude as its reasoning engine.

## What it does

- Polls a Gmail inbox for emails from authorised senders
- Processes each email using Claude (Sonnet 4.6) with a full tool loop
- Replies in the original email thread
- Creates, edits, and manages files across multiple GitHub repositories
- Maintains persistent memory and a self-modifiable identity

## Project structure

```
agent.py                  # Main agent loop and EmailAgent class
config.py                 # Environment config and constants

prompts/
  system.py               # Composes system prompt from agent-core files
  email.py                # Email processing prompt template

services/
  email.py                # Gmail API: polling, parsing, sending replies
  workspace.py            # Git workspace management (file ops + commit/push)
  agent_core.py           # Agent-core repo management (identity, soul, memory)
  github_service.py       # GitHub API: create repos, issues, branches, PRs
  git_repo.py             # Base class for git repository operations

tools/
  definitions.py          # Claude tool schemas
  handlers.py             # Tool routing and execution

agent-core/               # Local clone of the agent's configuration repo
  IDENTITY.md             # Character and working style (editable by agent)
  SOUL.md                 # Values and principles (editable by agent)
  MEMORY.md               # Persistent memory across conversations

repos/                    # Local clones of agent-managed repositories
  workspace/              # Default general-purpose workspace
  <other repos>/          # Additional repos created by the agent
```

## Agent configuration

The agent's behaviour is driven by three files in its `agent-core` repository:

- **IDENTITY.md** — character, tone, and working style
- **SOUL.md** — values and principles that guide decisions
- **MEMORY.md** — episodic memory written by the agent after conversations

These are loaded and composed into the system prompt on every email. The agent can update all three files via tools, with changes committed and pushed to GitHub immediately.

## Tools available to the agent

**Workspace (file management)**
- `save_document`, `read_document`, `delete_document`, `rename_document`
- `create_folder`, `delete_folder`, `examine_workspace`, `commit_and_push`
- All tools accept an optional `repo_name` parameter (defaults to `"workspace"`)

**GitHub administration**
- `list_repos` — list all repositories on the account
- `create_repo` — create a new GitHub repo and initialise a local workspace
- `create_issue` — open a GitHub issue in any repository
- `create_branch` — create a branch in any repository
- `create_pull_request` — open a pull request

**Self-modification**
- `list_agent_core`, `read_agent_core` — inspect configuration files
- `create_agent_core`, `update_agent_core` — modify identity, soul, or other config files
- `update_memory` — update persistent memory

## Environment variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GITHUB_TOKEN` | GitHub personal access token for the agent's account |
| `GOOGLE_TOKEN_JSON` | Gmail OAuth token (for production deployment) |
| `AUTHORIZED_SENDERS` | JSON array of email addresses allowed to contact the agent |

## Deployment

The agent is deployed on [Render](https://render.com) as a background worker. On startup it:

1. Authenticates with Gmail
2. Initialises the GitHub service
3. Clones (or pulls) the default workspace repo to `repos/workspace/`
4. Clones (or pulls) the agent-core repo, seeding default configuration if needed
5. Begins polling the inbox every 10 seconds

## Local development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run OAuth flow to generate token.json
python agent.py --auth

# Run the agent
python agent.py
```
