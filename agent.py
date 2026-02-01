"""
Autonomous Email Agent
==========================================
A simple agent named James Stevens that polls its Gmail inbox and replies to emails.
"""

import os
import base64
import json
import argparse
import time
import subprocess
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText


from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import anthropic

from prompts import SYSTEM_PROMPT
from tools import TOOLS, handle_tool_call

if os.environ.get('GOOGLE_TOKEN_JSON'):
    with open('token.json', 'w') as f:
        f.write(os.environ['GOOGLE_TOKEN_JSON'])

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

from config import (
    POLL_INTERVAL_SECONDS,
    WORKSPACE_DIR,
    AUTHORIZED_SENDERS,
    CLAUDE_MODEL,
    GIT_USER_NAME,
    GIT_USER_EMAIL,
)

class Workspace:
    """Manages the local git workspace."""
    
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.repo_url = None
    
    def init(self):
        """Initialize the workspace by cloning or pulling the repo."""
        token = os.environ.get('GITHUB_TOKEN')
        repo_name = os.environ.get('GITHUB_REPO')
        
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable not set")
        if not repo_name:
            raise ValueError("GITHUB_REPO environment variable not set (format: username/repo-name)")
        
        # Construct authenticated repo URL
        self.repo_url = f"https://{token}@github.com/{repo_name}.git"
        
        if self.workspace_dir.exists() and (self.workspace_dir / ".git").exists():
            # Workspace exists - pull latest
            print(f"Workspace exists at {self.workspace_dir}, pulling latest...")
            self._run_git(["pull"])
        else:
            # Clone fresh
            print(f"Cloning repository to {self.workspace_dir}...")
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", self.repo_url, str(self.workspace_dir)],
                check=True,
                capture_output=True
            )
        
        # Configure git user for commits
        self._run_git(["config", "user.email", GIT_USER_EMAIL])
        self._run_git(["config", "user.name", GIT_USER_NAME])
        
        print(f"Workspace ready: {self.workspace_dir}")
        return self
    
    def _run_git(self, args: list) -> subprocess.CompletedProcess:
        """Run a git command in the workspace directory."""
        return subprocess.run(
            ["git"] + args,
            cwd=self.workspace_dir,
            check=True,
            capture_output=True,
            text=True
        )
    
    def save_document(self, file_path: str, content: str) -> dict:
        """Save a document to the workspace."""
        try:
            full_path = self.workspace_dir / file_path
            
            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the file
            full_path.write_text(content)
            
            # Stage the file
            self._run_git(["add", file_path])
            
            return {
                "success": True,
                "action": "saved",
                "path": file_path,
                "message": f"Document saved to workspace: {file_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def commit_and_push(self, commit_message: str) -> dict:
        """Commit staged changes and push to remote."""
        try:
            # Check if there are changes to commit
            status = self._run_git(["status", "--porcelain"])
            
            if not status.stdout.strip():
                return {
                    "success": True,
                    "action": "no_changes",
                    "message": "No changes to commit."
                }
            
            # Commit
            self._run_git(["commit", "-m", commit_message])
            
            # Push
            self._run_git(["push"])
            
            return {
                "success": True,
                "action": "pushed",
                "message": f"Changes committed and pushed successfully."
            }
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"Git error: {e.stderr}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_documents(self) -> dict:
        """List all documents in the workspace."""
        try:
            documents = []
            for file_path in self.workspace_dir.rglob("*"):
                if file_path.is_file() and ".git" not in str(file_path):
                    relative_path = file_path.relative_to(self.workspace_dir)
                    documents.append(str(relative_path))
            
            return {
                "success": True,
                "documents": sorted(documents)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

class EmailAgent:
    def __init__(self):
        self.service = None
        self.creds = None
        self.claude = None
        self.workspace = None
        
    @property
    def services(self):
        return {
            "workspace": self.workspace
        }
    
    def authenticate(self, force_new=False):
        """Authenticate with Gmail API."""
        creds = None
        
        if os.path.exists('token.json') and not force_new:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Refreshing expired credentials...")
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    raise FileNotFoundError(
                        "credentials.json not found. Download it from Google Cloud Console."
                    )
                print("Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
                print("Credentials saved to token.json")
        
        self.creds = creds
        self.service = build('gmail', 'v1', credentials=creds)
        print("Successfully authenticated with Gmail API")
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
    
    def get_unread_emails(self):
        """Fetch unread emails from inbox."""
        try:
            results = self.service.users().messages().list(
                userId='me',
                q='is:unread in:inbox',
                maxResults=10
            ).execute()
            
            messages = results.get('messages', [])
            return messages
        except HttpError as error:
            print(f"Error fetching emails: {error}")
            return []
    
    def get_email_details(self, msg_id):
        """Get full details of an email."""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
            
            headers = message['payload']['headers']
            
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '(no subject)')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'unknown')
            
            body = self._extract_body(message['payload'])
            
            return {
                'id': msg_id,
                'subject': subject,
                'sender': sender,
                'body': body,
                'thread_id': message['threadId']
            }
        except HttpError as error:
            print(f"Error getting email details: {error}")
            return None
    
    def _extract_body(self, payload):
        """Extract plain text body from email payload."""
        if 'body' in payload and payload['body'].get('data'):
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if part['body'].get('data'):
                        return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                elif 'parts' in part:
                    result = self._extract_body(part)
                    if result:
                        return result
        
        return "(could not extract body)"
    
    def send_reply(self, original_email, reply_text):
        """Send a reply to an email."""
        try:
            message = MIMEText(reply_text)
            message['to'] = original_email['sender']
            message['subject'] = f"Re: {original_email['subject']}"
            message['In-Reply-To'] = original_email['id']
            message['References'] = original_email['id']
            
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            sent = self.service.users().messages().send(
                userId='me',
                body={
                    'raw': raw,
                    'threadId': original_email['thread_id']
                }
            ).execute()
            
            print(f"Reply sent (ID: {sent['id']})")
            return sent
        except HttpError as error:
            print(f"Error sending reply: {error}")
            return None
    
    def mark_as_read(self, msg_id):
        """Mark an email as read."""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=msg_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
        except HttpError as error:
            print(f"Error marking as read: {error}")
    
    def is_authorized_sender(self, sender):
        """Check if sender is in authorized list."""
        if not AUTHORIZED_SENDERS:
            print("WARNING: No authorized senders configured. Accepting all emails.")
            return True
        
        email = sender
        if '<' in sender:
            email = sender.split('<')[1].split('>')[0]
        
        return email.lower() in [s.lower() for s in AUTHORIZED_SENDERS]
    
    def handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool call and return the result."""
        if tool_name == "save_document":
            print(f"    -> Saving document: {tool_input['file_path']}")
            result = self.workspace.save_document(
                file_path=tool_input['file_path'],
                content=tool_input['content']
            )
            return json.dumps(result)
        
        elif tool_name == "commit_and_push":
            print(f"    -> Committing and pushing: {tool_input['commit_message']}")
            result = self.workspace.commit_and_push(
                commit_message=tool_input['commit_message']
            )
            return json.dumps(result)
        
        elif tool_name == "list_documents":
            print(f"    -> Listing documents")
            result = self.workspace.list_documents()
            return json.dumps(result)
        
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
    
    def process_email(self, email):
        """Process an email using Claude with tool support."""
        user_message = f"""You received an email:

From: {email['sender']}
Subject: {email['subject']}

Body:
{email['body']}

---
Please help with this request. If asked to create any document, use save_document to write it to your workspace, then commit_and_push to push it to the repository."""

        messages = [{"role": "user", "content": user_message}]
        
        try:
            # Initial response from Claude
            response = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
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
                    system=SYSTEM_PROMPT,
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
    agent.authenticate()
    agent.init_claude()
    agent.init_workspace()
    
    print(f"\nPolling interval: {POLL_INTERVAL_SECONDS} seconds")
    print(f"Authorized senders: {AUTHORIZED_SENDERS or 'ALL (not configured)'}")
    print(f"Claude model: {CLAUDE_MODEL}")
    print("\nAgent is running. Press Ctrl+C to stop.\n")
    
    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking for new emails...")
            
            emails = agent.get_unread_emails()
            
            if emails:
                print(f"Found {len(emails)} unread email(s)")
                
                for msg in emails:
                    email = agent.get_email_details(msg['id'])
                    
                    if not email:
                        continue
                    
                    print(f"\n  From: {email['sender']}")
                    print(f"  Subject: {email['subject']}")
                    
                    if not agent.is_authorized_sender(email['sender']):
                        print("  -> Skipping (unauthorized sender)")
                        agent.mark_as_read(email['id'])
                        continue
                    
                    print("  -> Processing with Claude...")
                    response = agent.process_email(email)
                    
                    print("  -> Sending reply...")
                    agent.send_reply(email, response)
                    
                    agent.mark_as_read(email['id'])
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
        agent = EmailAgent()
        agent.authenticate(force_new=True)
        print("\nAuthentication complete!")
        print("You can now deploy the agent with token.json")
    else:
        run_agent()


if __name__ == '__main__':
    main()