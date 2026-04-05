"""
Pipeline state for continuous runs: last run time and optional per-platform cursors.
Used to (1) know when we last ran, (2) optionally pass "after_utc" to actors to fetch only new posts.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any

from . import schema

_STATE_ID = "ingestion"
# Platforms whose actors we try to pass after_utc (cursor) for incremental fetch
_CURSOR_PLATFORMS = ("reddit",)


def get_pipeline_state(mongo_db) -> dict[str, Any]:
    """Return { lastRunAt: datetime | None, cursors: { platform: int (unix ts) }, keyword_offset: int }."""
    if mongo_db is None:
        return {"lastRunAt": None, "cursors": {}, "keyword_offset": 0}
    coll = mongo_db.pipeline_state if hasattr(mongo_db, "pipeline_state") else mongo_db["pipeline_state"]
    doc = coll.find_one({"_id": _STATE_ID})
    if not doc:
        return {"lastRunAt": None, "cursors": {}, "keyword_offset": 0}
    last = doc.get("lastRunAt")
    if isinstance(last, datetime):
        pass
    elif last is not None:
        try:
            last = datetime.utcfromtimestamp(last) if isinstance(last, (int, float)) else last
        except Exception:
            last = None
    cursors = doc.get("cursors") or {}
    keyword_offset = doc.get("keyword_offset")
    if keyword_offset is None or not isinstance(keyword_offset, int):
        keyword_offset = 0
    return {"lastRunAt": last, "cursors": cursors, "keyword_offset": keyword_offset}


def save_pipeline_state(
    mongo_db,
    last_run_at: datetime | None = None,
    cursors: dict[str, int | float] | None = None,
    update_last_run_at: bool = True,
    keyword_offset: int | None = None,
) -> None:
    """Persist last run time, per-platform cursors, and optional keyword_offset. Set update_last_run_at=False to only update cursors (for incremental save during a run)."""
    if mongo_db is None:
        return
    coll = mongo_db.pipeline_state if hasattr(mongo_db, "pipeline_state") else mongo_db["pipeline_state"]
    existing = coll.find_one({"_id": _STATE_ID}) if (cursors is not None and not update_last_run_at) or keyword_offset is not None else None
    if existing is None:
        existing = coll.find_one({"_id": _STATE_ID})
    if update_last_run_at or existing is None:
        now = last_run_at or datetime.utcnow()
    else:
        now = existing.get("lastRunAt")
        if isinstance(now, (int, float)):
            now = datetime.utcfromtimestamp(now)
        if now is None:
            now = datetime.utcnow()
    saved_cursors = cursors if cursors is not None else (existing.get("cursors") if existing else {})
    saved_keyword_offset = keyword_offset if keyword_offset is not None else (existing.get("keyword_offset", 0) if existing else 0)
    doc = {
        "_id": _STATE_ID,
        "schemaVersion": schema.SCHEMA_VERSION_PIPELINE_STATE,
        "lastRunAt": now,
        "cursors": saved_cursors,
        "keyword_offset": saved_keyword_offset,
        "updatedAt": datetime.utcnow(),
    }
    coll.replace_one({"_id": _STATE_ID}, doc, upsert=True)


def get_cursor_from_raw_posts(mongo_db, platform: str) -> int | None:
    """
    Bootstrap cursor from existing raw_posts so the next fetch only gets new posts.
    Returns max timestamp (Unix UTC) for the platform, or None if no data.
    """
    if mongo_db is None or platform not in _CURSOR_PLATFORMS:
        return None
    raw = mongo_db.raw_posts if hasattr(mongo_db, "raw_posts") else mongo_db["raw_posts"]
    doc = raw.find_one(
        {"platform": platform.lower()},
        sort=[("timestamp", -1)],
        projection={"timestamp": 1},
    )
    if not doc or not doc.get("timestamp"):
        return None
    ts = doc["timestamp"]
    if hasattr(ts, "timestamp"):
        return int(ts.timestamp())
    if isinstance(ts, (int, float)):
        return int(ts)
    return None


def merge_cursor_into_run_input(run_input: dict[str, Any], platform: str, cursor: int | float) -> dict[str, Any]:
    """If this platform supports incremental cursor, add after_utc to run_input. Returns a copy."""
    out = dict(run_input)
    if platform.lower() not in _CURSOR_PLATFORMS:
        return out
    # Reddit: fetch only posts after this timestamp (avoid re-scraping same posts)
    if "after_utc" not in out and "since" not in out:
        out["after_utc"] = int(cursor)
    return out


# Platforms that may accept since_date / startDate to fetch only recent posts (avoid duplicates)
_SINCE_PLATFORMS = ("twitter", "instagram", "facebook", "linkedin")


def merge_since_date_into_run_input(
    run_input: dict[str, Any],
    platform: str,
    last_run_at: datetime | None,
) -> dict[str, Any]:
    """Add since/startDate from last run so actors fetch only new posts. Returns a copy."""
    out = dict(run_input)
    if platform.lower() not in _SINCE_PLATFORMS or not last_run_at:
        return out
    # Many Apify actors accept "since", "startDate", or "minDate" as ISO date
    since_str = last_run_at.strftime("%Y-%m-%d") if hasattr(last_run_at, "strftime") else None
    if not since_str:
        return out
    if "since" not in out and "startDate" not in out and "minDate" not in out:
        out["since"] = since_str
    return out
