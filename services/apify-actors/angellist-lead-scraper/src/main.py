"""AngelList/YC Lead Scraper - Y Combinator Work at a Startup

Since AngelList/Wellfound requires authentication, this actor scrapes 
Y Combinator's "Work at a Startup" jobs board which is publicly 
accessible and contains high-quality startup job listings.
Also searches Google for Wellfound listings.
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


def calc_quality(text: str) -> float:
    text = text.lower()
    score = 25  # High base - YC startups are quality leads
    if any(k in text for k in ['senior', 'lead', 'staff', 'principal']):
        score += 15
    if any(k in text for k in ['remote', 'hybrid', 'anywhere']):
        score += 10
    if any(k in text for k in ['$', 'salary', 'compensation', 'equity', 'k-']):
        score += 15
    if any(k in text for k in ['developer', 'engineer', 'architect', 'designer']):
        score += 10
    if any(k in text for k in ['fullstack', 'full-stack', 'backend', 'frontend']):
        score += 10
    if any(k in text for k in ['series a', 'series b', 'funded', 'raised']):
        score += 10
    if any(k in text for k in ['founding', 'first hire', 'early stage']):
        score += 15
    return min(100, score)


async def main() -> None:
    async with Actor:
        async def on_aborting():
            await asyncio.sleep(1); await Actor.exit()
        Actor.on(Event.ABORTING, on_aborting)

        inp = await Actor.get_input() or {}
        keywords = inp.get('keywords', [
            'software engineer', 'developer', 'full stack',
            'frontend', 'backend', 'react', 'python',
            'founding engineer', 'startup',
        ])
        max_results = inp.get('maxResults', 50)

        Actor.log.info('=' * 80)
        Actor.log.info('🚀 AngelList/YC Lead Scraper')
        Actor.log.info(f'   Keywords: {keywords} | Max: {max_results}')
        Actor.log.info('=' * 80)

        leads_found = high_quality = 0
        seen: set[str] = set()

        async with httpx.AsyncClient(
            headers={'User-Agent': random.choice(USER_AGENTS), 'Accept': 'application/json'},
            follow_redirects=True,
            transport=httpx.AsyncHTTPTransport(retries=2),
        ) as client:
            # Strategy 1: YC Work at a Startup (JSON API)
            Actor.log.info('📡 Fetching YC Work at a Startup listings...')
            try:
                # Try the YC jobs API endpoint
                yc_url = 'https://www.workatastartup.com/companies?demographic=any&hasEquity=any&hasSalary=any&industry=any&interviewProcess=any&jobType=any&layout=list-compact&sortBy=created_desc&tab=any&usVisaNotRequired=any'

                resp = await client.get(yc_url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html, application/json',
                }, timeout=30.0, follow_redirects=True)

                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, 'html.parser')

                    # Look for job/company cards
                    cards = soup.select('div[class*="company"], div[class*="job"], tr, .company-row')
                    Actor.log.info(f'   YC WaaS: found {len(cards)} company/job cards')

                    for card in cards[:max_results]:
                        try:
                            title_el = card.select_one('h2, h3, h4, .company-name, a[href*="/companies/"]')
                            title = title_el.get_text(strip=True) if title_el else ''

                            link_el = card.select_one('a[href]')
                            href = link_el.get('href', '') if link_el else ''
                            url = href if href.startswith('http') else f'https://www.workatastartup.com{href}' if href else ''

                            if not title or url in seen:
                                continue
                            seen.add(url)

                            desc_el = card.select_one('p, .description, .tagline')
                            desc = desc_el.get_text(strip=True) if desc_el else ''

                            combined = f"{title} {desc}"
                            score = calc_quality(combined)
                            leads_found += 1
                            if score >= 40:
                                high_quality += 1

                            await Actor.push_data({
                                'platform': 'angellist',
                                'source': 'YC Work at a Startup',
                                'url': url,
                                'title': title,
                                'description': desc,
                                'scraped_at': datetime.now().isoformat(),
                                'quality_score': round(score, 1),
                                'lead_category': 'high_priority' if score >= 60 else 'medium_priority' if score >= 35 else 'low_priority',
                            })
                            Actor.log.info(f'   ✅ Lead #{leads_found}: {title[:45]}... (Q:{score:.0f})')

                        except Exception:
                            continue

            except Exception as e:
                Actor.log.warning(f'   YC WaaS error: {e}')

            # Strategy 2: Google search for Wellfound/AngelList
            for kw_idx, keyword in enumerate(keywords):
                if leads_found >= max_results:
                    break
                Actor.log.info(f'🔍 Google search: "{keyword}" ({kw_idx+1}/{len(keywords)})')
                if kw_idx > 0 or leads_found > 0:
                    await asyncio.sleep(random.uniform(5, 10))

                try:
                    queries = [
                        f'site:wellfound.com {keyword}',
                        f'site:workatastartup.com {keyword}',
                    ]

                    for query in queries:
                        if leads_found >= max_results:
                            break

                        resp = await client.get(
                            f'https://www.google.com/search?q={quote_plus(query)}&num=15',
                            headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                                'Accept': 'text/html',
                                'Accept-Language': 'en-US,en;q=0.9',
                            }, timeout=30.0, follow_redirects=True
                        )

                        if resp.status_code != 200:
                            continue

                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(resp.text, 'html.parser')

                        for result in soup.select('div.g'):
                            if leads_found >= max_results:
                                break
                            link_el = result.select_one('a[href*="wellfound.com"], a[href*="workatastartup.com"]')
                            if not link_el:
                                continue
                            url = link_el.get('href', '')
                            if url.startswith('/url?'):
                                import urllib.parse
                                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                                url = parsed.get('q', [url])[0]
                            if not url or url in seen:
                                continue
                            seen.add(url)

                            title_el = result.select_one('h3')
                            title = title_el.get_text(strip=True) if title_el else ''
                            snippet_el = result.select_one('div.VwiC3b')
                            snippet = snippet_el.get_text(strip=True) if snippet_el else ''

                            score = calc_quality(f'{title} {snippet}')
                            leads_found += 1
                            if score >= 40:
                                high_quality += 1

                            await Actor.push_data({
                                'platform': 'angellist',
                                'source': 'Wellfound/YC (via Google)',
                                'url': url, 'title': title,
                                'content_preview': snippet[:500],
                                'scraped_at': datetime.now().isoformat(),
                                'search_keyword': keyword,
                                'quality_score': round(score, 1),
                                'lead_category': 'high_priority' if score >= 60 else 'medium_priority',
                            })
                            Actor.log.info(f'   ✅ Lead #{leads_found}: {title[:45]}... (Q:{score:.0f})')

                        await asyncio.sleep(random.uniform(3, 5))

                except Exception as e:
                    Actor.log.warning(f'   Error: {e}')

        Actor.log.info(f'✅ COMPLETE! Leads: {leads_found}, HQ: {high_quality}')
