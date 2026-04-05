"""
Email queue: interface for adding jobs and (optionally) processing with SES.
Phase 1: store in MongoDB email_queue; worker can be Lambda + SES later.
Supports List-Unsubscribe header (stored in doc for worker); body should include visible link.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime
from typing import Any

from . import schema

_queue_log = logging.getLogger("pipeline.email_queue")


def get_list_unsubscribe_value() -> str | None:
    """Return value for List-Unsubscribe header (mailto or URL). From env UNSUBSCRIBE_MAILTO or UNSUBSCRIBE_URL."""
    mailto = os.environ.get("UNSUBSCRIBE_MAILTO", "").strip()
    if mailto:
        return f"<{mailto}>" if not mailto.startswith("<") else mailto
    url = os.environ.get("UNSUBSCRIBE_URL", "").strip()
    if url:
        return f"<{url}>" if not url.startswith("<") else url
    return None


def append_unsubscribe_footer(body_text: str, body_html: str, list_unsubscribe: str | None) -> tuple[str, str]:
    """Append visible unsubscribe line to body text and HTML. Returns (new_body_text, new_body_html)."""
    if not list_unsubscribe:
        return body_text, body_html
    # Strip angle brackets for display URL
    url = list_unsubscribe.strip("<>")
    line_text = f"\n\n---\nTo unsubscribe: {url}"
    line_html = f'<p style="font-size:12px;color:#666;"><a href="{url}">Unsubscribe</a></p>'
    return body_text + line_text, (body_html or body_text.replace("\n", "<br>\n")) + line_html


def add_to_queue(
    mongo_db,
    lead_id: str,
    subject: str,
    body_text: str,
    body_html: str = "",
    to_email: str | None = None,
    list_unsubscribe: str | None = None,
) -> tuple[bool, str]:
    """
    Add one email job to email_queue. Skips if this lead_id already has any job (pending or sent).
    Returns (success, action): (True, "added") | (True, "skipped_already_queued") | (True, "skipped_already_sent") | (False, "error").
    Caller can log action so we never blindly add then dedupe — we check first and log.
    """
    queue = mongo_db.email_queue if hasattr(mongo_db, "email_queue") else mongo_db["email_queue"]
    existing = queue.find_one({"leadId": lead_id, "status": {"$in": ["pending", "sent"]}})
    if existing:
        reason = "skipped_already_sent" if existing.get("status") == "sent" else "skipped_already_queued"
        _queue_log.info("Email queue: lead_id=%s not added — %s (no duplicate)", lead_id[:16] + "..." if len(lead_id) > 16 else lead_id, reason)
        return (True, reason)
    body_html = body_html or body_text.replace("\n", "<br>\n")
    doc = {
        "_schemaVersion": schema.SCHEMA_VERSION_EMAIL_QUEUE,
        "leadId": lead_id,
        "toEmail": to_email,
        "subject": subject,
        "bodyText": body_text,
        "bodyHtml": body_html,
        "status": "pending",
        "createdAt": datetime.utcnow(),
    }
    if list_unsubscribe:
        doc["listUnsubscribe"] = list_unsubscribe
    try:
        queue.insert_one(doc)
        return (True, "added")
    except Exception:
        return (False, "error")


def already_queued_or_sent(mongo_db, lead_id: str) -> bool:
    """True if this lead already has a pending or sent job (do not add again — no duplicate emails)."""
    queue = mongo_db.email_queue if hasattr(mongo_db, "email_queue") else mongo_db["email_queue"]
    return queue.find_one({"leadId": lead_id, "status": {"$in": ["pending", "sent"]}}) is not None


def get_pending(mongo_db, limit: int = 10) -> list[dict]:
    """Get pending email jobs (for worker)."""
    queue = mongo_db.email_queue if hasattr(mongo_db, "email_queue") else mongo_db["email_queue"]
    return list(queue.find({"status": "pending"}).limit(limit))


def mark_sent(mongo_db, job_id: Any) -> None:
    """Mark job as sent (worker calls after SES send)."""
    queue = mongo_db.email_queue if hasattr(mongo_db, "email_queue") else mongo_db["email_queue"]
    queue.update_one({"_id": job_id}, {"$set": {"status": "sent", "sentAt": datetime.utcnow()}})


def mark_failed(mongo_db, job_id: Any, error: str) -> None:
    """Mark job as failed."""
    queue = mongo_db.email_queue if hasattr(mongo_db, "email_queue") else mongo_db["email_queue"]
    queue.update_one(
        {"_id": job_id},
        {"$set": {"status": "failed", "error": error, "failedAt": datetime.utcnow()}},
    )
