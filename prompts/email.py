"""
User message template for processing received emails
"""

EMAIL_RECEIVED_TEMPLATE = """You received an email:

From: {sender}
Subject: {subject}

Body:
{body}

---
Please help with this request. If asked to create any document, use save_document to write it to your workspace, then commit_and_push to push it to the repository."""
