"""
Pipeline audit log: stores dedup and pipeline events in a separate MongoDB database
(lead_gen_audit) so logs survive even if the main lead_discovery data is lost.
Use for recovery: which posts were scraped, filtered, qualified, queued, sent.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

_COLLECTION = "pipeline_audit_log"
# Main pipeline data lives in lead_discovery; logs live in a different DB (schema).
MAIN_DB_NAME = "lead_discovery"
AUDIT_DB_NAME = "lead_gen_audit"

_log = logging.getLogger("pipeline.audit_log")


def get_audit_db():
    """
    Connect to the audit database (separate from lead_discovery).
    Uses MONGODB_URI_FOR_AUDIT if set (full URI for audit cluster); otherwise
    uses MONGODB_URI with database name lead_gen_audit so logs are isolated.
    """
    from urllib.parse import urlparse
    audit_uri = (os.environ.get("MONGODB_URI_FOR_AUDIT") or os.environ.get("MONGODB_URI_AUDIT") or "").strip()
    if audit_uri:
        uri = audit_uri
        path = (urlparse(uri).path or "").strip("/").split("?")[0]
        db_name = path if path else AUDIT_DB_NAME
    else:
        uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/").strip()
        db_name = AUDIT_DB_NAME  # same URI, different DB so logs are isolated from lead_discovery
    try:
        from pymongo import MongoClient
        client = MongoClient(uri)
        return client.get_database(db_name)
    except Exception as e:
        _log.debug("Audit DB connection failed (logging disabled): %s", e)
        return None


def ensure_audit_indexes(audit_db) -> None:
    """Create indexes on the audit collection for query by ts, leadId, runId."""
    if audit_db is None:
        return
    coll = audit_db[_COLLECTION] if hasattr(audit_db, "__getitem__") else audit_db[_COLLECTION]
    coll.create_index("ts")
    coll.create_index([("leadId", 1), ("ts", -1)])
    coll.create_index([("runId", 1), ("ts", 1)])
    coll.create_index([("stage", 1), ("action", 1), ("ts", -1)])


def log_audit(
    stage: str,
    action: str,
    lead_id: str,
    run_id: str | None = None,
    platform: str | None = None,
    post_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Write one audit record to the pipeline_audit_log collection (in lead_gen_audit DB).
    Does nothing if audit DB is unavailable. Minimal payload: enough to know which post and what happened.
    """
    db = get_audit_db()
    if db is None:
        return
    if run_id is None:
        try:
            from .logger import get_run_id
            run_id = get_run_id() or ""
        except Exception:
            run_id = ""
    from . import schema as _schema
    coll = db[_COLLECTION] if hasattr(db, "__getitem__") else db[_COLLECTION]
    now = datetime.utcnow()
    doc = {
        "_schemaVersion": _schema.SCHEMA_VERSION_AUDIT_LOG,
        "ts": now,
        "runId": run_id or "",
        "stage": stage,
        "action": action,
        "leadId": lead_id,
        "platform": platform or "",
        "postId": post_id or "",
    }
    if extra:
        doc["extra"] = {k: v for k, v in extra.items() if v is not None and v != ""}
    try:
        coll.insert_one(doc)
    except Exception as e:
        _log.warning("Audit log insert failed: %s", e)
