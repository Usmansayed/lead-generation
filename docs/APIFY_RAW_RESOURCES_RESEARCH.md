# Using Apify Raw Resources to Build Reddit-Style Powerful Scrapers

This document summarizes how to use **Apify’s raw building blocks** (Crawlee, proxy, storage, queues) — not pre-built Store actors — to build high-volume, reliable scrapers like the Reddit lead scraper, and how this applies to Twitter, Instagram, Facebook, and LinkedIn.

---

## 1. Why the Reddit Scraper Is “Powerful”

The Reddit lead scraper is effective because:

| Factor | Reddit | Twitter / Instagram / Facebook / LinkedIn (current) |
|--------|--------|------------------------------------------------------|
| **Data source** | **Direct JSON API**: `https://www.reddit.com/r/{subreddit}/new/.json?limit=100` | Search engines (DuckDuckGo, Bing, Google) → then visit result links |
| **Requests per lead** | 1 request ≈ many posts (e.g. 25–100) | Many SERP requests + 1 request per result URL |
| **Crawler type** | `BeautifulSoupCrawler` (HTTP only) | `httpx` + manual loop (Twitter/IG/FB) or `PlaywrightCrawler` (LinkedIn) |
| **Concurrency** | Crawlee’s pool + session rotation | Sequential or ad-hoc batching |
| **Retries / proxy** | Crawlee retries + `Actor.create_proxy_configuration()` | Manual retry; proxy only on some paths |
| **Discovery** | No search engine — direct subreddit URLs | Depends on DDG/Bing/Google |

So “powerful” here means: **direct, high-yield endpoints + Crawlee (HTTP when possible) + proxy + queue-driven concurrency**.

---

## 2. Apify Raw Resources to Use

Use these **raw** Apify/Crawlee features (no Store actors):

- **Crawlee crawlers**
  - **BeautifulSoupCrawler** – static HTML or any text (e.g. JSON). Fast, low memory.
  - **HttpCrawler** – when you need raw response/JSON without BeautifulSoup.
  - **PlaywrightCrawler** – only when the site needs a real browser (e.g. LinkedIn, heavy JS).
- **RequestQueue** (via Crawlee)
  - Add all “discovery” URLs upfront (e.g. one per keyword, one per subreddit, one per SERP).
  - Crawler pulls from the queue, runs with concurrency and retries; you don’t manage loops by hand.
- **Proxy**
  - `proxy_configuration = await Actor.create_proxy_configuration(groups=['RESIDENTIAL'])` (or default for Reddit).
  - Pass to crawler: `proxy_configuration=proxy_config`.
- **Concurrency**
  - `ConcurrencySettings(max_concurrency=50, max_tasks_per_minute=…)` for HTTP crawlers.
  - Lower for Playwright (e.g. 2–5) to avoid memory/CPU spikes.
- **Storage**
  - `await context.push_data(item)` or `Actor.push_data(item)` → default dataset (same as now).
- **Sessions**
  - `use_session_pool=True`, `SessionPool(...)` for cookie/identity per “user” and better success on strict sites.

Rule of thumb: **prefer HTTP/Cheerio (BeautifulSoup/HttpCrawler); use browser only when necessary** (docs and AGENTS.md in the repo).

---

## 3. How to Make Scrapers “Reddit-Like” With Raw Resources

### 3.1 Pattern: Queue-First, Crawlee-Driven

1. **Build a list of start URLs** (e.g. SERP URLs per keyword, or direct API/listing URLs).
2. **Create a crawler** (BeautifulSoup or Http for JSON/static; Playwright only if needed).
3. **Run with `crawler.run(start_requests)`**. Crawlee:
   - Uses the default RequestQueue (or one you pass).
   - Applies concurrency, retries, proxy rotation, and (if configured) session pool.
4. **In the handler**:
   - Parse the page (or JSON in `context.soup.get_text()` / response body).
   - Push leads with `context.push_data(lead)`.
   - Optionally **enqueue more URLs** (e.g. detail pages) with `context.add_requests([...])` so the same run processes them.

This gives you one place for retries, proxy, and scaling instead of manual `httpx` loops.

### 3.2 When You Have a Direct JSON/HTML Listing (Reddit-Like)

If a platform exposes something like:

- `https://example.com/api/posts.json`, or  
- `https://example.com/feed.rss`, or  
- Any URL that returns **many items in one response**,

then:

- Use **BeautifulSoupCrawler** or **HttpCrawler**.
- In the handler, parse JSON/XML from the response and push one dataset item per post.
- Enqueue pagination URLs (e.g. `?after=xyz`) via `context.add_requests([...])` if needed.
- Use **ConcurrencySettings** to run many such URLs in parallel (e.g. 20–50 for HTTP).

That’s the same pattern as Reddit: **one request → many leads**.

### 3.3 When You Only Have Search-Engine Discovery (Twitter, Instagram, Facebook)

There is no public “subreddit-like” JSON feed for Twitter/Instagram/Facebook. So:

- **Keep** search-engine discovery (DuckDuckGo/Bing) to get candidate URLs.
- **Move** that logic into a **Crawlee-based** scraper:
  - Enqueue **all SERP URLs** (e.g. `site:twitter.com keyword`, `site:instagram.com keyword`) as start requests.
  - Use **BeautifulSoupCrawler** with **ConcurrencySettings(max_concurrency=20–50)** and **proxy_configuration**.
  - In the handler: parse SERP HTML → extract result links → push leads (and optionally enqueue detail URLs for a second pass).
- Benefits: single place for retries, proxy rotation, and high concurrency; no custom `httpx` loop.

So they won’t be “as direct as Reddit,” but they become **as robust and scalable** as the Reddit scraper in terms of Apify/Crawlee usage.

### 3.4 LinkedIn (Browser Required)

LinkedIn often requires a real browser (login walls, JS). So:

- Keep **PlaywrightCrawler**.
- Use **RequestQueue**: start with Google SERP URLs; in the handler, **enqueue** LinkedIn job URLs with `context.add_requests([...])`.
- Use **ConcurrencySettings(desired_concurrency=2, max_concurrency=4)** so several tabs run without overloading memory.
- Use **proxy_configuration** (e.g. RESIDENTIAL) and **session pool** as now.
- Optionally reduce per-page delay a bit more if stability allows (you already use 0.8–2s).

---

## 4. Platform Reality: Direct vs Discovery

| Platform   | Direct JSON/listing? | Practical approach with raw Apify resources |
|-----------|----------------------|---------------------------------------------|
| **Reddit** | Yes (`.json` API)    | Already optimal: BeautifulSoupCrawler + direct URLs. |
| **Twitter/X** | No public feed; API v2 is official | Use Crawlee + SERP discovery (DDG/Bing), high concurrency + proxy; or use Twitter API v2 separately if you have access. |
| **Instagram** | No public bulk JSON; oEmbed needs token | Crawlee + SERP discovery; optionally Playwright only for detail pages if needed. |
| **Facebook** | No public listing API | Same: Crawlee + SERP discovery, then detail URLs if needed. |
| **LinkedIn** | No public listing; heavy JS | PlaywrightCrawler + Google SERP → enqueue job URLs; tune concurrency and proxy. |

So “as powerful as Reddit” means:

- **Architecturally**: same use of Crawlee, RequestQueue, proxy, ConcurrencySettings, push_data.
- **Throughput**: for Reddit we get 1 request = many posts; for the others we get **many parallel SERP requests** and optional parallel detail fetches, which is the best we can do without official APIs or direct feeds.

---

## 5. Concrete Recommendations

1. **Refactor Twitter, Instagram, Facebook**  
   - Use **BeautifulSoupCrawler** (or HttpCrawler) with:
     - Start requests = all SERP URLs (DDG/Bing per keyword).
     - `proxy_configuration` (RESIDENTIAL when needed).
     - `ConcurrencySettings(max_concurrency=20–50)`.
   - In the handler: parse SERP → push leads; optionally enqueue detail URLs for a second crawl.
   - This gives Reddit-like **reliability and scaling** (retries, proxy, queue) even though discovery is still via search.

2. **LinkedIn**  
   - Keep Playwright; feed start URLs from input (e.g. Google SERP URLs).
   - Use **add_requests** for job URLs; rely on Crawlee’s RequestQueue and ConcurrencySettings (e.g. 2–4 browser tabs).
   - Keep residential proxy and session pool.

3. **Whenever you find a direct listing**  
   - If any platform exposes an RSS, JSON, or HTML listing URL (e.g. some forums, niche sites), use **BeautifulSoupCrawler/HttpCrawler** and parse it; enqueue pagination URLs. That’s the same “Reddit-style” pattern.

4. **Deployment**  
   - Same as now: `apify push` per actor; pipeline keeps using `run_actor_and_fetch` and `phase1_sources` config. No change to how the rest of the system consumes the dataset.

---

## 6. References

- [Apify – Using Crawlee (Python)](https://docs.apify.com/sdk/python/docs/guides/crawlee)
- [Crawlee for Python – Scaling crawlers](https://crawlee.dev/python/docs/guides/scaling-crawlers) (ConcurrencySettings, max_concurrency, max_tasks_per_minute)
- [Crawlee – BeautifulSoupCrawler](https://crawlee.dev/python/api/class/BeautifulSoupCrawler)
- [Crawlee – RequestQueue](https://crawlee.dev/python/api/class/RequestQueue)
- [Apify – Residential proxy](https://docs.apify.com/platform/proxy/residential-proxy)
- Reddit scraper (reference): `services/apify-actors/reddit-lead-scraper/src/main.py`
- Pipeline config: `config/phase1_sources.yaml`, `pipeline/ingestion.py`

---

*Summary: Use Crawlee (BeautifulSoup/Http for HTTP, Playwright only when needed), RequestQueue for all discovery URLs, proxy + ConcurrencySettings + push_data. That makes scrapers as “powerful” as the Reddit one in terms of Apify raw resources; Reddit stays ahead in raw throughput only because it has a direct JSON API.*
