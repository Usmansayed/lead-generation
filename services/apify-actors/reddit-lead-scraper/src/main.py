"""Reddit Lead Scraper - Professional Grade (Crawlee Framework)

Rebuilt using Apify/Crawlee best practices for maximum reliability:
- Crawler framework with automatic retries
- Built-in proxy rotation
- Session management
- Streaming data storage
- Smart fuzzy keyword matching
"""

import asyncio
import re
from datetime import datetime
from typing import Any
from apify import Actor
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee import Request
from crawlee.sessions import SessionPool


# ── Smart keyword matching (inline to keep actor self-contained) ──────────

LEAD_SIGNALS = [
    'hiring', 'hire', 'looking for', 'seeking', 'need',
    'developer', 'engineer', 'programmer', 'designer',
    'freelance', 'contract', 'consultant', 'cofounder', 'co-founder',
    'help wanted', 'job', 'opportunity', 'project',
    'build', 'create', 'develop', 'budget', 'pay',
    'startup', 'saas', 'mvp', 'prototype',
    'remote', 'full-time', 'part-time', 'urgent', 'asap',
]

SYNONYMS = {
    'developer': ['dev', 'engineer', 'programmer', 'coder', 'software'],
    'hiring': ['hire', 'recruiting', 'looking for', 'seeking', 'need', 'wanted'],
    'freelance': ['freelancer', 'contract', 'contractor', 'consultant', 'gig'],
    'cofounder': ['co-founder', 'cofounder', 'co founder', 'technical founder'],
    'build': ['create', 'develop', 'make', 'implement', 'design'],
    'project': ['app', 'application', 'platform', 'tool', 'product', 'mvp', 'saas'],
    'web': ['website', 'webapp', 'web app', 'web application'],
    'help': ['assist', 'support', 'guidance', 'advice'],
    'budget': ['pay', 'salary', 'compensation', 'rate'],
}


def matches_keywords(text: str, keywords: list[str]) -> tuple[bool, list[str]]:
    """Smart keyword matching with fuzzy, word-level, and synonym support."""
    if not text:
        return False, []
    if not keywords:
        return True, ['<all>']

    text_lower = text.lower()
    text_words = set(re.findall(r'\b\w+\b', text_lower))
    matched = []

    for keyword in keywords:
        kw = keyword.lower().strip()
        # Exact substring
        if kw in text_lower:
            matched.append(keyword)
            continue
        # Word-level: match if ≥50% of keyword words appear
        kw_words = {w for w in re.findall(r'\b\w+\b', kw) if len(w) > 2}
        if kw_words:
            common = kw_words & text_words
            if len(common) / len(kw_words) >= 0.5 and len(common) >= 1:
                matched.append(keyword)
                continue
        # Synonym matching
        for word in kw_words:
            if word in SYNONYMS:
                if any(syn in text_lower for syn in SYNONYMS[word]):
                    matched.append(keyword)
                    break

    # Fallback: check for generic lead signals
    if not matched:
        sigs = [s for s in LEAD_SIGNALS if s in text_lower]
        if len(sigs) >= 2:
            matched = [f'[signal:{s}]' for s in sigs[:3]]

    return len(matched) > 0, list(dict.fromkeys(matched))


def extract_lead_quality_signals(post: dict[str, Any]) -> dict[str, Any]:
    """Extract quality signals from a Reddit post."""
    title = post.get('title', '').lower()
    selftext = post.get('selftext', '').lower()
    combined = f"{title} {selftext}"

    signals = {
        'has_contact': any(word in combined for word in ['email', 'contact', 'dm me', 'reach out', 'message me']),
        'has_budget': any(word in combined for word in ['$', 'budget', 'pay', 'rate', 'compensation', 'salary', 'equity']),
        'has_urgency': any(word in combined for word in ['asap', 'urgent', 'immediately', 'right away', 'soon', 'quick']),
        'has_timeline': any(word in combined for word in ['deadline', 'within', 'by', 'timeline', 'schedule']),
        'is_hiring': any(word in combined for word in ['hiring', 'looking for', 'seeking', 'need', 'want', 'search for']),
        'is_question': '?' in title or '?' in selftext,
        'score': post.get('score', 0),
        'num_comments': post.get('num_comments', 0),
        'is_fresh': (datetime.now().timestamp() - post.get('created_utc', 0)) < (7 * 24 * 3600),
    }
    return signals


def calculate_quality_score(post: dict[str, Any], signals: dict[str, Any]) -> float:
    """Calculate quality score (0-100) for a Reddit post."""
    score = 15  # Base score (increased from 0)
    score += 25 if signals['has_contact'] else 0
    score += 20 if signals['has_budget'] else 0
    score += 15 if signals['has_urgency'] else 0
    score += 10 if signals['has_timeline'] else 0
    score += 15 if signals['is_hiring'] else 0
    score += 5 if signals['is_fresh'] else 0
    score += min(5, signals['score'] / 50)
    score += min(5, signals['num_comments'] / 10)
    score += 5 if signals['is_question'] else 0
    return min(100, score)


async def main() -> None:
    """Main entry point for the Reddit Lead Scraper Actor."""
    async with Actor:
        actor_input = await Actor.get_input() or {}
        subreddits = actor_input.get('subreddits', ['Entrepreneur', 'startups', 'forhire',
                                                     'remotework', 'freelance', 'SaaS',
                                                     'cofounder', 'smallbusiness'])
        keywords = actor_input.get('keywords', [
            'looking for developer', 'need technical cofounder',
            'hire developer', 'seeking engineer', 'freelance project',
            'need help building', 'looking for someone to build',
            'startup cofounder', 'MVP development',
        ])
        max_posts = actor_input.get('maxPosts', 50)
        time_filter = actor_input.get('timeFilter', 'week')
        # Retention: only output posts newer than this (Unix UTC). Pipeline passes from last run.
        after_utc = actor_input.get('after_utc')
        if after_utc is not None:
            after_utc = int(after_utc)

        Actor.log.info('=' * 80)
        Actor.log.info('🚀 Starting Reddit Lead Scraper - Professional Mode with Crawlee')
        Actor.log.info('=' * 80)
        Actor.log.info(f'📋 Subreddits: {subreddits}')
        Actor.log.info(f'📋 Keywords: {keywords}')
        Actor.log.info(f'📋 Max posts/sub: {max_posts}, Time: {time_filter}')
        if after_utc is not None:
            Actor.log.info(f'📋 Retention: only posts after UTC {after_utc} (incremental)')
        Actor.log.info('=' * 80)

        total_posts = 0
        leads_found = 0
        high_quality_leads = 0
        subreddits_processed = 0

        proxy_config = await Actor.create_proxy_configuration()

        crawler = BeautifulSoupCrawler(
            proxy_configuration=proxy_config,
            max_requests_per_crawl=len(subreddits) * 2,
            max_request_retries=5,
            max_session_rotations=10,
            use_session_pool=True,
            session_pool=SessionPool(max_pool_size=10),
        )

        @crawler.router.default_handler
        async def handle_subreddit(context: BeautifulSoupCrawlingContext) -> None:
            nonlocal total_posts, leads_found, high_quality_leads, subreddits_processed
            url = context.request.url
            Actor.log.info(f'📡 Processing: {url}')

            try:
                import json
                response_text = context.soup.get_text()

                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError as e:
                    Actor.log.warning(f'Failed to parse JSON: {e}')
                    return

                if 'data' not in data or 'children' not in data['data']:
                    Actor.log.warning('Unexpected JSON structure')
                    return

                posts = data['data']['children']
                Actor.log.info(f'   Found {len(posts)} posts')

                for post_wrapper in posts:
                    post = post_wrapper.get('data', {})
                    total_posts += 1

                    # Retention: skip posts we already have (same as last run)
                    created = post.get('created_utc') or 0
                    if after_utc is not None and created <= after_utc:
                        continue

                    title = post.get('title', '')
                    selftext = post.get('selftext', '')
                    author = post.get('author', '')
                    subreddit = post.get('subreddit', '')
                    permalink = post.get('permalink', '')
                    url_link = f'https://www.reddit.com{permalink}' if permalink else ''

                    combined_text = f"{title} {selftext}"
                    matches, matched_keywords = matches_keywords(combined_text, keywords)

                    if not matches:
                        continue

                    leads_found += 1
                    quality_signals = extract_lead_quality_signals(post)
                    quality_score = calculate_quality_score(post, quality_signals)

                    if quality_score >= 40:
                        high_quality_leads += 1

                    lead = {
                        'platform': 'reddit',
                        'source': f'r/{subreddit}',
                        'url': url_link,
                        'title': title,
                        'selftext': selftext,
                        'text_preview': selftext[:500] if len(selftext) > 500 else selftext,
                        'author': author,
                        'author_url': f'https://www.reddit.com/user/{author}' if author else None,
                        'score': post.get('score', 0),
                        'upvote_ratio': post.get('upvote_ratio', 0),
                        'num_comments': post.get('num_comments', 0),
                        'subreddit': subreddit,
                        'post_flair': post.get('link_flair_text', ''),
                        'created_utc': post.get('created_utc', 0),
                        'scraped_at': datetime.now().isoformat(),
                        'matched_keywords': matched_keywords,
                        'quality_score': round(quality_score, 1),
                        'quality_signals': quality_signals,
                        'lead_category': 'high_priority' if quality_score >= 60 else 'medium_priority' if quality_score >= 35 else 'low_priority',
                        'has_contact_info': quality_signals['has_contact'],
                        'urgency_level': 'high' if quality_signals['has_urgency'] else 'normal',
                    }

                    await context.push_data(lead)
                    Actor.log.info(f'✅ Lead #{leads_found}: {title[:50]}... (Q:{quality_score:.0f}/100)')

                subreddits_processed += 1

            except Exception as e:
                Actor.log.error(f'❌ Error: {type(e).__name__}: {e}')
                import traceback
                Actor.log.error(traceback.format_exc())

        start_requests = []
        for subreddit in subreddits:
            url = f'https://www.reddit.com/r/{subreddit}/new/.json?limit={min(max_posts, 100)}&t={time_filter}'
            start_requests.append(Request.from_url(url))
            Actor.log.info(f'📝 Queued: r/{subreddit}')

        await crawler.run(start_requests)

        Actor.log.info('=' * 80)
        Actor.log.info('✅ SCRAPING COMPLETE!')
        Actor.log.info(f'   Subreddits: {subreddits_processed}/{len(subreddits)}')
        Actor.log.info(f'   Posts reviewed: {total_posts}')
        Actor.log.info(f'   Leads found: {leads_found}')
        Actor.log.info(f'   High-quality: {high_quality_leads}')
        Actor.log.info('=' * 80)


if __name__ == '__main__':
    asyncio.run(main())
