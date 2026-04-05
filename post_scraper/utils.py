"""
Shared utilities: job IDs, paths, logging.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

# Default base directory for downloaded media: inside this package (override via env)
_PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_MEDIA_BASE = os.environ.get("POST_SCRAPER_MEDIA_DIR", str(_PACKAGE_DIR / "media"))

_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """Return the module logger, configuring it once."""
    global _logger
    if _logger is None:
        _logger = logging.getLogger("post_scraper")
        if not _logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            )
            _logger.addHandler(handler)
            _logger.setLevel(logging.INFO)
    return _logger


def generate_job_id() -> str:
    """Generate a unique job id for a scrape run (safe for directory names)."""
    return uuid.uuid4().hex[:12]


def get_output_dir(base_dir: str | None, job_id: str) -> str:
    """
    Return the absolute output directory for this job.
    Creates the directory if it does not exist.
    """
    base = (base_dir or DEFAULT_MEDIA_BASE).strip() or DEFAULT_MEDIA_BASE
    out = Path(base).resolve() / job_id
    out.mkdir(parents=True, exist_ok=True)
    return str(out)


def normalize_url(url: str) -> str:
    """Trim and optionally normalize URL for consistency."""
    return (url or "").strip()
