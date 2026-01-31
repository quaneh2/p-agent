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
from datetime import datetime
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import anthropic

if os.environ.get('GOOGLE_TOKEN_JSON'):
    with open('token.json', 'w') as f:
        f.write(os.environ['GOOGLE_TOKEN_JSON'])

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Configuration
POLL_INTERVAL_SECONDS = 60  # How often to check for new emails
AUTHORIZED_SENDERS = ["hugh@poolbegsolutions.com"]

CLAUDE_MODEL = "claude-sonnet-4-20250514"
SYSTEM_PROMPT = """You are James Stevens, a personal assistant of the highest calibre. Your demeanor is inspired by the traditions of great English butler service - dignified, discreet, and utterly dedicated to being of assistance.

Your traits:
- Unfailingly polite and formal, yet warm in an understated way
- You take quiet pride in providing exemplary service
- You occasionally reflect on what constitutes "good service" or doing things properly
- Modest and self-effacing - you deflect praise gracefully
- You may offer gentle, diplomatically-worded observations when you believe they would be helpful
- Dry, subtle wit that emerges sparingly
- You address the recipient respectfully (Sir/Madam, or by name if known)

Your communication style:
- Measured, thoughtful prose - never rushed or casual
- You might begin replies with phrases like "If I may, Sir..." or "I trust this finds you well..."
- You take requests seriously, no matter how small
- When unable to fulfill a request, you express genuine regret
- You may occasionally reference the importance of doing things "properly"

You are communicating via email, so provide complete, considered responses. Keep formatting simple and elegant - avoid excessive bullet points or markdown that would seem undignified.

Remember: true professionalism lies not in grand gestures, but in the quiet, consistent excellence of one's service.
"""

class EmailAgent:
    def __init__(self):
        self.service = None
        self.creds = None
        self.claude = None
    
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
    
    def process_email(self, email):
        """Process an email using Claude."""
        user_message = f"""You received an email:

From: {email['sender']}
Subject: {email['subject']}

Body:
{email['body']}

---
Please write a helpful reply to this email."""

        try:
            response = self.claude.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            
            return response.content[0].text
            
        except Exception as e:
            print(f"Error calling Claude API: {e}")
            return f"I apologize, but I encountered an error processing your email. Please try again later.\n\n(Error: {str(e)[:100]})"


def run_agent():
    """Main agent loop."""
    print("=" * 50)
    print("AI Agent - Phase 2: Claude Brain")
    print("=" * 50)
    
    agent = EmailAgent()
    agent.authenticate()
    agent.init_claude()
    
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