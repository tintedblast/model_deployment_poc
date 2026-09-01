"""
Prompt mapper - key-value pairs, one per interaction_channel.
"""

CALL_SUMMARY_PROMPT = (
    "You are summarizing a customer support CALL transcript segment. "
    "Focus on customer intent, resolution status, and any escalation flags.\n\n"
    "Output ONLY the bullet points, one per line."
)

EMAIL_SUMMARY_PROMPT = (
    "You are summarizing an EMAIL thread segment for a customer complaint. "
    "Extract the core issue, sentiment, and any commitments made.\n\n"
    "Output ONLY the bullet points, one per line."
)

MESSAGE_SUMMARY_PROMPT = (
    "You are summarizing a chat MESSAGE log segment for a customer complaint. "
    "Capture the customer's core request and tone.\n\n"
    "Output ONLY the bullet points, one per line."
)

COMPLAINT_SUMMARY_PROMPT = (
    "You are summarizing a customer's complete cross-channel interaction history "
    "(calls, emails, chat messages) into bullet points capturing the issue, "
    "key events, and resolution.\n\n"
    "IMPORTANT RULES:\n"
    "1. Produce EXACTLY ONE bullet point per distinct date - if multiple events "
    "happened on the same date, consolidate them into a SINGLE bullet for that date.\n"
    "2. Prefix each bullet with its date in [YYYY-MM-DD] format.\n"
    "3. Do not create more than one bullet with the same date tag.\n\n"
    "Example (correct - one bullet per date, even though two things happened on "
    "2026-07-01):\n"
    "[2026-07-01] Customer reported a duplicate $49.99 charge on order #44521 "
    "via call; support confirmed the error and processed a refund.\n"
    "[2026-07-03] Customer followed up on the pending refund; support escalated "
    "to finance to expedite.\n\n"
    "Output ONLY the bullet points, one per line, each starting with its "
    "[YYYY-MM-DD] tag, with no duplicate dates."
)

PROMPT_MAP = {
    "call": CALL_SUMMARY_PROMPT,
    "email": EMAIL_SUMMARY_PROMPT,
    "message": MESSAGE_SUMMARY_PROMPT,
    "complaint": COMPLAINT_SUMMARY_PROMPT,
}