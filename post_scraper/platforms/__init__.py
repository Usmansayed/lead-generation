"""
Platform-specific scrapers (extensibility layer).

Register custom extractors or download logic per platform by implementing
PlatformHandler and adding to REGISTRY. The main scraper uses yt-dlp by default;
platform handlers can override metadata extraction or download behavior.
"""
from .base import PlatformHandler, REGISTRY, get_handler

__all__ = ["PlatformHandler", "REGISTRY", "get_handler"]
