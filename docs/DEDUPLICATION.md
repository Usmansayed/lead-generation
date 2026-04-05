# Pipeline deduplication at every stage

The pipeline avoids duplicate **raw posts**, **qualified leads**, and **emails** at each phase so that re-running ingest, filter, AI, or email steps does not create duplicates or send the same email twice.

**Approach: check first, then do.** We do not blindly process then filter out duplicates. At each stage we:

1. **Pre-check** — Count what needs work vs what is already done (e.g. only `status=raw` for static filter, only leads not in `email_queue`/`leads_no_email` for Step 4).
2. **Log** — Emit structured logs (e.g. `to_process`, `skipping`, `already_in_raw`) so you can see exactly what is being skipped and why.
3. **Process only what’s needed** — Query only the subset that needs processing (e.g. `find({"status": "raw"})`), so we never re-filter the same raw leads or re-score the same filtered leads.

---

## 1. Ingest (raw posts)

| Where | How |
|-------|-----|
| **Pre-check + log** | After fetch, we log `fetched`, `already_in_raw` (skipped), `to_process`. Only items not already in `raw_posts` are normalized and stored. |
| **Before store** | `_filter_already_in_raw()` in `pipeline/ingestion.py`: items whose `_id` (hash of platform + post_id) already exist in `raw_posts` are skipped before normalization. |
| **On store** | `store_raw_posts(..., dedupe=True)`: each lead is written with `replace_one({"_id": hash_id}, doc, upsert=True)`. Same lead = update one row, never a second row. |
| **Tracking** | `seen_post_hashes` is updated with the same `_id` for retention; it does not block re-fetch if `raw_posts` was cleared. |

**Result:** Re-running ingest does not create duplicate raw_posts; re-fetching the same post only updates the existing document.

---

## 2. Static filter

| Where | How |
|-------|-----|
| **Pre-check + log** | We count and log `to_process` (status=raw only), and `filtered`, `static_rejected`, `qualified`, `ai_rejected` (skipped). We never re-filter the same raw leads. |
| **Processing** | We query only `raw_posts.find({"status": "raw"})` and update each document in place (`status` → `filtered` or `static_rejected`). No new collection; no duplicate rows. |

**Result:** Re-running the static filter only processes leads that are still `raw`; already filtered/rejected are skipped and visible in logs.

---

## 3. AI scoring → qualified leads

| Where | How |
|-------|-----|
| **Pre-check + log** | We count and log `to_process` (status=filtered only), and `already qualified`, `already ai_rejected` (skipped). We never re-score the same filtered leads. |
| **Processing** | We query only `raw_posts.find({"status": "filtered"})`. |
| **Qualified leads** | In `pipeline/ai_scoring.py`, when a lead qualifies we do `qualified_coll.replace_one({"_id": lead.id}, doc_copy, upsert=True)`. Same lead_id = one row in `qualified_leads`, updated if already present. |

**Result:** Re-running AI scoring only processes leads that are still `filtered`; already qualified/rejected are skipped and visible in logs.

---

## 4. Email queue and sending (no duplicate emails)

| Where | How |
|-------|-----|
| **Pre-check + log** | In `run_pipeline.py` we log `qualified total`, `already_in_queue`, `already_no_email`, `skipping`, `to_process`. Only qualified leads not in `email_queue` or `leads_no_email` are processed. |
| **Step 4 (who gets processed)** | We build `already_done = already_queued | already_no_email` from **all** documents in `email_queue` (any status) and all `leads_no_email`. We never run full fetch + research + email for leads already in queue or no_email. |
| **Adding to queue** | `add_to_queue()` checks before inserting: if this `leadId` already has a job with `status` in `["pending", "sent"]`, we skip and log `skipped_already_queued` or `skipped_already_sent`. Returns `(success, action)` so callers can log; we never blindly add then dedupe. |
| **DB safeguard** | Unique partial index on `email_queue`: `(leadId, 1)` with `partialFilterExpression: { status: "pending" }` so at most one **pending** job per lead. |

**Result:** Re-running the pipeline does not create a second email for the same lead; logs show exactly what was skipped and why.

---

## 5. leads_no_email

| Where | How |
|-------|-----|
| **Upsert** | `add_lead_no_email()` uses `update_one({"_id": lead_id}, ..., upsert=True)`. One row per lead_id. |

**Result:** No duplicate rows in `leads_no_email`.

---

## Summary

| Stage | Collection / concept | Dedup mechanism |
|-------|------------------------|-----------------|
| Ingest | raw_posts | Pre-filter by existing _id; store with replace_one upsert |
| Static filter | raw_posts | In-place status updates only |
| AI scoring | qualified_leads | replace_one by _id (upsert) |
| Step 4 (who to process) | — | Skip qualified leads already in email_queue or leads_no_email |
| Add to email queue | email_queue | Skip if leadId already has pending or sent job |
| leads_no_email | leads_no_email | Upsert by _id |

All entry points that add to the email queue go through `add_to_queue()` (including `enqueue_lead_for_email`), so the same “no duplicate emails per lead” rule applies everywhere.
