"""
Database-driven keyword overrides. When app_config.keywords_override or
platform_keywords_override is set, these are merged into the search terms built from YAML.
Allows dashboard-driven keyword tweaks without redeploy.
"""
from __future__ import annotations

from typing import Any


def get_keywords_override(mongo_db) -> dict[str, Any]:
    """
    Read keyword overrides from app_config. Returns { keywords: list, platform_keywords: dict }.
    keywords: extra terms for all platforms; platform_keywords: { "reddit": [...], ... }.
    """
    out = {"keywords": [], "platform_keywords": {}}
    if mongo_db is None:
        return out
    coll = mongo_db.app_config if hasattr(mongo_db, "app_config") else mongo_db["app_config"]
    doc = coll.find_one({"_id": "default"})
    if not doc:
        return out
    kw = doc.get("keywords_override")
    if isinstance(kw, list):
        out["keywords"] = [str(x).strip() for x in kw if x]
    pk = doc.get("platform_keywords_override")
    if isinstance(pk, dict):
        for k, v in pk.items():
            if isinstance(v, list):
                out["platform_keywords"][str(k).lower()] = [str(x).strip() for x in v if x]
    return out


def merge_keywords_override(keywords: list[str], platform: str, overrides: dict[str, Any]) -> list[str]:
    """
    Merge override keywords into the built list. Keeps order: base keywords first, then overrides.
    """
    if not overrides:
        return keywords
    extra = list(overrides.get("keywords") or [])
    pk = overrides.get("platform_keywords") or {}
    platform_extra = pk.get(platform.lower()) or []
    combined = list(dict.fromkeys(keywords + extra + platform_extra))
    return combined
