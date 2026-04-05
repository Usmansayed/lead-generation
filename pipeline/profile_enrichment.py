"""
Profile enrichment: before sending email, scrape the lead's profile (from the post author)
to get more context (bio, about, recent activity). Makes emails feel super personalized.
Results cached in MongoDB enriched_profiles so we don't re-scrape every time.
"""
from __future__ import annotations
import os
import re
from datetime import datetime, timedelta
from typing import Any

from .models import CanonicalLead
from . import schema

# Optional: Apify actor to fetch URL content (e.g. apify/website-content-crawler or custom)
PROFILE_SCRAPER_ACTOR_ENV = "PROFILE_SCRAPER_ACTOR_ID"
CACHE_DAYS = 7


def _get_profile_url(lead: CanonicalLead) -> str | None:
    """Best available profile URL for this lead."""
    url = (lead.author.profile_url or "").strip()
    if url:
        return url
    # Fallback: build from platform + handle
    handle = (lead.author.handle or lead.author.name or "").strip()
    if not handle:
        return None
    platform = (lead.platform or "").lower()
    if platform == "reddit":
        return f"https://www.reddit.com/user/{re.sub(r'[^a-zA-Z0-9_]', '', handle)}"
    if platform == "twitter":
        handle_clean = handle.lstrip("@")
        return f"https://twitter.com/{handle_clean}"  # x.com redirects from twitter.com
    if platform == "linkedin":
        return None  # Usually need full URL
    if platform == "instagram":
        return f"https://www.instagram.com/{handle.lstrip('@')}"
    if platform == "facebook":
        return f"https://www.facebook.com/{handle}"
    return None


def _resolve_post_content_fetcher(client) -> str | None:
    """Resolve post-content-fetcher by name (same actor used for full post + profile fetch)."""
    actors = client.actors().list().items
    for actor in actors:
        if actor.get("name") == "post-content-fetcher":
            return actor["id"]
    return None


def _fetch_with_apify(profile_url: str) -> tuple[str, list[str]]:
    """Use Apify actor to fetch URL and return (main_text, links). Uses post-content-fetcher (one actor for all 5 platforms)."""
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        return "", []
    try:
        from apify_client import ApifyClient
        client = ApifyClient(token)
        actor_id = os.environ.get(PROFILE_SCRAPER_ACTOR_ENV, "").strip()
        if not actor_id:
            actor_id = _resolve_post_content_fetcher(client)
        if not actor_id:
            return "", []
        run = client.actor(actor_id).call(
            run_input={"url": profile_url, "useProxy": True},
            timeout_secs=60,
            memory_mbytes=1024,
        )
        if run.get("status") != "SUCCEEDED":
            return "", []
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return "", []
        items = list(client.dataset(dataset_id).iterate_items())
        if not items:
            return "", []
        first = items[0]
        text = ""
        for key in ("text", "content", "markdown", "body", "description"):
            val = first.get(key)
            if val and str(val).strip():
                text = (str(val).strip())[:3000]
                break
        # Optional: if actor returns links (e.g. from profile page), caller can use for email discovery
        links = first.get("links") or first.get("urls") or first.get("linksList")
        if isinstance(links, list):
            links = [str(u).strip() for u in links if u and str(u).strip()][:20]
        elif isinstance(links, str) and links.strip():
            links = [links.strip()]
        else:
            links = []
            return (text, links)
    except Exception:
        return ("", [])


def _fetch_simple(url: str) -> str:
    """Simple HTTP fetch and crude text extraction (no JS). Returns empty if not configured."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "LeadGenProfileEnrichment/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        # Strip tags and collapse whitespace
        text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:3000]
    except Exception:
        return ""


def get_cached_profile(mongo_db, lead_id: str) -> dict[str, Any] | None:
    """Return cached enrichment for lead_id if present and not stale."""
    if mongo_db is None:
        return None
    coll = mongo_db.enriched_profiles if hasattr(mongo_db, "enriched_profiles") else mongo_db["enriched_profiles"]
    doc = coll.find_one({"_id": lead_id})
    if not doc:
        return None
    enriched_at = doc.get("enrichedAt")
    if isinstance(enriched_at, datetime) and datetime.utcnow() - enriched_at > timedelta(days=CACHE_DAYS):
        return None
    return doc


def set_cached_profile(mongo_db, lead_id: str, profile_text: str, profile_url: str, profile_links: list[str] | None = None) -> None:
    """Store enrichment in cache. profile_links optional (URLs from profile page for email discovery)."""
    if mongo_db is None:
        return
    doc: dict[str, Any] = {
        "_id": lead_id,
        "_schemaVersion": schema.SCHEMA_VERSION_ENRICHED_PROFILES,
        "profileText": profile_text,
        "profileUrl": profile_url,
        "enrichedAt": datetime.utcnow(),
    }
    if profile_links:
        doc["profileLinks"] = profile_links[:20]
    coll = mongo_db.enriched_profiles if hasattr(mongo_db, "enriched_profiles") else mongo_db["enriched_profiles"]
    coll.replace_one({"_id": lead_id}, doc, upsert=True)


def enrich_lead_profile(lead: CanonicalLead, mongo_db) -> dict[str, Any]:
    """
    Fetch and cache profile content for the lead's author. Used before email to personalize.
    Returns dict: profile_text (str), profile_url (str), from_cache (bool).
    If no profile URL or scrape fails, profile_text is "" so email still uses only the post.
    """
    result = {"profile_text": "", "profile_url": "", "from_cache": False}
    profile_url = _get_profile_url(lead)
    result["profile_url"] = profile_url or ""

    cached = get_cached_profile(mongo_db, lead.id) if mongo_db is not None else None
    if cached:
        result["profile_text"] = (cached.get("profileText") or "").strip()
        result["profile_url"] = cached.get("profileUrl") or result["profile_url"]
        result["from_cache"] = True
        result["profile_links"] = cached.get("profileLinks") or []
        return result

    if not profile_url:
        return result

    # Prefer Apify actor (handles JS, auth, rate limits). Without it, skip fetch for social URLs to avoid 403/block.
    text, profile_links = _fetch_with_apify(profile_url)
    if not text and not os.environ.get(PROFILE_SCRAPER_ACTOR_ENV, "").strip():
        # No actor: only try simple fetch for non-social URLs (social often needs JS or returns 403)
        if not any(x in profile_url.lower() for x in ("reddit.com", "twitter.com", "linkedin.com", "facebook.com", "instagram.com")):
            text = _fetch_simple(profile_url)
        profile_links = []
    text = (text or "").strip()[:3000]
    result["profile_text"] = text
    result["profile_links"] = profile_links if isinstance(profile_links, list) else []
    if mongo_db is not None and (text or result["profile_links"]):
        set_cached_profile(mongo_db, lead.id, text, profile_url, result["profile_links"])
    return result
