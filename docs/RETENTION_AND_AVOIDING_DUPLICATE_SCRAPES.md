# Retention and Avoiding Duplicate Scrapes

## The problem

When you run the same scrapers repeatedly (e.g. Reddit every day) with the **same keyword map** and **no retention-specific measures**, you keep fetching the **same posts**. Result:

- First run: lots of leads.
- Later runs: almost no new leads, because SERP/listings return the same items and we already have them.

So you get no real new leads after the first fetch.

## How other companies fix it

### 1. **Cursor-based incremental sync** (recommended)

- **Idea:** Store a “cursor” (e.g. last `created_utc` or last item ID) after each run. On the next run, pass that cursor to the source so it returns **only items newer than** (or after) that cursor.
- **Used by:** dlt, Airbyte, many ETL/scraping pipelines.
- **Steps:**
  1. After each successful run, compute **max timestamp** (or last ID) per platform from the fetched items.
  2. Persist that in **state** (e.g. MongoDB `pipeline_state`, or a small JSON file).
  3. On the next run, pass that value into the actor/source (e.g. `after_utc`, `since`, `startDate`).
  4. The actor **only outputs items newer than the cursor** (or the API only returns them).

So you only fetch and process **new** content; no re-scraping the same posts.

### 2. **Deduplication by primary key**

- Even with cursors, boundaries can be inclusive, so the same record may appear twice. Use a **stable ID** (e.g. `platform + post_id` → hash) and **upsert** into your store so duplicates don’t create extra rows.
- We do this: `_id` = hash(platform + post_id), and we **replace_one with upsert** in `raw_posts`, plus we keep `seen_post_hashes` so we don’t re-process after retention deletes.

### 3. **Pre-filter already-seen items**

- Before normalizing and storing, **skip items we already have** in `raw_posts` (by the same hash). That way we don’t waste relevance/AI on known posts.
- We do this in `_filter_already_in_raw()` in `pipeline/ingestion.py`.

### 4. **Time windows**

- Use a **short time window** (e.g. “last 24h” or “last 7 days”) so each run is biased toward fresh content. We use `timeFilter: "day"` for Reddit in config; the actor must then **honor** a cursor so we don’t re-fetch the same “day” every time.

### 5. **SERP / search engines**

- For SERP-based scrapers (Twitter, Instagram, Facebook, LinkedIn via DDG/Bing), the **search engine doesn’t support a “since” parameter** in the URL. So we still request the same queries; retention is achieved by:
  - **Pre-filter:** `_filter_already_in_raw` so we don’t store or process items we already have.
  - **Stable keywords:** Same keyword map is fine; new leads appear when SERP results change (new pages, new posts). We don’t re-insert duplicates thanks to dedupe and `seen_post_hashes`.

## What we implemented in this repo

### Reddit (incremental by time)

- **State:** Pipeline stores **per-platform cursors** in `pipeline_state` (e.g. `cursors.reddit` = max `created_utc` from the last run).
- **Bootstrap:** If there is **no cursor in state** for a platform (e.g. first run after DB restore, or state was lost), the pipeline **bootstraps** the cursor from existing `raw_posts`: it takes the **max timestamp** for that platform and uses it as `after_utc`. So the next fetch only returns posts newer than what you already have; no need to have run the pipeline once before for retention to work.
- **Passing the cursor:** Before calling the Reddit actor, we call `merge_cursor_into_run_input(run_input, "reddit", cursors["reddit"])`, which sets **`after_utc`** in the actor input. You should see a log line: `Retention: passing after_utc to actor (only new posts)` when it is used.
- **Actor behavior:** The Reddit actor **reads `after_utc`** and **skips** any post where `created_utc <= after_utc`. So it only **outputs** posts newer than the last run → we only ingest new posts → no re-scraping the same Reddit posts. (The actor still requests the same listing URLs; filtering is done in code so the **output** is incremental.)
- **Saving the cursor:** After each platform run, we take the max `timestamp` (Unix) from the leads we got and update `cursors[platform]` in state. Bootstrapped cursors are also persisted so the next run has them even if the current run returns no new leads.

So for Reddit we have **retention-specific behavior**: same keyword map, but each run only adds **new** posts.

### Other platforms (Twitter, Instagram, Facebook, LinkedIn)

- We pass a **since date** from `lastRunAt` when the actor supports it (`merge_since_date_into_run_input`). Our current SERP-based Crawlee actors don’t use a date filter in the search URL (DDG/Bing don’t support it the same way).
- Retention for these is:
  - **Dedupe:** Upsert by `_id` (hash of platform + post_id); `seen_post_hashes` so we don’t re-process after TTL/deletes.
  - **Pre-filter:** `_filter_already_in_raw` so we don’t run relevance/AI on items we already have in `raw_posts`.
- New leads appear when SERP results actually change (new content indexed). We don’t re-store the same posts.

### Summary table

| Measure | Purpose |
|--------|--------|
| **`after_utc` (Reddit)** | Only fetch/output posts newer than last run; avoid same posts every run. |
| **Cursors in `pipeline_state`** | Persist max timestamp per platform so next run can pass `after_utc` (or equivalent). |
| **`_filter_already_in_raw`** | Skip items already in `raw_posts` so we don’t re-process or re-store. |
| **Upsert by `_id` + `seen_post_hashes`** | No duplicate rows; no re-fetch after retention delete. |
| **Same keyword map** | Safe; retention is handled by cursor + dedupe, not by changing keywords. |

## References

- [dlt: Cursor-based incremental loading](https://dlthub.com/docs/general-usage/incremental/cursor)
- [Airbyte: Incremental sync](https://docs.airbyte.com/platform/connector-development/connector-builder-ui/incremental-sync)
- [Apify: How to deduplicate scraped data](https://blog.apify.com/how-to-scraped-data-deduplication/)
- Reddit API: list endpoints support `after` / `before` (fullname) for pagination; we use **timestamp** (`after_utc`) in the actor to filter output so we only push new posts.
