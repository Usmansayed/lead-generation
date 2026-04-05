"""
Email Research (detective): find contact email from any post using AI, web search, and scraping.
Like a detective: extract every clue from the post → plan searches → search + scrape → AI verdict.

Flow:
  1. Lead intelligence (AI): company, person, role, product, URLs, search hints from post+profile.
  2. Domain discovery: from intel or search "{company} website".
  3. Search plan (AI): 8–12 detective-style queries to find this person's email.
  4. Execute searches: run all queries, extract emails from every result (with source).
  5. Scrape company: Apify contact scraper + site crawler on domain.
  6. Evidence bundle: all clues + (email, source) list.
  7. Detective verdict (AI): pick best email from evidence; optionally suggest one more search → repeat.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from . import email_finder as _finder

_LOG = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Step 1: Lead intelligence (AI)
# -----------------------------------------------------------------------------


def _extract_lead_intelligence(
    post_text: str,
    profile_text: str,
    web_context: str,
    author_handle: str,
    platform: str,
) -> dict[str, Any]:
    """
    AI extracts everything a detective could use: company, person, role, product,
    URLs, location hints, and suggested search phrases.
    """
    from .llm_client import call_llm, has_llm_config
    if not has_llm_config():
        return _fallback_intelligence(post_text, profile_text, author_handle)

    prompt = f"""You are a researcher. From this post and profile, extract EVERY clue that could help find this person's contact email.

POST:
{post_text or '(none)'}

PROFILE:
{profile_text or '(none)'}

SEARCH CONTEXT (from earlier web search):
{web_context or '(none)'}

AUTHOR HANDLE: {author_handle or '(none)'}
PLATFORM: {platform or '(none)'}

Extract and return JSON only (no markdown):
{{
  "company_name": "business or company name if mentioned",
  "company_website": "URL or domain if mentioned",
  "product_name": "product/app name if any",
  "person_full_name": "real name if stated or clearly inferrable (not the handle)",
  "person_role": "job title or role if mentioned (e.g. founder, CEO, developer)",
  "industry": "industry or niche if clear",
  "location": "city/country if mentioned",
  "mentioned_urls": ["any URLs in the post or profile"],
  "mentioned_emails": ["any email addresses already in the text"],
  "search_hints": ["3-5 short phrases to search for to find this person's email, e.g. 'John Smith Acme CEO', 'Acme contact email', 'Acme team']
}}

Use empty string or empty array for missing fields. search_hints should be specific and varied. Be concise."""

    try:
        out = (call_llm(prompt, temperature=0.2) or "").strip()
        if "```" in out:
            out = re.sub(r"```\w*\n?", "", out).strip()
        data = json.loads(out)
        return {
            "company_name": (data.get("company_name") or "").strip()[:120],
            "company_website": (data.get("company_website") or "").strip()[:200],
            "product_name": (data.get("product_name") or "").strip()[:120],
            "person_full_name": (data.get("person_full_name") or "").strip()[:80],
            "person_role": (data.get("person_role") or "").strip()[:80],
            "industry": (data.get("industry") or "").strip()[:60],
            "location": (data.get("location") or "").strip()[:60],
            "mentioned_urls": [str(u).strip()[:200] for u in (data.get("mentioned_urls") or [])[:10]],
            "mentioned_emails": [str(e).strip().lower() for e in (data.get("mentioned_emails") or []) if "@" in str(e)],
            "search_hints": [str(h).strip()[:150] for h in (data.get("search_hints") or [])[:8]],
        }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        _LOG.debug("Lead intelligence extraction failed: %s", e)
        return _fallback_intelligence(post_text, profile_text, author_handle)


def _fallback_intelligence(post_text: str, profile_text: str, author_handle: str) -> dict[str, Any]:
    """No LLM: minimal extraction from text."""
    combined = f"{post_text or ''} {profile_text or ''}"
    domain = _finder._extract_domain_from_text(combined)
    return {
        "company_name": "",
        "company_website": domain or "",
        "product_name": "",
        "person_full_name": "",
        "person_role": "",
        "industry": "",
        "location": "",
        "mentioned_urls": [],
        "mentioned_emails": [],
        "search_hints": [author_handle] if author_handle else [],
    }


# -----------------------------------------------------------------------------
# Step 2: Domain discovery
# -----------------------------------------------------------------------------


def _discover_domain(intel: dict[str, Any], post_text: str, profile_text: str, web_context: str) -> str | None:
    """Resolve company domain from intel or search."""
    domain = _finder._domain_from_url(intel.get("company_website") or "")
    if domain:
        return domain
    combined = f"{post_text or ''} {profile_text or ''} {web_context or ''}"
    domain = _finder._extract_domain_from_text(combined)
    if domain:
        return domain
    for u in intel.get("mentioned_urls") or []:
        domain = _finder._domain_from_url(u)
        if domain:
            return domain
    for name in [intel.get("company_name"), intel.get("product_name")]:
        if name and len(name) > 1:
            domain = _finder._search_domain_for_company(name)
            if domain:
                return domain
    return None


# -----------------------------------------------------------------------------
# Step 3: Search plan (AI) + execute
# -----------------------------------------------------------------------------


def _build_search_plan(intel: dict[str, Any], domain: str | None, author_handle: str) -> list[str]:
    """AI suggests detective-style search queries; we add defaults."""
    from .llm_client import call_llm, has_llm_config
    person = intel.get("person_full_name") or author_handle
    company = intel.get("company_name") or intel.get("product_name") or ""

    queries = list(intel.get("search_hints") or [])

    # Add structured queries
    if person and company:
        queries.append(f'"{person}" "{company}" email')
        queries.append(f'"{person}" "{company}" contact')
    if person and domain:
        queries.append(f'"{person}" site:{domain}')
        queries.append(f'"{person}" {domain} email')
    if domain:
        queries.append(f'{domain} contact email')
        queries.append(f'{domain} team email')
    if company:
        queries.append(f'"{company}" contact email')
        queries.append(f'"{company}" team')
    if person:
        queries.append(f'"{person}" email contact')
    if author_handle and not person:
        queries.append(f'"{author_handle}" email')

    if has_llm_config():
        try:
            prompt = f"""Person: {person or author_handle}. Company: {company}. Domain: {domain or 'unknown'}.
Given we need to find this person's email, suggest 5 more specific search queries (one per line, no numbering).
Variations: name+company+email, name+LinkedIn, company+about+team, domain+contact. Be specific."""
            out = (call_llm(prompt, temperature=0.3) or "").strip()
            for line in out.split("\n"):
                q = line.strip().lstrip(".-123456789) ")
                if len(q) > 10 and q not in queries:
                    queries.append(q[:150])
        except Exception:
            pass

    # Dedupe, cap
    seen = set()
    unique = []
    for q in queries:
        if q and q.lower() not in seen and len(unique) < 14:
            seen.add(q.lower())
            unique.append(q)
    return unique


def _run_searches(queries: list[str]) -> list[tuple[str, str]]:
    """Run each query via Tavily or DuckDuckGo; return (email, source_query) for every email found."""
    from .web_research import _duckduckgo_search, _tavily_search
    api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    results: list[tuple[str, str]] = []
    for q in queries:
        try:
            if api_key:
                raw = _tavily_search(q[:200], api_key)
                for r in raw[:6]:
                    text = (r.get("content") or "") + " " + (r.get("url") or "")
                    for email in _finder._extract_emails_from_text(text):
                        results.append((email, q))
            else:
                raw = _duckduckgo_search(q[:200], max_results=6)
                for r in raw[:6]:
                    text = (r.get("body") or "") + " " + (r.get("href") or "")
                    for email in _finder._extract_emails_from_text(text):
                        results.append((email, q))
        except Exception as e:
            _LOG.debug("Search failed for %s: %s", q[:50], e)
    return results


# -----------------------------------------------------------------------------
# Step 4: Scrape company (Apify)
# -----------------------------------------------------------------------------


def _scrape_company_emails(domain: str) -> list[tuple[str, str]]:
    """(email, source) from scraper: Apify when available + HTTP fallback (always)."""
    from .scraper import (
        run_contact_scraper,
        run_website_crawler,
        fetch_domain_emails_http,
        is_scraper_available,
    )
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    if is_scraper_available():
        try:
            for item in run_contact_scraper(domain):
                for e in (item.get("emails") or []):
                    if isinstance(e, str) and "@" in e:
                        e = e.strip().lower()
                        if e not in seen:
                            seen.add(e)
                            out.append((e, "scraped:contact"))
                    elif isinstance(e, dict) and e.get("address"):
                        e = str(e.get("address")).strip().lower()
                        if e not in seen:
                            seen.add(e)
                            out.append((e, "scraped:contact"))
                for email in _finder._extract_emails_from_text(item.get("text") or item.get("content") or ""):
                    if email not in seen:
                        seen.add(email)
                        out.append((email, "scraped:contact"))
            for item in run_website_crawler([f"https://{domain}", f"https://www.{domain}"]):
                text = item.get("text") or item.get("markdown") or item.get("content") or ""
                for email in _finder._extract_emails_from_text(text):
                    if email not in seen:
                        seen.add(email)
                        out.append((email, "scraped:site"))
        except Exception:
            pass
    # HTTP fallback: always run so we get emails when Apify fails or isn't set
    for email in fetch_domain_emails_http(domain):
        if email not in seen:
            seen.add(email)
            out.append((email, "scraped:http"))
    return out


# -----------------------------------------------------------------------------
# Step 5 & 6: Evidence bundle + Detective verdict (AI)
# -----------------------------------------------------------------------------


def _build_evidence_bundle(
    intel: dict[str, Any],
    search_results: list[tuple[str, str]],
    scraped: list[tuple[str, str]],
    domain: str | None,
) -> str:
    """Single text bundle for the detective LLM."""
    emails_with_sources: list[str] = []
    seen_emails: set[str] = set()
    for email, src in search_results + scraped:
        email = email.strip().lower()
        if email not in seen_emails:
            seen_emails.add(email)
            emails_with_sources.append(f"  - {email}  [from: {src}]")

    return f"""
WHO WE'RE LOOKING FOR:
  Name: {intel.get('person_full_name') or '(handle only)'}
  Role: {intel.get('person_role') or 'unknown'}
  Company: {intel.get('company_name') or 'unknown'}
  Product: {intel.get('product_name') or 'unknown'}
  Domain: {domain or 'unknown'}
  Industry: {intel.get('industry') or 'unknown'}
  Location: {intel.get('location') or 'unknown'}

FOUND EMAILS (with source):
{chr(10).join(emails_with_sources) if emails_with_sources else '  (none)'}

Already in post/profile: {', '.join(intel.get('mentioned_emails') or []) or 'none'}
""".strip()


def _detective_verdict(
    evidence: str,
    post_snippet: str,
    candidates: list[str],
) -> tuple[str | None, str | None]:
    """
    AI picks best email from evidence. Returns (best_email, suggested_search or None).
    """
    from .llm_client import call_llm, has_llm_config
    if not has_llm_config() or not candidates:
        return (candidates[0] if candidates else None, None)

    prompt = f"""You are a detective. We need to find the best email to contact this person for business outreach.

EVIDENCE:
{evidence}

POST SNIPPET (for context):
{post_snippet[:400]}

CANDIDATE EMAILS (choose one or reply NONE):
{chr(10).join(candidates[:25])}

Tasks:
1. Pick the ONE email most likely to be this person's direct or work contact. Prefer personal/founder/name-based over generic (info@, support@, hello@). Consider company size and role.
2. If you're unsure and one more search could help, suggest it in one line after "SUGGESTED_SEARCH:".

Reply format:
BEST_EMAIL: <one email or NONE>
SUGGESTED_SEARCH: <optional one search query or leave empty>"""

    try:
        out = (call_llm(prompt, temperature=0) or "").strip()
        best = None
        suggested = None
        cand_lower = [c.lower() for c in candidates]
        for line in out.split("\n"):
            line = line.strip()
            if line.upper().startswith("BEST_EMAIL:"):
                val = line.split(":", 1)[-1].strip().lower()
                if val and val != "none" and "@" in val:
                    if val in cand_lower:
                        best = val
                    else:
                        for c in candidates:
                            if c.lower() == val:
                                best = c.lower()
                                break
                        if best is None:
                            best = val
            if line.upper().startswith("SUGGESTED_SEARCH:"):
                suggested = line.split(":", 1)[-1].strip()[:200] or None
        if not best and candidates:
            best = candidates[0].lower()
        # Only return an email we actually found (no hallucination)
        if best and best not in cand_lower and not any(c.lower() == best for c in candidates):
            best = candidates[0].lower() if candidates else None
        return (best, suggested)
    except Exception as e:
        _LOG.debug("Detective verdict failed: %s", e)
        return (candidates[0] if candidates else None, None)


# -----------------------------------------------------------------------------
# Main entry: research and find email
# -----------------------------------------------------------------------------


def research_and_find_email(
    lead: Any,
    profile_data: dict[str, Any] | None = None,
    web_context: str | None = None,
) -> str | None:
    """
    Detective-style email research: extract clues from post → plan searches →
    search + scrape → AI verdict. Optionally one follow-up search round.
    Returns best email or None.
    """
    post_text = getattr(lead, "post_text", None) or (lead.get("postText") if isinstance(lead, dict) else "")
    profile_text = (profile_data or {}).get("profile_text") or ""
    author = getattr(lead, "author", None) or lead.get("author") if isinstance(lead, dict) else None
    author_handle = (getattr(author, "handle", None) or getattr(author, "name", None) or "").strip().lstrip("@")
    platform = getattr(lead, "platform", None) or (lead.get("platform") if isinstance(lead, dict) else "")

    # Already in text?
    direct_set = _finder._extract_emails_from_text(post_text) | _finder._extract_emails_from_text(profile_text)
    if direct_set:
        return next(iter(direct_set))

    intel = _extract_lead_intelligence(
        post_text or "",
        profile_text or "",
        web_context or "",
        author_handle,
        platform or "",
    )
    if intel.get("mentioned_emails"):
        return intel["mentioned_emails"][0]

    domain = _discover_domain(intel, post_text or "", profile_text or "", web_context or "")

    queries = _build_search_plan(intel, domain, author_handle)
    search_results = _run_searches(queries)
    scraped: list[tuple[str, str]] = []
    if domain:
        scraped = _scrape_company_emails(domain)

    all_emails = list({e for e, _ in search_results + scraped})
    if not all_emails:
        return None

    evidence = _build_evidence_bundle(intel, search_results, scraped, domain)
    best, suggested = _detective_verdict(evidence, post_text or "", all_emails)

    if suggested and suggested.strip():
        extra = _run_searches([suggested.strip()])
        if extra:
            for email, src in extra:
                if email not in all_emails:
                    all_emails.append(email)
                    search_results.append((email, src))
            evidence = _build_evidence_bundle(intel, search_results, scraped, domain)
            best, _ = _detective_verdict(evidence, post_text or "", all_emails)

    return best


def has_email_research_config() -> bool:
    """True if we can run (web search required; LLM and Apify improve results)."""
    return _finder.has_email_finder_config()
