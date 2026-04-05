"""
Web research: optional light web search to gather extra context about a lead (person/business)
before sending everything to the LLM for email.

- **Free (no API key):** Uses DuckDuckGo via duckduckgo-search — no cost.
- **Optional paid:** If TAVILY_API_KEY is set, uses Tavily instead (often better snippets).

Flow: fetch post → fetch profile → [web search] → business research → send all to LLM.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

# Tavily (optional, paid)
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_API_KEY_ENV = "TAVILY_API_KEY"

MAX_QUERIES = 2
MAX_RESULTS_PER_QUERY = 3
MAX_TOTAL_CHARS = 2000


def _duckduckgo_search(query: str, max_results: int = 3) -> list[dict[str, Any]]:
    """Free search via DuckDuckGo (no API key). Returns list of {title, href, body}."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            # .text() returns an iterator of dicts: title, href, body
            gen = ddgs.text(query[:200], max_results=max_results)
            return list(gen) if gen else []
    except Exception:
        return []


def _tavily_search(query: str, api_key: str) -> list[dict[str, Any]]:
    """Call Tavily Search API; return list of result dicts with title, url, content."""
    body = json.dumps({
        "query": query[:500],
        "search_depth": "basic",
        "max_results": MAX_RESULTS_PER_QUERY,
        "include_answer": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        TAVILY_SEARCH_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return (data.get("results") or [])
    except (urllib.error.URLError, json.JSONDecodeError, KeyError):
        return []


def _build_queries(lead: Any, full_post_text: str = "", profile_text: str = "") -> list[str]:
    """Build 1–2 search queries from author and a short phrase from post/profile."""
    author = getattr(lead, "author", None)
    name = (getattr(author, "name", None) or getattr(author, "handle", None) or "").strip() if author else ""
    handle = (getattr(author, "handle", None) or name or "").strip() if author else ""
    platform = (getattr(lead, "platform", "") or "").strip()
    combined = f"{full_post_text or ''} {profile_text or ''}".strip()
    words = re.findall(r"[a-zA-Z0-9]+", combined)
    stop = {"the", "a", "an", "and", "or", "is", "are", "we", "our", "my", "i", "to", "for", "of", "in", "on", "at"}
    meaningful = [w for w in words if w.lower() not in stop and len(w) > 1][:8]
    phrase = " ".join(meaningful[:5]) if meaningful else ""

    queries = []
    if name or handle:
        who = name or handle
        if platform:
            queries.append(f"{who} {platform}")
        if phrase and phrase != who:
            queries.append(f"{who} {phrase}")
    if not queries and phrase:
        queries.append(phrase[:80])
    return queries[:MAX_QUERIES]


def _results_to_context(
    results: list[dict[str, Any]],
    *,
    title_key: str = "title",
    body_key: str = "content",
    body_fallback_key: str = "body",
) -> list[str]:
    """Turn search result dicts into [title]\nbody lines. Tavily uses 'content'; DDG uses 'body'."""
    parts = []
    total = 0
    for r in results:
        title = (r.get(title_key) or "").strip()
        body = (r.get(body_key) or r.get(body_fallback_key) or "").strip()
        if not body:
            continue
        if total + len(body) > MAX_TOTAL_CHARS:
            body = body[: MAX_TOTAL_CHARS - total] + "..."
        parts.append(f"[{title}]\n{body}" if title else body)
        total += len(body)
        if total >= MAX_TOTAL_CHARS:
            break
    return parts


def web_search_lead(
    lead: Any,
    full_post_text: str = "",
    profile_text: str = "",
) -> str:
    """
    Run a light web search about the lead (person/business). Returns a short text snippet
    to pass to the LLM for more personalized email.

    - If TAVILY_API_KEY is set: uses Tavily (paid).
    - Else: uses DuckDuckGo via duckduckgo-search (free, no API key).
    """
    queries = _build_queries(lead, full_post_text, profile_text)
    if not queries:
        return ""

    api_key = (os.environ.get(TAVILY_API_KEY_ENV) or "").strip()
    use_tavily = bool(api_key)

    all_parts: list[str] = []
    total_chars = 0
    for q in queries:
        if total_chars >= MAX_TOTAL_CHARS:
            break
        if use_tavily:
            results = _tavily_search(q, api_key)
            new_parts = _results_to_context(results, body_key="content")
        else:
            results = _duckduckgo_search(q, max_results=MAX_RESULTS_PER_QUERY)
            new_parts = _results_to_context(results, body_key="body")
        for p in new_parts:
            if total_chars >= MAX_TOTAL_CHARS:
                break
            all_parts.append(p[: MAX_TOTAL_CHARS - total_chars] if len(p) + total_chars > MAX_TOTAL_CHARS else p)
            total_chars += len(all_parts[-1])

    combined = "\n\n".join(all_parts).strip()
    return combined[:MAX_TOTAL_CHARS] if combined else ""


def has_web_search_config() -> bool:
    """Return True if web search can run: either Tavily key set or duckduckgo-search installed (free)."""
    if (os.environ.get(TAVILY_API_KEY_ENV) or "").strip():
        return True
    try:
        from duckduckgo_search import DDGS
        return True
    except ImportError:
        return False
