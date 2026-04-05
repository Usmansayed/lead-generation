"""
Normalize each platform's Apify actor output into the canonical lead schema.

Instagram, Facebook, Twitter (and similar) often don't provide username/author at scrape time.
We still store these posts (author name/handle may be "Unknown" / empty). They run through
relevance, static filter, and AI. User details (profile, contact) are resolved only after
the lead is AI-qualified (see profile_enrichment + contact_discovery).
"""
from __future__ import annotations
import hashlib
import re
from datetime import datetime
from typing import Any

from .models import Author, CanonicalLead


def _hash_id(platform: str, post_id: str) -> str:
    return hashlib.sha256(f"{platform}{post_id}".encode()).hexdigest()


def _normalize_timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            pass
    return datetime.utcnow()


def _post_id_from_url(url: str, platform: str) -> str:
    """Extract a stable post ID from URL when platform doesn't provide one."""
    if not url:
        return ""
    # Use full URL as fallback ID (will be hashed)
    if platform == "reddit" and "/comments/" in url:
        m = re.search(r"/comments/([a-z0-9]+)", url, re.I)
        if m:
            return m.group(1)
    if "linkedin.com/jobs/view" in url:
        m = re.search(r"/(\d+)(?:\?|$)", url)
        if m:
            return m.group(1)
    return url.strip()


# Keys that commonly hold post body/full content per platform (order: prefer full content first).
# Actors may use different names; we try all so we actually fetch the lead's post text.
_CONTENT_KEYS_BY_PLATFORM = {
    "reddit": ["selftext", "body", "text", "content", "description", "text_preview", "content_preview"],
    "linkedin": ["description", "jobDescription", "summary", "content", "body", "text", "text_preview", "content_preview"],
    "twitter": ["full_text", "text", "content", "body", "description", "text_preview", "content_preview"],
    "instagram": ["caption", "text", "description", "content", "body", "text_preview", "content_preview"],
    "facebook": ["message", "story", "description", "content", "body", "text", "text_preview", "content_preview"],
}
# Fallback: any platform
_CONTENT_KEYS_FALLBACK = [
    "selftext", "body", "text", "content", "description", "summary",
    "text_preview", "content_preview", "message", "story", "caption",
    "jobDescription", "full_text",
]
# Title-like keys (we always prefer to include these for context)
_TITLE_KEYS = ["title", "headline", "subject", "name"]


def _first_non_empty(item: dict, keys: list[str]) -> str:
    """Return the first non-empty string value from item for the given keys."""
    for k in keys:
        v = item.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _post_text(item: dict, platform: str) -> str:
    """Build full post text from whatever fields the actor returned. Tries many key names so we capture the lead's post."""
    parts = []
    # Title / headline first (often the only thing in search results)
    title = _first_non_empty(item, _TITLE_KEYS)
    if title:
        parts.append(title)
    # Full body: platform-specific keys then fallback
    content_keys = _CONTENT_KEYS_BY_PLATFORM.get(platform.lower(), _CONTENT_KEYS_FALLBACK)
    body = _first_non_empty(item, content_keys)
    if body and body != title:
        parts.append(body)
    # Platform-specific extras
    if platform.lower() == "linkedin" and item.get("company"):
        parts.append(f"Company: {item['company']}")
    return "\n\n".join(parts).strip() or "(no text)"


def normalize_reddit(item: dict[str, Any]) -> CanonicalLead | None:
    url = item.get("url") or ""
    post_id = _post_id_from_url(url, "reddit") or item.get("id") or url
    post_text = _post_text(item, "reddit")
    author_name = item.get("author", "Unknown")
    lead_id = _hash_id("reddit", post_id)
    return CanonicalLead(
        id=lead_id,
        platform="reddit",
        post_id=post_id,
        post_text=post_text,
        author=Author(
            name=author_name,
            handle=author_name,
            profile_url=item.get("author_url"),
        ),
        post_url=url,
        timestamp=_normalize_timestamp(item.get("created_utc")),
        keywords_matched=item.get("matched_keywords") or [],
        static_score=0,
        status="raw",
        created_at=_normalize_timestamp(item.get("scraped_at")),
        raw=item,
    )


def normalize_linkedin(item: dict[str, Any]) -> CanonicalLead | None:
    url = item.get("url") or ""
    post_id = _post_id_from_url(url, "linkedin") or url
    post_text = _post_text(item, "linkedin")
    author_name = item.get("company") or "Unknown"
    lead_id = _hash_id("linkedin", post_id)
    return CanonicalLead(
        id=lead_id,
        platform="linkedin",
        post_id=post_id,
        post_text=post_text,
        author=Author(name=author_name, handle=author_name, profile_url=url),
        post_url=url,
        timestamp=_normalize_timestamp(item.get("scraped_at")),
        keywords_matched=[],
        static_score=0,
        status="raw",
        created_at=_normalize_timestamp(item.get("scraped_at")),
        raw=item,
    )


def normalize_twitter(item: dict[str, Any]) -> CanonicalLead | None:
    """Twitter/Instagram/Facebook may not have author at scrape; we get user details after AI phase."""
    url = item.get("url") or ""
    post_id = _post_id_from_url(url, "twitter") or url
    post_text = _post_text(item, "twitter")
    author_name = item.get("author") or item.get("username") or "Unknown"
    author_handle = item.get("username") or item.get("author") or ""
    lead_id = _hash_id("twitter", post_id)
    return CanonicalLead(
        id=lead_id,
        platform="twitter",
        post_id=post_id,
        post_text=post_text,
        author=Author(name=author_name, handle=author_handle, profile_url=url or item.get("author_url")),
        post_url=url,
        timestamp=_normalize_timestamp(item.get("scraped_at")),
        keywords_matched=[],
        static_score=0,
        status="raw",
        created_at=_normalize_timestamp(item.get("scraped_at")),
        raw=item,
    )


def normalize_instagram(item: dict[str, Any]) -> CanonicalLead | None:
    """Author/username often missing at scrape; user details fetched after AI qualification."""
    url = item.get("url") or ""
    post_id = _post_id_from_url(url, "instagram") or url
    post_text = _post_text(item, "instagram")
    author_name = item.get("author") or item.get("username") or "Unknown"
    author_handle = item.get("username") or item.get("author") or ""
    lead_id = _hash_id("instagram", post_id)
    return CanonicalLead(
        id=lead_id,
        platform="instagram",
        post_id=post_id,
        post_text=post_text,
        author=Author(name=author_name, handle=author_handle, profile_url=url or item.get("profile_url") or item.get("author_url")),
        post_url=url,
        timestamp=_normalize_timestamp(item.get("scraped_at")),
        keywords_matched=[],
        static_score=0,
        status="raw",
        created_at=_normalize_timestamp(item.get("scraped_at")),
        raw=item,
    )


def normalize_facebook(item: dict[str, Any]) -> CanonicalLead | None:
    """Author/username often missing at scrape; user details fetched after AI qualification."""
    url = item.get("url") or ""
    post_id = _post_id_from_url(url, "facebook") or url
    post_text = _post_text(item, "facebook")
    author_name = item.get("author") or item.get("username") or "Unknown"
    author_handle = item.get("username") or item.get("author") or ""
    lead_id = _hash_id("facebook", post_id)
    return CanonicalLead(
        id=lead_id,
        platform="facebook",
        post_id=post_id,
        post_text=post_text,
        author=Author(name=author_name, handle=author_handle, profile_url=url or item.get("profile_url") or item.get("author_url")),
        post_url=url,
        timestamp=_normalize_timestamp(item.get("scraped_at")),
        keywords_matched=[],
        static_score=0,
        status="raw",
        created_at=_normalize_timestamp(item.get("scraped_at")),
        raw=item,
    )


def get_hash_id_for_item(platform: str, item: dict[str, Any]) -> str | None:
    """
    Extract post_id from raw item and return hash (same as CanonicalLead.id).
    Used for pre-filter dedup before normalization. Returns None if item is invalid.
    """
    url = (item.get("url") or "").strip()
    post_id = _post_id_from_url(url, platform) or item.get("id") or url
    if not post_id:
        return None
    return _hash_id(platform, str(post_id))


NORMALIZERS = {
    "reddit": normalize_reddit,
    "linkedin": normalize_linkedin,
    "twitter": normalize_twitter,
    "instagram": normalize_instagram,
    "facebook": normalize_facebook,
}


def normalize_item(platform: str, item: dict[str, Any]) -> CanonicalLead | None:
    fn = NORMALIZERS.get(platform.lower())
    if not fn:
        return None
    return fn(item)
