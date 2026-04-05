"""
LinkedIn video fetch via Playwright + network interception + logged-in cookies.

Most reliable approach: run a real browser with your LinkedIn cookies, load the post
page, intercept network responses to capture the actual video URL, then download it.
Works when yt-dlp fails because the page structure changed.

Requires: pip install playwright && playwright install chromium
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .models import PostMetadata
from .utils import get_logger

logger = get_logger()

# Video URL patterns or content types we capture
VIDEO_EXT_PATTERN = re.compile(r"\.(mp4|m3u8|webm|mov)(?:\?|$)", re.IGNORECASE)
VIDEO_CONTENT_TYPES = ("video/mp4", "video/webm", "video/quicktime", "application/vnd.apple.mpegurl", "application/x-mpegurl")

# Image URL patterns or content types (profile photos, feed images)
IMAGE_EXT_PATTERN = re.compile(r"\.(jpg|jpeg|png|webp|gif)(?:\?|$)", re.IGNORECASE)
IMAGE_CONTENT_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")


def _load_cookies(cookies_file: str):
    """Load cookies from file. Supports Netscape format or JSON (list of Playwright-style dicts)."""
    path = Path(cookies_file)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return None
    # JSON: [{"name": "...", "value": "...", "domain": "...", "path": "/", ...}, ...]
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list) and data and isinstance(data[0], dict):
                out = []
                for c in data:
                    if "name" in c and "value" in c and ("domain" in c or "url" in c):
                        out.append({
                            "name": c["name"],
                            "value": c["value"],
                            "domain": c.get("domain") or (c.get("url") and "linkedin.com") or ".linkedin.com",
                            "path": c.get("path", "/"),
                            "expires": c.get("expires"),
                            "httpOnly": c.get("httpOnly", False),
                            "secure": c.get("secure", True),
                            "sameSite": c.get("sameSite", "Lax"),
                        })
                return out
        except json.JSONDecodeError:
            pass
    # Netscape format: domain\tflag\tpath\tsecure\texpires\tname\tvalue
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, path, secure, expires_str, name, value = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], "\t".join(parts[6:])
        if not domain or not name:
            continue
        try:
            expires = int(expires_str) if expires_str and expires_str != "0" else -1
        except ValueError:
            expires = -1
        if domain.startswith(".") is False and not domain.startswith("www."):
            domain = "." + domain
        entry = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": path or "/",
            "httpOnly": False,
            "secure": secure.upper() == "TRUE",
            "sameSite": "Lax",
        }
        if expires > 0:
            entry["expires"] = expires
        out.append(entry)
    return out if out else None


def _is_video_response(response) -> bool:
    """True if this response looks like a video (URL or content-type)."""
    try:
        url = response.url
        if VIDEO_EXT_PATTERN.search(url):
            return True
        ct = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
        if any(ct.startswith(t) for t in ("video/", "application/vnd.apple.mpegurl", "application/x-mpegurl")):
            return True
    except Exception:
        pass
    return False


def _is_image_response(response) -> bool:
    """True if this response looks like an image (URL or content-type)."""
    try:
        url = response.url
        if IMAGE_EXT_PATTERN.search(url):
            return True
        ct = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
        if any(ct.startswith(t) for t in IMAGE_CONTENT_TYPES):
            return True
    except Exception:
        pass
    return False


def fetch_linkedin_video_playwright(
    url: str,
    output_dir: str,
    *,
    cookies_file: str | None = None,
    headless: bool = True,
    timeout_ms: int = 45_000,
) -> dict | None:
    """
    Fetch a LinkedIn post video using Playwright: load page (optionally with cookies),
    intercept network to capture the video URL, download and save to output_dir.

    Returns:
        Dict with video_path, thumbnail_path (optional), metadata (PostMetadata), error (str or None).
        None if playwright is not installed or no usable video URL is captured.
    """
    # Cookies are optional (recommended for private / restricted content).
    cookies = None
    cookies_path = cookies_file or os.environ.get("POST_SCRAPER_COOKIES_FILE")
    if cookies_path and Path(cookies_path).exists():
        cookies = _load_cookies(cookies_path)
        if not cookies:
            logger.warning("LinkedIn Playwright: no cookies parsed from %s", cookies_path)
    else:
        logger.info("LinkedIn Playwright: no cookies file provided; browsing anonymously (public posts only).")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright not installed; pip install playwright && playwright install chromium")
        return None

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    # List of (url, content_type) for captured media responses
    captured_videos: list[tuple[str, str]] = []
    captured_images: list[str] = []

    def on_response(response):
        try:
            u = response.url
            ct = (response.headers.get("content-type") or "").split(";")[0].strip()
            if _is_video_response(response):
                if u and not any(u == x[0] for x in captured_videos):
                    captured_videos.append((u, ct))
                    logger.info("Captured LinkedIn video URL (content-type: %s): %s", ct, u[:80])
            elif _is_image_response(response):
                # Skip obvious profile photos; keep feed/post images
                if u and "licdn.com" in u and "profile-displayphoto" not in u and u not in captured_images:
                    captured_images.append(u)
                    logger.info("Captured LinkedIn image URL (content-type: %s): %s", ct, u[:80])
        except Exception as e:
            logger.debug("Response handler error: %s", e)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720},
            )
            if cookies:
                context.add_cookies(cookies)
            page = context.new_page()
            page.on("response", on_response)
            logger.info("Navigating to LinkedIn post (Playwright): %s", url[:80])
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Allow time for media to be requested
            page.wait_for_timeout(5000)
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms - 5000)
            except Exception:
                pass

            # ---- Extract post metadata (author, username from URL, caption, counts) ----
            author = None
            username_slug: str | None = None
            caption = None
            likes: int | None = None
            comments: int | None = None
            post_date: str | None = None

            try:
                # Meta tags
                try:
                    og_title = page.locator("meta[property='og:title']").get_attribute("content")
                except Exception:
                    og_title = None
                try:
                    og_desc = page.locator("meta[property='og:description']").get_attribute("content")
                except Exception:
                    og_desc = None
                try:
                    title_text = page.title()
                except Exception:
                    title_text = None

                if og_title:
                    pipe = og_title.rfind(" | ")
                    if pipe > 0:
                        author = og_title[pipe + 3 :].strip()
                    else:
                        author = og_title.replace("'s Post", "").strip()
                if og_desc and not caption:
                    caption = og_desc

                if title_text and not author:
                    # e.g. "Big lesson ... | Usman Sayed"
                    if "|" in title_text:
                        author = title_text.split("|")[-1].strip()

                # Username slug from URL: /posts/<username>_...
                try:
                    m_slug = re.search(r"linkedin\\.com/posts/([^_/?]+)", url)
                    if m_slug:
                        username_slug = m_slug.group(1)
                except Exception:
                    username_slug = None

                # Main card for richer text
                card_selectors = [
                    "[data-test-id='main-feed-activity-card']",
                    "[data-chameleon-result-urn]",
                    "article.feed-shared-update-v2",
                    "section.feed-shared-update-v2",
                    ".scaffold-feed__main",
                ]
                card = None
                for sel in card_selectors:
                    loc = page.locator(sel)
                    try:
                        if loc.count():
                            card = loc.first
                            break
                    except Exception:
                        continue

                if card:
                    commentary_selectors = [
                        "[data-test-id='main-feed-activity-card__commentary']",
                        ".feed-shared-inline-show-more-text",
                        ".feed-shared-text span[dir='ltr']",
                        "[dir='ltr']",
                    ]
                    for sel in commentary_selectors:
                        loc = card.locator(sel)
                        try:
                            if loc.count():
                                t = loc.first.inner_text().strip()
                                if t and len(t) > 20:
                                    caption = t
                                    break
                        except Exception:
                            continue
                    if not caption:
                        try:
                            t = card.inner_text().strip()
                            if t and len(t) > 20:
                                caption = t[:10000]
                        except Exception:
                            pass

                # Timestamp
                try:
                    time_loc = page.locator(
                        "time, [data-test-id='feed-timestamp'], .feed-shared-actor__sub-description, .update-components-actor__sub-description"
                    ).first
                    if time_loc().count():
                        post_date = time_loc().inner_text().strip()
                except Exception:
                    post_date = None

                # Social counts
                try:
                    social_selectors = [
                        "[data-test-id='social-actions']",
                        ".social-details-social-counts",
                        ".social-details-social-actions",
                        ".feed-shared-social-actions",
                    ]
                    for sel in social_selectors:
                        loc = page.locator(sel)
                        if loc.count():
                            txt = loc.first.inner_text()
                            if not txt:
                                continue
                            m_like = re.search(r"(\\d+)\\s*(reaction|like)", txt, re.IGNORECASE)
                            m_comment = re.search(r"(\\d+)\\s*comment", txt, re.IGNORECASE)
                            if m_like:
                                likes = int(m_like.group(1))
                            if m_comment:
                                comments = int(m_comment.group(1))
                            if likes or comments:
                                break
                except Exception:
                    pass

            except Exception as e:
                logger.debug("LinkedIn Playwright: metadata extraction failed: %s", e)

            # ---- Download video if present ----
            # Prefer .mp4 (by URL or content-type) over m3u8
            video_url = None
            for u, ct in captured_videos:
                if ".mp4" in u.lower() or (ct and "video/mp4" in ct.lower()):
                    video_url = u
                    break
            if not video_url and captured_videos:
                video_url = captured_videos[0][0]

            video_path: str | None = None
            if video_url:
                try:
                    res = context.request.get(video_url)
                    if res.status >= 400:
                        logger.warning("LinkedIn Playwright: video request failed HTTP %s", res.status)
                    else:
                        ext = ".mp4"
                        if ".m3u8" in video_url.lower():
                            ext = ".m3u8"
                        elif ".webm" in video_url.lower():
                            ext = ".webm"
                        out_video = out_path / f"video{ext}"
                        out_video.write_bytes(res.body())
                        logger.info("Saved LinkedIn video via Playwright: %s", out_video)
                        video_path = str(out_video.resolve())
                except Exception as e:
                    logger.debug("LinkedIn Playwright: failed to download video %s: %s", video_url[:80], e)

            # ---- Download images for OCR / analysis (excluding profile photos) ----
            image_paths: list[str] = []
            for idx, img_url in enumerate(captured_images, start=1):
                try:
                    res = context.request.get(img_url)
                    if res.status >= 400:
                        continue
                    body = res.body()
                    if not body:
                        continue
                    ext = ".jpg"
                    m = IMAGE_EXT_PATTERN.search(img_url)
                    if m:
                        ext = f".{m.group(1).lower()}"
                    else:
                        ct = (res.headers.get("content-type") or "").split(";")[0].strip().lower()
                        if "png" in ct:
                            ext = ".png"
                        elif "webp" in ct:
                            ext = ".webp"
                        elif "gif" in ct:
                            ext = ".gif"
                    out_img = out_path / f"image_{idx}{ext}"
                    out_img.write_bytes(body)
                    image_paths.append(str(out_img.resolve()))
                except Exception as e:
                    logger.debug("LinkedIn Playwright: failed to download image %s: %s", img_url[:80], e)

            hashtags = re.findall(r"#(\\w+)", caption or "") if caption else []

            meta = PostMetadata(
                platform="linkedin",
                author=author,
                author_id=username_slug,
                caption=caption,
                hashtags=hashtags,
                post_date=post_date,
                likes=likes,
                comments=comments,
                thumbnail_url=None,
                raw={"source": "playwright", "url": url},
            )

            return {
                "video_path": video_path,
                "image_paths": image_paths,
                "thumbnail_path": None,
                "metadata": meta,
                "error": None,
            }
        finally:
            browser.close()
