"""Hacker News Lead Scraper - Production-Grade Actor

Uses the official HN Firebase API with smart keyword matching and
improved quality scoring for better lead detection.
"""
from __future__ import annotations
import asyncio, json, random, re
from datetime import datetime
from typing import Any
from apify import Actor, Event
import httpx

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
]

# ── Smart keyword matching ────────────────────────────────────────────────
LEAD_SIGNALS = [
    'hiring', 'hire', 'looking for', 'seeking', 'need',
    'developer', 'engineer', 'freelance', 'contract', 'consultant',
    'cofounder', 'co-founder', 'help wanted', 'job', 'opportunity',
    'build', 'create', 'budget', 'pay', 'startup', 'saas', 'mvp',
    'remote', 'full-time', 'part-time', 'urgent', 'asap',
]

SYNONYMS = {
    'developer': ['dev', 'engineer', 'programmer', 'coder', 'software'],
    'hiring': ['hire', 'recruiting', 'looking for', 'seeking', 'need', 'wanted'],
    'freelance': ['freelancer', 'contract', 'contractor', 'consultant', 'gig'],
    'build': ['create', 'develop', 'make', 'implement', 'design'],
    'project': ['app', 'application', 'platform', 'tool', 'product', 'mvp', 'saas'],
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
            if len(common) / len(kw_words) >= 0.5 and len(common) >= 1:
                matched.append(keyword); continue
        for word in kw_words:
            if word in SYNONYMS and any(syn in text_lower for syn in SYNONYMS[word]):
                matched.append(keyword); break
    if not matched:
        sigs = [s for s in LEAD_SIGNALS if s in text_lower]
        if len(sigs) >= 2:
            matched = [f'[signal:{s}]' for s in sigs[:3]]
    return len(matched) > 0, list(dict.fromkeys(matched))


def extract_lead_quality_signals(story: dict[str, Any], comments_text: str = '') -> dict[str, Any]:
    combined = f"{story.get('title', '')} {story.get('text', '')} {comments_text}".lower()
    return {
        'has_email': bool(re.search(r'[\w.+-]+@[\w.-]+\.\w{2,}', combined)),
        'has_budget': any(k in combined for k in ['$', 'budget', 'pay', 'rate', 'compensation', 'salary']),
        'has_urgency': any(k in combined for k in ['asap', 'urgent', 'immediately', 'right away', 'quick']),
        'has_timeline': any(k in combined for k in ['deadline', 'within', 'by', 'timeline', 'schedule']),
        'has_contact': any(k in combined for k in ['email me', 'contact me', 'reach out', 'dm me', 'apply']),
        'engagement_score': story.get('score', 0) + (story.get('descendants', 0) * 2),
        'is_fresh': (datetime.now().timestamp() - story.get('time', 0)) < 86400 * 7,
        'is_show_hn': story.get('title', '').lower().startswith('show hn'),
        'is_ask_hn': story.get('title', '').lower().startswith('ask hn'),
    }


async def fetch_item(client: httpx.AsyncClient, item_id: int) -> dict | None:
    try:
        r = await client.get(f'https://hacker-news.firebaseio.com/v0/item/{item_id}.json', timeout=10.0)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


async def fetch_comments(client: httpx.AsyncClient, ids: list[int], depth: int = 0, max_depth: int = 2) -> str:
    if not ids or depth >= max_depth:
        return ''
    texts = []
    for cid in ids[:10]:
        c = await fetch_item(client, cid)
        if c and 'text' in c:
            texts.append(re.sub(r'<[^>]+>', ' ', c.get('text', '')))
            if 'kids' in c:
                texts.append(await fetch_comments(client, c['kids'], depth + 1, max_depth))
        await asyncio.sleep(0.05)
    return ' '.join(texts)


async def main() -> None:
    async with Actor:
        async def on_aborting():
            await asyncio.sleep(1); await Actor.exit()
        Actor.on(Event.ABORTING, on_aborting)

        inp = await Actor.get_input() or {}
        search_type = inp.get('searchType', 'all')
        keywords = inp.get('keywords', [
            'hiring', 'looking for developer', 'cofounder', 'freelance',
            'need engineer', 'startup job', 'seeking technical',
        ])
        max_stories = inp.get('maxStories', 100)
        include_comments = inp.get('includeComments', True)

        Actor.log.info('=' * 80)
        Actor.log.info('🚀 HackerNews Lead Scraper')
        Actor.log.info(f'   Type: {search_type} | Keywords: {keywords} | Max: {max_stories}')
        Actor.log.info('=' * 80)

        endpoints = {'all': 'newstories', 'ask': 'askstories', 'show': 'showstories', 'jobs': 'jobstories'}
        endpoint = endpoints.get(search_type, 'newstories')

        stories_processed = leads_found = high_quality_leads = 0

        async with httpx.AsyncClient(
            headers={'User-Agent': random.choice(USER_AGENTS)},
            follow_redirects=True,
            transport=httpx.AsyncHTTPTransport(retries=2),
        ) as client:
            r = await client.get(f'https://hacker-news.firebaseio.com/v0/{endpoint}.json', timeout=30.0)
            if r.status_code != 200:
                Actor.log.error(f'Failed to fetch story IDs: HTTP {r.status_code}')
                return

            story_ids = r.json()
            Actor.log.info(f'✅ Fetched {len(story_ids)} story IDs')

            for story_id in story_ids[:max_stories]:
                await asyncio.sleep(random.uniform(0.3, 0.8))
                story = await fetch_item(client, story_id)
                if not story or story.get('deleted') or story.get('dead'):
                    continue

                stories_processed += 1
                title = story.get('title', '')
                text = story.get('text', '')
                story_type = story.get('type', '')
                combined = f"{title} {text}"

                comments_text = ''
                if include_comments and 'kids' in story:
                    comments_text = await fetch_comments(client, story['kids'])
                    combined += ' ' + comments_text

                matches, matched_kw = matches_keywords(combined, keywords)
                if not matches:
                    continue

                leads_found += 1
                signals = extract_lead_quality_signals(story, comments_text)

                # Scoring: HN jobs get +40 base, Show/Ask HN get +20
                base = 40 if (story_type == 'job' or search_type == 'jobs') else 20 if (signals['is_show_hn'] or signals['is_ask_hn']) else 15
                score = base
                score += 25 if signals['has_email'] else 0
                score += 20 if signals['has_budget'] else 0
                score += 10 if signals['has_urgency'] else 0
                score += 10 if signals['has_contact'] else 0
                score += 5 if signals['is_fresh'] else 0
                score += min(5, signals['engagement_score'] / 20)
                score = min(100, score)

                if score >= 40:
                    high_quality_leads += 1

                await Actor.push_data({
                    'platform': 'hackernews',
                    'source': f'{search_type.upper()} HN',
                    'story_id': story_id,
                    'url': f'https://news.ycombinator.com/item?id={story_id}',
                    'title': title,
                    'content': text,
                    'content_preview': text[:500] if text else '',
                    'external_url': story.get('url', ''),
                    'author': story.get('by', ''),
                    'author_url': f'https://news.ycombinator.com/user?id={story.get("by", "")}',
                    'story_type': story_type,
                    'score': story.get('score', 0),
                    'num_comments': story.get('descendants', 0),
                    'created_at': datetime.fromtimestamp(story.get('time', 0)).isoformat(),
                    'scraped_at': datetime.now().isoformat(),
                    'matched_keywords': matched_kw,
                    'quality_score': round(score, 1),
                    'quality_signals': signals,
                    'lead_category': 'high_priority' if score >= 60 else 'medium_priority' if score >= 35 else 'low_priority',
                    'has_contact_info': signals['has_email'] or signals['has_contact'],
                    'urgency_level': 'high' if signals['has_urgency'] else 'normal',
                })
                Actor.log.info(f'✅ Lead #{leads_found}: {title[:50]}... (Q:{score:.0f})')

                if stories_processed % 20 == 0:
                    Actor.log.info(f'📊 {stories_processed} processed, {leads_found} leads')

        Actor.log.info(f'✅ COMPLETE! Processed:{stories_processed} Leads:{leads_found} HQ:{high_quality_leads}')
