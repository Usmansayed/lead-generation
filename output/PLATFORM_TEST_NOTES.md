# All-Platform Test: Findings & Solutions

Test run: full pipeline (post fetch → profile fetch → research → contact → email) on Reddit, Twitter, Instagram, Facebook, LinkedIn.

## Summary

| Platform   | Post fetch      | Profile fetch   | Contact fallback | Notes |
|-----------|------------------|------------------|-------------------|--------|
| **Reddit**   | ✅ Works (cached/API) | ✅ or 503 sometimes | profile URL       | Best supported; use real subreddit post URLs. |
| **Twitter/X**| ✅ HTML (often "JS disabled" page) | Same             | profile URL       | Fetcher gets static HTML; pipeline uses `lead.post_text` when needed. |
| **Instagram**| ⚠️ 0 chars (timeout/login) | ⚠️ 0 chars       | profile URL       | Playwright + proxy used; Meta may timeout. Pipeline uses `lead.post_text` + profile link. |
| **Facebook** | ⚠️ 0 (timeout/400) | ⚠️ 0            | profile URL       | Real post URLs may work; pipeline uses `lead.post_text` + profile. |
| **LinkedIn** | ✅ sometimes (httpx fallback) | ⚠️ 999 denied | profile URL   | Post feed URL can return 425+ chars via httpx; profile blocked. Use post_text when empty. |

## How we make it work for all platforms

1. **post-content-fetcher** uses **Playwright** for social URLs (Reddit, Twitter, Instagram, Facebook, LinkedIn) so JS-rendered content is fetched when possible. It falls back to **httpx** when Playwright times out or returns a "enable JavaScript" wall.
2. **Pipeline always has a fallback:** When full post or profile fetch returns empty, the pipeline still uses **`lead.post_text`** (the snippet from phase 1 scraping) for business research and email generation, and **contact** is set to the profile URL (or post URL) so you can reach the lead via DM/message.
3. **Reddit** and **Twitter** consistently return content (cached or live). **LinkedIn** post URLs sometimes return content via httpx. **Instagram** and **Facebook** often timeout or require login; the pipeline still produces a personalized email from `post_text` and gives you the profile link to contact.

## Bugs fixed during test

1. **Empty actor response** – When Apify post-content-fetcher returned `{"text":"","content":"", "url":"..."}`, the pipeline was storing `str(first)` (the dict string) as profile/post text. **Fix:** In `full_post_fetch.py` and `profile_enrichment.py`, return `""` when no key has non-empty content instead of `str(first)`.
2. **Twitter profile URL** – Profile URL built as `https://twitter.com/{handle}`; x.com redirects work. No code change needed; documented.
3. **Pipeline resilience** – When full_post_text or profile_text is empty, research and email still use `lead.post_text` and contact falls back to profile URL or post URL. No exception; all 5 platforms complete.

## How to run

```bash
python scripts/test_all_platforms.py
```

Output: `output/all_platforms_test_result.json` (per-platform results + contact + email + platform_notes).

## Solutions for low/no content

- **Always have post_text** – Lead scrapers (phase 1) should store the post snippet/title so when full fetch fails we still have content for research and email.
- **Contact = email or profile** – If no email found, we output profile URL (or post URL) so you can reach via DM/message.
- **Residential proxy** – Already used for post-content-fetcher when `useProxy: True`; helps with Reddit and sometimes Twitter/Instagram/Facebook.
- **LinkedIn/Instagram/Facebook** – For production, consider official APIs or authenticated scrapers; our pipeline degrades gracefully (post_text + profile link + generated email).
