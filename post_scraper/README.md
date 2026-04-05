# post_scraper

**Standalone project:** content ingestion for social media posts. Everything lives in this folder.

Accepts a post URL → detects platform → extracts metadata → downloads media → saves under `post_scraper/media/` for downstream use (OCR, transcription, etc.).

## Supported platforms

We detect and fetch posts from:

- **Instagram** (reels, posts, carousels)
- **YouTube** (videos, Shorts)
- **TikTok**
- **Twitter / X**
- **Facebook** (reels, Watch, posts)
- **Reddit**
- **LinkedIn** (cookies recommended)
- **Vimeo**
- **Pinterest**
- **Tumblr**

Extraction is done by [yt-dlp](https://github.com/yt-dlp/yt-dlp). For details, limits, and cookies usage see **[PLATFORM_SUPPORT.md](PLATFORM_SUPPORT.md)**.

## Install (inside this folder)

```bash
cd post_scraper
pip install -r requirements.txt
```

Optional: **ffmpeg** on PATH for audio extraction (WAV from video).

## Run the test web UI

From **inside** the `post_scraper` folder:

```bash
cd post_scraper
python run_server.py
```

Then open **http://localhost:8765**. Paste a post URL, click **Download**, and see the result. All downloaded files go to `post_scraper/media/{job_id}/`.

Other port:

```bash
PORT=9000 python run_server.py
```

## Project layout (all in this folder)

```
post_scraper/
├── run_server.py          # Run this to start the test UI
├── server.py              # FastAPI app
├── static/
│   └── index.html         # Test UI
├── scraper.py             # Main controller: scrape_post(url)
├── downloader.py          # Media download (yt-dlp)
├── metadata_extractor.py
├── platform_detector.py
├── utils.py
├── models.py
├── platforms/             # Optional per-platform overrides
├── media/                 # Created on first run; downloaded files go here
├── requirements.txt
└── README.md
```

## Use as a library

From the **parent** of `post_scraper` (so `post_scraper` is a package):

```python
from post_scraper import scrape_post

result = scrape_post("https://www.instagram.com/reel/xxx/")
if result.success:
    print(result.media_path)   # e.g. .../post_scraper/media/abc123/video.mp4
    print(result.metadata.author)
else:
    print(result.error)
```

## Output layout

Media is stored under **this folder** by default:

```
post_scraper/media/
  {job_id}/
    video.mp4
    audio.wav      # if ffmpeg available
    thumbnail.jpg
    metadata.json
```

Override with env: `POST_SCRAPER_MEDIA_DIR=/other/path python run_server.py`

For **LinkedIn**, the most reliable approach is **Playwright + network interception + cookies**: install `playwright`, run `playwright install chromium`, then set a cookies file from a logged-in LinkedIn session. The scraper will use it first for LinkedIn URLs. Alternatively, when yt-dlp fails, the **Apify fallback** runs if `APIFY_TOKEN` is set.

```bash
# Optional: cookies for logged-in session (required for Playwright LinkedIn)
set POST_SCRAPER_COOKIES_FILE=C:\path\to\cookies.txt
# Optional: Playwright for LinkedIn (most reliable)
pip install playwright
playwright install chromium
# Optional: when yt-dlp fails on LinkedIn, use Apify
set APIFY_TOKEN=your_apify_token
python run_server.py
```

Or pass `cookies_file="path/to/cookies.txt"` when calling `scrape_post()` in code. See [PLATFORM_SUPPORT.md](PLATFORM_SUPPORT.md#linkedin-when-yt-dlp-fails) for LinkedIn details.

## API

- **`scrape_post(url, base_dir=None, job_id=None, ...)`**  
  Returns `ScrapedPost` (success, paths, metadata, or error message).
- **`detect_platform(url)`**  
  Returns platform id or `"unknown"`.
- **`is_supported_platform(platform)`**  
  Whether the platform is supported.

Errors (private/deleted, unsupported platform, download failure) are returned as `ScrapedPost(success=False, error="...")`, so the module is safe for background jobs.

## Extensibility

See `platforms/base.py` and the stub modules (`instagram_scraper.py`, etc.) to add or override per-platform logic.
