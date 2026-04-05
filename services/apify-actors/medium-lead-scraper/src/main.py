"""Medium Lead Scraper - RSS-based fetch

Uses Medium tag RSS feeds to collect posts quickly and reliably.
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Any
import xml.etree.ElementTree as ET
from html import unescape
import httpx
from apify import Actor

LEAD_SIGNALS = [
    'hiring', 'hire', 'looking for', 'seeking', 'need',
    'developer', 'engineer', 'freelance', 'contract',
    'startup', 'saas', 'founder', 'build', 'create',
]

SYNONYMS = {
    'developer': ['dev', 'engineer', 'programmer', 'coder'],
    'hiring': ['hire', 'recruiting', 'looking for', 'seeking'],
    'freelance': ['freelancer', 'contract', 'contractor'],
    'startup': ['start-up', 'early stage', 'founded'],
    'build': ['create', 'develop', 'make', 'implement'],
}


def matches_keywords(text: str, keywords: list[str]) -> tuple[bool, list[str]]:
    if not text:
        return False, []
    if not keywords:
        return True, ['<all>']
    text_lower = text.lower()
    text_words = set(re.findall(r'\b\w+\b', text_lower))
    matched = []
    for keyword in keywords:
        kw = keyword.lower().strip()
        if kw in text_lower:
            matched.append(keyword); continue
        kw_words = {w for w in re.findall(r'\b\w+\b', kw) if len(w) > 2}
        if kw_words:
            common = kw_words & text_words
            if len(common) / len(kw_words) >= 0.5 and common:
                matched.append(keyword); continue
        for word in kw_words:
            if word in SYNONYMS and any(s in text_lower for s in SYNONYMS[word]):
                matched.append(keyword); break
    if not matched:
        sigs = [s for s in LEAD_SIGNALS if s in text_lower]
        if len(sigs) >= 2:
            matched = [f'[signal:{s}]' for s in sigs[:3]]
    return len(matched) > 0, list(dict.fromkeys(matched))


def calc_quality(data: dict[str, Any]) -> float:
    text = f"{data.get('title', '')} {data.get('content', '')}".lower()
    score = 20
    if any(k in text for k in ['hiring', 'job', 'opportunity', 'position']):
        score += 25
    if any(k in text for k in ['freelance', 'contract', 'consulting', 'gig']):
        score += 20
    if any(k in text for k in ['startup', 'founder', 'entrepreneur', 'saas']):
        score += 15
    if any(k in text for k in ['$', 'budget', 'pay', 'salary', 'revenue']):
        score += 10
    if any(k in text for k in ['guide', 'tutorial', 'how to', 'best practices']):
        score += 10
    if data.get('has_author', False):
        score += 5
    return min(100, score)


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        keywords = inp.get('keywords', [
            'hiring developer', 'startup founder', 'freelance',
            'looking for engineer', 'saas building', 'entrepreneur',
        ])
        max_results = int(inp.get('maxResults', 30))

        Actor.log.info(f'🚀 Medium Lead Scraper (RSS) | Keywords: {keywords}')

        def strip_html(text: str) -> str:
            if not text:
                return ""
            return re.sub(r'<[^>]+>', ' ', unescape(text))

        def extract_tags(keys: list[str]) -> list[str]:
            base = {'startup', 'hiring', 'developer', 'freelance', 'saas', 'entrepreneur', 'founder', 'job'}
            tags: set[str] = set()
            for k in keys:
                for word in re.findall(r'\b\w+\b', k.lower()):
                    if word in base:
                        tags.add(word)
            return sorted(tags) or ['startup', 'hiring']

        tags = extract_tags(keywords)
        Actor.log.info(f'Using tags: {tags}')

        leads_found = high_quality = 0
        seen_urls: set[str] = set()

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            for tag in tags:
                if leads_found >= max_results:
                    break
                feed_url = f'https://medium.com/feed/tag/{tag}'
                Actor.log.info(f'Fetching RSS: {feed_url}')
                try:
                    resp = await client.get(feed_url)
                except Exception as exc:
                    Actor.log.warning(f'RSS fetch failed for {tag}: {exc}')
                    continue
                if resp.status_code != 200:
                    Actor.log.warning(f'RSS fetch failed for {tag}: {resp.status_code}')
                    continue

                try:
                    root = ET.fromstring(resp.text)
                except Exception:
                    Actor.log.warning(f'RSS parse failed for {tag}')
                    continue

                for item in root.findall('.//item'):
                    if leads_found >= max_results:
                        break
                    title = (item.findtext('title') or '').strip()
                    link = (item.findtext('link') or '').strip()
                    desc = (item.findtext('description') or '').strip()
                    content_el = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
                    content = content_el.text if content_el is not None else ''
                    snippet = strip_html(content or desc)
                    if not link or link in seen_urls:
                        continue
                    seen_urls.add(link)

                    text = f"{title} {snippet}"
                    matched, matched_keywords = matches_keywords(text, keywords)
                    if not matched:
                        continue

                    score = calc_quality({
                        'title': title,
                        'content': snippet,
                        'has_author': False,
                    })
                    if score >= 40:
                        high_quality += 1

                    await Actor.push_data({
                        'platform': 'medium',
                        'source': 'Medium',
                        'url': link,
                        'title': title,
                        'content_preview': snippet[:500],
                        'author': '',
                        'scraped_at': datetime.now().isoformat(),
                        'matched_keywords': matched_keywords,
                        'quality_score': round(score, 1),
                        'lead_category': 'high_priority' if score >= 60 else 'medium_priority' if score >= 35 else 'low_priority',
                        'source_tag': tag,
                    })
                    leads_found += 1
                    Actor.log.info(f'   ✅ Lead #{leads_found}: {title[:40]}... (Q:{score:.0f})')

        Actor.log.info(f'✅ Complete! Leads: {leads_found}, HQ: {high_quality}')
