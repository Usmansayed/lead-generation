"""App config: read/write safe runtime options (sending_paused, send_delay_ms, etc.)."""
from fastapi import APIRouter, HTTPException, Body

from db import get_mongo_db
from serialize import serialize_doc

router = APIRouter(prefix="/api/config", tags=["config"])

# Keys the dashboard is allowed to read/write (no secrets)
ALLOWED_KEYS = {
    "sending_paused",
    "send_delay_ms",
    "send_batch_size",
    "default_platforms",
    "after_filter_limit",
    "keywords_override",           # list of extra keywords for all platforms
    "platform_keywords_override",  # { "reddit": ["x", "y"], ... }
}


def _db():
    d = get_mongo_db()
    if d is None:
        raise HTTPException(status_code=503, detail="MongoDB not available")
    return d


def _coll(db):
    return db.app_config if hasattr(db, "app_config") else db["app_config"]


@router.get("")
def get_config():
    """Get all app config (allowed keys only)."""
    db = _db()
    coll = _coll(db)
    doc = coll.find_one({"_id": "default"})
    if not doc:
        return {k: None for k in ALLOWED_KEYS}
    out = {}
    for k in ALLOWED_KEYS:
        out[k] = doc.get(k)
    return out


@router.put("")
def update_config(updates: dict = Body(default={})):
    """Update config. Only allowed keys are applied. Body: { \"send_delay_ms\": 30000 }."""
    if not updates:
        return get_config()
    bad = set(updates.keys()) - ALLOWED_KEYS
    if bad:
        raise HTTPException(status_code=400, detail=f"Not allowed keys: {bad}")
    # Normalize keywords_override to list
    if "keywords_override" in updates and not isinstance(updates["keywords_override"], list):
        if isinstance(updates["keywords_override"], str):
            updates["keywords_override"] = [x.strip() for x in updates["keywords_override"].splitlines() if x.strip()]
        else:
            updates["keywords_override"] = []
    db = _db()
    coll = _coll(db)
    from datetime import datetime
    updates["updatedAt"] = datetime.utcnow()
    coll.update_one({"_id": "default"}, {"$set": updates}, upsert=True)
    return get_config()
