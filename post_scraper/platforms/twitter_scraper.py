"""
Twitter/X-specific scraper (extensibility stub).

To add custom logic: implement PlatformHandler and register in REGISTRY.
Default behavior uses yt-dlp in metadata_extractor and downloader.
"""
from .base import PlatformHandler, REGISTRY


class TwitterHandler(PlatformHandler):
    """Example: override Twitter/X metadata or download if needed."""

    @property
    def platform_id(self) -> str:
        return "twitter"

    def extract_metadata(self, url: str):
        return None

    def download_media(self, url: str, output_dir: str, **kwargs):
        return None


def register():
    REGISTRY["twitter"] = TwitterHandler()
