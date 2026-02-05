"""
Autonomous Email Agent
==========================================
A simple agent that polls its Gmail inbox and replies to emails.
"""

import os
import argparse
import time
from datetime import datetime

import anthropic

from config import (
    POLL_INTERVAL_SECONDS,
    WORKSPACE_DIR,
    AUTHORIZED_SENDERS,
    CLAUDE_MODEL,
)
from prompts import load_system_prompt, EMAIL_RECEIVED_TEMPLATE
from tools import TOOLS, handle_tool_call
from services import Workspace, EmailService, AgentCore


class EmailAgent:
    def __init__(self):
        self.email_service = None
        self.claude = None
        self.workspace = None
        self.agent_core = None

    @property
    def services(self):
        return {
            "workspace": self.workspace,
            "agent_core": self.agent_core,
        }

    def init_email(self):
        """Initialize email service."""
        self.email_service = EmailService()
        self.email_service.authenticate()
        return self

    def init_claude(self):
        """Initialize Claude client."""
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.claude = anthropic.Anthropic(api_key=api_key)
        print("Successfully initialized Claude client")
        return self

    def init_workspace(self):
        """Initialize the git workspace."""
        self.workspace = Workspace(WORKSPACE_DIR)
        self.workspace.init()
        return self

    def init_agent_core(self):
        """Initialize the agent-core configuration repo."""
        self.agent_core = AgentCore()
        self.agent_core.init()
        return self

    def is_authorized_sender(self, sender):
        """Check if sender is in authorized list."""
        if not AUTHORIZED_SENDERS:
            print("WARNING: No authorized senders configured. Accepting all emails.")
            return True

        email = sender
        if '<' in sender:
            email = sender.split('<')[1].split('>')[0]

        return email.lower() in [s.lower() for s in AUTHORIZED_SENDERS]

    def process_email(self, email):
        """Process an email using Claude with tool support."""
        # Pull latest config and load current system prompt
        self.agent_core.pull_latest()
        system_prompt = load_system_prompt()

        user_message = EMAIL_RECEIVED_TEMPLATE.format(
            sender=email['sender'],
            subject=email['subject'],
            body=email['body']
        )

        messages = [{"role": "user", "content": user_message}]

        try:
            # Initial response from Claude
            response = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=system_prompt,
                tools=TOOLS,
                messages=messages
            )

            # Handle tool use loop
            while response.stop_reason == "tool_use":
                # Extract tool calls
                tool_calls = [block for block in response.content if block.type == "tool_use"]

                # Add assistant's response to messages
                messages.append({"role": "assistant", "content": response.content})

                # Process each tool call
                tool_results = []
                for tool_call in tool_calls:
                    result = handle_tool_call(tool_call.name, tool_call.input, self.services)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": result
                    })

                # Add tool results to messages
                messages.append({"role": "user", "content": tool_results})

                # Get Claude's next response
                response = self.claude.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages
                )

            # Extract final text response
            text_blocks = [block.text for block in response.content if hasattr(block, 'text')]
            return "\n".join(text_blocks)

        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return f"I must apologise, but I encountered an error whilst processing your request. Please do try again later.\n\n(Error: {str(e)[:100]})"


def run_agent():
    """Main agent loop."""
    print("=" * 50)
    print("AI Agent")
    print("=" * 50)

    agent = EmailAgent()
    agent.init_email()
    agent.init_claude()
    agent.init_workspace()
    agent.init_agent_core()

    print(f"\nPolling interval: {POLL_INTERVAL_SECONDS} seconds")
    print(f"Authorized senders: {AUTHORIZED_SENDERS or 'ALL (not configured)'}")
    print(f"Claude model: {CLAUDE_MODEL}")
    print("\nAgent is running. Press Ctrl+C to stop.\n")

    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking for new emails...")

            emails = agent.email_service.get_unread_emails()

            if emails:
                print(f"Found {len(emails)} unread email(s)")

                for msg in emails:
                    email = agent.email_service.get_email_details(msg['id'])

                    if not email:
                        continue

                    print(f"\n  From: {email['sender']}")
                    print(f"  Subject: {email['subject']}")

                    if not agent.is_authorized_sender(email['sender']):
                        print("  -> Skipping (unauthorized sender)")
                        agent.email_service.mark_as_read(email['id'])
                        continue

                    print("  -> Processing with Claude...")
                    response = agent.process_email(email)

                    print("  -> Sending reply...")
                    agent.email_service.send_reply(email, response)

                    agent.email_service.mark_as_read(email['id'])
                    print("  -> Done!")
            else:
                print("No new emails")

            print(f"Sleeping for {POLL_INTERVAL_SECONDS} seconds...\n")
            time.sleep(POLL_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("\n\nAgent stopped by user.")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            print(f"Retrying in {POLL_INTERVAL_SECONDS} seconds...")
            time.sleep(POLL_INTERVAL_SECONDS)


def main():
    parser = argparse.ArgumentParser(description='AI Email Agent')
    parser.add_argument('--auth', action='store_true', help='Run authentication flow only')
    args = parser.parse_args()

    if args.auth:
        print("Running authentication flow...")
        email_service = EmailService()
        email_service.authenticate(force_new=True)
        print("\nAuthentication complete!")
        print("You can now deploy the agent with token.json")
    else:
        run_agent()


if __name__ == '__main__':
    main()
