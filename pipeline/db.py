"""
MongoDB collections and indexes for the lead generation pipeline (lead_discovery DB).
All pipeline data is stored systematically: _schemaVersion, createdAt, and updatedAt on every write.

Lead discovery (main DB) — systematic layout:
  raw_posts       — _id, _schemaVersion, platform, postId, postText, author, postUrl, timestamp,
                    status, staticScore, keywordsMatched, createdAt, updatedAt, (aiScore, intentLabel when set)
  qualified_leads — copy from raw_posts when AI qualifies; same shape + updatedAt on each write
  email_queue     — _schemaVersion, leadId, toEmail, subject, bodyText, bodyHtml, status, createdAt
  pipeline_state  — lastRunAt, cursors, keyword_offset, updatedAt
  seen_post_hashes, suppression_list, enriched_*, pipeline_jobs, leads_no_email — each with schema + timestamps

Audit data lives in a separate DB (lead_gen_audit); see pipeline/audit_log.py.

Optional: set RAW_POSTS_TTL_DAYS in env to auto-expire very old raw_posts.
"""
from __future__ import annotations

import os


def ensure_indexes(db) -> dict[str, list]:
    """
    Create recommended indexes on raw_posts, qualified_leads, email_queue.
    Returns dict of collection_name -> list of index names created.
    """
    created: dict[str, list] = {}
    # raw_posts
    raw = db.raw_posts if hasattr(db, "raw_posts") else db["raw_posts"]
    raw.create_index("status")
    raw.create_index("staticScore")
    ttl_days = int(os.environ.get("RAW_POSTS_TTL_DAYS", "0") or "0")
    if ttl_days > 0:
        raw.create_index("createdAt", expireAfterSeconds=ttl_days * 86400, name="createdAt_ttl")
    else:
        raw.create_index("createdAt")
    raw.create_index("platform")
    raw.create_index([("status", 1), ("staticScore", -1)])
    raw.create_index([("platform", 1), ("createdAt", -1)])
    raw.create_index([("platform", 1), ("timestamp", -1)])  # retention: bootstrap cursor (max timestamp per platform)
    created["raw_posts"] = ["status", "staticScore", "createdAt", "platform", "status_staticScore", "platform_createdAt", "platform_timestamp"]
    # qualified_leads
    qual = db.qualified_leads if hasattr(db, "qualified_leads") else db["qualified_leads"]
    qual.create_index("status")
    qual.create_index("aiScore")
    qual.create_index("createdAt")
    qual.create_index("platform")
    created["qualified_leads"] = ["status", "aiScore", "createdAt", "platform"]
    # email_queue: one pending job per lead (no duplicates when re-running filter)
    queue = db.email_queue if hasattr(db, "email_queue") else db["email_queue"]
    queue.create_index("status")
    queue.create_index("createdAt")
    queue.create_index("leadId")
    try:
        queue.create_index(
            [("leadId", 1)],
            unique=True,
            partialFilterExpression={"status": "pending"},
            name="leadId_pending_unique",
        )
    except Exception:
        pass  # index may already exist or server doesn't support partialFilterExpression
    created["email_queue"] = ["status", "createdAt", "leadId", "leadId_pending_unique"]
    # suppression_list (bounce/complaint/unsubscribe)
    from .suppression import ensure_indexes as suppression_indexes
    suppression_indexes(db)
    created["suppression_list"] = ["leadId", "email", "createdAt"]
    # enriched_profiles (profile scrape cache for email personalization)
    if hasattr(db, "enriched_profiles"):
        ep = db.enriched_profiles
    else:
        ep = db["enriched_profiles"]
    ep.create_index("enrichedAt")
    created["enriched_profiles"] = ["enrichedAt"]
    # enriched_posts (full post fetch cache for email personalization)
    epo = db.enriched_posts if hasattr(db, "enriched_posts") else db["enriched_posts"]
    epo.create_index("fetchedAt")
    created["enriched_posts"] = ["fetchedAt"]
    # seen_post_hashes: permanent record of fetched post IDs (hash = SHA256(platform+post_id))
    # Kept even when raw_posts are deleted (retention); prevents re-fetching the same posts.
    seen = db.seen_post_hashes if hasattr(db, "seen_post_hashes") else db["seen_post_hashes"]
    seen.create_index("firstSeenAt")
    created["seen_post_hashes"] = ["firstSeenAt"]
    # pipeline_jobs (dashboard job runner)
    pj = db.pipeline_jobs if hasattr(db, "pipeline_jobs") else db["pipeline_jobs"]
    pj.create_index("createdAt")
    pj.create_index([("jobType", 1), ("status", 1)])
    created["pipeline_jobs"] = ["createdAt", "jobType_status"]
    # leads_no_email (manual outreach when email not found)
    lne = db.leads_no_email if hasattr(db, "leads_no_email") else db["leads_no_email"]
    lne.create_index("messageSent")
    lne.create_index("createdAt")
    created["leads_no_email"] = ["messageSent", "createdAt"]
    return created
