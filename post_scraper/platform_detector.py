"""
Platform detection from social media post URLs.
Maps URL domains to platform identifiers for routing to platform-specific logic.
All detection and supported-list live here so we can fetch from all major platforms.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import Platform

# Single source of truth: platforms we support (detection + yt-dlp extraction)
SUPPORTED_PLATFORMS = (
    "instagram",
    "youtube",
    "tiktok",
    "twitter",
    "facebook",
    "reddit",
    "linkedin",
    "vimeo",
    "pinterest",
    "tumblr",
)

# Domain patterns: (regex pattern, platform_id). Order matters for overlapping domains.
_DOMAIN_PATTERNS: list[tuple[str, str]] = [
    (r"^(?:www\.)?instagram\.com$", "instagram"),
    (r"^(?:www\.)?(?:youtube\.com|youtu\.be)$", "youtube"),
    (r"^(?:www\.)?(?:vm\.)?tiktok\.com$", "tiktok"),
    (r"^(?:www\.)?(?:twitter\.com|x\.com)$", "twitter"),
    (r"^(?:www\.)?facebook\.com$", "facebook"),
    (r"^(?:www\.)?fb\.(?:watch|reel)$", "facebook"),
    (r"^(?:www\.)?reddit\.com$", "reddit"),
    (r"^(?:www\.)?linkedin\.com$", "linkedin"),
    (r"^(?:www\.)?vimeo\.com$", "vimeo"),
    (r"^(?:www\.)?pinterest\.(?:com|[a-z]{2})$", "pinterest"),
    (r"^(?:www\.)?tumblr\.com$", "tumblr"),
]

_COMPILED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p, re.IGNORECASE), platform) for p, platform in _DOMAIN_PATTERNS
]


def detect_platform(url: str) -> Platform:
    """
    Determine which platform a URL belongs to.

    Args:
        url: Full post URL (e.g. https://www.instagram.com/reel/xxx/).

    Returns:
        Platform identifier (e.g. instagram, youtube, linkedin) or "unknown".
    """
    if not url or not url.strip():
        return "unknown"
    try:
        parsed = urlparse(url.strip())
        netloc = (parsed.netloc or "").lower().strip()
        if not netloc:
            return "unknown"
        host = netloc.split(":")[0]
        for pattern, platform in _COMPILED:
            if pattern.search(host):
                return platform
        return "unknown"
    except Exception:
        return "unknown"


def is_supported_platform(platform: Platform) -> bool:
    """Return True if the platform is supported for scraping (we detect it and yt-dlp can extract)."""
    return platform in SUPPORTED_PLATFORMS


def list_supported_platforms() -> tuple[str, ...]:
    """Return the list of supported platform IDs (for docs/API)."""
    return SUPPORTED_PLATFORMS
