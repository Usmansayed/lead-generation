# Platform support

The scraper **detects** and **fetches** posts from the platforms below. Extraction is done by [yt-dlp](https://github.com/yt-dlp/yt-dlp), so support and limits follow yt-dlp’s extractors.

## Supported platforms

| Platform   | URL examples                    | Detection | Fetch (yt-dlp) | Notes |
|-----------|----------------------------------|-----------|----------------|--------|
| **Instagram** | instagram.com/reel/..., /p/...   | ✅        | ✅             | Reels, posts, carousels. Rate limits possible; cookies can help. |
| **YouTube**   | youtube.com/watch?v=..., youtu.be/... | ✅   | ✅             | Videos, Shorts. Very reliable. |
| **TikTok**    | tiktok.com/..., vm.tiktok.com/... | ✅    | ✅             | Videos. |
| **Twitter / X** | twitter.com/..., x.com/...      | ✅        | ✅             | Tweets with video. |
| **Facebook**  | facebook.com/..., fb.watch/..., fb.reel/... | ✅ | ✅   | Reels, Watch, posts. May need cookies for some content. |
| **Reddit**    | reddit.com/...                   | ✅        | ✅             | Videos, v.redd.it. May need cookies. |
| **LinkedIn**  | linkedin.com/...                 | ✅        | ⚠️ yt-dlp often fails | **Options:** (1) Update yt-dlp + cookies; (2) set **APIFY_TOKEN** for Apify fallback (see below). extension (e.g. “Get cookies.txt”) and set `POST_SCRAPER_COOKIES_FILE` or pass `cookies_file` to `scrape_post()`. |
| **Vimeo**     | vimeo.com/...                    | ✅        | ✅             | Public videos. |
| **Pinterest** | pinterest.com/..., pinterest.*/... | ✅     | ✅             | Pins with video. |
| **Tumblr**    | tumblr.com/...                   | ✅        | ✅             | Posts with media. |

If you paste a URL from another site (e.g. Twitch, Dailymotion), we may still return `"unknown"` from `detect_platform()` and refuse to scrape. To support more domains, add them in `platform_detector.py` and ensure yt-dlp has an extractor for that site.

## How to maximize success across platforms

1. **Keep yt-dlp up to date**  
   Platforms change often; update regularly:
   ```bash
   pip install -U yt-dlp
   ```

2. **Use cookies for login-only or restricted content**  
   For LinkedIn (and sometimes Instagram, Facebook, Reddit), use a Netscape-format cookies file:
   - Export from your browser (e.g. “Get cookies.txt” or similar).
   - Set the path when calling the scraper:
     - Env: `POST_SCRAPER_COOKIES_FILE=/path/to/cookies.txt`
     - Or pass `cookies_file="/path/to/cookies.txt"` to `scrape_post()`.
   - Do not commit or share this file; add it to `.gitignore`.

3. **Public vs private**  
   Public posts work without cookies on most platforms. Private, unlisted, or region-locked content often needs cookies or may fail with “private/deleted/unavailable”.

4. **Rate limits**  
   Instagram and others may throttle or block if you send too many requests. Use reasonable delays and cookies if needed.

## LinkedIn: when yt-dlp fails

yt-dlp’s LinkedIn extractor often fails on **post** videos with an error like `Unable to extract video`. Detailed research and source references: [docs/LINKEDIN_RESEARCH.md](docs/LINKEDIN_RESEARCH.md). LinkedIn Learning URLs tend to work better (different code path).

**What to do:**

1. **Playwright + network interception + cookies (most reliable)**  
   `pip install playwright` then `playwright install chromium`. Set **`POST_SCRAPER_COOKIES_FILE`** to a cookies file (Netscape or JSON). For LinkedIn with cookies set, the scraper tries this first and captures the video URL from network traffic.

2. **Update yt-dlp**  
   `pip install -U yt-dlp`

3. **Use cookies with yt-dlp only**  
   Export a Netscape-format cookies file from a logged-in LinkedIn session and set `POST_SCRAPER_COOKIES_FILE` (or pass `cookies_file` to `scrape_post()`). Sometimes this still doesn’t fix the extractor.

4. **Use the Apify fallback**  
   If you have an [Apify](https://apify.com) account, set **`APIFY_TOKEN`** in the environment and install the client:
   ```bash
   pip install apify-client
   ```
   When yt-dlp fails on a LinkedIn URL, the scraper will automatically call the Apify actor **pocesar/download-linkedin-video**, download the video from the Key-Value store, and save it under your job directory. The actor may have usage costs; see [Apify pricing](https://apify.com/pocesar/download-linkedin-video).

## Adding more platforms

1. **Detection**  
   In `platform_detector.py`, add a `(regex, platform_id)` entry to `_DOMAIN_PATTERNS` and add the `platform_id` to `SUPPORTED_PLATFORMS`.

2. **Extraction**  
   We rely on yt-dlp. Check [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md). If the site is there, detection is usually enough. If it needs auth, add cookies support (already available via `cookies_file`).

3. **Optional overrides**  
   For custom logic per platform, implement a `PlatformHandler` in `platforms/` and register it (see `platforms/base.py`).
