"""
LinkedIn fallback via Apify when yt-dlp fails (e.g. "Unable to extract video").

yt-dlp's LinkedIn extractor often fails on post videos. If APIFY_TOKEN is set,
we run the Apify actor pocesar/download-linkedin-video, fetch the chunked video
from the Key-Value store, and save as video.mp4 in the job directory.

Requires: pip install apify-client
"""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

from .models import PostMetadata
from .utils import get_logger

logger = get_logger()

# Apify actor for LinkedIn video download (chunked to KVS)
LINKEDIN_VIDEO_ACTOR_ID = "pocesar/download-linkedin-video"


def _is_linkedin_extraction_error(err: Exception) -> bool:
    """True if this is the known yt-dlp LinkedIn 'Unable to extract' failure."""
    msg = (str(err) or "").lower()
    return "linkedin" in msg and ("unable to extract" in msg or "unable to extract video" in msg)


def scrape_linkedin_via_apify(
    url: str,
    output_dir: str,
    *,
    apify_token: str | None = None,
) -> dict | None:
    """
    Try to get LinkedIn post video via Apify actor. Returns None if token missing
    or actor run fails; otherwise returns a dict with video_path and minimal metadata.

    Returned dict: video_path, thumbnail_path (optional), metadata (PostMetadata), error (str or None).
    """
    token = (apify_token or os.environ.get("APIFY_TOKEN") or "").strip()
    if not token:
        return None
    try:
        from apify_client import ApifyClient
    except ImportError:
        logger.warning("apify-client not installed; LinkedIn Apify fallback disabled")
        return None

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    video_file = out_path / "video.mp4"

    client = ApifyClient(token)
    run_input = {
        "startUrls": [{"url": url}],
        "proxy": {"useApifyProxy": True},
        "maxRequestRetries": 5,
    }
    logger.info("Running Apify LinkedIn actor for url=%s", url)
    run = client.actor(LINKEDIN_VIDEO_ACTOR_ID).call(run_input=run_input)
    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        logger.warning("Apify LinkedIn run produced no dataset")
        return {"video_path": None, "metadata": None, "error": "Apify run produced no dataset"}

    items = list(client.dataset(dataset_id).iterate_items())
    if not items:
        logger.warning("Apify LinkedIn dataset empty")
        return {"video_path": None, "metadata": None, "error": "No video in Apify result"}

    first = items[0]
    if first.get("#error"):
        return {"video_path": None, "metadata": None, "error": first.get("error", "Apify actor reported error")}

    parts_url = first.get("partsUrl")
    if not parts_url:
        return {"video_path": None, "metadata": None, "error": "No partsUrl in Apify result"}

    # Fetch KVS record: { parts: [url, ...], length, contentType }
    req = urllib.request.Request(parts_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        import json as _json
        data = _json.load(resp)
    parts = data.get("parts") or []
    if not parts:
        return {"video_path": None, "metadata": None, "error": "No video parts in store"}

    # Download and concatenate
    with open(video_file, "wb") as f:
        for i, part_url in enumerate(parts):
            preq = urllib.request.Request(part_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(preq, timeout=120) as pr:
                f.write(pr.read())
            logger.debug("Downloaded LinkedIn video part %s/%s", i + 1, len(parts))

    logger.info("LinkedIn video saved via Apify: %s", video_file)
    meta = PostMetadata(
        platform="linkedin",
        author=None,
        author_id=None,
        caption=None,
        hashtags=[],
        post_date=None,
        likes=None,
        comments=None,
        thumbnail_url=None,
        raw={"source": "apify", "url": url, "actor": LINKEDIN_VIDEO_ACTOR_ID},
    )
    return {
        "video_path": str(video_file.resolve()),
        "thumbnail_path": None,
        "metadata": meta,
        "error": None,
    }


def is_linkedin_yt_dlp_error(err: Exception) -> bool:
    """Use this to decide whether to try the Apify fallback."""
    return _is_linkedin_extraction_error(err)
