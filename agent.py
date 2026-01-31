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

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Configuration
POLL_INTERVAL_SECONDS = 60  # How often to check for new emails
AUTHORIZED_SENDERS = ["hugh@poolbegsolutions.com"]


class EmailAgent:
    def __init__(self):
        self.service = None
        self.creds = None
    
    def authenticate(self, force_new=False):
        """Authenticate with Gmail API."""
        creds = None
        
        # Check for existing token
        if os.path.exists('token.json') and not force_new:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        # If no valid creds, authenticate
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
            
            # Save credentials for future runs
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
                print("Credentials saved to token.json")
        
        self.creds = creds
        self.service = build('gmail', 'v1', credentials=creds)
        print("Successfully authenticated with Gmail API")
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
            
            # Extract relevant headers
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '(no subject)')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'unknown')
            
            # Extract body
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
                    # Recursively check nested parts
                    result = self._extract_body(part)
                    if result:
                        return result
        
        return "(could not extract body)"
    
    def send_reply(self, original_email, reply_text):
        """Send a reply to an email."""
        try:
            # Create reply message
            message = MIMEText(reply_text)
            message['to'] = original_email['sender']
            message['subject'] = f"Re: {original_email['subject']}"
            message['In-Reply-To'] = original_email['id']
            message['References'] = original_email['id']
            
            # Encode message
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Send as reply in same thread
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
        
        # Extract email from "Name <email>" format
        email = sender
        if '<' in sender:
            email = sender.split('<')[1].split('>')[0]
        
        return email.lower() in [s.lower() for s in AUTHORIZED_SENDERS]
    
    def process_email(self, email):
        """Process an email and generate response (Phase 1: Echo)."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        response = f"""Hello,

I received your email at {timestamp}.

You said:
---
{email['body'][:1000]}
---

This is an automated response from your PA.

Best,
James Stevens"""
        
        return response


def run_agent():
    """Main agent loop."""
    print("=" * 50)
    print("p Agent")
    print("=" * 50)
    
    agent = EmailAgent()
    agent.authenticate()
    
    print(f"\nPolling interval: {POLL_INTERVAL_SECONDS} seconds")
    print(f"Authorized senders: {AUTHORIZED_SENDERS or 'ALL (not configured)'}")
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
                    
                    # Check authorization
                    if not agent.is_authorized_sender(email['sender']):
                        print("  -> Skipping (unauthorized sender)")
                        agent.mark_as_read(email['id'])
                        continue
                    
                    # Process and reply
                    print("  -> Processing...")
                    response = agent.process_email(email)
                    
                    print("  -> Sending reply...")
                    agent.send_reply(email, response)
                    
                    # Mark as read
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
    parser = argparse.ArgumentParser(description='P Agent')
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