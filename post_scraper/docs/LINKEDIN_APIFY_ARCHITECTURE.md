# LinkedIn post downloader — Apify actor architecture

This doc describes the **recommended architecture** for a production LinkedIn post downloader on Apify: Crawlee + PlaywrightCrawler + network interception.

---

## Core idea

LinkedIn is a **React SPA**. The video/media is **not** in the initial HTML; the browser loads it later via **network requests**. So the actor must:

1. Open the post URL
2. Wait for JS rendering
3. **Capture network requests** (intercept responses)
4. Extract media URLs (`.mp4`, `.m3u8`, `media.licdn.com`, `dms/video`)
5. Download video/images (and optionally extract metadata from the DOM)

Browser automation (Playwright inside Apify actors) is built for this.

---

## Recommended actor stack

| Layer | Choice |
|--------|--------|
| Platform | Apify Actor |
| Crawler | **Crawlee** |
| Browser | **PlaywrightCrawler** + headless Chrome |
| Proxy | Apify proxy (e.g. RESIDENTIAL) to reduce blocking |

Apify provides templates that already include this crawler structure.

---

## High-level pipeline

```
Input: { "urls": ["https://www.linkedin.com/posts/...activity-123"] }
         ↓
Step 1 — Open page with Playwright
         await page.goto(postUrl)
         await page.waitForLoadState("networkidle")
         ↓
Step 2 — Capture network traffic
         page.on("response", ...) → look for *.mp4, *.m3u8, media.licdn.com, dms/video
         ↓
Step 3 — Extract metadata from DOM (after React renders)
         post text, author, timestamp, likes, comments
         ↓
Step 4 — Download media
         fetch(video_url) → save to Apify key-value store (or return URL for backend)
         ↓
Output: dataset with post metadata + media URLs or stored files
```

---

## Network interception — what to look for

LinkedIn media is typically served from:

- **`media.licdn.com`** (especially **`/dms/video`** paths)
- URLs ending in **`.mp4`** or **`.m3u8`**

Example check:

```js
page.on("response", (response) => {
  const url = response.url();
  if (url.includes("licdn.com/dms/video") || url.includes(".mp4") || url.includes(".m3u8")) {
    // capture url for download
  }
});
```

---

## Reliability improvements (production-grade)

1. **Apify proxy**  
   Use **RESIDENTIAL** (or configured proxy) to reduce LinkedIn blocking.

2. **Browser fingerprint / stealth**  
   - Stealth plugin  
   - Random or realistic user agents  

3. **Retries**  
   `maxRequestRetries: 3` (or similar) for failed pages.

4. **Post type detection**  
   Handle: video posts, image posts, document posts, article links (different selectors or logic).

5. **Cookies / session**  
   If needed, inject cookies for a logged-in session (e.g. from actor input or secrets).

---

## Enrich output for downstream (recommended)

Inside the actor, also extract when possible:

- **Video transcript** (if exposed in DOM or via a separate request)
- **Hashtags**
- **Mentions**
- **External links**

This supports a **fact-checking or content-analysis pipeline** later.

---

## Expected reliability and cost

| Method | Reliability |
|--------|-------------|
| yt-dlp | Low (HTML structure changes) |
| Raw HTML scraping | Very low |
| LinkedIn API (official) | Medium (rate limits, access) |
| **Playwright actor (network interception)** | **Very high (~95–99%)** |

**Cost (typical):** ~5–10 seconds per post → about **$0.002–$0.01 per post** on Apify, depending on proxy usage.

---

## Where this sits in your project

Multi-platform post ingestion:

```
User shares link
       ↓
Platform detector (e.g. post_scraper.platform_detector)
       ↓
If LinkedIn → call LinkedIn Apify actor (this architecture)
       ↓
Actor: Playwright → intercept media URLs → extract metadata → store media + result
       ↓
Your backend: store in DB, pass to fact-checking/analysis
```

The **post_scraper** can call this custom actor (by Apify actor ID) when `APIFY_TOKEN` is set, instead of or in addition to the generic `pocesar/download-linkedin-video` actor.

---

## Faster variant (optional)

A **hidden API** or internal request that the LinkedIn player uses can sometimes be reverse‑engineered. Using that directly (once known) can make a downloader **2–3× faster** than full browser scraping, at the cost of higher breakage risk when LinkedIn changes the API. If you have the exact request (URL pattern, headers, cookies), it can be documented here and wired into the actor or a separate “fast path.”

---

## Reference implementation

A minimal actor that follows this architecture lives in this repo:

**`services/apify-actors/linkedin-post-downloader/`** (Node.js: Crawlee + PlaywrightCrawler)

- Response interception for `media.licdn.com`, `.mp4`, `.m3u8`
- DOM metadata: post text, author, timestamp, likes, comments, hashtags, mentions, links
- Retries and timeout; ready for Apify proxy in run config
- Output: dataset items with `postUrl`, `metadata`, `videoUrls`, `bestVideoUrl`

See that folder’s **README** and **`src/main.js`** for run and deploy. After you deploy to Apify, you can call this actor (by actor ID) from **post_scraper** instead of or in addition to `pocesar/download-linkedin-video` by setting an env var or option for the custom actor ID.
