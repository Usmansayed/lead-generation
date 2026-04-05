# Lead Generation Pipeline (Phase 1)

Orchestrates **5 platforms only**: LinkedIn, Twitter/X, Instagram, Facebook, Reddit.

## Architecture

1. **Ingestion** — Run Apify actors, normalize to canonical schema, run **relevance engine** (keyword + quality scoring), deduplicate, store in `raw_posts` with `staticScore` and `keywordsMatched`. Rejected by relevance get `status: "rejected"`.
2. **Static filter** — For `status: raw`, if `staticScore >= threshold` → `status: "filtered"` (for AI). Else → `static_rejected`.
3. **AI scoring** — LLM scores filtered leads; above threshold → `status: "qualified"`, copied to `qualified_leads`.
4. **Email** — For each qualified lead we run the **after-filter flow** (below), then AI generates subject + body; jobs added to `email_queue` (SES worker or Lambda consumes).

**Deduplication** at every stage (no duplicate raw posts, qualified leads, or emails when re-running): see `docs/DEDUPLICATION.md`.

### After-filter flow (post → best email)

For each qualified lead we gather maximum context, then send it all to the LLM:

1. **Fetch post** — Full content of the lead’s post (Apify post-content-fetcher); cached in `enriched_posts`.
2. **Fetch profile** — Profile page content (same actor on profile URL); cached in `enriched_profiles`.
3. **Web research** — Optional: light web search (Tavily; set `TAVILY_API_KEY`) for extra context on the person/business.
4. **Business research** — Rule-based: business type, size, has_website, suggested_offers, should_skip.
5. **Contact discovery** — Email from post/profile, or fallback to profile/post URL.
6. **LLM** — Receives: post text + profile text + web context (if any) + business research + suggested offers → one personalized email.

## Relevance & keyword matching (best posts = highest potential customers)

- **Phrase-first:** Full phrases (e.g. "looking for developer") with synonym expansion (e.g. "dev", "engineer").
- **Intent tiers:** High (5 pts) / medium (3 pts) / soft (1 pt). See `config/relevance_keywords.yaml`.
- **Negative gate:** Learning, hobby, job-seeking, open-source, low-quality → reject (`config/filters.yaml`).
- **Quality bonuses:** Contact (email/DM), budget, urgency, decision-maker language, recency, engagement, platform weight.

Only high-signal posts reach AI and email.

## Config

- `config/relevance_keywords.yaml` — Intent tiers, synonyms, quality signals, minimum gate (main relevance config).
- `config/filters.yaml` — Negative patterns, minimum word count.
- `config/keywords_master.json` — Legacy intent categories (optional).
- `config/phase1_sources.yaml` — Actor folder names, run input (keywords, maxResults, delays), and optional `timeout_secs` / `memory_mbytes` per platform. All 5 platforms use the same volume (e.g. maxResults/maxPosts 80) and efficient delays so Instagram, Twitter, LinkedIn, Facebook run at similar rate to Reddit.
- `config/search_strategy.yaml` — Keywords, subreddits, limits (max_search_terms_per_platform, reddit_sort, reddit_time_filter).
- `config/static_scoring_rules.yaml` — Minimum threshold to pass to AI (e.g. 5).

## Env

- `APIFY_TOKEN` — Required for ingestion.
- `MONGODB_URI` — Optional; default `mongodb://localhost:27017/` with DB `lead_discovery`.
- **Bedrock LLM** (required for AI scoring and email): use **either** `AWS_BEDROCK_API` (single Bedrock API key; set `MODEL_ID` e.g. `amazon.nova-pro-v1:0` and `AWS_REGION`) **or** IAM: `AWS2_ACCESS_KEY_ID` + `AWS2_SECRET_ACCESS_KEY` (or `CLAUDE_*` / `AWS_*`).
- `TAVILY_API_KEY` — Optional; when set, web research uses Tavily. Otherwise we use **DuckDuckGo (free, no API key)** via the `duckduckgo-search` package.
- `INGEST_DELAY_SECONDS` — Optional; seconds between starting each platform actor (default 1). Set to 0 for fastest back-to-back runs.
- `INGEST_ACTOR_TIMEOUT_SECS` / `INGEST_ACTOR_MEMORY_MB` — Optional overrides for all platforms; per-platform values in `phase1_sources.yaml` take precedence.

## Run

```bash
cd c:\Users\usman\Music\lead-generation
pip install -r pipeline/requirements.txt
# Optional: python-dotenv and .env with APIFY_TOKEN, AWS_BEDROCK_API or AWS2_* (or CLAUDE_*) for Bedrock, MONGODB_URI

# Full pipeline
python -m pipeline.run_pipeline

# Only ingestion (e.g. Reddit only to test)
python -m pipeline.run_pipeline --ingest-only --platforms reddit

# Only static filter (no API calls)
python -m pipeline.run_pipeline --filter-only

# AI scoring only (needs AWS_BEDROCK_API or AWS2_* / CLAUDE_* for Bedrock)
python -m pipeline.run_pipeline --ai-only

# Skip email step
python -m pipeline.run_pipeline --no-email
```

## MongoDB: main DB (lead_discovery) and audit DB (lead_gen_audit)

- **Main data** lives in the database named in `MONGODB_URI` (default DB: `lead_discovery` when URI has no path). Collections: `raw_posts`, `qualified_leads`, `email_queue`, `pipeline_state`, etc.
- **Audit log** lives in a **separate database** (`lead_gen_audit` by default, or the DB in `MONGODB_URI_FOR_AUDIT` if set). Collection `pipeline_audit_log` stores one document per event: scraped, skipped_already_in_raw, filtered, static_rejected, qualified, ai_rejected, queued, no_email, sent, failed. So logs survive even if main data is lost. See `pipeline/audit_log.py`.

## MongoDB collections (main DB)

- `raw_posts` — Canonical leads from all platforms; `status`: raw | filtered | qualified | rejected | ai_rejected.
- `qualified_leads` — Copy of qualified leads for email stage.
- `email_queue` — Pending/sent/failed email jobs (for SES worker).

## AWS (do in console at the end)

See **`AWS_CHECKLIST.md`** in the project root: SES (verify domain, DKIM/SPF/DMARC, warm-up), SQS queue, Lambda (SES sender), SNS (bounce/complaint), CloudWatch alarms.

A minimal Lambda sender is in **`workers/lambda_ses_sender/`** — zip and upload; set env `SES_FROM_EMAIL`, `SES_REGION`; attach SQS trigger and SES + SQS permissions.
