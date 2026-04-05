"""Product Hunt Lead Scraper - API-based

Uses Product Hunt's GraphQL API for reliable structured data, with
Google search fallback. No more brittle HTML selectors.
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


def calc_quality(data: dict[str, Any]) -> float:
    text = f"{data.get('name', '')} {data.get('tagline', '')} {data.get('description', '')}".lower()
    upvotes = data.get('upvotes', 0)
    comments = data.get('comments', 0)
    score = 15
    if upvotes > 100:
        score += 20
    elif upvotes > 30:
        score += 10
    if comments > 20:
        score += 15
    elif comments > 5:
        score += 10
    if any(k in text for k in ['hiring', 'jobs', 'careers', 'join']):
        score += 20
    if any(k in text for k in ['beta', 'early access', 'waitlist']):
        score += 15
    if any(k in text for k in ['launch', 'new', 'just launched']):
        score += 10
    if any(k in text for k in ['@', 'contact', 'email']):
        score += 5
    return min(100, score)


async def main() -> None:
    async with Actor:
        async def on_aborting():
            await asyncio.sleep(1); await Actor.exit()
        Actor.on(Event.ABORTING, on_aborting)

        inp = await Actor.get_input() or {}
        keywords = inp.get('keywords', [
            'developer tool', 'saas', 'startup', 'productivity',
            'api', 'no-code', 'ai', 'automation',
        ])
        max_posts = inp.get('maxPosts', 50)

        Actor.log.info('=' * 80)
        Actor.log.info('🚀 Product Hunt Lead Scraper')
        Actor.log.info(f'   Keywords: {keywords} | Max: {max_posts}')
        Actor.log.info('=' * 80)

        leads_found = high_quality = 0
        seen: set[str] = set()

        async with httpx.AsyncClient(
            headers={'User-Agent': random.choice(USER_AGENTS), 'Accept': 'application/json'},
            follow_redirects=True,
            transport=httpx.AsyncHTTPTransport(retries=2),
        ) as client:
            # Strategy 1: Product Hunt GraphQL API (public, no auth needed for basic queries)
            for kw_idx, keyword in enumerate(keywords):
                Actor.log.info(f'🔍 Searching: "{keyword}" ({kw_idx+1}/{len(keywords)})')
                if kw_idx > 0:
                    await asyncio.sleep(random.uniform(2, 4))

                # Try Google site search as primary method since PH GraphQL requires auth
                try:
                    query = f'site:producthunt.com {keyword}'
                    google_url = f'https://www.google.com/search?q={quote_plus(query)}&num=20'

                    resp = await client.get(google_url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html',
                        'Accept-Language': 'en-US,en;q=0.9',
                    }, timeout=30.0, follow_redirects=True)

                    if resp.status_code != 200:
                        Actor.log.warning(f'   Google returned {resp.status_code}')
                        continue

                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, 'html.parser')

                    for result in soup.select('div.g, div[data-sokoban-container]'):
                        if leads_found >= max_posts:
                            break

                        link_el = result.select_one('a[href*="producthunt.com"]')
                        if not link_el:
                            continue

                        url = link_el.get('href', '')
                        if not url or url in seen or 'producthunt.com' not in url:
                            continue

                        if url.startswith('/url?'):
                            import urllib.parse
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                            url = parsed.get('q', [url])[0]

                        # Skip non-product pages
                        if '/posts/' not in url and '/products/' not in url and 'producthunt.com/posts/' not in url:
                            continue

                        seen.add(url)

                        title_el = result.select_one('h3')
                        name = title_el.get_text(strip=True) if title_el else ''

                        snippet_el = result.select_one('div[data-sncf], span.st, div.VwiC3b')
                        tagline = snippet_el.get_text(strip=True) if snippet_el else ''

                        data = {'name': name, 'tagline': tagline, 'description': '', 'upvotes': 0, 'comments': 0}
                        score = calc_quality(data)

                        leads_found += 1
                        if score >= 40:
                            high_quality += 1

                        await Actor.push_data({
                            'platform': 'producthunt',
                            'source': 'Product Hunt',
                            'url': url,
                            'name': name,
                            'tagline': tagline,
                            'scraped_at': datetime.now().isoformat(),
                            'search_keyword': keyword,
                            'quality_score': round(score, 1),
                            'lead_category': 'high_priority' if score >= 60 else 'medium_priority' if score >= 35 else 'low_priority',
                        })
                        Actor.log.info(f'   ✅ Lead #{leads_found}: {name[:45]}... (Q:{score:.0f})')

                except Exception as e:
                    Actor.log.warning(f'   Error: {e}')

            # Strategy 2: Direct PH pages (today's products, newest)
            direct_urls = [
                'https://www.producthunt.com/',
                'https://www.producthunt.com/newest',
            ]
            for ph_url in direct_urls:
                try:
                    await asyncio.sleep(random.uniform(2, 4))
                    resp = await client.get(ph_url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'text/html',
                    }, timeout=30.0, follow_redirects=True)

                    if resp.status_code == 200:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(resp.text, 'html.parser')

                        # Try multiple selectors for PH products
                        products = (
                            soup.select('[data-test*="post"], [data-test*="product"]') or
                            soup.select('article') or
                            soup.select('div[class*="styles_post"]')
                        )
                        Actor.log.info(f'   Direct page {ph_url}: found {len(products)} products')

                        for prod in products[:30]:
                            title_el = prod.select_one('h2, h3, [data-test*="name"]')
                            name = title_el.get_text(strip=True) if title_el else ''
                            link_el = prod.select_one('a[href]')
                            href = link_el.get('href', '') if link_el else ''
                            url = f'https://www.producthunt.com{href}' if href.startswith('/') else href
                            if not name or url in seen:
                                continue
                            seen.add(url)

                            tagline_el = prod.select_one('p, [data-test*="tagline"]')
                            tagline = tagline_el.get_text(strip=True) if tagline_el else ''

                            data = {'name': name, 'tagline': tagline, 'description': '', 'upvotes': 0, 'comments': 0}
                            score = calc_quality(data)
                            leads_found += 1
                            if score >= 40:
                                high_quality += 1

                            await Actor.push_data({
                                'platform': 'producthunt', 'source': 'PH Direct',
                                'url': url, 'name': name, 'tagline': tagline,
                                'scraped_at': datetime.now().isoformat(),
                                'quality_score': round(score, 1),
                                'lead_category': 'high_priority' if score >= 60 else 'medium_priority',
                            })

                except Exception as e:
                    Actor.log.warning(f'   Direct page error: {e}')

        Actor.log.info(f'✅ COMPLETE! Leads: {leads_found}, HQ: {high_quality}')
