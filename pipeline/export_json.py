"""
Export pipeline collections to JSON for inspection. Handles ObjectId and datetime.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Any

try:
    from bson import ObjectId
except ImportError:
    ObjectId = None


def _serialize_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat() + "Z"
    if ObjectId is not None and isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, dict):
        return {k: _serialize_value(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_serialize_value(x) for x in v]
    return v


def export_raw_posts_and_qualified(db, path: str, raw_limit: int = 500, qualified_limit: int = 200) -> dict[str, Any]:
    """
    Write raw_posts and qualified_leads to a JSON file. Returns summary { raw_count, qualified_count, path }.
    """
    raw_coll = db.raw_posts if hasattr(db, "raw_posts") else db["raw_posts"]
    qual_coll = db.qualified_leads if hasattr(db, "qualified_leads") else db["qualified_leads"]
    raw_docs = list(raw_coll.find().sort("createdAt", -1).limit(raw_limit))
    qual_docs = list(qual_coll.find().sort("createdAt", -1).limit(qualified_limit))
    payload = {
        "export_meta": {
            "raw_posts_limit": raw_limit,
            "qualified_leads_limit": qualified_limit,
            "raw_posts_count": len(raw_docs),
            "qualified_leads_count": len(qual_docs),
        },
        "raw_posts": [_serialize_value(d) for d in raw_docs],
        "qualified_leads": [_serialize_value(d) for d in qual_docs],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return {"raw_count": len(raw_docs), "qualified_count": len(qual_docs), "path": path}
