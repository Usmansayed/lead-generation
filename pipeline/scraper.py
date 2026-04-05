"""
Powerful scraper: fetch emails from any domain.
- HTTP fallback (always): fetches domain + /contact, /about with urllib; extracts emails. No API key.
- Apify (when APIFY_TOKEN set): Contact Details + Website Crawler with proxy rotation and anti-bot.

When we have a domain we always try HTTP first or as fallback so we never return nothing just because Apify failed.
"""
from __future__ import annotations

import logging
import os
import re
import ssl
import urllib.error
import urllib.request
from typing import Any

_TIMEOUT = 12
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

_LOG = logging.getLogger(__name__)

# Actor IDs
ACTOR_CONTACT_DETAILS = "practicaltools/contact-details-scraper"
ACTOR_WEBSITE_CRAWLER = "apify/website-content-crawler"

# Env
APIFY_TOKEN_ENV = "APIFY_TOKEN"
APIFY_PROXY_GROUPS_ENV = "APIFY_PROXY_GROUPS"
APIFY_PROXY_COUNTRY_ENV = "APIFY_PROXY_COUNTRY"
APIFY_SCRAPER_RETRIES_ENV = "APIFY_SCRAPER_RETRIES"
APIFY_SESSION_ROTATIONS_ENV = "APIFY_SESSION_ROTATIONS"

# Email extraction (minimal, no dependency on email_finder)
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
SKIP_EMAIL_DOMAINS = (
    "example.com", "test@", "noreply@", "no-reply@", "@sentry", "sentry.io",
    "wixpress.com", "github.com", "facebook.com", "twitter.com", "linkedin.com",
    "youtube.com", "google.com", "apple.com", "amazon.com", "cloudflare",
    "schema.org", "w3.org", "gravatar.com", "googleapis.com", "gstatic.com",
)


def _proxy_config() -> dict[str, Any]:
    """Build Apify Proxy config: rotation, optional residential + country."""
    cfg: dict[str, Any] = {"useApifyProxy": True}
    groups = (os.environ.get(APIFY_PROXY_GROUPS_ENV) or "").strip().upper()
    if groups:
        cfg["apifyProxyGroups"] = [g.strip() for g in groups.split(",") if g.strip()]
    country = (os.environ.get(APIFY_PROXY_COUNTRY_ENV) or "").strip()[:2]
    if country:
        cfg["apifyProxyCountry"] = country
    return cfg


def _retries() -> int:
    try:
        return max(1, min(10, int(os.environ.get(APIFY_SCRAPER_RETRIES_ENV) or "5")))
    except ValueError:
        return 5


def _session_rotations() -> int:
    try:
        return max(1, min(20, int(os.environ.get(APIFY_SESSION_ROTATIONS_ENV) or "5")))
    except ValueError:
        return 5


def _client():
    """Apify client from APIFY_TOKEN."""
    token = (os.environ.get(APIFY_TOKEN_ENV) or "").strip()
    if not token:
        raise ValueError("APIFY_TOKEN is required for scraping")
    from apify_client import ApifyClient
    return ApifyClient(token)


def _normalize_domain(domain: str) -> str | None:
    domain = (domain or "").strip().lower()
    for p in ("https://", "http://", "www."):
        if domain.startswith(p):
            domain = domain[len(p):]
    if "/" in domain:
        domain = domain.split("/")[0]
    if "?" in domain:
        domain = domain.split("?")[0]
    if not re.match(r"^[a-z0-9][a-z0-9.-]+\.[a-z]{2,}$", domain):
        return None
    if any(x in domain for x in ("reddit.com", "facebook.com", "twitter.com", "linkedin.com", "instagram.com", "example.com")):
        return None
    return domain


def _extract_emails_from_text(text: str | None) -> set[str]:
    if not text or not text.strip():
        return set()
    found = set()
    for m in EMAIL_PATTERN.finditer(text):
        email = m.group(0).strip().lower()
        if any(skip in email for skip in SKIP_EMAIL_DOMAINS):
            continue
        if len(email) > 6 and "." in email.split("@")[-1]:
            found.add(email)
    return found


# -----------------------------------------------------------------------------
# HTTP fallback: fetch domain pages and extract emails (no Apify, highly reliable)
# -----------------------------------------------------------------------------

# Common paths where contact/team emails appear
_CONTACT_PATHS = (
    "",
    "/",
    "/contact",
    "/about",
    "/about-us",
    "/team",
    "/contact-us",
    "/get-in-touch",
    "/hire",
    "/hello",
    "/reach-us",
    "/reach",
    "/email",
    "/connect",
    "/support",
)

# Link href keywords to follow from homepage when initial fetch finds no emails
_LINK_KEYWORDS = ("contact", "about", "team", "reach", "hello", "hire", "connect", "support", "email")


def _fetch_url(url: str, ctx: ssl.SSLContext) -> str | None:
    """Fetch URL and return body or None."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=ctx) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            _LOG.debug("HTTP %s for %s: %s", e.code, url, e)
        return None
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        _LOG.debug("Fetch failed %s: %s", url, e)
        return None


def _extract_mailto_from_html(html: str) -> set[str]:
    """Extract emails from mailto: links (high confidence)."""
    found = set()
    # mailto:email or mailto:?to=email
    for m in re.finditer(r"mailto:\s*([^\"'?\s&]+)", html, re.IGNORECASE):
        raw = m.group(1).strip().lower()
        if "," in raw:
            raw = raw.split(",")[0].strip()
        if "@" in raw and "." in raw.split("@")[-1]:
            if not any(skip in raw for skip in SKIP_EMAIL_DOMAINS):
                found.add(raw)
    return found


def _find_contact_links(html: str, base_domain: str) -> list[str]:
    """From HTML find same-domain links whose href contains contact/about/team etc."""
    if not html or not base_domain:
        return []
    # href="..." or href='...'
    urls = set()
    for m in re.finditer(r'href\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE):
        href = (m.group(1) or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        href_lower = href.lower()
        if not any(kw in href_lower for kw in _LINK_KEYWORDS):
            continue
        if href.startswith("//"):
            full = "https:" + href
        elif href.startswith("http://") or href.startswith("https://"):
            full = href
        else:
            full = f"https://{base_domain}" + (href if href.startswith("/") else "/" + href)
        try:
            from urllib.parse import urlparse
            p = urlparse(full)
            host = (p.netloc or "").lower().replace("www.", "")
            if host == base_domain.replace("www.", "") or host.endswith("." + base_domain):
                urls.add(full)
        except Exception:
            pass
    return list(urls)[:8]


def fetch_domain_emails_http(domain: str) -> list[str]:
    """
    Highly reliable: fetch many domain pages and extract emails.
    - Tries homepage, www, and common paths (/contact, /about, /team, etc.).
    - Extracts mailto: links first, then regex on body.
    - If still no emails, parses homepage for contact/about links and fetches those.
    No API key, no Apify.
    """
    domain = _normalize_domain(domain)
    if not domain:
        return []
    base = f"https://{domain}"
    base_www = f"https://www.{domain}"
    urls_tried: set[str] = set()
    emails: set[str] = set()
    ctx = ssl.create_default_context()
    if hasattr(ctx, "check_hostname"):
        ctx.check_hostname = True

    # 1) Fixed set of URLs
    for path in _CONTACT_PATHS:
        for prefix in (base, base_www):
            url = prefix if path in ("", "/") else (prefix.rstrip("/") + path)
            if url in urls_tried:
                continue
            urls_tried.add(url)
            body = _fetch_url(url, ctx)
            if not body:
                continue
            emails |= _extract_mailto_from_html(body)
            emails |= _extract_emails_from_text(body)

    # 2) If nothing found, follow contact/about links from homepage
    if not emails:
        for url in (base, base_www):
            body = _fetch_url(url, ctx)
            if not body:
                continue
            for link in _find_contact_links(body, domain):
                if link in urls_tried:
                    continue
                urls_tried.add(link)
                sub = _fetch_url(link, ctx)
                if sub:
                    emails |= _extract_mailto_from_html(sub)
                    emails |= _extract_emails_from_text(sub)
                if len(emails) >= 5:
                    break
            if emails:
                break

    return list(emails)


# -----------------------------------------------------------------------------
# Contact Details Scraper (emails, phones, social from contact/about pages)
# -----------------------------------------------------------------------------


def run_contact_scraper(domain: str, *, max_pages: int = 20, timeout_secs: int = 180) -> list[dict[str, Any]]:
    """
    Run Contact Details Scraper on domain. Proxy + anti-bot from env.
    Returns list of dataset items (each can have emails, phones, social, url, text).
    """
    domain = _normalize_domain(domain)
    if not domain:
        return []
    try:
        client = _client()
        start_urls = [
            {"url": f"https://{domain}"},
            {"url": f"https://{domain}/contact"},
            {"url": f"https://{domain}/about"},
            {"url": f"https://{domain}/team"},
            {"url": f"https://www.{domain}"},
        ]
        run_input = {
            "startUrls": start_urls,
            "maxCrawlDepth": 1,
            "stayWithinDomain": True,
            "maxCrawlPages": max_pages,
            "extractFromText": True,
            "proxyConfiguration": _proxy_config(),
            "waitForLoadState": "domcontentloaded",
            "includeScriptContent": True,
        }
        run = client.actor(ACTOR_CONTACT_DETAILS).call(
            run_input=run_input,
            timeout_secs=timeout_secs,
        )
        if run.get("status") != "SUCCEEDED":
            _LOG.warning("Contact scraper run status: %s", run.get("status"))
            return []
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return []
        return list(client.dataset(dataset_id).iterate_items())
    except Exception as e:
        _LOG.warning("Contact scraper failed for %s: %s", domain, e)
        return []


# -----------------------------------------------------------------------------
# Website Content Crawler (full page text, markdown; JS support)
# -----------------------------------------------------------------------------


def run_website_crawler(
    start_urls: list[str],
    *,
    max_crawl_pages: int = 15,
    max_crawl_depth: int = 1,
    timeout_secs: int = 180,
) -> list[dict[str, Any]]:
    """
    Run Website Content Crawler on given URLs. Proxy, retries, session rotation from env.
    Returns list of dataset items (url, text, markdown, content).
    """
    if not start_urls:
        return []
    urls = [u.strip() for u in start_urls if u and u.strip().startswith(("http://", "https://"))]
    if not urls:
        return []
    try:
        client = _client()
        run_input = {
            "startUrls": [{"url": u} for u in urls[:10]],
            "maxCrawlDepth": max_crawl_depth,
            "maxCrawlPages": max_crawl_pages,
            "crawlerType": "playwright:firefox",
            "proxyConfiguration": _proxy_config(),
            "maxRequestRetries": _retries(),
            "maxSessionRotations": _session_rotations(),
            "requestTimeoutSecs": 90,
            "dynamicContentWaitSecs": 15,
            "removeCookieWarnings": True,
            "initialConcurrency": 2,
            "maxConcurrency": 4,
        }
        run = client.actor(ACTOR_WEBSITE_CRAWLER).call(
            run_input=run_input,
            timeout_secs=timeout_secs,
        )
        if run.get("status") != "SUCCEEDED":
            _LOG.warning("Website crawler run status: %s", run.get("status"))
            return []
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return []
        return list(client.dataset(dataset_id).iterate_items())
    except Exception as e:
        _LOG.warning("Website crawler failed: %s", e)
        return []


# -----------------------------------------------------------------------------
# High-level API
# -----------------------------------------------------------------------------


def scrape_domain_for_emails(domain: str) -> list[str]:
    """
    Get all emails from a domain. Always uses HTTP fallback (fetch homepage + contact/about).
    If APIFY_TOKEN is set, also runs Apify Contact Scraper + Website Crawler and merges results.
    """
    domain = _normalize_domain(domain)
    if not domain:
        return []
    emails: set[str] = set()
    # 1) HTTP fallback: always run so we get emails even when Apify fails or isn't configured
    emails.update(fetch_domain_emails_http(domain))
    # 2) Apify when available (adds more coverage, JS-rendered pages)
    if is_scraper_available():
        try:
            items = run_contact_scraper(domain)
            for item in items:
                for e in (item.get("emails") or []):
                    if isinstance(e, str) and "@" in e:
                        emails.add(e.strip().lower())
                    elif isinstance(e, dict) and e.get("address"):
                        emails.add(str(e.get("address")).strip().lower())
                text = item.get("text") or item.get("content") or ""
                emails |= _extract_emails_from_text(text)
            crawler_items = run_website_crawler(
                [f"https://{domain}", f"https://www.{domain}"],
                max_crawl_pages=15,
            )
            for item in crawler_items:
                text = item.get("text") or item.get("markdown") or item.get("content") or ""
                emails |= _extract_emails_from_text(text)
        except Exception as e:
            _LOG.debug("Apify scrape failed, HTTP results still used: %s", e)
    return list(emails)


def scrape_urls_for_content(
    urls: list[str],
    *,
    max_pages: int = 20,
    max_depth: int = 1,
) -> list[dict[str, Any]]:
    """
    Scrape given URLs and return content (url, text, markdown) per page.
    Uses Website Content Crawler with full proxy and anti-bot config.
    """
    return run_website_crawler(
        urls,
        max_crawl_pages=max_pages,
        max_crawl_depth=max_depth,
    )


def is_scraper_available() -> bool:
    """True if APIFY_TOKEN is set."""
    return bool((os.environ.get(APIFY_TOKEN_ENV) or "").strip())
