# Lead Generation — Workflow & How It Works

High-level view of the project: what it does, how data flows, and how to run it.

---

## What the system does

The system **discovers leads** from social and professional platforms (Reddit, Twitter, Instagram, Facebook, LinkedIn), **scores** them with keywords and AI, and **queues personalized emails** (or manual outreach) for qualified leads. All state lives in **MongoDB**; scraping runs on **Apify** actors; scoring and email generation use **AWS Bedrock**.

- **Input:** Platform + keyword/subreddit config (YAML).
- **Output:** `raw_posts` (scraped) → filtered → `qualified_leads` → research + contact discovery → `email_queue` (pending/sent).

---

## Architecture (abstract)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Apify Actors   │     │ Python Pipeline │     │ React Dashboard │
│  (scrape by     │ ──► │ ingest → filter │ ──► │ + FastAPI       │
│   platform)     │     │ → AI → queue    │     │ (view, run jobs) │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                        ┌─────────────────┐
                        │    MongoDB      │
                        │ raw_posts,      │
                        │ qualified_leads,│
                        │ email_queue,    │
                        │ pipeline_state  │
                        └─────────────────┘
```

- **Actors** run per platform with keywords/subreddits and optional `after_utc` / `since` for incremental fetch.
- **Pipeline** normalizes, dedupes, scores (static + LLM), then runs research + contact discovery and enqueues emails.
- **Dashboard** shows counts, runs pipeline jobs, and (optionally) sends queued emails via AWS SES.

---

## Pipeline stages (in order)

| Stage | What it does | In → Out |
|-------|----------------|----------|
| **1. Ingest** | Run Apify actors per platform; normalize; relevance score; dedupe; store | Config + state → `raw_posts` (status: raw / rejected) |
| **2. Static filter** | Keep only `raw_posts` with score ≥ threshold | raw → filtered / static_rejected |
| **3. AI scoring** | LLM qualifies intent | filtered → `qualified_leads` |
| **4. Research & queue** | Full post, profile, contact discovery, email generation | qualified_leads → `email_queue` (pending) or leads_no_email |
| **5. Send** | Drain pending queue via AWS SES | email_queue (pending) → sent / failed |

How we prevent duplicates at each phase:

---

## Deduplication in every phase

We **check first, then process** — we never blindly add then filter duplicates. Each stage only processes what still needs work and uses stable IDs so the same entity never appears twice.

| Phase | What we avoid | How we prevent it |
|-------|----------------|-------------------|
| **1. Ingest** | Duplicate raw posts (same post from same platform) | **Stable ID:** `_id` = SHA256(platform + post_id). Before store we skip items whose `_id` is already in `raw_posts` (`_filter_already_in_raw`). On store we use `replace_one({"_id": id}, doc, upsert=True)` — same post only updates one row. We also write the same `_id` to `seen_post_hashes` for retention. |
| **2. Static filter** | Re-filtering the same lead | We only query `raw_posts.find({"status": "raw"})`. Already filtered or rejected rows are skipped (we log counts). Updates are in-place (status → filtered / static_rejected); no new collection. |
| **3. AI scoring** | Duplicate rows in qualified_leads | We only process `status: "filtered"`. When a lead qualifies we do `qualified_coll.replace_one({"_id": lead.id}, doc, upsert=True)` — one row per lead, updated if already present. |
| **4. Research & queue** | Running full fetch + email for leads we already queued or marked no-email | We build `already_done` from all `email_queue` (any status) and all `leads_no_email`. We only process qualified leads whose id is **not** in `already_done`. |
| **4. Add to queue** | Two email jobs for the same lead | `add_to_queue()` checks: if this `leadId` already has a job with status `pending` or `sent`, we skip and return e.g. `skipped_already_queued`. DB has a unique partial index: at most one **pending** job per `leadId`. |
| **leads_no_email** | Duplicate no-email rows | `add_lead_no_email()` uses `update_one({"_id": lead_id}, ..., upsert=True)` — one row per lead. |

**Result:** Re-running ingest, filter, AI, or email steps does not create duplicate raw_posts, qualified_leads, or email jobs; logs show what was skipped. Full detail: `docs/DEDUPLICATION.md`.

**Audit data (separate DB):** All auditing is done in a **separate MongoDB database** (`lead_gen_audit`). The **`pipeline_audit_log`** collection stores every dedup/pipeline event (scraped, skipped_already_in_raw, filtered, static_rejected, qualified, ai_rejected, queued, no_email, sent, failed) with `_schemaVersion`, `ts`, `runId`, `stage`, `action`, `leadId`, `platform`, `postId`, and optional `extra`. So even if the main `lead_discovery` data is lost, you still have a full trail. Use the same URI with DB `lead_gen_audit`, or set `MONGODB_URI_FOR_AUDIT` for a dedicated audit cluster. See `pipeline/audit_log.py`.

**Lead discovery (main DB) — systematic storage:** All data in `lead_discovery` is stored with a consistent layout: every document has `_schemaVersion` and timestamps (`createdAt`, `updatedAt` on every write). So you can rely on schema versioning and “last updated” for every collection. See `pipeline/db.py` and `pipeline/schema.py`.

---

## Getting different posts on each run

- **Keyword rotation:** Pipeline state keeps a `keyword_offset`. Each run uses a **rotated slice** of the keyword list (chunk size 12). So run 1 uses terms 0–11, run 2 uses 12–23, etc., and you see different result sets across runs.
- **Time-based cursor (Reddit):** `after_utc` is passed from the last run; only posts **newer** than that are fetched. If a run returns no new leads, the cursor is still advanced to “now” so the next run doesn’t re-fetch the same window.
- **Since date (Twitter, Instagram, Facebook, LinkedIn):** When supported, actors receive a “since” date from the last run to focus on recent content.

Together, rotation + cursor/since keep batches under ~10 minutes and reduce duplicate posts across repeated runs.

---

## Time and volume limits

- **Scrapers:** Per-actor timeout is capped at **10 minutes** (600s). Default is 600s; override with `INGEST_ACTOR_TIMEOUT_SECS` in `.env`.
- **Static filter:** At most **5000** raw posts per run (`STATIC_FILTER_MAX_PER_RUN`, default 5000) so the step finishes in reasonable time.
- **AI step:** `--ai-limit` caps how many leads are sent to the LLM per run (e.g. 50–100).

Config in `config/phase1_sources.yaml` (e.g. 120s per platform) is respected but never exceeds the 10‑minute cap.

---

## Configuration (abstract)

- **`config/phase1_sources.yaml`** — Platforms, actor folders, base input (keywords, maxResults, timeout, memory).
- **`config/search_strategy.yaml`** — Keyword themes, platform limits, Reddit subreddits, sort/time filter. Optional **`config/keywords_map.yaml`** for a large phrase set.
- **`config/static_scoring_rules.yaml`** — Minimum score to pass from static filter to AI.
- **`config/relevance_keywords.yaml`**, **`config/filters.yaml`** — Intent tiers, negative patterns, quality signals used at ingestion.

Dashboard can override keywords via MongoDB `app_config` (see API/config docs).

---

## Environment (summary)

| Purpose | Variables |
|--------|-----------|
| Scraping | `APIFY_TOKEN` (required for ingest) |
| Storage | `MONGODB_URI` (default: `mongodb://localhost:27017/`; DB: `lead_discovery`) |
| AI (Bedrock) | `AWS_BEDROCK_API` + `MODEL_ID` + `AWS_REGION` **or** `AWS2_ACCESS_KEY_ID` / `AWS2_SECRET_ACCESS_KEY` |
| Email (SES) | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `SES_FROM_EMAIL`, etc. |
| Limits | `INGEST_ACTOR_TIMEOUT_SECS` (cap 600), `STATIC_FILTER_MAX_PER_RUN` |

Copy `.env.example` to `.env` and fill in. See `pipeline/README.md` for full env and run options.

---

## How to run

**One-off full pipeline (ingest → filter → AI → queue; no send):**
```bash
python -m pipeline.run_pipeline
```

**Ingest only (e.g. Reddit):**
```bash
python -m pipeline.run_pipeline --ingest-only --platforms reddit
```

**Filter only / AI only:**  
`--filter-only` or `--ai-only`. Use `--no-email` to skip the research+queue step.

**Send queued emails (after a run):**
```bash
python -m pipeline.run_pipeline --send-only
```

**Continuous (e.g. daily) with optional send after each run:**
```bash
python run_continuous.py --interval-hours 24 --send-email
# or --no-email to only queue; send later with --send-only
```

**Dashboard:** Start API + dashboard (see `services/dashboard/README.md` and `services/DASHBOARD_README.md`). From the UI you can run pipeline jobs and view raw_posts, qualified_leads, and email queue.

**Tests (no Apify):**
```bash
python -m pipeline.tests.test_components
python -m pipeline.tests.test_components --mongo   # with MongoDB
```

Minimal Apify test (low usage): set `APIFY_MINIMAL_TEST=1` and run ingest for one platform.

---

## Production readiness & improvements

**Verdict: the software is good to use** for internal lead gen (single team, dashboard-driven runs, SES sending). Core pipeline, dedup, cursors, keyword rotation, and email queue are in place. The following are **optional** improvements, not blockers.

### In place

- Empty DB handling (indexes created on startup).
- Deduplication at every stage; `seen_post_hashes` survives raw_posts cleanup.
- Incremental fetch: Reddit `after_utc`, others `since` from last run; cursor advances even when a run returns no new leads.
- Keyword rotation so repeated runs get different posts.
- Time/volume caps: scrapers ≤10 min, static filter capped per run.
- Platform toggles, job cancel, pause/resume sending via dashboard.
- SES: app_config-driven (batch size, delay, pause), retries with backoff, auto-suppress on bounces/complaints, List-Unsubscribe.
- Optional raw_posts TTL: set `RAW_POSTS_TTL_DAYS` to auto-expire old posts.
- Pipeline tests: `pipeline/tests/test_components.py`, `test_ingestion_minimal.py`; SES test script in `scripts/test_ses_sender.py`.

### Optional improvements (not required to run)

| Area | Suggestion |
|------|------------|
| **Scheduling** | Use cron / Task Scheduler (or `run_continuous.py`) for periodic ingest; doc in WORKFLOW. |
| **CORS** | In production, set `allow_origins` in `services/api/main.py` to your dashboard origin instead of `["*"]`. |
| **Secrets** | Keep using env (or AWS Secrets Manager); ensure API keys are never logged. |
| **Monitoring** | Add CloudWatch (or similar) for SES bounce/complaint rates and queue depth; see `AWS_CHECKLIST.md`. |
| **Tests** | Add more integration tests for pipeline + API if you scale or change logic often. |

For a full production checklist (SES, SQS, Lambda, SNS, IAM), see **`AWS_CHECKLIST.md`**. For empty-DB and SES verification, see **`docs/PRODUCTION_READINESS.md`**.

---

## Where to look next

- **Pipeline detail, config, MongoDB collections:** `pipeline/README.md`
- **Deduplication and retention:** `docs/DEDUPLICATION.md`, `docs/RETENTION_AND_AVOIDING_DUPLICATE_SCRAPES.md`
- **AWS SES and production checklist:** `AWS_CHECKLIST.md`
- **Dashboard and API:** `services/dashboard/README.md`, `services/DASHBOARD_README.md`
