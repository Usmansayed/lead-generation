"""GitHub Lead Scraper - Professional Grade (API-based)

Uses the GitHub Search API to find issues, discussions, and repos
that indicate business leads. All API results are stored as leads
since the search query already filters for relevance.
"""
import asyncio, json, re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus
from apify import Actor
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee import Request
from crawlee.sessions import SessionPool


def extract_lead_quality_signals(item: dict[str, Any]) -> dict[str, Any]:
    title = item.get('title', '').lower()
    body = item.get('body', '').lower() if item.get('body') else ''
    combined = f"{title} {body}"
    labels = [l.get('name', '').lower() for l in item.get('labels', [])]
    return {
        'has_email': bool(re.search(r'[\w.+-]+@[\w.-]+\.\w{2,}', combined)),
        'has_budget': any(k in combined for k in ['$', 'budget', 'pay', 'bounty', 'reward', 'sponsor']),
        'has_urgency': any(k in combined for k in ['asap', 'urgent', 'immediately', 'help needed', 'critical']),
        'has_question': '?' in title or 'help' in title or 'how to' in title,
        'is_open': item.get('state', '') == 'open',
        'has_reactions': item.get('reactions', {}).get('total_count', 0) > 0,
        'has_comments': item.get('comments', 0) > 0,
        'is_help_wanted': 'help wanted' in ' '.join(labels),
        'is_good_first_issue': 'good first issue' in ' '.join(labels),
        'is_bounty': any(k in ' '.join(labels) for k in ['bounty', 'reward', 'sponsor', 'paid']),
    }


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        keywords = inp.get('keywords', [
            'looking for developer', 'need help building',
            'hiring', 'freelance', 'bounty', 'paid',
            'help wanted', 'seeking contributor',
        ])
        search_types = inp.get('searchTypes', ['issues'])
        max_results = inp.get('maxResultsPerQuery', 50)

        Actor.log.info('=' * 80)
        Actor.log.info('🚀 GitHub Lead Scraper - API Mode')
        Actor.log.info(f'   Keywords: {keywords} | Types: {search_types} | Max: {max_results}')
        Actor.log.info('=' * 80)

        total = leads_found = high_quality = 0
        seen: set[str] = set()

        proxy_config = await Actor.create_proxy_configuration()
        crawler = BeautifulSoupCrawler(
            proxy_configuration=proxy_config,
            max_requests_per_crawl=len(keywords) * len(search_types) * 2,
            max_request_retries=5,
            max_session_rotations=10,
            use_session_pool=True,
            session_pool=SessionPool(max_pool_size=10),
        )

        @crawler.router.default_handler
        async def handle(context: BeautifulSoupCrawlingContext) -> None:
            nonlocal total, leads_found, high_quality, seen
            search_type = context.request.user_data.get('search_type', 'issues')
            keyword = context.request.user_data.get('keyword', '')

            try:
                data = json.loads(context.soup.get_text())
                items = data.get('items', [])
                Actor.log.info(f'📡 GitHub {search_type} for "{keyword}": {len(items)} results')

                for item in items:
                    url = item.get('html_url', '')
                    if url in seen:
                        continue
                    seen.add(url)
                    total += 1

                    title = item.get('title', '')
                    body = item.get('body', '') or ''
                    signals = extract_lead_quality_signals(item)

                    # Scoring: all API results get a base score since search already filtered
                    score = 20  # base for matching search query
                    score += 25 if signals['has_email'] else 0
                    score += 20 if signals['has_budget'] or signals['is_bounty'] else 0
                    score += 10 if signals['has_urgency'] else 0
                    score += 10 if signals['has_question'] else 0
                    score += 5 if signals['is_open'] else 0
                    score += 5 if signals['is_help_wanted'] else 0
                    score += min(5, item.get('reactions', {}).get('total_count', 0))
                    score = min(100, score)

                    leads_found += 1
                    if score >= 40:
                        high_quality += 1

                    labels = [l.get('name') for l in item.get('labels', [])]
                    repo_url = item.get('repository_url', '')
                    repo_name = '/'.join(repo_url.split('/')[-2:]) if repo_url else ''

                    await context.push_data({
                        'platform': 'github',
                        'source': f'GitHub {search_type}',
                        'url': url,
                        'title': title,
                        'body_preview': body[:500],
                        'author': item.get('user', {}).get('login', ''),
                        'author_url': item.get('user', {}).get('html_url', ''),
                        'repository': repo_name,
                        'state': item.get('state', ''),
                        'comments_count': item.get('comments', 0),
                        'labels': labels,
                        'created_at': item.get('created_at', ''),
                        'scraped_at': datetime.now().isoformat(),
                        'matched_keywords': [keyword],
                        'quality_score': round(score, 1),
                        'quality_signals': signals,
                        'lead_category': 'high_priority' if score >= 60 else 'medium_priority' if score >= 35 else 'low_priority',
                        'has_contact_info': signals['has_email'],
                        'urgency_level': 'high' if signals['has_urgency'] else 'normal',
                    })
                    Actor.log.info(f'   ✅ Lead #{leads_found}: {title[:45]}... (Q:{score})')

            except json.JSONDecodeError as e:
                Actor.log.error(f'❌ JSON parse error: {e}')
            except Exception as e:
                Actor.log.error(f'❌ Error: {e}')

        # Build requests
        requests = []
        for keyword in keywords:
            for st in search_types:
                if st == 'issues':
                    q = f'{quote_plus(keyword)}+type:issue+state:open'
                    url = f'https://api.github.com/search/issues?q={q}&sort=created&order=desc&per_page={min(max_results, 100)}'
                elif st == 'discussions':
                    q = f'{quote_plus(keyword)}+label:discussion'
                    url = f'https://api.github.com/search/issues?q={q}&sort=created&order=desc&per_page={min(max_results, 100)}'
                else:
                    q = quote_plus(keyword)
                    url = f'https://api.github.com/search/repositories?q={q}&sort=updated&order=desc&per_page={min(max_results, 100)}'

                requests.append(Request.from_url(url, user_data={'search_type': st, 'keyword': keyword}))

        await crawler.run(requests)
        Actor.log.info(f'✅ COMPLETE! Items:{total} Leads:{leads_found} HQ:{high_quality}')
