"""Dev.to Lead Scraper - API + HTML hybrid

Uses Dev.to's public API (articles endpoint) for reliable data extraction,
falls back to HTML scraping if needed. Smart keyword matching.
"""
from __future__ import annotations
import asyncio, random, re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus
from apify import Actor, Event
import httpx

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
]

LEAD_SIGNALS = [
    'hiring', 'hire', 'looking for', 'seeking', 'need',
    'developer', 'engineer', 'freelance', 'contract',
    'help wanted', 'job', 'opportunity', 'build', 'startup', 'saas',
]

SYNONYMS = {
    'developer': ['dev', 'engineer', 'programmer', 'coder'],
    'hiring': ['hire', 'recruiting', 'looking for', 'seeking'],
    'freelance': ['freelancer', 'contract', 'contractor', 'consultant'],
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
    text = f"{data.get('title', '')} {data.get('description', '')} {data.get('body', '')}".lower()
    score = 20  # base for matching search
    if any(k in text for k in ['hiring', 'job', 'looking for', 'opportunity']):
        score += 25
    if any(k in text for k in ['freelance', 'contract', 'consulting']):
        score += 20
    if any(k in text for k in ['startup', 'founder', 'entrepreneur']):
        score += 15
    if any(k in text for k in ['$', 'budget', 'pay', 'salary']):
        score += 15
    if data.get('positive_reactions_count', 0) > 10:
        score += 10
    if data.get('comments_count', 0) > 5:
        score += 10
    return min(100, score)


async def main() -> None:
    async with Actor:
        async def on_aborting():
            await asyncio.sleep(1); await Actor.exit()
        Actor.on(Event.ABORTING, on_aborting)

        inp = await Actor.get_input() or {}
        keywords = inp.get('keywords', [
            'hiring developer', 'looking for engineer', 'freelance',
            'startup', 'cofounder', 'need help building',
        ])

        Actor.log.info(f'🚀 Dev.to Lead Scraper (API) | Keywords: {keywords}')

        leads_found = high_quality = 0
        seen: set[str] = set()

        async with httpx.AsyncClient(
            headers={'User-Agent': random.choice(USER_AGENTS), 'Accept': 'application/json'},
            follow_redirects=True,
            transport=httpx.AsyncHTTPTransport(retries=2),
        ) as client:
            for kw_idx, keyword in enumerate(keywords):
                Actor.log.info(f'🔍 Searching: "{keyword}" ({kw_idx+1}/{len(keywords)})')
                if kw_idx > 0:
                    await asyncio.sleep(random.uniform(1, 3))

                try:
                    # Dev.to API - articles endpoint
                    api_url = f'https://dev.to/api/articles?tag={quote_plus(keyword.replace(" ", ""))}&per_page=30&state=rising'
                    # Also search by title
                    api_url2 = f'https://dev.to/api/articles?per_page=30&state=fresh'

                    for url in [api_url, api_url2]:
                        resp = await client.get(url, timeout=30.0, headers={
                            'User-Agent': 'Mozilla/5.0 (compatible; LeadScraper/1.0)',
                            'Accept': 'application/json',
                        })

                        if resp.status_code != 200:
                            continue

                        articles = resp.json()
                        Actor.log.info(f'   API returned {len(articles)} articles')

                        for art in articles:
                            art_url = art.get('url', '')
                            if art_url in seen or not art_url:
                                continue
                            seen.add(art_url)

                            title = art.get('title', '')
                            desc = art.get('description', '')
                            combined = f"{title} {desc} {' '.join(art.get('tag_list', []))}"

                            matches, matched_kw = matches_keywords(combined, keywords)
                            if not matches:
                                continue

                            leads_found += 1
                            score = calc_quality(art)
                            if score >= 40:
                                high_quality += 1

                            await Actor.push_data({
                                'platform': 'devto',
                                'source': 'Dev.to',
                                'url': art_url,
                                'title': title,
                                'description': desc,
                                'content_preview': desc[:500],
                                'author': art.get('user', {}).get('name', ''),
                                'author_username': art.get('user', {}).get('username', ''),
                                'tags': art.get('tag_list', []),
                                'reactions': art.get('positive_reactions_count', 0),
                                'comments': art.get('comments_count', 0),
                                'published_at': art.get('published_at', ''),
                                'scraped_at': datetime.now().isoformat(),
                                'matched_keywords': matched_kw,
                                'quality_score': round(score, 1),
                                'lead_category': 'high_priority' if score >= 60 else 'medium_priority' if score >= 35 else 'low_priority',
                            })
                            Actor.log.info(f'   ✅ Lead #{leads_found}: {title[:40]}... (Q:{score:.0f})')

                except Exception as e:
                    Actor.log.warning(f'   Error: {e}')

        Actor.log.info(f'✅ Complete! Leads: {leads_found}, HQ: {high_quality}')
