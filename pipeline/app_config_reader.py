"""
Read app_config from MongoDB. Used by ses_sender and other pipeline stages.
Config is managed by the dashboard API; pipeline reads it at runtime.
"""
from __future__ import annotations


def get_app_config(mongo_db) -> dict:
    """Return app_config doc (allowed keys only). Empty dict if no config."""
    if mongo_db is None:
        return {}
    coll = mongo_db.app_config if hasattr(mongo_db, "app_config") else mongo_db["app_config"]
    doc = coll.find_one({"_id": "default"})
    if not doc:
        return {}
    allowed = {"sending_paused", "send_delay_ms", "send_batch_size", "default_platforms", "after_filter_limit"}
    return {k: doc.get(k) for k in allowed}
