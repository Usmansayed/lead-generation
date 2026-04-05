"""
Minimal web server to test the post_scraper: paste URL, click Download, see result.
Run: python -m post_scraper.server   or   uvicorn post_scraper.server:app --reload
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .platform_detector import list_supported_platforms
from .scraper import scrape_post

app = FastAPI(title="Post Scraper Test", version="0.1.0")

# Serve static files (index.html) from post_scraper/static
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ScrapeRequest(BaseModel):
    url: str


@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the test UI."""
    html_path = STATIC_DIR / "index.html"
    if not STATIC_DIR.exists() or not html_path.exists():
        return _fallback_html()
    return FileResponse(html_path)


@app.get("/api/platforms")
def api_platforms():
    """Return the list of supported platform IDs (for UI or API clients)."""
    return {"platforms": list(list_supported_platforms())}


@app.post("/api/scrape")
def api_scrape(req: ScrapeRequest):
    """Run the scraper for the given URL and return the result."""
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    result = scrape_post(url)
    return result.to_dict()


def _fallback_html():
    """Inline HTML if static file is missing."""
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>Post Scraper</title></head>
        <body>
        <h1>Post Scraper</h1>
        <p>Static file not found. Create post_scraper/static/index.html</p>
        </body>
        </html>
        """
    )


def main():
    import socket
    import uvicorn

    base_port = int(os.environ.get("PORT", "8765"))
    port = base_port
    for _ in range(10):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
        except OSError as e:
            # Windows: 10048 = address already in use; Unix: 98 = address already in use
            if getattr(e, "errno", None) in (10048, 98):
                port += 1
                continue
            raise
        break
    if port != base_port:
        print(f"Port {base_port} in use, using {port} instead.", flush=True)
    print(f"Open in browser: http://127.0.0.1:{port}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
