"""
Instagram-specific scraper (extensibility stub).

To add custom logic: implement PlatformHandler and register in REGISTRY.
Default behavior uses yt-dlp in metadata_extractor and downloader.
"""
from .base import PlatformHandler, REGISTRY


class InstagramHandler(PlatformHandler):
    """Example: override Instagram metadata or download if needed."""

    @property
    def platform_id(self) -> str:
        return "instagram"

    def extract_metadata(self, url: str):
        # Return None to use default yt-dlp extraction
        return None

    def download_media(self, url: str, output_dir: str, **kwargs):
        # Return None to use default yt-dlp download
        return None


def register():
    REGISTRY["instagram"] = InstagramHandler()
