"""
Contact discovery: find email (or other contact) ONLY after lead passes AI filter.
Sources: (1) post text, (2) profile text, (3) Hunter.io with smart extraction.
Hunter flow: LLM extracts company_name, website, person_name from message -> domain discovery -> Email Finder or Domain Search.
Set HUNTER_API_KEY in .env to enable Hunter enrichment.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

# Simple email regex (good enough for extraction from text)
EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)

# Domain-like pattern (crude: word.word.tld)
DOMAIN_PATTERN = re.compile(
    r"\b([a-zA-Z0-9][-a-zA-Z0-9]*\.(?:com|net|org|io|co|biz|info|dev)[a-zA-Z0-9./?#-]*)\b"
)
# Full URL pattern (capture host part)
URL_PATTERN = re.compile(
    r"https?://(?:www\.)?([a-zA-Z0-9][-a-zA-Z0-9.]*\.[a-zA-Z]{2,})(?:/[\w./?#-]*)?",
    re.IGNORECASE,
)
SKIP_DOMAINS = (
    "reddit.com", "facebook.com", "twitter.com", "linkedin.com", "instagram.com",
    "youtube.com", "tiktok.com", "example.com", "google.com", "apple.com", "amazon.com",
)

HUNTER_API_KEY_ENV = "HUNTER_API_KEY"
_LOG = logging.getLogger(__name__)


def _extract_first_email(text: str | None) -> str | None:
    """Return first valid-looking email in text, or None."""
    if not text or not text.strip():
        return None
    match = EMAIL_PATTERN.search(text)
    if not match:
        return None
    email = match.group(0).strip().lower()
    # Skip common false positives
    if any(skip in email for skip in ("example.com", "test@", "noreply@", "no-reply@", "@sentry")):
        return None
    return email


def _extract_domain(text: str | None) -> str | None:
    """Extract first plausible domain from text (e.g. company website)."""
    if not text or not text.strip():
        return None
    match = DOMAIN_PATTERN.search(text)
    if not match:
        return None
    domain = match.group(1).lower()
    # Strip path/query
    if "/" in domain:
        domain = domain.split("/")[0]
    if "?" in domain:
        domain = domain.split("?")[0]
    if any(skip in domain for skip in ("example.com", "facebook.com", "twitter.com", "reddit.com", "linkedin.com", "instagram.com")):
        return None
    return domain


def _extract_all_domains_from_text(text: str | None, max_domains: int = 5) -> list[str]:
    """
    Extract all plausible company/website domains from text (URLs and bare domains).
    Profile or post often contains "Website: mycompany.com" or "https://mycompany.com".
    Returns list of unique domains, excluding social networks; profile-first use case.
    """
    if not text or not text.strip():
        return []
    seen: set[str] = set()
    out: list[str] = []
    # 1) Full URLs first (most reliable)
    for m in URL_PATTERN.finditer(text):
        raw = m.group(1).lower()
        if "/" in raw:
            raw = raw.split("/")[0]
        if "?" in raw:
            raw = raw.split("?")[0]
        if raw in seen:
            continue
        if any(skip in raw for skip in SKIP_DOMAINS):
            continue
        if len(raw) > 4 and "." in raw:
            seen.add(raw)
            out.append(raw)
            if len(out) >= max_domains:
                return out
    # 2) Bare domain-like strings
    for m in DOMAIN_PATTERN.finditer(text):
        domain = m.group(1).lower()
        if "/" in domain:
            domain = domain.split("/")[0]
        if "?" in domain:
            domain = domain.split("?")[0]
        if domain in seen:
            continue
        if any(skip in domain for skip in SKIP_DOMAINS):
            continue
        seen.add(domain)
        out.append(domain)
        if len(out) >= max_domains:
            return out
    return out


def _extract_name_parts(author: Any) -> tuple[str, str]:
    """Return (first_name, last_name) from author.name or handle."""
    name = ""
    if hasattr(author, "name") and author.name:
        name = str(author.name).strip()
    elif hasattr(author, "handle") and author.handle:
        name = str(author.handle).strip().lstrip("@")
    if not name:
        return "", ""
    parts = name.split(None, 1)
    first = (parts[0] or "").strip()
    last = (parts[1] or "").strip() if len(parts) > 1 else ""
    return first, last


def _parse_name_into_first_last(full_name: str) -> tuple[str, str]:
    """Split full name into first and last. Handles single names (use as first)."""
    full_name = (full_name or "").strip()
    if not full_name:
        return "", ""
    parts = full_name.split(None, 1)
    first = (parts[0] or "").strip()
    last = (parts[1] or "").strip() if len(parts) > 1 else ""
    return first, last


def _is_realistic_name(name: str) -> bool:
    """Heuristic: looks like a real name (not Reddit handle like Wrong-Material-7435)."""
    if not name or len(name) < 2:
        return False
    # Skip handles with numbers, hyphens, underscores
    if re.search(r"\d|[-_]{2,}", name):
        return False
    # Prefer names that look like "First Last"
    words = name.split()
    return all(w.isalpha() and len(w) > 1 for w in words[:2])


def _llm_extract_contact_info(
    post_text: str,
    profile_text: str,
    web_context: str,
    author_handle: str,
) -> dict[str, str]:
    """
    Use LLM to understand the message and extract company/website/person for Hunter.
    Returns {company_name, company_website, person_full_name} with empty strings if not found.
    """
    from .llm_client import call_llm, has_llm_config

    if not has_llm_config():
        return {"company_name": "", "company_website": "", "person_full_name": ""}

    combined = f"""
POST: {post_text or ''}

PROFILE: {profile_text or ''}

SEARCH CONTEXT: {web_context or ''}

AUTHOR HANDLE: {author_handle or ''}

From the above, extract (if mentioned):
1. company_name: The business/company/project name the person runs or works for (e.g. "Acme Inc", "MyStartup").
2. company_website: A full URL or domain of their company website (e.g. acme.com or https://acme.com).
3. person_full_name: The person's real full name if mentioned or inferrable (e.g. "John Smith"), NOT the author handle.

Reply in JSON only: {"company_name":"...","company_website":"...","person_full_name":"..."}
Use empty string for any field you cannot confidently infer. Be concise.
""".strip()

    try:
        out = call_llm(combined, temperature=0.1)
        if not out:
            return {"company_name": "", "company_website": "", "person_full_name": ""}
        out = out.strip()
        # Handle markdown code blocks
        if "```" in out:
            out = re.sub(r"```\w*\n?", "", out).strip()
        data = json.loads(out)
        return {
            "company_name": str(data.get("company_name", "") or "").strip()[:120],
            "company_website": str(data.get("company_website", "") or "").strip()[:200],
            "person_full_name": str(data.get("person_full_name", "") or "").strip()[:80],
        }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        _LOG.debug("LLM contact extraction failed: %s", e)
        return {"company_name": "", "company_website": "", "person_full_name": ""}


def _domain_from_url(url_or_domain: str) -> str | None:
    """Extract clean domain from URL or domain string."""
    s = (url_or_domain or "").strip().lower()
    if not s:
        return None
    # Remove protocol
    for p in ("https://", "http://", "www."):
        if s.startswith(p):
            s = s[len(p):]
    # Take host part only
    if "/" in s:
        s = s.split("/")[0]
    if "?" in s:
        s = s.split("?")[0]
    # Validate
    if any(skip in s for skip in ("reddit.com", "facebook.com", "twitter.com", "linkedin.com", "instagram.com", "example.com")):
        return None
    if "." in s and len(s) > 4:
        return s
    return None


def _search_domain_for_company(company_name: str) -> str | None:
    """Web search for company website and extract domain from results."""
    if not company_name or len(company_name) < 2:
        return None
    try:
        from .web_research import _duckduckgo_search, _tavily_search
        query = f"{company_name} official website"
        api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
        if api_key:
            results = _tavily_search(query[:200], api_key)
            text = " ".join((r.get("content") or r.get("url") or "") for r in results[:5])
        else:
            results = _duckduckgo_search(query[:200], max_results=5)
            text = " ".join((r.get("href") or r.get("body") or "") for r in results[:5])
        return _extract_domain(text) or _domain_from_url(text)
    except Exception:
        return None


def _hunter_email_finder(domain: str, first_name: str, last_name: str) -> str | None:
    """
    Use Hunter.io Email Finder API to get professional email from domain + name.
    Returns email or None.
    """
    api_key = os.environ.get(HUNTER_API_KEY_ENV, "").strip()
    if not api_key or not domain or not first_name:
        return None
    try:
        import urllib.request
        import urllib.parse
        import json

        params = urllib.parse.urlencode({
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name,
            "api_key": api_key,
        })
        url = f"https://api.hunter.io/v2/email-finder?{params}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        d = data.get("data") or {}
        email = (d.get("email") or "").strip()
        return email if email and "@" in email else None
    except Exception:
        return None


def _hunter_domain_search(domain: str | None = None, company: str | None = None) -> str | None:
    """
    Hunter Domain Search: returns emails at domain (or company). Uses domain OR company.
    Picks best email: personal first, then hello@, contact@, info@.
    """
    api_key = os.environ.get(HUNTER_API_KEY_ENV, "").strip()
    if not api_key or (not domain and not company):
        return None
    try:
        import urllib.request
        import urllib.parse
        import json as _json

        params = {"api_key": api_key}
        if domain:
            params["domain"] = domain.strip().lower()
        if company:
            params["company"] = company.strip()
        url = f"https://api.hunter.io/v2/domain-search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        emails = (data.get("data") or {}).get("emails") or []
        if not emails:
            return None
        # Prefer personal, then hello@, contact@, info@, then first
        preferred = ("hello", "contact", "info", "hi")
        for e in emails:
            val = (e.get("value") or "").strip().lower()
            if not val or "@" not in val:
                continue
            local = val.split("@")[0]
            if e.get("type") == "personal":
                return val
        for p in preferred:
            for e in emails:
                val = (e.get("value") or "").strip().lower()
                local = val.split("@")[0] if "@" in val else ""
                if local == p:
                    return val
        return (emails[0].get("value") or "").strip() if emails else None
    except Exception:
        return None


def get_contact_for_lead(
    lead: Any,
    profile_data: dict[str, Any] | None = None,
    web_context: str | None = None,
) -> str | None:
    """
    Find an email to contact this lead. Only run AFTER lead passes AI filter.
    Primary: Email Research (detective) — AI extracts clues from post, plans searches,
    runs web search + Apify scraping, then AI verdict. Optional: Hunter API if configured.
    """
    post_text = getattr(lead, "post_text", None) or (lead.get("postText") if isinstance(lead, dict) else None)
    profile_text = (profile_data or {}).get("profile_text") or ""

    # 1) Direct from post or profile
    email = _extract_first_email(post_text)
    if email:
        return email
    email = _extract_first_email(profile_text)
    if email:
        return email

    # 1b) Profile-first website scrape: use explicit profile links first (actor may return "Website" hrefs), then domains from text
    from .scraper import fetch_domain_emails_http

    def _scrape_domain_for_email(text: str, max_domains: int = 4) -> str | None:
        seen: set[str] = set()
        for candidate_domain in (_extract_all_domains_from_text(text, max_domains=max_domains) if text else []):
            dom = _domain_from_url(candidate_domain) or (candidate_domain if "." in candidate_domain else None)
            if not dom or dom in seen:
                continue
            seen.add(dom)
            if any(skip in dom.lower() for skip in SKIP_DOMAINS):
                continue
            try:
                http_emails = fetch_domain_emails_http(dom)
            except Exception:
                http_emails = []
            if http_emails:
                for prefix in ("hello", "contact", "team", "info", "hi", "reach"):
                    for e in http_emails:
                        if e.split("@")[0] == prefix:
                            return e
                return http_emails[0]
        return None

    # Prefer explicit profile links (e.g. "Website" link from profile page)
    profile_links = (profile_data or {}).get("profile_links") or []
    for url in profile_links[:4]:
        if not url or not isinstance(url, str):
            continue
        d = _domain_from_url(url.strip())
        if not d or any(skip in d.lower() for skip in SKIP_DOMAINS):
            continue
        try:
            http_emails = fetch_domain_emails_http(d)
        except Exception:
            http_emails = []
        if http_emails:
            for prefix in ("hello", "contact", "team", "info", "hi", "reach"):
                for e in http_emails:
                    if e.split("@")[0] == prefix:
                        return e
            return http_emails[0]

    # Then domains extracted from profile text (often "Website: https://..." or company name in bio)
    found = _scrape_domain_for_email(profile_text, max_domains=4)
    if found:
        return found
    # Also try domains from post + web context
    found = _scrape_domain_for_email(f"{post_text or ''} {web_context or ''}", max_domains=2)
    if found:
        return found

    # 2) Email Research (detective): AI + web search + scraping + verdict
    from .email_research import research_and_find_email, has_email_research_config
    if has_email_research_config():
        found = research_and_find_email(lead, profile_data, web_context)
        if found:
            return found

    # 3) Optional Hunter API (fast path when key is set)
    author = getattr(lead, "author", None) or lead.get("author") if isinstance(lead, dict) else None
    if not author:
        return None
    first_name, last_name = _extract_name_parts(author)
    extracted = _llm_extract_contact_info(
        post_text or "", profile_text or "", web_context or "",
        (getattr(author, "handle", None) or getattr(author, "name", None) or "").strip().lstrip("@"),
    )
    company_name = (extracted.get("company_name") or "").strip()
    company_website = (extracted.get("company_website") or "").strip()
    person_full_name = (extracted.get("person_full_name") or "").strip()
    if person_full_name and _is_realistic_name(person_full_name):
        first_name, last_name = _parse_name_into_first_last(person_full_name)
    if not first_name:
        first_name = (getattr(author, "handle", None) or "").strip().split()[0] or ""
        last_name = ""
    domain = _domain_from_url(company_website)
    if not domain:
        domain = _extract_domain(f"{post_text or ''} {profile_text or ''} {web_context or ''}")
    if not domain and company_name:
        domain = _search_domain_for_company(company_name)
    api_key = os.environ.get(HUNTER_API_KEY_ENV, "").strip()
    if api_key:
        if domain and first_name:
            found = _hunter_email_finder(domain, first_name, last_name)
            if found:
                return found
        if domain or company_name:
            found = _hunter_domain_search(domain=domain, company=company_name if not domain else None)
            if found:
                return found

    # 4) Last resort: domain HTTP fetch (many paths + mailto + link-follow)
    if domain:
        from .scraper import fetch_domain_emails_http
        http_emails = fetch_domain_emails_http(domain)
        if http_emails:
            # Prefer hello@, contact@, team@, info@ for outreach
            for prefix in ("hello", "contact", "team", "info", "hi", "reach"):
                for e in http_emails:
                    if e.split("@")[0] == prefix:
                        return e
            return http_emails[0]

    return None
