"""Indie Hackers Lead Scraper - RSS feed fetch.

Uses the community RSS feed to collect posts quickly and reliably.
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Any
import xml.etree.ElementTree as ET
from html import unescape
import httpx
from apify import Actor


def calc_quality(text: str) -> float:
    text = text.lower()
    score = 20
    if any(k in text for k in ['cofounder', 'looking for']): score += 25
    if any(k in text for k in ['developer', 'technical']): score += 15
    if any(k in text for k in ['revenue', 'mrr', 'profit']): score += 15
    if any(k in text for k in ['hiring', 'job']): score += 20
    return min(100, score)


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        keywords = inp.get('keywords', ['cofounder', 'developer needed'])
        max_results = int(inp.get('maxResults', 50))

        Actor.log.info(f'🚀 Indie Hackers Scraper (RSS) | Keywords: {keywords}')

        leads_found = high_quality = 0
        seen: set[str] = set()
        matched_any = False

        feed_url = "https://feed.indiehackers.world/posts.rss"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            )
        }

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
            Actor.log.info(f"Processing: {feed_url}")
            try:
                resp = await client.get(feed_url)
            except Exception as exc:
                Actor.log.error(f"Feed fetch failed: {exc}")
                return

            if resp.status_code >= 400:
                Actor.log.error(f"Feed HTTP {resp.status_code}: {feed_url}")
                return

            try:
                root = ET.fromstring(resp.text)
            except Exception as exc:
                Actor.log.error(f"Feed parse failed: {exc}")
                return

            items = root.findall("./channel/item")

            async def process_items(filter_keywords: bool) -> None:
                nonlocal leads_found, high_quality, matched_any
                for item in items:
                    if leads_found >= max_results:
                        break
                    title = (item.findtext("title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    description = unescape(item.findtext("description") or "")
                    description = re.sub(r"<[^>]+>", " ", description)
                    description = re.sub(r"\s+", " ", description).strip()
                    if not title or not link:
                        continue
                    if link in seen:
                        continue

                    text_lower = f"{title} {description}".lower()
                    matched = [kw for kw in keywords if kw.lower() in text_lower]
                    if filter_keywords and keywords and not matched:
                        continue

                    seen.add(link)
                    if matched:
                        matched_any = True

                    score = calc_quality(text_lower)
                    if score >= 40:
                        high_quality += 1

                    leads_found += 1
                    await Actor.push_data({
                        "platform": "indiehackers",
                        "source": "IndieHackers",
                        "url": link,
                        "title": title,
                        "content_preview": description[:500],
                        "scraped_at": datetime.utcnow().isoformat(),
                        "matched_keywords": matched,
                        "quality_score": score,
                    })
                    Actor.log.info(f'✅ Lead #{leads_found}: {title[:60]}... (Q:{score})')

            await process_items(filter_keywords=True)
            if keywords and not matched_any and leads_found < max_results:
                Actor.log.info("No keyword matches found, falling back to latest posts.")
                await process_items(filter_keywords=False)

        Actor.log.info(f'✅ Complete! Leads: {leads_found}, HQ: {high_quality}')
