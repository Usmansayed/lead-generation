# LinkedIn post video extraction – research summary

This document summarizes research on the **yt-dlp LinkedIn “Unable to extract video”** error, so you have accurate, source-level context.

---

## The error you see

```
ERROR: [LinkedIn] 7432040278024286208: Unable to extract video; please report this issue on https://github.com/yt-dlp/yt-dlp/issues?q= ...
Confirm you are on the latest version using  yt-dlp -U
```

- **`7432040278024286208`** (or similar) is the **post/activity ID** that yt-dlp extracted from your URL. So the URL is recognized and the LinkedIn extractor runs.
- **“Unable to extract video”** is raised when a **regex fails** inside the LinkedIn extractor. In yt-dlp this comes from `RegexNotFoundError` (e.g. “Unable to extract {name}”) when a required pattern is not found in the page.

So the failure is: **URL is supported → page is downloaded → the HTML no longer matches what the extractor expects** (or the video isn’t in the initial HTML).

---

## How the yt-dlp LinkedIn extractor works (source-level)

From the current [yt-dlp LinkedIn extractor](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/linkedin.py):

1. **URL patterns it handles**
   - `https://www.linkedin.com/posts/...-{id}-...` (e.g. `.../username_activity-7151241570371948544-4Gu7`)
   - `https://www.linkedin.com/feed/update/urn:li:activity:{id}` (e.g. `.../urn:li:activity:7016901149999955968`)

   Feed URLs were added in **PR #12927** (April 2025), which closed **Issue #6104** (“Unsupported URL” for feed links). So feed URLs are *supported*; your error is a different step.

2. **Where “Unable to extract video” comes from**
   - The extractor downloads the **webpage** for that URL.
   - It then runs a **regex** to find a **`<video ...>`** tag (with attributes) in the HTML.
   - It reads **`data-sources`** from that tag (JSON list of video sources) and builds formats from that.
   - If the regex does **not** find that video tag, yt-dlp raises **`RegexNotFoundError('Unable to extract video')`**.

So: **“Unable to extract video” = the page HTML no longer contains the expected `<video ... data-sources="...">` pattern** (or it’s structured differently). Common causes:

- LinkedIn changed the **page structure** or moved video into a different element/attribute.
- Video is loaded **client-side** (JavaScript) and is not present in the initial HTML that yt-dlp downloads.
- The page is **login-gated** or **region/rights restricted**, so the HTML you get doesn’t include the player.
- **Ad-blockers / different user-agent** can sometimes change what the server returns (less common but possible).

---

## What’s supported vs what fails

| Content type              | URL form                    | Typical yt-dlp result |
|---------------------------|-----------------------------|------------------------|
| **LinkedIn Learning**     | `linkedin.com/learning/...` | Works with login/cookies; uses a different code path (API). |
| **Feed / post videos**    | `feed/update/urn:li:activity:...` or `posts/...` | Often **“Unable to extract video”** because of the HTML/regex step above. |
| **Events (live/replay)**  | `linkedin.com/events/...`   | Separate extractor; may require `li_at` cookie. |

So the problem is **specific to post/feed video pages**: the extractor expects a certain HTML shape that LinkedIn often no longer sends (or only sends after JS).

---

## References (official / source)

- **yt-dlp LinkedIn extractor**  
  https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/linkedin.py  
  – `LinkedInIE._real_extract`: regex on webpage for `<video ...>` and `data-sources`.

- **Feed URL support (fix for “Unsupported URL”)**  
  - Issue #6104: [LinkedIn download returns "Unsupported URL" error](https://github.com/yt-dlp/yt-dlp/issues/6104)  
  - PR #12927: [[ie/linkedin] Support feed URLs](https://github.com/yt-dlp/yt-dlp/pull/12927) (merged April 2025).

- **Historical context (posts vs Learning)**  
  - [LinkedIn supports only videos from linkedinLearning, but not from posts](https://github.com/ytdl-org/youtube-dl/issues/31501) (youtube-dl).

- **Error origin**  
  The message is from yt-dlp’s generic regex failure: **`RegexNotFoundError`** → “Unable to extract {name}” (e.g. “video”). So it’s **not** “unsupported URL” anymore; it’s “supported URL, but required pattern missing in HTML”.

---

## What you can do (in order of practicality)

1. **Playwright + network interception + logged-in cookies (most reliable)**  
   Use a real browser with your LinkedIn cookies; the scraper intercepts network responses to capture the actual video URL and downloads it.  
   - Install: `pip install playwright` then `playwright install chromium`  
   - Export cookies (Netscape or JSON) from a logged-in LinkedIn session and set **`POST_SCRAPER_COOKIES_FILE`** (or pass `cookies_file` to `scrape_post()`).  
   - For LinkedIn URLs, when cookies are set, the scraper tries this **first** before yt-dlp.  
   - Cookie formats: **Netscape** (e.g. from "Get cookies.txt" browser extensions) or **JSON** (list of `{name, value, domain, path, ...}`).

2. **Update yt-dlp**  
   `pip install -U yt-dlp`  
   Ensures you have feed URL support and any newer fixes. It often does **not** fix “Unable to extract video” if LinkedIn changed the player HTML.

3. **Use cookies with yt-dlp only**  
   Export a Netscape-format cookies file and set **`POST_SCRAPER_COOKIES_FILE`** (or pass `cookies_file` to `scrape_post()`).  
   Sometimes the **logged-in** HTML still has the old structure; sometimes it doesn’t. Worth trying.

4. **Use the Apify fallback**  
   Set **`APIFY_TOKEN`** and install **`apify-client`**. When yt-dlp fails with this error, the scraper can call the Apify actor **pocesar/download-linkedin-video**, which uses a different method (browser/automation) to get the video. See [PLATFORM_SUPPORT.md](../PLATFORM_SUPPORT.md#linkedin-when-yt-dlp-fails).

5. **Report to yt-dlp (optional)**  
   If you have a **public** post URL and can share it, you can open an issue at https://github.com/yt-dlp/yt-dlp/issues with:
   - The exact URL
   - That you’re on the latest yt-dlp (`yt-dlp -U`)
   - That the video plays in your browser when logged in
   - Full verbose output: `yt-dlp -v "URL"`  
   Maintainers can then adjust the extractor if the HTML structure has changed.

---

## Short summary

- **Error:** “Unable to extract video” = the LinkedIn **post/feed** extractor did not find the expected **`<video ... data-sources="...">`** in the page HTML (regex failed).
- **Cause:** LinkedIn’s page structure or loading behavior no longer matches what the extractor expects (or video is JS-only / login-dependent).
- **Fix in yt-dlp:** Would require a maintainer to update the extractor for the current LinkedIn HTML/API; until then, **Playwright + cookies** (most reliable), **Apify fallback**, or **cookies with yt-dlp** are the practical options for post videos.
