"""
Data models for the post_scraper content ingestion pipeline.
Structured types for metadata, scraped results, and errors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# Supported platforms (extensible)
Platform = str  # "instagram" | "youtube" | "tiktok" | "twitter" | "unknown"


@dataclass
class PostMetadata:
    """Structured metadata extracted from a social media post."""

    platform: str
    author: Optional[str] = None
    author_id: Optional[str] = None
    caption: Optional[str] = None
    hashtags: list[str] = field(default_factory=list)
    post_date: Optional[str] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    thumbnail_url: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "author": self.author,
            "author_id": self.author_id,
            "caption": self.caption,
            "hashtags": self.hashtags,
            "post_date": self.post_date,
            "likes": self.likes,
            "comments": self.comments,
            "thumbnail_url": self.thumbnail_url,
            "raw": self.raw,
        }


@dataclass
class ScrapedPost:
    """Result of scraping a single post: paths and metadata."""

    platform: str
    url: str
    job_id: str
    media_path: Optional[str] = None
    audio_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    image_paths: list[str] = field(default_factory=list)
    metadata: Optional[PostMetadata] = None
    output_dir: Optional[str] = None
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "url": self.url,
            "job_id": self.job_id,
            "media_path": self.media_path,
            "audio_path": self.audio_path,
            "thumbnail_path": self.thumbnail_path,
            "image_paths": self.image_paths,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "output_dir": self.output_dir,
            "success": self.success,
            "error": self.error,
        }


# --- Error types for clear handling ---


class PostScraperError(Exception):
    """Base exception for post_scraper module."""

    def __init__(self, message: str, url: Optional[str] = None):
        self.url = url
        super().__init__(message)


class UnsupportedPlatformError(PostScraperError):
    """URL belongs to an unsupported or unknown platform."""

    pass


class PrivateOrDeletedError(PostScraperError):
    """Post is private, deleted, or inaccessible."""

    pass


class DownloadError(PostScraperError):
    """Media download failed."""

    pass


class MetadataExtractionError(PostScraperError):
    """Failed to extract metadata from the post."""

    pass
