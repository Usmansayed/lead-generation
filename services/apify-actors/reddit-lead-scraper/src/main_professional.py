"""Reddit Lead Scraper - Professional Grade (Crawlee Framework)

Rebuilt using Apify/Crawlee best practices for maximum reliability:
- Crawler framework with automatic retries
- Built-in proxy rotation
- Session management
- Streaming data storage
- Proper error handling
"""

import asyncio
from datetime import datetime
from typing import Any
from apify import Actor
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee import ProxyConfiguration, SessionPool, Request


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
        'is_fresh': (datetime.now().timestamp() - post.get('created_utc', 0)) < (7 * 24 * 3600),  # < 7 days old
    }
    return signals


def calculate_quality_score(post: dict[str, Any], signals: dict[str, Any]) -> float:
    """Calculate quality score (0-100) for a Reddit post."""
    score = 0

    # Contact info is most valuable
    score += 30 if signals['has_contact'] else 0

    # Budget indicates serious opportunity
    score += 20 if signals['has_budget'] else 0

    # Urgency suggests immediate need
    score += 15 if signals['has_urgency'] else 0

    # Timeline shows planning
    score += 10 if signals['has_timeline'] else 0

    # Hiring keywords are good signals
    score += 15 if signals['is_hiring'] else 0

    # Fresh posts are more relevant
    score += 10 if signals['is_fresh'] else 0

    # Engagement indicates quality
    score += min(10, signals['score'] / 50)  # Up to 10 points for high score
    score += min(5, signals['num_comments'] / 10)  # Up to 5 points for comments

    # Questions show active seeking
    score += 5 if signals['is_question'] else 0

    return min(100, score)  # Cap at 100


def matches_keywords(text: str, keywords: list[str]) -> tuple[bool, list[str]]:
    """Check if text matches any keywords (case-insensitive)."""
    if not text or not keywords:
        return False, []

    text_lower = text.lower()
    matched = []

    for keyword in keywords:
        if keyword.lower() in text_lower:
            matched.append(keyword)

    return len(matched) > 0, matched


async def main() -> None:
    """Main entry point for the Reddit Lead Scraper Actor."""
    async with Actor:
        # Get Actor input
        actor_input = await Actor.get_input() or {}
        subreddits = actor_input.get('subreddits', ['Entrepreneur', 'startups', 'forhire'])
        keywords = actor_input.get('keywords', ['looking for developer', 'need technical cofounder'])
        max_posts = actor_input.get('maxPosts', 50)
        time_filter = actor_input.get('timeFilter', 'week')  # hour, day, week, month, year, all

        Actor.log.info('=' * 80)
        Actor.log.info('🚀 Starting Reddit Lead Scraper - Professional Mode with Crawlee')
        Actor.log.info('=' * 80)
        Actor.log.info(f'📋 Configuration:')
        Actor.log.info(f'   Subreddits: {subreddits}')
        Actor.log.info(f'   Keywords: {keywords}')
        Actor.log.info(f'   Max posts per subreddit: {max_posts}')
        Actor.log.info(f'   Time filter: {time_filter}')
        Actor.log.info(f'   Using: Crawlee framework with automatic proxies & retries')
        Actor.log.info('=' * 80)

        # Metrics
        total_posts = 0
        leads_found = 0
        high_quality_leads = 0
        subreddits_processed = 0

        # Configure proxies (Apify provides automatically when on platform)
        proxy_config = ProxyConfiguration()

        # Create professional crawler with all best practices
        crawler = BeautifulSoupCrawler(
            # Proxy configuration
            proxy_configuration=proxy_config,

            # Request management
            max_requests_per_crawl=len(subreddits) * max_posts,
            max_request_retries=5,  # Automatic retries on failure
            max_session_rotations=10,  # Rotate sessions if persistent failures

            # Session management for consistent identity
            use_session_pool=True,
            session_pool=SessionPool(max_pool_size=10),

            # Rate limiting (built-in, no manual sleep needed!)
            max_requests_per_minute=30,  # Stay under Reddit's radar
        )

        # Define request handler using router pattern
        @crawler.router.default_handler
        async def handle_subreddit(context: BeautifulSoupCrawlingContext) -> None:
            """Handle subreddit JSON scraping."""
            nonlocal total_posts, leads_found, high_quality_leads, subreddits_processed

            url = context.request.url
            Actor.log.info(f'📡 Processing: {url}')

            try:
                # Reddit JSON API returns soup with text - we need to parse JSON
                import json

                # Get JSON from page text
                response_text = context.soup.get_text()

                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError as e:
                    Actor.log.warning(f'Failed to parse JSON: {e}')
                    Actor.log.warning(f'Response text preview: {response_text[:200]}')
                    return

                # Reddit JSON structure: data.children is list of posts
                if 'data' not in data or 'children' not in data['data']:
                    Actor.log.warning('Unexpected JSON structure')
                    return

                posts = data['data']['children']
                Actor.log.info(f'   Found {len(posts)} posts')

                for post_wrapper in posts:
                    if total_posts >= max_posts * len(subreddits):
                        Actor.log.info('🎯 Reached maximum posts limit')
                        return

                    post = post_wrapper.get('data', {})
                    total_posts += 1

                    # Extract post data
                    title = post.get('title', '')
                    selftext = post.get('selftext', '')
                    author = post.get('author', '')
                    subreddit = post.get('subreddit', '')
                    permalink = post.get('permalink', '')
                    url_link = f'https://www.reddit.com{permalink}' if permalink else ''

                    # Check keyword matching
                    combined_text = f"{title} {selftext}"
                    matches, matched_keywords = matches_keywords(combined_text, keywords)

                    if not matches:
                        continue

                    leads_found += 1

                    # Extract quality signals
                    quality_signals = extract_lead_quality_signals(post)

                    # Calculate quality score
                    quality_score = calculate_quality_score(post, quality_signals)

                    if quality_score >= 50:
                        high_quality_leads += 1

                    # Build lead data
                    lead = {
                        # Core identification
                        'platform': 'reddit',
                        'source': f'r/{subreddit}',
                        'url': url_link,

                        # Content
                        'title': title,
                        'selftext': selftext,
                        'text_preview': selftext[:500] if len(selftext) > 500 else selftext,

                        # Author info
                        'author': author,
                        'author_url': f'https://www.reddit.com/user/{author}' if author else None,

                        # Engagement
                        'score': post.get('score', 0),
                        'upvote_ratio': post.get('upvote_ratio', 0),
                        'num_comments': post.get('num_comments', 0),

                        # Metadata
                        'subreddit': subreddit,
                        'post_flair': post.get('link_flair_text', ''),
                        'created_utc': post.get('created_utc', 0),
                        'is_self': post.get('is_self', True),
                        'scraped_at': datetime.now().isoformat(),

                        # Lead quality
                        'matched_keywords': matched_keywords,
                        'quality_score': round(quality_score, 1),
                        'quality_signals': quality_signals,

                        # Categorization
                        'lead_category': 'high_priority' if quality_score >= 70 else 'medium_priority' if quality_score >= 50 else 'low_priority',
                        'has_contact_info': quality_signals['has_contact'],
                        'urgency_level': 'high' if quality_signals['has_urgency'] else 'normal',
                    }

                    # Push data immediately (streaming storage - survives crashes!)
                    await context.push_data(lead)

                    Actor.log.info(f'✅ Lead #{leads_found}: {title[:50]}... (Quality: {quality_score}/100)')

                    if quality_score >= 70:
                        Actor.log.info(f'   ⭐ HIGH QUALITY LEAD!')

                subreddits_processed += 1
                Actor.log.info(f'📊 Progress: {subreddits_processed}/{len(subreddits)} subreddits completed')

            except Exception as e:
                Actor.log.error(f'❌ Error processing subreddit: {type(e).__name__}: {e}')
                import traceback
                Actor.log.error(f'Stack trace: {traceback.format_exc()}')

        # Build start requests for all subreddits
        start_requests = []
        for subreddit in subreddits:
            # Use Reddit JSON API (add .json to get structured data)
            url = f'https://www.reddit.com/r/{subreddit}/new/.json?limit={min(max_posts, 100)}&t={time_filter}'

            # Create Request object
            start_requests.append(Request.from_url(url))

            Actor.log.info(f'📝 Queued: r/{subreddit}')

        # Run crawler with all requests
        Actor.log.info('🏃 Starting crawler...')
        await crawler.run(start_requests)

        # Final summary
        Actor.log.info('=' * 80)
        Actor.log.info('✅ SCRAPING COMPLETE!')
        Actor.log.info('=' * 80)
        Actor.log.info(f'📊 Final Statistics:')
        Actor.log.info(f'   Subreddits processed: {subreddits_processed}/{len(subreddits)}')
        Actor.log.info(f'   Total posts reviewed: {total_posts}')
        Actor.log.info(f'   Leads found: {leads_found}')
        Actor.log.info(f'   High-quality leads: {high_quality_leads} ({(high_quality_leads/leads_found*100) if leads_found > 0 else 0:.1f}%)')
        Actor.log.info('=' * 80)

        if leads_found == 0:
            Actor.log.warning('⚠️  No leads found! Consider:')
            Actor.log.warning('   - Broadening your keywords')
            Actor.log.warning('   - Trying different subreddits')
            Actor.log.warning('   - Adjusting the time filter')
            Actor.log.warning('   - Check if Reddit API structure changed')


if __name__ == '__main__':
    asyncio.run(main())
