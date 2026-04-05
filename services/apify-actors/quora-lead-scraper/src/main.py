"""Quora Lead Scraper - HTTP + DuckDuckGo discovery.

Uses DuckDuckGo HTML results to discover Quora links and snippets.
Avoids heavy browser rendering and login prompts.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus, unquote, urlparse, parse_qs
import httpx
from bs4 import BeautifulSoup
from apify import Actor


def calc_quality(text: str) -> float:
    text = text.lower()
    score = 15
    if any(k in text for k in ['hiring', 'looking for', 'need']): score += 25
    if any(k in text for k in ['developer', 'engineer', 'programmer']): score += 15
    if any(k in text for k in ['startup', 'founder']): score += 10
    if any(k in text for k in ['recommend', 'agency', 'outsource']): score += 15
    return min(100, score)


def _normalize_ddg_url(href: str) -> str:
    if not href:
        return ""
    if "duckduckgo.com/l/" in href:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        href = unquote(qs.get("uddg", [""])[0])
    return href


def _extract_ddg_results(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []
    for anchor in soup.select("a.result__a"):
        href = _normalize_ddg_url(anchor.get("href", ""))
        title = anchor.get_text(" ", strip=True)
        container = anchor.find_parent("div", class_="result")
        snippet_el = container.select_one(".result__snippet") if container else None
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        if href and title:
            results.append({"url": href, "title": title, "snippet": snippet})
    return results


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        keywords = inp.get("keywords", ["hire developer"])
        max_results = int(inp.get("maxResults", 50))

        Actor.log.info(f"🚀 Quora Scraper (HTTP+DuckDuckGo) | Keywords: {keywords}")

        leads_found = high_quality = 0
        seen: set[str] = set()

        search_urls = [
            f"https://duckduckgo.com/html/?q=site:quora.com+{quote_plus(kw)}"
            for kw in keywords
        ]

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            )
        }

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
            for search_url in search_urls:
                if leads_found >= max_results:
                    break
                Actor.log.info(f"Processing: {search_url[:80]}...")
                try:
                    resp = await client.get(search_url)
                except Exception as exc:
                    Actor.log.warning(f"DuckDuckGo fetch failed: {exc}")
                    continue

                results = _extract_ddg_results(resp.text)
                Actor.log.info(f"Found {len(results)} Quora results")

                for item in results:
                    if leads_found >= max_results:
                        break
                    url = item["url"]
                    if not url or url in seen:
                        continue
                    if "quora.com" not in url:
                        continue
                    seen.add(url)

                    text = f"{item['title']} {item['snippet']}".strip()
                    score = calc_quality(text)
                    leads_found += 1
                    if score >= 40:
                        high_quality += 1

                    await Actor.push_data({
                        "platform": "quora",
                        "source": "Quora",
                        "url": url,
                        "title": item["title"][:200],
                        "content_preview": item["snippet"][:500],
                        "scraped_at": datetime.utcnow().isoformat(),
                        "quality_score": round(score, 1),
                        "lead_category": "high_priority" if score >= 60 else "medium_priority",
                    })
                    Actor.log.info(f"✅ Lead #{leads_found}: {item['title'][:60]}... (Q:{score})")

        Actor.log.info(f"✅ Complete! Leads: {leads_found}, HQ: {high_quality}")
