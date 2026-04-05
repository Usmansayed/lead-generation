# Production Readiness Checklist

This document summarizes the current state of the lead generation pipeline and dashboard for production use, especially when starting with an **empty database**.

---

## Empty DB / First Run

When you delete the DB and start fresh:

1. **API startup** – On startup, the API calls `ensure_indexes(db)` to create all required indexes on empty collections. Collections are created implicitly on first write.

2. **Collections used** (all created on first write):
   - `raw_posts` – scraped leads
   - `qualified_leads` – AI-qualified leads
   - `email_queue` – pending/sent/failed emails
   - `suppression_list` – bounced/unsubscribed
   - `seen_post_hashes` – permanent dedup (survives raw_posts retention)
   - `pipeline_state` – cursors, last run time
   - `pipeline_jobs` – job history (dashboard)
   - `app_config` – sending_paused, default_platforms, etc.
   - `enriched_profiles`, `enriched_posts` – caches for email personalization

3. **First run flow**:
   - Dashboard → Pipeline → Run "Scrape posts" → job creates `pipeline_jobs` doc, runs `run_pipeline --ingest-only`
   - Pipeline calls `ensure_indexes` again (idempotent)
   - Ingestion: no cursors/state → fetches full time window (e.g. Reddit "day")
   - `store_raw_posts` writes to `raw_posts` and `seen_post_hashes`

---

## Environment Variables

| Variable | Required for | Description |
|----------|--------------|-------------|
| `MONGODB_URI` | API, Pipeline | e.g. `mongodb://localhost:27017/lead_discovery` |
| `APIFY_TOKEN` | Ingest (Scrape) | Apify API key for actors |
| `AWS2_*` or `CLAUDE_*` (Bedrock) | AI scoring | Nova Lite for intent scoring |
| `AWS_ACCESS_KEY_ID` | Send emails | IAM user access key (SES permissions) |
| `AWS_SECRET_ACCESS_KEY` | Send emails | IAM user secret key |
| `AWS_REGION` | Send emails | SES region (e.g. us-east-1) |
| `SES_FROM_EMAIL` | Send emails | Verified sender address in SES |
| `SES_DAILY_CAP` | Send emails | Max emails per day (default: 100) |
| `SES_REPLY_TO_EMAIL` | Send emails | Optional Reply-To header |
| `AWS_SES_ENDPOINT_URL` | Optional | Only for LocalStack; leave unset for real AWS |

Set in `.env` at project root.

---

## Production Considerations

### Done
- [x] Empty DB handling – API creates indexes on startup
- [x] Deduplication – `seen_post_hashes` persists across raw_posts retention
- [x] Cursors – Reddit `after_utc`, others `since` from last run
- [x] Platform toggles – Settings → Scraping platforms
- [x] Job cancel – Kill running subprocess
- [x] Pause/resume – app_config.sending_paused
- [x] Suppression list – avoid bounced/complained

### SES Email Sender
- [x] **SES sender reads app_config** – `sending_paused`, `send_delay_ms`, `send_batch_size` from dashboard
- [x] **Reply-To, Message-ID, X-Mailer** – Production headers for deliverability
- [x] **Exponential backoff** – Retries on transient SES errors (throttle, timeout)
- [x] **Auto-suppress** – Adds permanent bounces/complaints to suppression list
- [x] **Test script** – `python scripts/test_ses_sender.py --dry-run` or `--send-one you@example.com`

### Optional improvements
- [ ] **Scheduled runs** – cron or Task Scheduler for periodic ingest
- [ ] **Retention policy** – TTL or manual cleanup of old `raw_posts`
- [ ] **CORS** – tighten `allow_origins` in production
- [ ] **Secrets** – never log API keys; use env only

---

## Quick Start (Fresh DB)

```bash
# 1. Set .env (MONGODB_URI, APIFY_TOKEN, etc.)
# 2. Start API + dashboard
python start_all.py

# 3. Open http://localhost:3000 (or port shown)
# 4. Dashboard → Settings → enable desired platforms
# 5. Pipeline → Run "Scrape posts"
# 6. Run Static filter, AI scoring, Research & queue, Send emails in order
```

---

## Verifying

- **Health**: `GET /api/health` → `{"ok": true}` when MongoDB connected
- **Stats**: `GET /api/stats` → all zeros for empty DB
- **Config**: `GET /api/config` → `{sending_paused: null, ...}` for fresh config

### SES Sender Testing

```bash
# Dry run: validate env, show pending count (no send)
python scripts/test_ses_sender.py --dry-run

# Send one test email (requires verified SES_FROM_EMAIL; in SES sandbox, TO must be verified)
python scripts/test_ses_sender.py --send-one you@example.com
```
