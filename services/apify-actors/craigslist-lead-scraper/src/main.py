"""Craigslist Lead Scraper - RSS search.

Uses Craigslist search RSS feeds to collect listings quickly and reliably.
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET
from html import unescape
import httpx
from apify import Actor


def calc_quality(text: str) -> float:
    text = text.lower()
    score = 15
    if any(k in text for k in ['remote', 'telecommute']): score += 15
    if any(k in text for k in ['senior', 'expert']): score += 10
    if any(k in text for k in ['python', 'react', 'node', 'dev']): score += 10
    if any(k in text for k in ['startup', 'tech']): score += 10
    return min(100, score)


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        keywords = inp.get("keywords", ["web developer"])
        cities = inp.get("cities", ["newyork", "sfbay", "austin"])
        max_results = int(inp.get("maxResults", 50))

        Actor.log.info(f"🚀 Craigslist Scraper (RSS) | Keywords: {keywords} | Cities: {cities}")

        leads_found = high_quality = 0
        seen: set[str] = set()

        feed_urls = []
        for city in cities:
            for kw in keywords:
                feed_urls.append(
                    f"https://{city}.craigslist.org/search/jjj?query={quote_plus(kw)}&format=rss"
                )
                feed_urls.append(
                    f"https://{city}.craigslist.org/search/ggg?query={quote_plus(kw)}&format=rss"
                )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            )
        }

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
            for feed_url in feed_urls:
                if leads_found >= max_results:
                    break
                Actor.log.info(f"Processing: {feed_url[:80]}...")
                try:
                    resp = await client.get(feed_url)
                except Exception as exc:
                    Actor.log.warning(f"Feed fetch failed: {exc}")
                    continue

                if resp.status_code >= 400:
                    Actor.log.warning(f"Feed HTTP {resp.status_code}: {feed_url}")
                    continue

                try:
                    root = ET.fromstring(resp.text)
                except Exception as exc:
                    Actor.log.warning(f"Feed parse failed: {exc}")
                    continue

                for item in root.findall("./channel/item"):
                    if leads_found >= max_results:
                        break
                    title = (item.findtext("title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    description = _strip_html(unescape(item.findtext("description") or ""))
                    if not title or not link:
                        continue
                    if link in seen:
                        continue
                    seen.add(link)

                    score = calc_quality(f"{title} {description}")
                    leads_found += 1
                    if score >= 40:
                        high_quality += 1

                    city_match = re.search(r"//(\w+)\.craigslist", link)
                    city = city_match.group(1) if city_match else ""

                    await Actor.push_data({
                        "platform": "craigslist",
                        "source": "Craigslist",
                        "url": link,
                        "title": title,
                        "city": city,
                        "content_preview": description[:500],
                        "scraped_at": datetime.utcnow().isoformat(),
                        "quality_score": round(score, 1),
                        "lead_category": "high_priority" if score >= 60 else "medium_priority",
                    })
                    Actor.log.info(f"✅ Lead #{leads_found}: {title[:60]}... ({city}) (Q:{score})")

        Actor.log.info(f"✅ Complete! Leads: {leads_found}, HQ: {high_quality}")
