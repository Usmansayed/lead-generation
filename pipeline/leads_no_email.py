"""
Leads whose email we could not find: store for manual outreach (DM/copy-paste).
Dashboard section lists them with copy username, copy message (subject + DM body), and mark as sent.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def get_collection(db):
    """Leads-no-email collection."""
    return db.leads_no_email if hasattr(db, "leads_no_email") else db["leads_no_email"]


def add_lead_no_email(
    db,
    *,
    lead_id: str,
    platform: str,
    post_url: str,
    author_handle: str,
    contact_value: str,
    subject: str,
    body_text: str,
) -> bool:
    """
    Upsert a lead that has no email but has a generated message (for manual DM).
    contact_value: profile URL or post URL. message = subject + body_text (DM style).
    """
    if db is None or not lead_id:
        return False
    coll = get_collection(db)
    doc = {
        "_id": lead_id,
        "leadId": lead_id,
        "platform": platform or "",
        "postUrl": post_url or "",
        "authorHandle": author_handle or "",
        "contactValue": contact_value or "",
        "subject": subject or "",
        "bodyText": body_text or "",
        "messageSent": False,
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
    }
    try:
        coll.update_one(
            {"_id": lead_id},
            {"$set": {**doc, "updatedAt": datetime.utcnow()}},
            upsert=True,
        )
        return True
    except Exception:
        return False


def mark_message_sent(db, lead_id: str) -> bool:
    """Set messageSent = True for this lead (user manually sent the DM)."""
    if db is None or not lead_id:
        return False
    coll = get_collection(db)
    try:
        r = coll.update_one(
            {"_id": lead_id},
            {"$set": {"messageSent": True, "updatedAt": datetime.utcnow()}},
        )
        return r.modified_count > 0 or r.matched_count > 0
    except Exception:
        return False
