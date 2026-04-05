"""
Base type and registry for platform-specific scrapers.
Override extract_metadata or download_media per platform by registering a handler.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models import PostMetadata, ScrapedPost

REGISTRY: dict[str, "PlatformHandler"] = {}


def get_handler(platform: str) -> "PlatformHandler | None":
    """Return the registered handler for a platform, or None to use default (yt-dlp)."""
    return REGISTRY.get(platform)


class PlatformHandler(ABC):
    """Override metadata extraction or download for a specific platform."""

    @property
    @abstractmethod
    def platform_id(self) -> str:
        """Platform identifier (e.g. 'instagram', 'youtube')."""
        ...

    def extract_metadata(self, url: str) -> "PostMetadata | None":
        """
        Optionally extract metadata. Return None to fall back to default (yt-dlp).
        """
        return None

    def download_media(
        self,
        url: str,
        output_dir: str,
        **kwargs: Any,
    ) -> dict[str, str | None] | None:
        """
        Optionally perform download. Return None to fall back to default (yt-dlp).
        Return a dict with keys: video_path, audio_path, thumbnail_path, image_paths.
        """
        return None
