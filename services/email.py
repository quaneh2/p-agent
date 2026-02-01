"""
Email service - handles Gmail API operations
"""

import os
import base64
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import SCOPES


class EmailService:
    """Handles Gmail API operations."""

    def __init__(self):
        self.service = None
        self.creds = None

    def authenticate(self, force_new=False):
        """Authenticate with Gmail API."""
        # Load token from environment variable if available (for production)
        if os.environ.get('GOOGLE_TOKEN_JSON'):
            with open('token.json', 'w') as f:
                f.write(os.environ['GOOGLE_TOKEN_JSON'])

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
            message_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), None)

            body = self._extract_body(message['payload'])

            return {
                'id': msg_id,
                'subject': subject,
                'sender': sender,
                'body': body,
                'thread_id': message['threadId'],
                'message_id': message_id
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
            if original_email.get('message_id'):
                message['In-Reply-To'] = original_email['message_id']
                message['References'] = original_email['message_id']

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
