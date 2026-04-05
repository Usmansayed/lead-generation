"""Stack Overflow Lead Scraper - Production-Grade Actor

Uses the Stack Exchange API v2.3 for reliable structured data extraction.
Finds questions with lead signals like budget mentions, hiring, help wanted, etc.
Features: retry logic, user-agent rotation, robust error handling.
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


async def fetch_with_retry(client: httpx.AsyncClient, url: str, max_retries: int = 3) -> httpx.Response | None:
    """Fetch URL with automatic retry on failure."""
    for attempt in range(max_retries):
        try:
            resp = await client.get(url, timeout=30.0)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 429:  # Rate limited
                wait = (attempt + 1) * 5
                Actor.log.warning(f'Rate limited, waiting {wait}s...')
                await asyncio.sleep(wait)
                continue
            if resp.status_code >= 500:
                await asyncio.sleep((attempt + 1) * 2)
                continue
            Actor.log.warning(f'HTTP {resp.status_code} for {url[:80]}')
            return resp
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            Actor.log.warning(f'Attempt {attempt+1}/{max_retries} failed: {e}')
            if attempt < max_retries - 1:
                await asyncio.sleep((attempt + 1) * 2)
    return None

LEAD_SIGNALS = [
    'hiring', 'hire', 'looking for', 'seeking', 'need',
    'developer', 'engineer', 'freelance', 'contract', 'consultant',
    'help wanted', 'job', 'opportunity', 'build', 'create',
    'budget', 'pay', 'startup', 'saas', 'mvp', 'recommendation',
]

SYNONYMS = {
    'developer': ['dev', 'engineer', 'programmer', 'coder'],
    'hiring': ['hire', 'recruiting', 'looking for', 'seeking', 'need'],
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


def calc_quality(q: dict[str, Any]) -> float:
    text = f"{q.get('title', '')} {q.get('body', '')}".lower()
    tags = ' '.join(q.get('tags', []))
    combined = f"{text} {tags}"
    score = 15  # base
    if any(k in combined for k in ['$', 'budget', 'pay', 'bounty']):
        score += 20
    if any(k in combined for k in ['hiring', 'job', 'position', 'career']):
        score += 20
    if any(k in combined for k in ['help', 'recommend', 'looking for', 'need']):
        score += 15
    if any(k in combined for k in ['urgent', 'asap', 'immediately']):
        score += 10
    if q.get('bounty_amount', 0) > 0:
        score += 25
    if q.get('answer_count', 0) == 0:
        score += 5  # unanswered = opportunity
    if q.get('view_count', 0) > 100:
        score += 5
    return min(100, score)


async def main() -> None:
    async with Actor:
        async def on_aborting():
            await asyncio.sleep(1); await Actor.exit()
        Actor.on(Event.ABORTING, on_aborting)

        inp = await Actor.get_input() or {}
        keywords = inp.get('keywords', [
            'looking for developer', 'need help building',
            'hiring', 'freelance developer', 'recommend a tool',
            'best framework for', 'how to build',
        ])
        tags = inp.get('tags', ['python', 'javascript', 'react', 'node.js', 'api', 'web-development'])
        max_questions = inp.get('maxQuestions', 50)

        Actor.log.info('=' * 80)
        Actor.log.info('🚀 Stack Overflow Lead Scraper - API Mode')
        Actor.log.info(f'   Keywords: {keywords} | Tags: {tags} | Max: {max_questions}')
        Actor.log.info('=' * 80)

        total = leads_found = high_quality = 0
        seen: set[int] = set()

        async with httpx.AsyncClient(
            headers={'User-Agent': random.choice(USER_AGENTS), 'Accept': 'application/json'},
            follow_redirects=True,
            transport=httpx.AsyncHTTPTransport(retries=2),
        ) as client:
            # Strategy 1: Search by keywords using SE API
            for kw_idx, keyword in enumerate(keywords):
                Actor.log.info(f'🔍 Searching: "{keyword}" ({kw_idx+1}/{len(keywords)})')
                if kw_idx > 0:
                    await asyncio.sleep(random.uniform(1, 2))

                try:
                    api_url = (
                        f'https://api.stackexchange.com/2.3/search/advanced'
                        f'?order=desc&sort=creation&q={quote_plus(keyword)}'
                        f'&site=stackoverflow&filter=withbody&pagesize={min(max_questions, 100)}'
                    )
                    resp = await client.get(api_url, timeout=30.0)

                    if resp.status_code != 200:
                        Actor.log.warning(f'   API returned {resp.status_code}')
                        continue

                    data = resp.json()
                    items = data.get('items', [])
                    Actor.log.info(f'   Found {len(items)} questions')

                    for q in items:
                        qid = q.get('question_id', 0)
                        if qid in seen:
                            continue
                        seen.add(qid)
                        total += 1

                        title = q.get('title', '')
                        body = q.get('body', '')
                        # Strip HTML from body
                        body_clean = re.sub(r'<[^>]+>', ' ', body)

                        combined = f"{title} {body_clean}"
                        matches, matched_kw = matches_keywords(combined, keywords)
                        if not matches:
                            continue

                        score = calc_quality(q)
                        leads_found += 1
                        if score >= 40:
                            high_quality += 1

                        await Actor.push_data({
                            'platform': 'stackoverflow',
                            'source': 'Stack Overflow',
                            'url': q.get('link', f'https://stackoverflow.com/q/{qid}'),
                            'title': title,
                            'body_preview': body_clean[:500],
                            'tags': q.get('tags', []),
                            'author': q.get('owner', {}).get('display_name', ''),
                            'author_url': q.get('owner', {}).get('link', ''),
                            'score': q.get('score', 0),
                            'view_count': q.get('view_count', 0),
                            'answer_count': q.get('answer_count', 0),
                            'is_answered': q.get('is_answered', False),
                            'bounty_amount': q.get('bounty_amount', 0),
                            'creation_date': datetime.fromtimestamp(q.get('creation_date', 0)).isoformat(),
                            'scraped_at': datetime.now().isoformat(),
                            'matched_keywords': matched_kw,
                            'quality_score': round(score, 1),
                            'lead_category': 'high_priority' if score >= 60 else 'medium_priority' if score >= 35 else 'low_priority',
                            'has_contact_info': bool(re.search(r'[\w.+-]+@[\w.-]+\.\w{2,}', combined)),
                        })
                        Actor.log.info(f'   ✅ Lead #{leads_found}: {title[:45]}... (Q:{score:.0f})')

                except Exception as e:
                    Actor.log.error(f'   ❌ Error: {e}')

            # Strategy 2: Search by popular tags for bounty questions
            Actor.log.info('🏷️ Searching bounty questions by tags...')
            for tag in tags[:5]:
                try:
                    await asyncio.sleep(random.uniform(1, 2))
                    url = (
                        f'https://api.stackexchange.com/2.3/questions/featured'
                        f'?order=desc&sort=creation&tagged={quote_plus(tag)}'
                        f'&site=stackoverflow&filter=withbody&pagesize=20'
                    )
                    resp = await client.get(url, timeout=30.0)
                    if resp.status_code == 200:
                        items = resp.json().get('items', [])
                        Actor.log.info(f'   Tag [{tag}]: {len(items)} bounty questions')
                        for q in items:
                            qid = q.get('question_id', 0)
                            if qid in seen:
                                continue
                            seen.add(qid)
                            total += 1
                            leads_found += 1
                            title = q.get('title', '')
                            body_clean = re.sub(r'<[^>]+>', ' ', q.get('body', ''))
                            score = calc_quality(q)
                            if score >= 40:
                                high_quality += 1
                            await Actor.push_data({
                                'platform': 'stackoverflow',
                                'source': 'SO Bounty',
                                'url': q.get('link', ''),
                                'title': title,
                                'body_preview': body_clean[:500],
                                'tags': q.get('tags', []),
                                'bounty_amount': q.get('bounty_amount', 0),
                                'author': q.get('owner', {}).get('display_name', ''),
                                'scraped_at': datetime.now().isoformat(),
                                'quality_score': round(score, 1),
                                'lead_category': 'high_priority' if score >= 60 else 'medium_priority',
                            })
                except Exception as e:
                    Actor.log.warning(f'   Tag [{tag}] error: {e}')

        Actor.log.info(f'✅ COMPLETE! Questions:{total} Leads:{leads_found} HQ:{high_quality}')
