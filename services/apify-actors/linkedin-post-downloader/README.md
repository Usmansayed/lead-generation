# LinkedIn Post Downloader (Apify Actor)

LinkedIn post **video/media downloader** using **Crawlee + PlaywrightCrawler**: open post → wait for JS → **capture network** (media.licdn.com, .mp4, .m3u8) → extract metadata from DOM → output URLs + metadata.

## Why this approach

LinkedIn is a **React SPA**; video is not in the initial HTML. The browser loads it via **network requests**. This actor uses Playwright to load the page and intercepts responses to capture the real media URLs (~95–99% reliability vs low for yt-dlp on posts).

## Input

```json
{
  "urls": [
    "https://www.linkedin.com/posts/username_activity-1234567890-AbCd",
    "https://www.linkedin.com/feed/update/urn:li:activity:1234567890"
  ]
}
```

## Output (dataset)

Each item:

- **postUrl** – requested URL
- **metadata** – postText, **author** (display name), **authorUsername** (profile slug, e.g. `usman-sayed-56884735b`), timestamp, likes, comments, hashtags, mentions, links
- **videoUrls** – all captured video URLs (e.g. .mp4, .m3u8, media.licdn.com/dms/video)
- **imageUrls** – all captured image URLs (e.g. media.licdn.com images, .jpg, .png; includes profile photos and post images)
- **bestVideoUrl** – preferred video URL for download (.mp4 when available)

Your backend or the [post_scraper](../..) can then `fetch(bestVideoUrl)` (with cookies if needed) and store the file.

## Run locally

```bash
npm install
npm start
```

With input in Apify format (e.g. `{ "urls": ["https://www.linkedin.com/posts/..."] }` in `INPUT_SCHEMA.json` prefill or via API).

### Test with example URL (no Apify)

```bash
npm run test:local
```

This runs the crawler against a real post URL and prints the result (post + metadata). Example output for [this post](https://www.linkedin.com/posts/usman-sayed-56884735b_big-lesson-from-the-claude-code-security-share-7432040278024286208-pbhV):

- **postUrl**, **metadata.postText**, **metadata.author** (e.g. "Usman Sayed"), **metadata.timestamp** ("2w"), **metadata.likes** ("6"), **videoUrls**, **bestVideoUrl**

## Deploy to Apify

1. Push to a repo or zip the actor.
2. Create a new Actor in Apify, connect the repo or upload the zip.
3. Build (Dockerfile uses `apify/actor-node-playwright-chrome`).
4. Run with input `{ "urls": ["..."] }`.

## Reliability

- Use **Apify proxy** (e.g. RESIDENTIAL) in the run config to reduce blocking.
- **maxRequestRetries: 3** is set in the crawler.
- For **cookies** (logged-in session), you can extend the actor to inject cookies from input or secrets.

## Architecture

See **[post_scraper/docs/LINKEDIN_APIFY_ARCHITECTURE.md](../../../post_scraper/docs/LINKEDIN_APIFY_ARCHITECTURE.md)** in the main project for the full pipeline, cost notes, and optional “hidden API” faster variant.

## Project layout

```
linkedin-post-downloader/
├── src/
│   ├── main.js              # Crawlee + PlaywrightCrawler, response interception
│   └── utils/
│       ├── mediaExtractor.js   # isMediaResponse, pickBestVideoUrl
│       └── metadataParser.js   # extractMetadataFromPage (DOM)
├── .actor/
│   └── actor.json
├── INPUT_SCHEMA.json
├── Dockerfile
├── package.json
└── README.md
```
