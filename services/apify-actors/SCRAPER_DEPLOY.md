# Deploy Scrapers to Apify

The **Twitter, Instagram, Facebook, and LinkedIn** lead scrapers are refactored to **Crawlee** for **100+ leads in under 1 minute** (same target as Reddit). Deploy to use them in the pipeline:

1. **Install Apify CLI** (if needed): `npm install -g apify-cli`
2. **Log in**: `apify login`
3. **Deploy each actor** from project root:

```bash
cd services/apify-actors/twitter-lead-scraper && apify push && cd ../..
cd services/apify-actors/instagram-lead-scraper && apify push && cd ../..
cd services/apify-actors/facebook-lead-scraper && apify push && cd ../..
cd services/apify-actors/linkedin-lead-scraper && apify push && cd ../..
```

Or from project root (PowerShell):

```powershell
cd c:\Users\usman\Music\lead-generation
foreach ($dir in "twitter-lead-scraper","instagram-lead-scraper","facebook-lead-scraper","linkedin-lead-scraper") {
  Set-Location "services\apify-actors\$dir"; apify push; Set-Location "..\..\.."
}
```

After deployment, run ingestion as usual; the pipeline uses the actors by name (`twitter-lead-scraper`, etc.).

## What changed (Crawlee, 100+ leads/min)

| Scraper   | Change |
|-----------|--------|
| **Twitter** | **Crawlee BeautifulSoupCrawler**: all SERP URLs (DDG + Bing per keyword) enqueued; concurrency 50; residential proxy; no per-request delay. `maxResults` default 120. |
| **Instagram** | Same: Crawlee + all SERPs in parallel; filter to post/reel URLs. `maxResults` default 120. |
| **Facebook** | Same: Crawlee + DDG/Bing; filter to post/permalink/group URLs. `maxResults` default 120. |
| **LinkedIn** | **SERP-only**: BeautifulSoupCrawler on DDG/Bing for `site:linkedin.com/jobs`; pushes leads from title/snippet/url (no browser). `maxResults` default 120. |
| **Config** | `config/phase1_sources.yaml`: `maxResults: 120`, `timeout_secs: 120`, `memory_mbytes: 2048` for all four; Reddit `maxPosts: 100`. |

See `docs/APIFY_RAW_RESOURCES_RESEARCH.md` for the design and raw Apify resources used.

## Required: `beautifulsoup4[lxml]`

All four Crawlee scrapers **must** use `beautifulsoup4[lxml]` in `requirements.txt` (not just `beautifulsoup4`). Crawlee’s BeautifulSoupCrawler uses the lxml parser by default; without it, every request fails with "Couldn't find a tree builder with the features you requested: lxml" and **0 leads** are returned.

## Test results (Twitter)

- **Before fix**: 0 leads (lxml missing in Docker image).
- **After lxml + Crawlee**: **86 leads** in ~1 min 32 s crawler runtime (120 SERP requests, 0 failed). Pipeline: **86 ingested, 86 inserted** into MongoDB.
- Concurrency tuned with `min_concurrency=20`, `desired_concurrency=40` for higher throughput. Deploy all four actors after pulling latest (each has `beautifulsoup4[lxml]` and concurrency settings).
