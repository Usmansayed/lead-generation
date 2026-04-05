"""
Metadata extraction from social media posts using yt-dlp.
Supports Instagram, YouTube, TikTok, Twitter/X, and other yt-dlp extractors.
"""
from __future__ import annotations

from pathlib import Path

from .models import MetadataExtractionError, PostMetadata, PrivateOrDeletedError
from .platform_detector import detect_platform
from .utils import get_logger

logger = get_logger()

try:
    import yt_dlp
except ImportError:
    yt_dlp = None  # type: ignore[assignment]


def _extract_hashtags(text: str | None) -> list[str]:
    if not text:
        return []
    import re
    return list(dict.fromkeys(re.findall(r"#(\w+)", text)))


def _normalize_epoch(ts: float | int | None) -> str | None:
    if ts is None:
        return None
    try:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return str(ts)


def extract_metadata(
    url: str,
    platform_hint: str | None = None,
    cookies_file: str | None = None,
) -> PostMetadata:
    """
    Extract metadata from a post URL using yt-dlp (info only, no download).

    Args:
        url: Post URL.
        platform_hint: Optional platform from detect_platform() for logging.
        cookies_file: Optional path to a Netscape-format cookies file for
            platforms that require login (e.g. LinkedIn, some Instagram).

    Returns:
        PostMetadata with author, caption, hashtags, counts, thumbnail_url, etc.

    Raises:
        MetadataExtractionError: If yt-dlp is not installed or extraction fails
            (e.g. private/deleted post).
    """
    if yt_dlp is None:
        raise MetadataExtractionError(
            "yt-dlp is not installed. Install with: pip install yt-dlp",
            url=url,
        )
    platform = platform_hint or detect_platform(url)
    logger.info("Extracting metadata for url=%s platform=%s", url, platform)

    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
    }
    if cookies_file and Path(cookies_file).exists():
        opts["cookiefile"] = cookies_file
        logger.debug("Using cookies file: %s", cookies_file)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        err_msg = str(e).lower()
        if "private" in err_msg or "removed" in err_msg or "deleted" in err_msg or "unavailable" in err_msg:
            raise PrivateOrDeletedError(
                f"Post is private, deleted, or unavailable: {e}",
                url=url,
            )
        raise MetadataExtractionError(
            f"Metadata extraction failed: {e}",
            url=url,
        )

    if not info:
        raise MetadataExtractionError("No metadata returned for URL", url=url)

    # Normalize fields from yt-dlp info (varies by extractor)
    uploader = info.get("uploader") or info.get("channel") or info.get("creator")
    uploader_id = info.get("uploader_id") or info.get("channel_id") or info.get("creator_id")
    caption = info.get("description") or info.get("title") or ""
    hashtags = _extract_hashtags(caption)
    # Some extractors use upload_date (YYYYMMDD), others timestamp
    post_date = info.get("upload_date")
    if post_date and len(str(post_date)) == 8:
        try:
            y, m, d = str(post_date)[:4], str(post_date)[4:6], str(post_date)[6:8]
            post_date = f"{y}-{m}-{d}"
        except Exception:
            pass
    if not post_date:
        post_date = _normalize_epoch(info.get("timestamp"))
    likes = info.get("like_count") or info.get("likes")
    comments = info.get("comment_count") or info.get("comments")
    thumbnail = info.get("thumbnail")

    meta = PostMetadata(
        platform=platform,
        author=uploader,
        author_id=uploader_id,
        caption=caption or None,
        hashtags=hashtags,
        post_date=post_date,
        likes=int(likes) if likes is not None else None,
        comments=int(comments) if comments is not None else None,
        thumbnail_url=thumbnail,
        raw=dict(info),
    )
    logger.info("Metadata extraction succeeded for url=%s author=%s", url, meta.author)
    return meta
