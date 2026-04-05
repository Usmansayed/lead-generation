"""
post_scraper: Content ingestion pipeline for social media posts.

Ingest a post URL → detect platform → extract metadata → download media →
save in a structured directory for downstream processing (OCR, transcription, etc.).

Usage:
    from post_scraper import scrape_post

    result = scrape_post("https://www.instagram.com/reel/xxx/")
    if result.success:
        print(result.media_path, result.metadata)
    else:
        print(result.error)
"""
from .models import (
    DownloadError,
    MetadataExtractionError,
    PostMetadata,
    PostScraperError,
    PrivateOrDeletedError,
    ScrapedPost,
    UnsupportedPlatformError,
)
from .platform_detector import (
    detect_platform,
    is_supported_platform,
    list_supported_platforms,
)
from .scraper import scrape_post

__all__ = [
    "scrape_post",
    "detect_platform",
    "is_supported_platform",
    "list_supported_platforms",
    "ScrapedPost",
    "PostMetadata",
    "PostScraperError",
    "UnsupportedPlatformError",
    "PrivateOrDeletedError",
    "DownloadError",
    "MetadataExtractionError",
]
