"""
Static filter: only leads with status=raw and staticScore >= threshold pass to AI.
Score comes from the relevance engine (run at ingestion). If missing, backfill with relevance.
We only ever process status=raw; all other statuses are skipped. Capped per run so batches finish in under ~10 min.
"""
from __future__ import annotations
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .audit_log import log_audit
from .config_loader import PROJECT_ROOT
from .models import CanonicalLead
from .relevance import compute_relevance

CONFIG_DIR = PROJECT_ROOT / "config"
RULES_PATH = CONFIG_DIR / "static_scoring_rules.yaml"
# Max raw posts to process per run so filter step finishes in reasonable time (env: STATIC_FILTER_MAX_PER_RUN)
MAX_RAW_PER_RUN = int(os.environ.get("STATIC_FILTER_MAX_PER_RUN", "5000"))
_log = logging.getLogger("pipeline.static_filter")


def _load_rules() -> dict[str, Any]:
    if not RULES_PATH.exists():
        return {"minimum_threshold": 5}
    with open(RULES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def apply_static_filter(
    mongo_db,
    min_threshold: int | None = None,
    max_per_run: int | None = None,
) -> dict[str, Any]:
    """
    Read raw_posts with status=raw. Use stored staticScore (from relevance at ingestion).
    If staticScore missing, backfill with relevance engine, then apply threshold.
    If score >= threshold -> status=filtered (for AI). Else -> status=static_rejected.
    Dedup: updates in place by _id; no new collection, no duplicate rows.
    max_per_run caps how many raw posts we process so this step finishes in <10 min with scrapers.
    Returns: processed, passed, rejected.
    """
    rules = _load_rules()
    threshold = min_threshold if min_threshold is not None else rules.get("minimum_threshold", 5)
    limit = max_per_run if max_per_run is not None else MAX_RAW_PER_RUN
    raw_posts = mongo_db.raw_posts if hasattr(mongo_db, "raw_posts") else mongo_db["raw_posts"]

    # Pre-check: only process status=raw; log what we are skipping so we never blindly filter then dedupe
    n_raw = raw_posts.count_documents({"status": "raw"})
    n_filtered = raw_posts.count_documents({"status": "filtered"})
    n_static_rejected = raw_posts.count_documents({"status": "static_rejected"})
    n_qualified = raw_posts.count_documents({"status": "qualified"})
    n_ai_rejected = raw_posts.count_documents({"status": "ai_rejected"})
    _log.info(
        "Static filter pre-check: to_process=%s (status=raw only, max_per_run=%s). Skipping: filtered=%s static_rejected=%s qualified=%s ai_rejected=%s",
        n_raw, limit, n_filtered, n_static_rejected, n_qualified, n_ai_rejected,
    )
    if n_raw == 0:
        return {"processed": 0, "passed": 0, "rejected": 0}

    cursor = raw_posts.find({"status": "raw"}).limit(limit)
    processed = passed = rejected = 0
    now = datetime.utcnow()
    for doc in cursor:
        processed += 1
        lead = CanonicalLead.from_doc(doc)
        score = doc.get("staticScore")
        if score is None:
            # Backfill: run relevance and persist
            rel = compute_relevance(
                lead.post_text,
                lead.platform,
                lead.timestamp,
                raw_item=lead.raw,
            )
            score = rel.get("score", 0)
            raw_posts.update_one(
                {"_id": lead.id},
                {
                    "$set": {
                        "staticScore": score,
                        "keywordsMatched": rel.get("matched_keywords") or [],
                        "updatedAt": now,
                    },
                },
            )
        if score >= threshold:
            raw_posts.update_one(
                {"_id": lead.id},
                {"$set": {"status": "filtered", "updatedAt": now}},
            )
            log_audit("static_filter", "filtered", lead.id, platform=lead.platform, post_id=lead.post_id)
            passed += 1
        else:
            raw_posts.update_one(
                {"_id": lead.id},
                {"$set": {"status": "static_rejected", "updatedAt": now}},
            )
            log_audit("static_filter", "static_rejected", lead.id, platform=lead.platform, post_id=lead.post_id)
            rejected += 1
    return {"processed": processed, "passed": passed, "rejected": rejected}
