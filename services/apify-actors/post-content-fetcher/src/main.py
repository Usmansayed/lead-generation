"""
Post Content Fetcher - Fetch a single URL and return main text content.
Stealth-hardened: anti-detection launch args, viewport, locale, optional playwright-stealth,
residential proxy, and human-like delays. Uses Playwright for social URLs; falls back to httpx.
"""
from __future__ import annotations

import asyncio
import random
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from apify import Actor

# Domains that typically need JavaScript (use Playwright first)
SOCIAL_DOMAINS = (
    "reddit.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "facebook.com",
    "linkedin.com",
)

# Chrome launch args to reduce automation detection (navigator.webdriver, infobars, etc.)
STEALTH_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-extensions",
    "--disable-infobars",
    "--no-first-run",
    "--enable-webgl",
    "--use-gl=swiftshader",
    "--enable-accelerated-2d-canvas",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
]

# Realistic viewport and locale
VIEWPORT = {"width": 1280, "height": 720}
LOCALE = "en-US"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)


def _is_social_url(url: str) -> bool:
    return any(d in url.lower() for d in SOCIAL_DOMAINS)


def _looks_like_js_wall(text: str) -> bool:
    if not text or len(text.strip()) < 100:
        return True
    lower = text.lower()
    if "javascript is not available" in lower or "enable javascript" in lower:
        return True
    if "please enable js" in lower or "switch to a supported browser" in lower:
        return True
    return False


def _extract_main_text(html: str) -> str:
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script, style, nav, footer, header"):
        tag.decompose()
    body = soup.find("body") or soup
    text = body.get_text(separator=" ", strip=True) if body else ""
    text = re.sub(r"\s+", " ", text).strip()
    return text[:5000]


async def _fetch_playwright(url: str, use_proxy: bool) -> str:
    """Fetch with Playwright: stealth args, viewport, proxy, optional playwright-stealth."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        Actor.log.warning("Playwright not available")
        return ""

    proxy_ctx: dict[str, Any] = {}
    if use_proxy:
        try:
            proxy_cfg = await Actor.create_proxy_configuration(groups=["RESIDENTIAL"])
            proxy_url = await proxy_cfg.new_url()
            if proxy_url:
                proxy_ctx = {"server": proxy_url}
                Actor.log.info("Using residential proxy (Playwright)")
        except Exception as e:
            Actor.log.warning(f"Proxy not available: {e}")

    try:
        # Optional: apply playwright-stealth for stronger anti-detection
        try:
            from playwright_stealth import Stealth
            playwright_runner = Stealth().use_async(async_playwright())
            Actor.log.info("Using playwright-stealth")
        except Exception:
            playwright_runner = async_playwright()

        async with playwright_runner as p:
            browser = await p.chromium.launch(
                headless=True,
                args=STEALTH_LAUNCH_ARGS,
            )
            try:
                ctx_opts: dict[str, Any] = {
                    "user_agent": USER_AGENT,
                    "viewport": VIEWPORT,
                    "locale": LOCALE,
                    "ignore_https_errors": True,
                }
                if proxy_ctx:
                    ctx_opts["proxy"] = proxy_ctx
                context = await browser.new_context(**ctx_opts)
                page = await context.new_page()
                # Human-like: short random delay before navigation
                await asyncio.sleep(random.uniform(0.5, 1.5))
                await page.goto(url, wait_until="commit", timeout=40000)
                await page.wait_for_timeout(int(random.uniform(2500, 4500)))
                html = await page.content()
                await page.close()
                await context.close()
            finally:
                await browser.close()
            return _extract_main_text(html)
    except Exception as e:
        Actor.log.warning(f"Playwright fetch failed: {e}")
        return ""


async def _fetch_httpx(url: str, use_proxy: bool) -> str:
    headers = {"User-Agent": USER_AGENT}
    proxy_url: str | None = None
    if use_proxy:
        try:
            proxy_cfg = await Actor.create_proxy_configuration(groups=["RESIDENTIAL"])
            proxy_url = await proxy_cfg.new_url()
            Actor.log.info("Using residential proxy (httpx)")
        except Exception as e:
            Actor.log.warning(f"Proxy not available: {e}")

    client_kwargs: dict[str, Any] = {
        "timeout": 25.0,
        "follow_redirects": True,
        "headers": headers,
        "verify": False,
    }
    if proxy_url:
        client_kwargs["proxy"] = proxy_url
    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return _extract_main_text(resp.text)
    except Exception as e:
        Actor.log.warning(f"Fetch failed: {e}")
        return ""


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        url = (inp.get("url") or "").strip()
        use_proxy = inp.get("useProxy", True)

        if not url:
            Actor.log.warning("No url in input")
            await Actor.push_data({"text": "", "content": "", "url": ""})
            return

        Actor.log.info(f"Fetching: {url[:80]}...")

        text = ""
        if _is_social_url(url):
            Actor.log.info("Social URL detected, using Playwright (stealth)")
            text = await _fetch_playwright(url, use_proxy)
            if not text or _looks_like_js_wall(text):
                Actor.log.info("Playwright empty/JS wall, trying httpx")
                text = await _fetch_httpx(url, use_proxy)
        else:
            text = await _fetch_httpx(url, use_proxy)
            if not text or _looks_like_js_wall(text):
                text = await _fetch_playwright(url, use_proxy)

        await Actor.push_data({"text": text, "content": text, "url": url})
        Actor.log.info(f"Done. Extracted {len(text)} chars")
