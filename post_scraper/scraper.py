"""
Main controller for the post_scraper content ingestion pipeline.
Orchestrates: platform detection → metadata extraction → media download → save → return result.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .downloader import download_media
from .linkedin_apify import is_linkedin_yt_dlp_error, scrape_linkedin_via_apify
from .linkedin_playwright import fetch_linkedin_video_playwright
from .metadata_extractor import extract_metadata
from .models import (
    PostMetadata,
    PostScraperError,
    PrivateOrDeletedError,
    ScrapedPost,
    UnsupportedPlatformError,
)
from .platform_detector import detect_platform, is_supported_platform
from .utils import generate_job_id, get_logger, get_output_dir, normalize_url

logger = get_logger()

# Default base directory for media output (can be overridden per call)
DEFAULT_BASE_DIR = None  # uses utils.DEFAULT_MEDIA_BASE


def scrape_post(
    url: str,
    *,
    base_dir: str | None = DEFAULT_BASE_DIR,
    job_id: str | None = None,
    download_video: bool = True,
    download_audio: bool = True,
    download_thumbnail: bool = True,
    cookies_file: str | None = None,
) -> ScrapedPost:
    """
    Ingest a social media post URL: detect platform, extract metadata, download media,
    save to a structured directory, and return a structured result.

    Workflow:
        1. Normalize URL and detect platform.
        2. If platform unsupported, return a failed ScrapedPost with error.
        3. Extract metadata (yt-dlp). On private/deleted → return failed ScrapedPost.
        4. Create output directory and download media.
        5. Save metadata.json into the job directory.
        6. Return ScrapedPost with paths and metadata.

    Args:
        url: Social media post URL (Instagram, YouTube, TikTok, Twitter/X, etc.).
        base_dir: Base directory for media output (default: env POST_SCRAPER_MEDIA_DIR or "media").
        job_id: Optional job id; if not provided, one is generated.
        download_video: Whether to download video.
        download_audio: Whether to extract audio to WAV.
        download_thumbnail: Whether to download thumbnail.
        cookies_file: Optional path to a cookies file (Netscape format) for LinkedIn,
            Instagram, etc. Can also set env POST_SCRAPER_COOKIES_FILE.

    Returns:
        ScrapedPost with platform, job_id, paths (media_path, thumbnail_path, etc.),
        metadata, success flag, and optional error message. Never raises; failures
        are returned as ScrapedPost(success=False, error="...").
    """
    url = normalize_url(url)
    if not url:
        return _fail(url or "(empty)", None, "URL is empty")
    jid = job_id or generate_job_id()
    logger.info("Scrape request url=%s job_id=%s", url, jid)

    # 1. Detect platform
    platform = detect_platform(url)
    logger.info("Platform detected: %s", platform)
    if not is_supported_platform(platform):
        return _fail(
            url,
            jid,
            f"Unsupported or unknown platform: {platform}",
            platform=platform,
        )

    cookies = cookies_file or os.environ.get("POST_SCRAPER_COOKIES_FILE")

    # LinkedIn: always try Playwright + network interception first (most reliable for posts)
    if platform == "linkedin":
        output_dir = get_output_dir(base_dir, jid)
        playwright_result = _try_linkedin_playwright(url, output_dir, jid, cookies)
        if playwright_result is not None:
            return playwright_result

    # 2. Extract metadata (may raise; we catch and return failed result)
    metadata = None
    try:
        metadata = extract_metadata(url, platform_hint=platform, cookies_file=cookies)
    except PrivateOrDeletedError as e:
        logger.warning("Post inaccessible (private/deleted): %s", e)
        return _fail(url, jid, str(e), platform=platform)
    except (PostScraperError, Exception) as e:
        # LinkedIn: yt-dlp often fails with "Unable to extract video"; try Apify if token set
        if platform == "linkedin" and is_linkedin_yt_dlp_error(e):
            fallback = _try_linkedin_apify(url, get_output_dir(base_dir, jid), jid)
            if fallback is not None:
                return fallback
            return _fail(
                url,
                jid,
                _linkedin_help_message(e),
                platform=platform,
            )
        if isinstance(e, PostScraperError):
            logger.exception("Metadata extraction failed for url=%s", url)
        else:
            logger.exception("Unexpected error during metadata extraction: %s", e)
        return _fail(url, jid, f"Metadata extraction failed: {e}", platform=platform)

    # 3. Output directory
    output_dir = get_output_dir(base_dir, jid)

    # 4. Download media
    try:
        paths = download_media(
            url,
            output_dir,
            download_video=download_video,
            download_audio=download_audio,
            download_thumbnail=download_thumbnail,
            cookies_file=cookies,
        )
    except PostScraperError as e:
        if platform == "linkedin" and is_linkedin_yt_dlp_error(e):
            fallback = _try_linkedin_apify(url, output_dir, jid, metadata=metadata)
            if fallback is not None:
                return fallback
        logger.warning("Download failed for url=%s: %s", url, e)
        _save_metadata_json(output_dir, metadata)
        return ScrapedPost(
            platform=platform,
            url=url,
            job_id=jid,
            metadata=metadata,
            output_dir=output_dir,
            success=False,
            error=str(e) if platform != "linkedin" else _linkedin_help_message(e),
        )
    except Exception as e:
        if platform == "linkedin" and is_linkedin_yt_dlp_error(e):
            fallback = _try_linkedin_apify(url, output_dir, jid, metadata=metadata)
            if fallback is not None:
                return fallback
        logger.exception("Unexpected error during download: %s", e)
        _save_metadata_json(output_dir, metadata)
        return ScrapedPost(
            platform=platform,
            url=url,
            job_id=jid,
            metadata=metadata,
            output_dir=output_dir,
            success=False,
            error=str(e) if platform != "linkedin" else _linkedin_help_message(e),
        )

    # 5. Parse image_paths string to list
    image_paths = []
    if paths.get("image_paths"):
        image_paths = [p.strip() for p in str(paths["image_paths"]).split(",") if p.strip()]

    # 6. Save metadata.json
    _save_metadata_json(output_dir, metadata)

    return ScrapedPost(
        platform=platform,
        url=url,
        job_id=jid,
        media_path=paths.get("video_path"),
        audio_path=paths.get("audio_path"),
        thumbnail_path=paths.get("thumbnail_path"),
        image_paths=image_paths,
        metadata=metadata,
        output_dir=output_dir,
        success=True,
    )


def _linkedin_help_message(original_error: Exception) -> str:
    """User-facing message when LinkedIn yt-dlp fails, with next steps."""
    return (
        "LinkedIn post video could not be extracted (yt-dlp known issue). "
        "We already try Playwright + network interception first. For private/restricted posts, "
        "set POST_SCRAPER_COOKIES_FILE (Netscape/JSON cookies) and ensure Playwright is installed. "
        "Optionally: pip install -U yt-dlp, or set APIFY_TOKEN for Apify fallback."
    )


def _try_linkedin_playwright(
    url: str,
    output_dir: str,
    job_id: str,
    cookies_file: str | None,
) -> ScrapedPost | None:
    """Fetch LinkedIn media via Playwright + network interception; return ScrapedPost on success."""
    result = fetch_linkedin_video_playwright(url, output_dir, cookies_file=cookies_file)
    if result is None or result.get("error"):
        return None
    meta = result.get("metadata")
    if meta and output_dir:
        _save_metadata_json(output_dir, meta)
    image_paths = result.get("image_paths") or []
    return ScrapedPost(
        platform="linkedin",
        url=url,
        job_id=job_id,
        media_path=result.get("video_path"),
        thumbnail_path=result.get("thumbnail_path"),
        image_paths=image_paths,
        metadata=meta,
        output_dir=output_dir,
        success=True,
    )


def _try_linkedin_apify(
    url: str,
    output_dir: str,
    job_id: str,
    metadata: PostMetadata | None = None,
) -> ScrapedPost | None:
    """If APIFY_TOKEN is set, run Apify LinkedIn actor and return ScrapedPost on success."""
    result = scrape_linkedin_via_apify(url, output_dir)
    if result is None or result.get("error"):
        return None
    meta = result.get("metadata") or metadata
    if meta is None:
        meta = PostMetadata(platform="linkedin", raw={"source": "apify", "url": url})
    if meta and output_dir:
        _save_metadata_json(output_dir, meta)
    return ScrapedPost(
        platform="linkedin",
        url=url,
        job_id=job_id,
        media_path=result.get("video_path"),
        thumbnail_path=result.get("thumbnail_path"),
        metadata=meta,
        output_dir=output_dir,
        success=True,
    )


def _fail(
    url: str,
    job_id: str,
    error: str,
    platform: str = "unknown",
) -> ScrapedPost:
    return ScrapedPost(
        platform=platform,
        url=url,
        job_id=job_id,
        success=False,
        error=error,
    )


def _save_metadata_json(output_dir: str, metadata: PostMetadata) -> None:
    path = Path(output_dir) / "metadata.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("Saved metadata to %s", path)
    except Exception as e:
        logger.warning("Could not write metadata.json: %s", e)
