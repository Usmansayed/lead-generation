"""LinkedIn Lead Scraper - Crawlee SERP-only (100+ leads in <1 min).

Uses BeautifulSoupCrawler to scrape Bing/DDG for site:linkedin.com/jobs; pushes leads
from SERP title/snippet/url without visiting each job page. Residential proxy + high
concurrency for maximum throughput.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

from apify import Actor
from crawlee import Request
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee import ConcurrencySettings


def calc_quality(text: str) -> float:
    text = text.lower()
    score = 20
    if any(k in text for k in ["hiring", "job", "opportunity", "position"]):
        score += 25
    if any(k in text for k in ["remote", "hybrid", "onsite"]):
        score += 10
    if any(k in text for k in ["senior", "lead", "principal", "architect"]):
        score += 15
    if any(k in text for k in ["startup", "series a", "early stage", "founder"]):
        score += 15
    if any(k in text for k in ["$", "salary", "compensation", "equity"]):
        score += 10
    return min(100, score)


def _normalize_ddg_url(href: str) -> str:
    if not href:
        return ""
    if "duckduckgo.com/l/" in href:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        href = unquote(qs.get("uddg", [""])[0])
    return href


def _extract_ddg_results(soup) -> list[dict]:
    results = []
    for anchor in soup.select("a.result__a"):
        href = _normalize_ddg_url(anchor.get("href", ""))
        title = anchor.get_text(" ", strip=True)
        container = anchor.find_parent("div", class_="result")
        snippet_el = container.select_one(".result__snippet") if container else None
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        if href and title and "linkedin.com" in href:
            results.append({"url": href, "title": title, "snippet": snippet})
    return results


def _extract_bing_results(soup) -> list[dict]:
    results = []
    for li in soup.select("li.b_algo"):
        h2_a = li.select_one("h2 a")
        if not h2_a:
            continue
        href = h2_a.get("href", "")
        title = h2_a.get_text(" ", strip=True)
        snippet_el = li.select_one("p") or li.select_one(".b_caption p")
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        if href and title and "linkedin.com/jobs" in href:
            results.append({"url": href, "title": title, "snippet": snippet})
    return results


def _normalize_linkedin_url(url: str) -> str:
    if "/url?q=" in url:
        url = unquote(url.split("/url?q=")[1].split("&")[0])
    return url.strip()


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        keywords = inp.get("keywords", ["hiring developer"])
        max_results = int(inp.get("maxResults", 120))
        use_proxy = inp.get("useProxy", True)

        Actor.log.info(
            f"🚀 LinkedIn Scraper (Crawlee SERP) | Keywords: {len(keywords)}, maxResults: {max_results}, target 100+ in <1 min"
        )

        seen = set()
        leads_count = 0

        start_requests = []
        for kw in keywords:
            start_requests.append(
                Request.from_url(
                    f"https://duckduckgo.com/html/?q=site:linkedin.com/jobs+{quote_plus(kw)}",
                    user_data={"engine": "ddg", "keyword": kw},
                )
            )
            start_requests.append(
                Request.from_url(
                    f"https://www.bing.com/search?q=site:linkedin.com/jobs+{quote_plus(kw)}",
                    user_data={"engine": "bing", "keyword": kw},
                )
            )

        proxy_config = None
        if use_proxy:
            try:
                proxy_config = await Actor.create_proxy_configuration(groups=["RESIDENTIAL"], country_code="US")
                Actor.log.info("Using residential proxy")
            except Exception as e:
                Actor.log.warning(f"Proxy not available: {e}")

        concurrency = ConcurrencySettings(
            max_concurrency=min(50, len(start_requests)),
            min_concurrency=20,
            desired_concurrency=min(40, len(start_requests)),
        )

        crawler = BeautifulSoupCrawler(
            proxy_configuration=proxy_config,
            max_requests_per_crawl=len(start_requests),
            max_request_retries=3,
            concurrency_settings=concurrency,
        )

        @crawler.router.default_handler
        async def handle_serp(context: BeautifulSoupCrawlingContext) -> None:
            nonlocal leads_count
            url = context.request.url
            if leads_count >= max_results:
                return
            soup = context.soup
            if "duckduckgo.com" in url:
                results = _extract_ddg_results(soup)
            elif "bing.com" in url:
                results = _extract_bing_results(soup)
            else:
                return

            for item in results:
                if leads_count >= max_results:
                    break
                link_url = _normalize_linkedin_url(item.get("url") or "")
                if not link_url or "linkedin.com/jobs" not in link_url or link_url in seen:
                    continue
                seen.add(link_url)
                text = f"{item.get('title', '')} {item.get('snippet', '')}".strip()
                score = calc_quality(text)
                leads_count += 1
                await context.push_data({
                    "platform": "linkedin",
                    "source": "LinkedIn Jobs",
                    "url": link_url,
                    "title": (item.get("title") or "")[:200],
                    "company": "",  # SERP-only; enrich later if needed
                    "location": "",
                    "content_preview": (item.get("snippet") or "")[:500],
                    "scraped_at": datetime.utcnow().isoformat(),
                    "quality_score": round(score, 1),
                    "lead_category": "high_priority" if score >= 60 else "medium_priority",
                })
                Actor.log.info(f"✅ Lead #{leads_count}: {(item.get('title') or '')[:50]}... (Q:{score})")

        await crawler.run(start_requests)
        Actor.log.info(f"✅ Complete! Leads: {leads_count}")


if __name__ == "__main__":
    asyncio.run(main())
