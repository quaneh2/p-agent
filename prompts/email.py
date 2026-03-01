"""
User message template for processing received emails
"""

EMAIL_RECEIVED_TEMPLATE = """You received an email from your employer:

From: {sender}
Subject: {subject}

{body}

---
Your response will be sent directly as an email reply. Write as you would in a professional email—concise, no meta-commentary about what you did. If you used tools to complete a task, confirm the outcome naturally, don't narrate the process.

If asked to create any document, use save_document to write it to your workspace, then commit_and_push to push it to the repository."""
