"""Product Hunt Lead Scraper - Production-Grade Actor

A bulletproof Product Hunt scraper that extracts product launches and discussions
with proper anti-bot measures, rate limiting, and error handling.
"""

from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime
from typing import Any

from apify import Actor, Event
from crawlee import Request
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee.sessions import SessionPool


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


def extract_lead_quality_signals(product_data: dict[str, Any]) -> dict[str, Any]:
    """Extract quality signals from a Product Hunt product."""
    name = product_data.get('name', '').lower()
    tagline = product_data.get('tagline', '').lower()
    description = product_data.get('description', '').lower()
    combined = f"{name} {tagline} {description}"

    upvotes = product_data.get('upvotes', 0)
    comments = product_data.get('comments', 0)

    signals = {
        'has_high_engagement': upvotes > 100 or comments > 20,
        'is_new_launch': 'launch' in combined or 'new' in combined or 'beta' in combined,
        'is_hiring': 'hiring' in combined or 'jobs' in combined or 'careers' in combined,
        'is_beta': 'beta' in combined or 'early access' in combined,
        'has_comments': comments > 0,
        'has_contact': '@' in combined or 'contact' in combined or 'email' in combined,
    }
    return signals


async def main() -> None:
    """Main entry point for the Product Hunt Lead Scraper Actor."""
    async with Actor:
        actor_input = await Actor.get_input() or {}
        sections = actor_input.get('sections', ['newest'])
        keywords = actor_input.get('keywords', [])
        max_posts = actor_input.get('maxPosts', 50)
        min_delay_ms = actor_input.get('minDelayMs', 2000)
        max_delay_ms = actor_input.get('maxDelayMs', 5000)

        Actor.log.info('=' * 80)
        Actor.log.info('🚀 Starting Product Hunt Lead Scraper')
        Actor.log.info('=' * 80)
        Actor.log.info(f'📋 Configuration:')
        Actor.log.info(f'   Sections: {sections}')
        Actor.log.info(f'   Keywords: {keywords}')
        Actor.log.info(f'   Max posts: {max_posts}')
        Actor.log.info('=' * 80)

        posts_scraped = 0
        leads_found = 0
        high_quality_leads = 0
        errors_count = 0
        seen_urls = set()

        # Build URLs
        start_requests = []
        for section in sections:
            url = f'https://www.producthunt.com/{section}'
            start_requests.append(Request.from_url(url))

        crawler = BeautifulSoupCrawler(
            max_requests_per_crawl=max_posts + len(sections),
            max_request_retries=5,
            max_session_rotations=10,
            session_pool=SessionPool(max_pool_size=10),
        )

        @crawler.router.default_handler
        async def request_handler(context: BeautifulSoupCrawlingContext) -> None:
            nonlocal posts_scraped, leads_found, high_quality_leads, errors_count

            url = context.request.url
            Actor.log.info(f'📡 Scraping: {url}')

            delay = random.uniform(min_delay_ms / 1000, max_delay_ms / 1000)
            Actor.log.info(f'⏱️  Rate limiting: waiting {delay:.2f}s')
            await asyncio.sleep(delay)

            try:
                soup = context.soup

                # Find post containers
                post_containers = (
                    soup.find_all(attrs={'data-test': re.compile(r'post|product', re.I)}) or
                    soup.find_all('div', class_=re.compile(r'styles_post|styles_product', re.I)) or
                    soup.find_all('article')
                )

                Actor.log.info(f'   Found {len(post_containers)} potential posts/products on page')

                for container in post_containers:
                    if posts_scraped >= max_posts:
                        Actor.log.info(f'🎯 Reached max posts limit ({max_posts})')
                        return

                    try:
                        # Extract name
                        name_elem = (
                            container.find('h2') or
                            container.find('h3') or
                            container.find(attrs={'data-test': 'post-name'})
                        )
                        name = name_elem.get_text(strip=True) if name_elem else ''

                        # Extract tagline
                        tagline_elem = (
                            container.find(attrs={'data-test': 'post-tagline'}) or
                            container.find('p', class_=re.compile(r'tagline|description', re.I))
                        )
                        tagline = tagline_elem.get_text(strip=True) if tagline_elem else ''

                        # Extract description
                        description_elem = container.find('div', class_=re.compile(r'description|content', re.I))
                        description = description_elem.get_text(strip=True) if description_elem else tagline

                        # Extract URL
                        link_elem = container.find('a', href=True)
                        post_url = ''
                        if link_elem:
                            href = link_elem['href']
                            if href.startswith('/'):
                                post_url = f'https://www.producthunt.com{href}'
                            elif href.startswith('http'):
                                post_url = href

                        # Extract upvotes
                        upvotes = 0
                        upvote_elem = container.find(attrs={'data-test': re.compile(r'vote', re.I)})
                        if upvote_elem:
                            upvote_text = upvote_elem.get_text(strip=True)
                            upvote_match = re.search(r'(\d+)', upvote_text)
                            if upvote_match:
                                upvotes = int(upvote_match.group(1))

                        # Extract comments
                        comments = 0
                        comment_elem = container.find(attrs={'data-test': re.compile(r'comment', re.I)})
                        if comment_elem:
                            comment_text = comment_elem.get_text(strip=True)
                            comment_match = re.search(r'(\d+)', comment_text)
                            if comment_match:
                                comments = int(comment_match.group(1))

                        # Extract maker
                        maker_elem = container.find(attrs={'data-test': re.compile(r'maker|hunter', re.I)})
                        maker = maker_elem.get_text(strip=True) if maker_elem else ''

                        # Skip if no data
                        if not name and not tagline:
                            continue

                        # Deduplication
                        if post_url in seen_urls:
                            continue
                        if post_url:
                            seen_urls.add(post_url)

                        posts_scraped += 1

                        # Keyword matching
                        combined_text = f"{name} {tagline} {description}"
                        matches, matched_keywords = matches_keywords(combined_text, keywords)

                        # Store all products
                        leads_found += 1

                        # Build product data
                        product_data = {
                            'name': name,
                            'tagline': tagline,
                            'description': description,
                            'upvotes': upvotes,
                            'comments': comments,
                            'url': post_url,
                        }

                        # Calculate quality score
                        quality_signals = extract_lead_quality_signals(product_data)
                        quality_score = (
                            (25 if quality_signals['has_high_engagement'] else min(15, upvotes // 5)) +
                            (15 if quality_signals['is_new_launch'] else 0) +
                            (20 if quality_signals['is_hiring'] else 0) +
                            (15 if quality_signals['is_beta'] else 0) +
                            (10 if quality_signals['has_comments'] else 0) +
                            (10 if quality_signals['has_contact'] else 0) +
                            5
                        )

                        if quality_score >= 50:
                            high_quality_leads += 1

                        # Create lead
                        lead = {
                            'platform': 'producthunt',
                            'source': 'Product Hunt',
                            'url': post_url if post_url else url,
                            'name': name,
                            'tagline': tagline,
                            'description': description,
                            'description_preview': description[:500] if len(description) > 500 else description,
                            'upvotes': upvotes,
                            'comments': comments,
                            'maker': maker if maker else None,
                            'scraped_at': datetime.now().isoformat(),
                            'matched_keywords': matched_keywords if matches else [],
                            'quality_score': round(quality_score, 1),
                            'quality_signals': quality_signals,
                            'lead_category': 'high_priority' if quality_score >= 70 else 'medium_priority' if quality_score >= 50 else 'low_priority',
                            'has_contact_info': quality_signals['has_contact'],
                            'urgency_level': 'high' if quality_signals['is_new_launch'] else 'normal',
                        }

                        Actor.log.info(f'✅ Lead #{leads_found}: {name[:50]}... (Quality: {quality_score}/100)')

                        if quality_score >= 70:
                            Actor.log.info(f'   ⭐ HIGH QUALITY LEAD!')

                        await context.push_data(lead)

                    except Exception as e:
                        Actor.log.warning(f'Error processing post: {e}')
                        continue

                Actor.log.info(f'📊 Progress: {posts_scraped} posts processed, {leads_found} leads found ({high_quality_leads} high-quality)')

            except Exception as e:
                Actor.log.error(f'❌ Error processing page {url}: {type(e).__name__}: {e}')
                errors_count += 1

        # Run crawler
        Actor.log.info('🏃 Starting crawler...')
        await crawler.run(start_requests)

        # Final summary
        Actor.log.info('=' * 80)
        Actor.log.info('✅ SCRAPING COMPLETE!')
        Actor.log.info('=' * 80)
        Actor.log.info(f'📊 Final Statistics:')
        Actor.log.info(f'   Posts processed: {posts_scraped}')
        Actor.log.info(f'   Leads found: {leads_found}')
        Actor.log.info(f'   High-quality leads: {high_quality_leads} ({(high_quality_leads/leads_found*100) if leads_found > 0 else 0:.1f}%)')
        Actor.log.info(f'   Errors: {errors_count}')
        Actor.log.info('=' * 80)


if __name__ == '__main__':
    asyncio.run(main())
