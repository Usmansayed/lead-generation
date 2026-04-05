"""
YouTube-specific scraper (extensibility stub).

To add custom logic: implement PlatformHandler and register in REGISTRY.
Default behavior uses yt-dlp in metadata_extractor and downloader.
"""
from .base import PlatformHandler, REGISTRY


class YouTubeHandler(PlatformHandler):
    """Example: override YouTube metadata or download if needed."""

    @property
    def platform_id(self) -> str:
        return "youtube"

    def extract_metadata(self, url: str):
        return None

    def download_media(self, url: str, output_dir: str, **kwargs):
        return None


def register():
    REGISTRY["youtube"] = YouTubeHandler()
