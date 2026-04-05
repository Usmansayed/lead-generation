"""
Hunter alternative: find contact emails using web search, Apify scrapers, and AI.
No Hunter API required. Uses: search -> pipeline.scraper (powerful Apify) -> AI ranking.

Scraping is done by pipeline.scraper (proxy rotation, anti-bot, retries). Set APIFY_TOKEN.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

_LOG = logging.getLogger(__name__)

APIFY_TOKEN_ENV = "APIFY_TOKEN"

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
DOMAIN_PATTERN = re.compile(
    r"\b([a-zA-Z0-9][-a-zA-Z0-9]*\.(?:com|net|org|io|co|biz|info|dev)[a-zA-Z0-9./?#-]*)\b"
)
SKIP_DOMAINS = (
    "example.com", "test@", "noreply@", "no-reply@", "@sentry", "sentry.io",
    "wixpress.com", "github.com", "facebook.com", "twitter.com", "linkedin.com",
    "youtube.com", "google.com", "apple.com", "amazon.com", "cloudflare",
    "schema.org", "w3.org", "gravatar.com", "googleapis.com", "gstatic.com",
)


def _domain_from_url(url_or_domain: str) -> str | None:
    s = (url_or_domain or "").strip().lower()
    if not s:
        return None
    for p in ("https://", "http://", "www."):
        if s.startswith(p):
            s = s[len(p):]
    if "/" in s:
        s = s.split("/")[0]
    if "?" in s:
        s = s.split("?")[0]
    if any(x in s for x in ("reddit.com", "facebook.com", "twitter.com", "linkedin.com", "instagram.com", "example.com")):
        return None
    return s if "." in s and len(s) > 4 else None


def _extract_domain_from_text(text: str | None) -> str | None:
    if not text or not text.strip():
        return None
    m = DOMAIN_PATTERN.search(text)
    if not m:
        return None
    d = m.group(1).lower()
    if "/" in d:
        d = d.split("/")[0]
    if "?" in d:
        d = d.split("?")[0]
    if any(x in d for x in ("example.com", "facebook.com", "twitter.com", "reddit.com", "linkedin.com", "instagram.com")):
        return None
    return d


def _search_domain_for_company(company_name: str) -> str | None:
    if not company_name or len(company_name) < 2:
        return None
    try:
        from .web_research import _duckduckgo_search, _tavily_search
        q = f"{company_name} official website"
        api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
        if api_key:
            results = _tavily_search(q[:200], api_key)
            text = " ".join((r.get("content") or r.get("url") or "") for r in results[:5])
        else:
            results = _duckduckgo_search(q[:200], max_results=5)
            text = " ".join((r.get("href") or r.get("body") or "") for r in results[:5])
        return _extract_domain_from_text(text) or _domain_from_url(text)
    except Exception:
        return None


def _extract_emails_from_text(text: str | None) -> set[str]:
    """Extract all plausible emails from text; filter junk."""
    if not text or not text.strip():
        return set()
    found = set()
    for m in EMAIL_PATTERN.finditer(text):
        email = m.group(0).strip().lower()
        if any(skip in email for skip in SKIP_DOMAINS):
            continue
        if len(email) > 6 and "." in email.split("@")[-1]:
            found.add(email)
    return found


def _search_finder(
    person_name: str,
    company_name: str,
    domain: str,
    web_context: str,
) -> set[str]:
    """Run targeted web searches to find emails; extract from snippets/URLs."""
    queries = []
    if person_name and company_name:
        queries.append(f'"{person_name}" "{company_name}" email contact')
    if person_name and domain:
        queries.append(f'"{person_name}" site:{domain} email')
    if domain:
        queries.append(f'{domain} contact email')
    if company_name:
        queries.append(f'"{company_name}" contact email')

    if not queries:
        return set()

    try:
        from .web_research import _duckduckgo_search, _tavily_search
        api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
        all_emails: set[str] = set()
        for q in queries[:4]:  # cap queries
            if api_key:
                results = _tavily_search(q[:200], api_key)
                for r in results[:5]:
                    text = (r.get("content") or "") + " " + (r.get("url") or "")
                    all_emails |= _extract_emails_from_text(text)
            else:
                results = _duckduckgo_search(q[:200], max_results=5)
                for r in results[:5]:
                    text = (r.get("body") or "") + " " + (r.get("href") or "")
                    all_emails |= _extract_emails_from_text(text)
        return all_emails
    except Exception as e:
        _LOG.debug("Search finder failed: %s", e)
        return set()


def _ai_rank_emails(
    candidates: list[str],
    person_name: str,
    company_name: str,
    context_snippet: str,
) -> str | None:
    """Use LLM to pick the best contact email for this lead from candidates."""
    if not candidates:
        return None
    try:
        from .llm_client import call_llm, has_llm_config
        if not has_llm_config():
            return candidates[0] if candidates else None
        prompt = f"""We want to email this person for business outreach.

PERSON: {person_name or 'unknown'}
COMPANY: {company_name or 'unknown'}
CONTEXT: {context_snippet[:500]}

CANDIDATE EMAILS (one per line):
{chr(10).join(candidates[:15])}

Which single email is most likely the right one to contact this person? Prefer personal/work emails over generic (info@, support@). Reply with ONLY that one email address, nothing else. If none look right, reply: NONE"""
        out = (call_llm(prompt, temperature=0) or "").strip()
        if not out or out.upper() == "NONE":
            return candidates[0] if candidates else None
        chosen = out.split()[0].strip().lower()
        if "@" in chosen and chosen in [c.lower() for c in candidates]:
            return chosen
        if "@" in chosen:
            return chosen
        return candidates[0] if candidates else None
    except Exception as e:
        _LOG.debug("AI rank emails failed: %s", e)
        return candidates[0] if candidates else None


def find_emails_for_lead(
    lead: Any,
    profile_data: dict[str, Any] | None = None,
    web_context: str | None = None,
    *,
    extracted: dict[str, str] | None = None,
) -> str | None:
    """
    Hunter alternative: find contact email using search, Apify scrapers, and AI.
    extracted: optional {company_name, company_website, person_full_name} from LLM.
    Returns best email or None.
    """
    author = getattr(lead, "author", None) or (lead.get("author") if isinstance(lead, dict) else None)
    author_handle = (getattr(author, "handle", None) or getattr(author, "name", None) or "").strip().lstrip("@")
    post_text = getattr(lead, "post_text", None) or (lead.get("postText") if isinstance(lead, dict) else "")
    profile_text = (profile_data or {}).get("profile_text") or ""

    company_name = (extracted or {}).get("company_name") or ""
    company_website = (extracted or {}).get("company_website") or ""
    person_full_name = (extracted or {}).get("person_full_name") or ""
    person_name = person_full_name or author_handle or ""

    domain = _domain_from_url(company_website) if company_website else None
    if not domain and (post_text or profile_text or web_context):
        domain = _extract_domain_from_text(f"{post_text or ''} {profile_text or ''} {web_context or ''}")
        if not domain and company_name:
            domain = _search_domain_for_company(company_name)

    all_emails: set[str] = set()

    # 1) Search-based
    search_emails = _search_finder(person_name, company_name, domain or "", web_context or "")
    all_emails |= search_emails

    # 2) Powerful scraper (Contact Details + Website Crawler, proxy + anti-bot)
    if domain:
        from .scraper import scrape_domain_for_emails, is_scraper_available
        if is_scraper_available():
            scraped_emails = scrape_domain_for_emails(domain)
            all_emails.update(scraped_emails)

    candidates = list(all_emails)
    if not candidates:
        return None

    context_snippet = f"{post_text or ''} {profile_text or ''} {web_context or ''}"[:400]
    best = _ai_rank_emails(candidates, person_name, company_name, context_snippet)
    return best


def has_email_finder_config() -> bool:
    """True if web search is available (Tavily or DuckDuckGo); Apify is optional."""
    from .web_research import has_web_search_config
    return has_web_search_config()
