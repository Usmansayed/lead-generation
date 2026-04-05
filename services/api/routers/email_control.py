"""Email control: pause/resume sending, cancel queued email."""
from fastapi import APIRouter, HTTPException

from db import get_mongo_db
from serialize import serialize_doc

router = APIRouter(prefix="/api/email", tags=["email"])


def _db():
    d = get_mongo_db()
    if d is None:
        raise HTTPException(status_code=503, detail="MongoDB not available")
    return d


@router.post("/pause")
def pause_sending():
    """Set sending_paused so the send job skips actually sending (or future sender checks this)."""
    db = _db()
    coll = db.app_config if hasattr(db, "app_config") else db["app_config"]
    from datetime import datetime
    coll.update_one({"_id": "default"}, {"$set": {"sending_paused": True, "updatedAt": datetime.utcnow()}}, upsert=True)
    return {"paused": True}


@router.post("/resume")
def resume_sending():
    """Clear sending_paused."""
    db = _db()
    coll = db.app_config if hasattr(db, "app_config") else db["app_config"]
    from datetime import datetime
    coll.update_one({"_id": "default"}, {"$set": {"sending_paused": False, "updatedAt": datetime.utcnow()}}, upsert=True)
    return {"paused": False}


@router.put("/queue/{item_id}/cancel")
def cancel_queued_email(item_id: str):
    """Mark a pending email_queue item as cancelled (so it won't be sent)."""
    db = _db()
    queue = db.email_queue if hasattr(db, "email_queue") else db["email_queue"]
    from bson import ObjectId
    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")
    r = queue.update_one({"_id": oid, "status": "pending"}, {"$set": {"status": "cancelled"}})
    if r.modified_count == 0:
        doc = queue.find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Not found")
        if doc.get("status") != "pending":
            raise HTTPException(status_code=400, detail="Email is not pending")
    return {"cancelled": True, "id": item_id}
