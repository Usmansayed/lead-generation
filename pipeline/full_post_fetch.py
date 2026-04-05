"""
Full post fetch: after a lead passes AI filter, fetch the full post content from post_url.
Used to gather information for hyper-personalized email. Results cached in MongoDB enriched_posts.
"""
from __future__ import annotations
import os
import re
from datetime import datetime, timedelta
from typing import Any

from .models import CanonicalLead
from . import schema

POST_SCRAPER_ACTOR_ENV = "POST_SCRAPER_ACTOR_ID"
CACHE_DAYS = 7


def get_cached_post(mongo_db, lead_id: str) -> dict[str, Any] | None:
    """Return cached full post for lead_id if present and not stale."""
    if mongo_db is None:
        return None
    coll = mongo_db.enriched_posts if hasattr(mongo_db, "enriched_posts") else mongo_db["enriched_posts"]
    doc = coll.find_one({"_id": lead_id})
    if not doc:
        return None
    fetched_at = doc.get("fetchedAt")
    if isinstance(fetched_at, datetime) and datetime.utcnow() - fetched_at > timedelta(days=CACHE_DAYS):
        return None
    return doc


def set_cached_post(mongo_db, lead_id: str, full_text: str, post_url: str) -> None:
    """Store full post content in cache."""
    if mongo_db is None:
        return
    coll = mongo_db.enriched_posts if hasattr(mongo_db, "enriched_posts") else mongo_db["enriched_posts"]
    coll.replace_one(
        {"_id": lead_id},
        {
            "_id": lead_id,
            "_schemaVersion": getattr(schema, "SCHEMA_VERSION_ENRICHED_POSTS", 1),
            "fullPostText": full_text,
            "postUrl": post_url,
            "fetchedAt": datetime.utcnow(),
        },
        upsert=True,
    )


def _resolve_post_fetcher_actor_id(client) -> str | None:
    """Resolve post-content-fetcher actor by name (for creators account using your own actors)."""
    actors = client.actors().list().items
    for actor in actors:
        if actor.get("name") == "post-content-fetcher":
            return actor["id"]
    return None


def _fetch_with_apify(post_url: str) -> str:
    """Use your own Apify actor (post-content-fetcher) to fetch URL and return main text. Returns empty on failure."""
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        return ""
    try:
        from apify_client import ApifyClient
        client = ApifyClient(token)
        actor_id = os.environ.get(POST_SCRAPER_ACTOR_ENV, "").strip()
        if not actor_id:
            actor_id = _resolve_post_fetcher_actor_id(client)
        if not actor_id:
            return ""
        run = client.actor(actor_id).call(
            run_input={"url": post_url, "useProxy": True},
            timeout_secs=60,
            memory_mbytes=1024,
        )
        if run.get("status") != "SUCCEEDED":
            return ""
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return ""
        items = list(client.dataset(dataset_id).iterate_items())
        if not items:
            return ""
        first = items[0]
        for key in ("text", "content", "markdown", "body", "description"):
            val = first.get(key)
            if val and str(val).strip():
                return (str(val).strip())[:5000]
        return ""
    except Exception:
        return ""


def _fetch_simple(url: str) -> str:
    """Simple HTTP fetch and crude text extraction. Returns empty for social URLs (often 403)."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (LeadGenPostFetch/1.0)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:5000]
    except Exception:
        return ""


def fetch_full_post(lead: CanonicalLead, mongo_db) -> dict[str, Any]:
    """
    Fetch full post content from lead.post_url. Used after qualify for email personalization.
    Returns: { full_post_text, post_url, from_cache }.
    """
    result = {"full_post_text": "", "post_url": lead.post_url or "", "from_cache": False}
    post_url = (lead.post_url or "").strip()
    if not post_url:
        return result

    cached = get_cached_post(mongo_db, lead.id) if mongo_db is not None else None
    if cached:
        result["full_post_text"] = (cached.get("fullPostText") or "").strip()
        result["from_cache"] = True
        return result

    text = _fetch_with_apify(post_url)
    if not text:
        if not any(x in post_url.lower() for x in ("instagram.com", "facebook.com", "reddit.com", "twitter.com", "linkedin.com")):
            text = _fetch_simple(post_url)
    text = (text or "").strip()[:5000]
    result["full_post_text"] = text
    if mongo_db is not None and text:
        set_cached_post(mongo_db, lead.id, text, post_url)
    return result
