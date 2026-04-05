"""
Suppression list: do not email leads or addresses that bounced, complained, or unsubscribed.
Check before adding to email_queue. Bounce/complaint handlers (SNS/Lambda) can add entries.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any

from . import schema


def _coll(mongo_db):
    if mongo_db is None:
        return None
    return mongo_db.suppression_list if hasattr(mongo_db, "suppression_list") else mongo_db["suppression_list"]


def ensure_indexes(db) -> None:
    """Create indexes on suppression_list for fast lookup."""
    coll = _coll(db)
    if coll is None:
        return
    coll.create_index("leadId")
    coll.create_index("email")
    coll.create_index("createdAt")


def add_to_suppression_list(
    mongo_db,
    *,
    lead_id: str | None = None,
    email: str | None = None,
    reason: str = "manual",
) -> bool:
    """Add an entry so we never email this lead_id and/or email again. Returns True if added."""
    coll = _coll(mongo_db)
    if coll is None:
        return False
    if not lead_id and not email:
        return False
    email = (email or "").strip().lower() or None
    doc = {
        "_schemaVersion": schema.SCHEMA_VERSION_SUPPRESSION_LIST,
        "leadId": lead_id,
        "email": email,
        "reason": reason,
        "createdAt": datetime.utcnow(),
    }
    try:
        coll.insert_one(doc)
        return True
    except Exception:
        return False


def is_suppressed(mongo_db, *, lead_id: str | None = None, email: str | None = None) -> bool:
    """Return True if this lead_id and/or email is on the suppression list (do not send)."""
    coll = _coll(mongo_db)
    if coll is None:
        return False
    q: dict[str, Any] = {"$or": []}
    if lead_id:
        q["$or"].append({"leadId": lead_id})
    if email and email.strip():
        q["$or"].append({"email": email.strip().lower()})
    if not q["$or"]:
        return False
    return coll.find_one(q) is not None
