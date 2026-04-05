"""Freelancer Lead Scraper - Production-Grade Actor

Scrapes Freelancer.com using their public API instead of browser automation
for maximum reliability. All jobs matching the keyword search are stored as
leads (no restrictive keyword post-filtering).
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
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
]


def extract_budget(text: str) -> tuple[float | None, str]:
    if not text:
        return None, 'not_specified'
    fixed = re.search(r'[\$€£]\s*(\d+(?:,\d+)?(?:\.\d{2})?)', text)
    if fixed:
        amt = float(fixed.group(1).replace(',', ''))
        if amt >= 50:
            return amt, 'fixed'
    hourly = re.search(r'[\$€£]\s*(\d+(?:\.\d{2})?)\s*(?:-|to)\s*[\$€£]\s*(\d+(?:\.\d{2})?)', text)
    if hourly and 'hour' in text.lower():
        return (float(hourly.group(1)) + float(hourly.group(2))) / 2, 'hourly'
    return None, 'not_specified'


def calc_quality(job: dict[str, Any]) -> float:
    text = f"{job.get('title', '')} {job.get('description', '')}".lower()
    budget_amt, budget_type = extract_budget(text)
    score = 15  # base
    if budget_amt:
        score += 25 if (budget_type == 'fixed' and budget_amt >= 500) else 20 if budget_amt else 10
    if any(k in text for k in ['long term', 'ongoing', 'monthly']):
        score += 15
    if any(k in text for k in ['expert', 'senior', 'experienced', 'professional']):
        score += 15
    if any(k in text for k in ['asap', 'urgent', 'immediately']):
        score += 10
    if any(k in text for k in ['deadline', 'within', 'timeline']):
        score += 5
    bids = job.get('bids_count', 0)
    if bids < 5:
        score += 10
    elif bids < 15:
        score += 5
    return min(100, score)


async def main() -> None:
    async with Actor:
        async def on_aborting():
            await asyncio.sleep(1); await Actor.exit()
        Actor.on(Event.ABORTING, on_aborting)

        inp = await Actor.get_input() or {}
        keywords = inp.get('keywords', [
            'web developer', 'python developer', 'react developer',
            'mobile app', 'full stack', 'api development',
            'saas', 'mvp', 'startup',
        ])
        max_jobs = inp.get('maxJobsPerKeyword', 30)

        Actor.log.info('=' * 80)
        Actor.log.info('🚀 Freelancer Lead Scraper - API Mode')
        Actor.log.info(f'   Keywords: {keywords} | Max/kw: {max_jobs}')
        Actor.log.info('=' * 80)

        total_jobs = leads_found = high_quality = 0
        seen_urls: set[str] = set()

        async with httpx.AsyncClient(
            headers={'User-Agent': random.choice(USER_AGENTS), 'Accept': 'application/json'},
            follow_redirects=True,
            transport=httpx.AsyncHTTPTransport(retries=2),
        ) as client:
            for kw_idx, keyword in enumerate(keywords):
                Actor.log.info(f'🔍 Searching: "{keyword}" ({kw_idx+1}/{len(keywords)})')

                if kw_idx > 0:
                    await asyncio.sleep(random.uniform(2, 4))

                # Try Freelancer API first
                api_url = f'https://www.freelancer.com/api/projects/0.1/projects/active/?query={quote_plus(keyword)}&compact=true&limit={max_jobs}&full_description=true&job_details=true&sort_field=time_updated&sort_direction=desc'

                try:
                    headers = {'User-Agent': USER_AGENTS[0], 'Accept': 'application/json'}
                    resp = await client.get(api_url, headers=headers, timeout=30.0, follow_redirects=True)

                    if resp.status_code == 200:
                        data = resp.json()
                        projects = data.get('result', {}).get('projects', [])
                        Actor.log.info(f'   API returned {len(projects)} projects')

                        for proj in projects:
                            pid = proj.get('id', '')
                            url = f'https://www.freelancer.com/projects/{proj.get("seo_url", pid)}'
                            if url in seen_urls:
                                continue
                            seen_urls.add(url)
                            total_jobs += 1

                            title = proj.get('title', '')
                            desc = proj.get('description', '') or proj.get('preview_description', '')
                            budget_min = proj.get('budget', {}).get('minimum', 0)
                            budget_max = proj.get('budget', {}).get('maximum', 0)
                            currency = proj.get('currency', {}).get('code', 'USD')
                            bid_count = proj.get('bid_stats', {}).get('bid_count', 0)
                            skills = [j.get('name', '') for j in proj.get('jobs', [])]

                            job_data = {
                                'title': title, 'description': desc,
                                'bids_count': bid_count,
                            }
                            score = calc_quality(job_data)
                            # Budget boost from structured data
                            if budget_max >= 500:
                                score = min(100, score + 10)

                            leads_found += 1
                            if score >= 40:
                                high_quality += 1

                            await Actor.push_data({
                                'platform': 'freelancer',
                                'source': 'Freelancer.com',
                                'url': url,
                                'title': title,
                                'description': desc,
                                'description_preview': desc[:500],
                                'budget_min': budget_min,
                                'budget_max': budget_max,
                                'budget_currency': currency,
                                'bid_count': bid_count,
                                'skills': skills,
                                'time_submitted': proj.get('time_submitted'),
                                'scraped_at': datetime.now().isoformat(),
                                'search_keyword': keyword,
                                'quality_score': round(score, 1),
                                'lead_category': 'high_priority' if score >= 60 else 'medium_priority' if score >= 35 else 'low_priority',
                                'urgency_level': 'high' if proj.get('urgency') else 'normal',
                            })
                            Actor.log.info(f'   ✅ Lead #{leads_found}: {title[:45]}... (Q:{score:.0f})')

                    else:
                        Actor.log.warning(f'   API returned {resp.status_code}, trying HTML fallback')
                        # HTML fallback - scrape search results page
                        html_url = f'https://www.freelancer.com/jobs/?keyword={quote_plus(keyword)}'
                        resp2 = await client.get(html_url, headers={'User-Agent': USER_AGENTS[0]}, timeout=30.0, follow_redirects=True)
                        if resp2.status_code == 200:
                            from bs4 import BeautifulSoup
                            soup = BeautifulSoup(resp2.text, 'html.parser')
                            cards = soup.select('.JobSearchCard-item, [data-job-id], .project-details')
                            Actor.log.info(f'   HTML found {len(cards)} job cards')
                            for card in cards[:max_jobs]:
                                title_el = card.select_one('h2 a, .JobSearchCard-primary-heading a')
                                title = title_el.get_text(strip=True) if title_el else ''
                                desc_el = card.select_one('.JobSearchCard-primary-description, p.description')
                                desc = desc_el.get_text(strip=True) if desc_el else ''
                                link = title_el.get('href', '') if title_el else ''
                                url = f'https://www.freelancer.com{link}' if link.startswith('/') else link
                                if not title or url in seen_urls:
                                    continue
                                seen_urls.add(url)
                                total_jobs += 1
                                leads_found += 1
                                score = calc_quality({'title': title, 'description': desc, 'bids_count': 0})
                                if score >= 40:
                                    high_quality += 1
                                await Actor.push_data({
                                    'platform': 'freelancer', 'source': 'Freelancer.com',
                                    'url': url, 'title': title, 'description': desc,
                                    'description_preview': desc[:500],
                                    'scraped_at': datetime.now().isoformat(),
                                    'search_keyword': keyword,
                                    'quality_score': round(score, 1),
                                    'lead_category': 'high_priority' if score >= 60 else 'medium_priority',
                                })
                except Exception as e:
                    Actor.log.error(f'   ❌ Error: {e}')

        Actor.log.info(f'✅ COMPLETE! Jobs:{total_jobs} Leads:{leads_found} HQ:{high_quality}')
