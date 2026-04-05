"""
Optional Redis cache for Apify actor results.
Reduces redundant API calls when re-running the same platform+input within TTL.
Set REDIS_URL in .env to enable.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

REDIS_URL_ENV = "REDIS_URL"
CACHE_TTL_SEC = 3600  # 1 hour
CACHE_PREFIX = "leadgen:apify:"


def _redis_client():
    """Return Redis client or None if not configured."""
    url = os.environ.get(REDIS_URL_ENV, "").strip()
    if not url:
        return None
    try:
        import redis
        return redis.from_url(url, decode_responses=True)
    except ImportError:
        return None
    except Exception:
        return None


def _cache_key(actor_id: str, run_input: dict[str, Any]) -> str:
    """Stable cache key from actor_id + run_input."""
    # Sort keys for deterministic hash
    serial = json.dumps(run_input, sort_keys=True, default=str)
    h = hashlib.sha256(serial.encode()).hexdigest()
    return f"{CACHE_PREFIX}{actor_id}:{h[:16]}"


def get_cached(actor_id: str, run_input: dict[str, Any]) -> list[dict] | None:
    """
    Return cached dataset items if present and not expired.
    Returns None if cache miss or Redis unavailable.
    """
    r = _redis_client()
    if not r:
        return None
    key = _cache_key(actor_id, run_input)
    try:
        data = r.get(key)
        if data:
            return json.loads(data)
    except Exception:
        pass
    return None


def set_cached(actor_id: str, run_input: dict[str, Any], items: list[dict]) -> None:
    """Store dataset items in Redis with TTL."""
    r = _redis_client()
    if not r:
        return
    key = _cache_key(actor_id, run_input)
    try:
        r.setex(key, CACHE_TTL_SEC, json.dumps(items, default=str))
    except Exception:
        pass
