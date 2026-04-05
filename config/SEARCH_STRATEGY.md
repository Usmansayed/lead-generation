# Search & Fetch Strategy

This folder defines **what we search for** when scraping. **Target: any type of business** — law firm, architecture firm, consulting firm, small business (retail, service, professional). Not just restaurant/cafe/local. Exclude very technical businesses and large MNCs. We focus on **all 5 platforms** (LinkedIn, Twitter, Instagram, Facebook, Reddit) equally. See **TARGET_AUDIENCE.md** for the full rationale.

Goals: **all platforms**, **any business type**, global coverage, latest posts first, no re-scraping, high volume.

## How it works

1. **`keywords_map.yaml`** — **Primary source for search keywords** (the “magic”): themes (announcement_launch, international_launch, need_developer) in priority order (core → extended → long_tail) plus platform_keywords per platform. See **KEYWORDS_MAP.md**. When present, `search_strategy.yaml` references it via `keywords_source: keywords_map.yaml`.

2. **`search_strategy.yaml`** — Strategy and limits:
   - **Keywords**: From `keywords_map.yaml` when `keywords_source` is set (or file exists). Themes there: announcement_launch (core/extended/long_tail), international_launch, need_developer; plus platform_keywords per platform.
   - **Limits**: max search terms per platform (35–40), announcement_term_ratio (0.8), max subreddits, reddit sort/time.
   - **Reddit**: Business-owner + professional_services subreddits. Tech/indie communities excluded.

2. **`phase1_sources.yaml`** — Actor IDs (folder names) and non-search params:
   - `maxResults`, `maxPosts`, `minDelayMs`, `maxDelayMs`, etc.
   - Base `keywords` / `subreddits` here are **overridden** by `search_strategy.yaml` when the pipeline runs (defaults are also business-owner focused).

3. **Pipeline** — `pipeline/search_builder.py` builds the actual actor `run_input`:
   - Loads `search_strategy.yaml`, merges themes with `announcement_term_ratio`, adds platform expansions, applies caps.
   - Result is merged into the actor config from `phase1_sources.yaml` (so delays, maxPosts, etc. stay).

## Tuning without code

- **More announcement-heavy**: In `search_strategy.yaml` → `limits.announcement_term_ratio` (e.g. `0.9`).
- **More/fewer search terms**: `limits.max_search_terms_per_platform` per platform.
- **New phrases**: Add under `themes.announcement_launch.seed_phrases` or `themes.need_developer.seed_phrases`.
- **New hashtags**: Under `platform_expansions.twitter.hashtags` or `platform_expansions.instagram.hashtags`.
- **New subreddits**: Add to `reddit_sources` groups and/or `reddit_active_groups`. Prefer business-owner communities; avoid tech/CS/indie builder subs.
- **Reddit sort/time**: `limits.reddit_sort` (`new`, `hot`, `top`), `limits.reddit_time_filter` (`day`, `week`, `month`).

## Reddit subreddit groups (any business type)

- **business_owners**: smallbusiness, SweatyStartup, Entrepreneur, Etsy, EtsySellers, shopify, ecommerce.
- **professional_services**: LawFirm, consulting, smallbusiness, Entrepreneur, Accounting, Construction, marketing (law, architecture, consulting, small firms).
- **local_business**: smallbusiness, SweatyStartup, restaurant_owners, BarOwners, Etsy, EtsySellers, shopify.
- **sellers_retail**: Etsy, EtsySellers, shopify, ecommerce, FulfillmentByAmazon, smallbusiness.
- **Regional**: uk, india, australia, canada, europe (business-focused).
- **Excluded**: SideProject, indiehackers, IMadeThis — "I built this app" posts, not our leads.

Enable/disable groups via `reddit_active_groups`. Subreddits are merged and deduped, then capped by `max_subreddits`.

## Platform-specific notes (all 5 platforms)

- **LinkedIn**: Firm/practice language: "new firm", "opened our practice", "launching our firm", "new venture", "proud to announce", "we are pleased to announce".
- **Twitter**: Phrases + hashtags: #smallbusiness, #grandopening, #lawfirm, #consulting, #architecture; phrases for new firm, opened practice.
- **Instagram**: Hashtags (grandopening, newbusiness, smallbusiness, newfirm) + phrase_additions for any business type.
- **Facebook**: Phrases: grand opening, new business, open for business, new firm, opened our practice, new practice, come visit us.
- **Reddit**: Subreddits (business_owners + professional_services + local_business + sellers_retail + regional) + keywords including new firm, new practice, opened our office; `sortBy: new`, `timeFilter: day`.

## Global coverage (most countries)

- **International phrases** in `themes.international_launch`: Spanish, Portuguese, French, German, Hindi, Arabic, Dutch, Italian, Turkish, Indonesian (e.g. "nuevo negocio", "abrimos", "nouvelle entreprise", "eröffnung", "grand opening"). These are merged with announcement phrases so we fetch from many regions.
- **Regional Reddit subreddits** in `reddit_sources`: UK, India, Australia, Canada, Europe (see `reddit_active_groups`). Enable/disable groups to focus or widen.

## Latest first + no duplicate posts

- **Reddit**: `sortBy: "new"`, `timeFilter: "day"` (last 24h). Pipeline passes `after_utc` (last run’s max post timestamp) so the next run only fetches posts newer than that — no re-scraping the same posts.
- **Twitter / Instagram / Facebook / LinkedIn**: Pipeline passes `since: <lastRunAt date>` when available so actors can return only posts after the last run. (Actors must support `since` or `startDate`.)
- **Dedupe at store**: Every post is stored with `_id = hash(platform + postId)`. We upsert by `_id`, so the same post is never stored twice.

## High volume (enough to pass the filter)

- **limits.max_search_terms_per_platform**: 35–40 so we send many queries per platform.
- **limits.max_subreddits**: 25; **reddit_active_groups** includes regional groups.
- **phase1_sources.yaml**: `maxResults` 50 (LinkedIn, Twitter, IG, Facebook), `maxPosts` 80 (Reddit). Run daily so you get a steady flow of new posts.

## Testing

Run ingestion as usual; the pipeline will load `search_strategy.yaml` and build keywords/subreddits from it. To test with minimal Apify usage: `APIFY_MINIMAL_TEST=1` (uses a small fixed Reddit input).
