"""Reddit Lead Scraper - Production-Grade Actor

A bulletproof Reddit scraper that extracts business leads from subreddits
with proper anti-bot measures, rate limiting, and error handling.

Features:
- Realistic browser headers to avoid blocks
- Configurable rate limiting
- Apify proxy support
- Comprehensive error handling
- Deduplication
- Detailed logging and metrics
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from datetime import datetime
from typing import Any

from apify import Actor, Event
from crawlee.crawlers import HttpCrawler, HttpCrawlingContext
from crawlee.sessions import SessionPool


# User agents pool for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
]


def get_browser_headers() -> dict[str, str]:
    """Generate realistic browser headers to avoid blocking."""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }


def matches_keywords(text: str, keywords: list[str]) -> tuple[bool, list[str]]:
    """Check if text matches any keywords (case-insensitive)."""
    if not text:
        return False, []

    text_lower = text.lower()
    matched = []

    for keyword in keywords:
        if keyword.lower() in text_lower:
            matched.append(keyword)

    return len(matched) > 0, matched


def extract_lead_quality_signals(post: dict[str, Any]) -> dict[str, Any]:
    """Extract quality signals from a Reddit post."""
    signals = {
        'has_email': bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', post.get('selftext', ''))),
        'has_budget': any(keyword in post.get('selftext', '').lower() for keyword in ['$', 'budget', 'pay', 'rate', 'compensation']),
        'has_urgency': any(keyword in post.get('selftext', '').lower() + post.get('title', '').lower()
                          for keyword in ['asap', 'urgent', 'immediately', 'right away', 'quick']),
        'has_timeline': any(keyword in post.get('selftext', '').lower()
                           for keyword in ['deadline', 'within', 'by', 'timeline', 'schedule']),
        'engagement_score': post.get('score', 0) + (post.get('num_comments', 0) * 2),  # Comments weighted higher
        'is_fresh': (datetime.now().timestamp() - post.get('created_utc', 0)) < 86400 * 7,  # Within 7 days
    }
    return signals


async def main() -> None:
    """Main entry point for the Reddit Lead Scraper Actor."""
    async with Actor:
        # Handle graceful abort
        async def on_aborting() -> None:
            Actor.log.warning('Actor is aborting, cleaning up...')
            await asyncio.sleep(1)
            await Actor.exit()

        Actor.on(Event.ABORTING, on_aborting)

        # Get Actor input with validation
        actor_input = await Actor.get_input() or {}
        subreddits = actor_input.get('subreddits', ['Entrepreneur'])
        keywords = actor_input.get('keywords', ['looking for developer'])
        max_posts = actor_input.get('maxPosts', 50)
        sort_by = actor_input.get('sortBy', 'new')
        time_filter = actor_input.get('timeFilter', 'week')
        use_apify_proxy = actor_input.get('useApifyProxy', False)
        min_delay_ms = actor_input.get('minDelayMs', 1000)  # Rate limiting
        max_delay_ms = actor_input.get('maxDelayMs', 3000)

        # Validate input
        if not subreddits:
            Actor.log.error('No subreddits provided')
            return
        if not keywords:
            Actor.log.error('No keywords provided')
            return

        Actor.log.info('=' * 80)
        Actor.log.info('🚀 Starting Reddit Lead Scraper - Production Mode')
        Actor.log.info('=' * 80)
        Actor.log.info(f'📋 Configuration:')
        Actor.log.info(f'   Subreddits: {subreddits}')
        Actor.log.info(f'   Keywords: {keywords}')
        Actor.log.info(f'   Max posts per subreddit: {max_posts}')
        Actor.log.info(f'   Sort by: {sort_by}')
        Actor.log.info(f'   Apify Proxy: {"✅ Enabled" if use_apify_proxy else "❌ Disabled"}')
        Actor.log.info(f'   Rate limiting: {min_delay_ms}-{max_delay_ms}ms between requests')
        Actor.log.info('=' * 80)

        # Build Reddit JSON API URLs with headers
        from crawlee import Request
        start_requests = []
        for subreddit in subreddits:
            url = f'https://www.reddit.com/r/{subreddit}/{sort_by}.json'
            if sort_by in ['top', 'controversial']:
                url += f'?t={time_filter}&limit=100&raw_json=1'
            else:
                url += '?limit=100&raw_json=1'

            # Create request with realistic headers
            headers = get_browser_headers()
            start_requests.append(Request.from_url(url, headers=headers))

        if not start_requests:
            Actor.log.error('No valid URLs to scrape')
            return

        # Configure proxy if enabled
        proxy_config = None
        if use_apify_proxy:
            Actor.log.info('🔒 Using Apify Proxy for requests')
            proxy_config = await Actor.create_proxy_configuration()

        # Create crawler with production settings
        crawler = HttpCrawler(
            max_requests_per_crawl=len(subreddits) * 10,  # Allow more pagination
            max_request_retries=5,  # Retry failed requests
            max_session_rotations=10,  # Rotate sessions on blocks
            session_pool=SessionPool(max_pool_size=10),  # Session management
            proxy_configuration=proxy_config,
            # Add default headers to all requests
            additional_http_error_status_codes=[429],  # Treat 429 as an error
            ignore_http_error_status_codes=[403],  # Don't fail on 403, we'll handle it
        )

        # Metrics tracking
        posts_scraped = 0
        leads_found = 0
        high_quality_leads = 0
        requests_made = 0
        errors_count = 0
        seen_post_ids = set()  # Deduplication

        @crawler.router.default_handler
        async def request_handler(context: HttpCrawlingContext) -> None:
            nonlocal posts_scraped, leads_found, high_quality_leads, requests_made, errors_count

            url = context.request.url
            requests_made += 1

            Actor.log.info(f'📡 Request #{requests_made}: {url}')

            # Add rate limiting to be polite
            delay = random.uniform(min_delay_ms / 1000, max_delay_ms / 1000)
            Actor.log.info(f'⏱️  Rate limiting: waiting {delay:.2f}s')
            await asyncio.sleep(delay)

            try:
                # Get the HTTP response
                content = await context.http_response.read()

                # Check response status
                if context.http_response.status_code != 200:
                    Actor.log.warning(f'⚠️  Non-200 status code: {context.http_response.status_code}')
                    if context.http_response.status_code == 429:
                        Actor.log.error('🚫 Rate limited by Reddit! Increasing delay...')
                        await asyncio.sleep(60)  # Wait 1 minute
                        return
                    elif context.http_response.status_code == 403:
                        Actor.log.error('🚫 Blocked by Reddit (403). Try enabling Apify Proxy.')
                        errors_count += 1
                        return

                # Parse JSON response
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    Actor.log.error(f'❌ Failed to parse JSON: {e}')
                    Actor.log.error(f'Response preview: {content[:500]}')
                    errors_count += 1
                    return

                # Validate Reddit API structure
                if not isinstance(data, dict) or 'data' not in data or 'children' not in data.get('data', {}):
                    Actor.log.warning(f'⚠️  Unexpected Reddit API response structure')
                    Actor.log.debug(f'Response keys: {data.keys() if isinstance(data, dict) else "not a dict"}')
                    errors_count += 1
                    return

                posts = data['data']['children']
                Actor.log.info(f'✅ Successfully fetched {len(posts)} posts')

                # Process each post
                for post_data in posts:
                    if posts_scraped >= max_posts:
                        Actor.log.info(f'🎯 Reached max posts limit ({max_posts})')
                        return

                    post = post_data.get('data', {})
                    post_id = post.get('id', '')

                    # Deduplication
                    if post_id in seen_post_ids:
                        Actor.log.debug(f'⏭️  Skipping duplicate post: {post_id}')
                        continue
                    seen_post_ids.add(post_id)

                    # Extract post information
                    title = post.get('title', '')
                    selftext = post.get('selftext', '')
                    author = post.get('author', '')
                    subreddit = post.get('subreddit', '')
                    permalink = post.get('permalink', '')
                    created_utc = post.get('created_utc', 0)
                    score = post.get('score', 0)
                    num_comments = post.get('num_comments', 0)
                    url_post = post.get('url', '')
                    upvote_ratio = post.get('upvote_ratio', 0)
                    is_self = post.get('is_self', False)

                    # Skip deleted/removed posts
                    if author in ['[deleted]', '[removed]', 'AutoModerator']:
                        continue

                    # Combine title and body for keyword matching
                    combined_text = f"{title} {selftext}"

                    # Check if post matches keywords
                    matches, matched_keywords = matches_keywords(combined_text, keywords)

                    if matches:
                        leads_found += 1

                        # Extract quality signals
                        quality_signals = extract_lead_quality_signals(post)

                        # Calculate quality score (0-100)
                        quality_score = (
                            (30 if quality_signals['has_email'] else 0) +
                            (20 if quality_signals['has_budget'] else 0) +
                            (15 if quality_signals['has_urgency'] else 0) +
                            (10 if quality_signals['has_timeline'] else 0) +
                            (10 if quality_signals['is_fresh'] else 0) +
                            (min(15, quality_signals['engagement_score'] / 10))  # Up to 15 points for engagement
                        )

                        if quality_score >= 50:
                            high_quality_leads += 1

                        # Create comprehensive lead data
                        lead = {
                            # Core identification
                            'platform': 'reddit',
                            'source': f'r/{subreddit}',
                            'post_id': post_id,
                            'url': f'https://www.reddit.com{permalink}',

                            # Content
                            'title': title,
                            'content': selftext,
                            'content_preview': selftext[:500] if len(selftext) > 500 else selftext,

                            # Author info
                            'author': author,
                            'author_url': f'https://www.reddit.com/user/{author}' if author else None,

                            # Metadata
                            'post_url': url_post if url_post and url_post != f'https://www.reddit.com{permalink}' else None,
                            'score': score,
                            'num_comments': num_comments,
                            'upvote_ratio': upvote_ratio,
                            'is_self_post': is_self,
                            'created_at': datetime.fromtimestamp(created_utc).isoformat(),
                            'scraped_at': datetime.now().isoformat(),

                            # Lead quality
                            'matched_keywords': matched_keywords,
                            'quality_score': round(quality_score, 1),
                            'quality_signals': quality_signals,

                            # Categorization
                            'lead_category': 'high_priority' if quality_score >= 70 else 'medium_priority' if quality_score >= 50 else 'low_priority',
                            'has_contact_info': quality_signals['has_email'],
                            'urgency_level': 'high' if quality_signals['has_urgency'] else 'normal',
                        }

                        Actor.log.info(f'✅ Lead #{leads_found}: {title[:50]}... (Quality: {quality_score}/100)')

                        if quality_score >= 70:
                            Actor.log.info(f'   ⭐ HIGH QUALITY LEAD!')

                        # Store the lead
                        await context.push_data(lead)

                    posts_scraped += 1

                    # Progress update every 10 posts
                    if posts_scraped % 10 == 0:
                        Actor.log.info(f'📊 Progress: {posts_scraped} posts processed, {leads_found} leads found ({high_quality_leads} high-quality)')

                # Handle pagination - Reddit provides "after" token
                after_token = data['data'].get('after')
                if after_token and posts_scraped < max_posts:
                    # Build next page URL
                    current_url = context.request.url
                    if 'after=' in current_url:
                        next_url = re.sub(r'after=[^&]*', f'after={after_token}', current_url)
                    else:
                        separator = '&' if '?' in current_url else '?'
                        next_url = f'{current_url}{separator}after={after_token}'

                    Actor.log.info(f'📄 Fetching next page (after={after_token[:10]}...)')

                    # Add pagination request with headers
                    next_headers = get_browser_headers()
                    next_request = Request.from_url(next_url, headers=next_headers)
                    await context.add_requests([next_request])

            except json.JSONDecodeError as e:
                Actor.log.error(f'❌ JSON parsing failed for {url}: {e}')
                errors_count += 1
            except Exception as e:
                Actor.log.error(f'❌ Unexpected error processing {url}: {type(e).__name__}: {e}')
                errors_count += 1
                import traceback
                Actor.log.error(f'Stack trace: {traceback.format_exc()}')

        # Run the crawler
        Actor.log.info('🏃 Starting crawler...')
        await crawler.run(start_requests)

        # Final summary
        Actor.log.info('=' * 80)
        Actor.log.info('✅ SCRAPING COMPLETE!')
        Actor.log.info('=' * 80)
        Actor.log.info(f'📊 Final Statistics:')
        Actor.log.info(f'   Total HTTP requests: {requests_made}')
        Actor.log.info(f'   Posts processed: {posts_scraped}')
        Actor.log.info(f'   Leads found: {leads_found}')
        Actor.log.info(f'   High-quality leads: {high_quality_leads} ({(high_quality_leads/leads_found*100) if leads_found > 0 else 0:.1f}%)')
        Actor.log.info(f'   Errors encountered: {errors_count}')
        Actor.log.info(f'   Success rate: {((requests_made-errors_count)/requests_made*100) if requests_made > 0 else 0:.1f}%')
        Actor.log.info('=' * 80)

        if leads_found == 0:
            Actor.log.warning('⚠️  No leads found! Consider:')
            Actor.log.warning('   - Broadening your keywords')
            Actor.log.warning('   - Trying different subreddits')
            Actor.log.warning('   - Adjusting the time filter')
