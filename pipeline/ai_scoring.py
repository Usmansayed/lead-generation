"""
AI intent scoring: call LLM with post content only, in batches, for speed.
Only leads above AI threshold move to qualified_leads.
"""
from __future__ import annotations
import json
import logging
import os
from typing import Any

from .audit_log import log_audit
from .config_loader import load_keywords_master, PROJECT_ROOT
from .models import CanonicalLead

CONFIG_DIR = PROJECT_ROOT / "config"
# Max chars of post content per lead in batch (keep prompts small and fast)
POST_CONTENT_MAX_CHARS = 600
# Batch size for one LLM call (more = faster, but larger context)
AI_SCORE_BATCH_SIZE = 8


def _load_prompts() -> dict[str, Any]:
    p = CONFIG_DIR / "prompts.yaml"
    if not p.exists():
        return {}
    import yaml
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _post_content_only(lead: CanonicalLead, max_chars: int = POST_CONTENT_MAX_CHARS) -> str:
    """Return only the main post content, truncated."""
    text = (lead.post_text or "").strip()
    if not text:
        return ""
    if len(text) > max_chars:
        text = text[: max_chars] + "..."
    return text


def _build_analysis_prompt(lead: CanonicalLead, keywords_master: dict) -> str:
    """Single-lead prompt (fallback). Uses post content only for consistency."""
    body = _post_content_only(lead, max_chars=800)
    return (
        "Analyze this post for commercial intent (software/services need).\n\n"
        "POST:\n" + body + "\n\n"
        "Return JSON only: {\"intentScore\": 0-100, \"confidence\": \"low\"|\"medium\"|\"high\", "
        "\"intentType\": \"software_need\"|\"business_launch\"|\"hiring_signal\"|\"problem_signal\"|\"other\"}"
    )


def _build_batch_prompt(leads: list[CanonicalLead]) -> str:
    """One prompt with only post content for N leads, numbered. Ask for JSON array."""
    n = len(leads)
    parts = []
    for i, lead in enumerate(leads, 1):
        content = _post_content_only(lead)
        parts.append(f"[{i}]\n{content}")
    posts_block = "\n\n".join(parts)
    return (
        "Analyze each of the following posts for commercial intent (software/services need). "
        "Return a JSON array of exactly " + str(n) + " objects in order. "
        "Each object: {\"intentScore\": 0-100, \"confidence\": \"low\"|\"medium\"|\"high\", "
        "\"intentType\": \"software_need\"|\"business_launch\"|\"hiring_signal\"|\"problem_signal\"|\"other\"}. "
        "Post content only (no author/platform).\n\n" + posts_block + "\n\nJSON array:"
    )


def _parse_json_from_response(text: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response (handle markdown code blocks)."""
    if not text:
        return None
    text = text.strip()
    if "```" in text:
        start = text.find("```")
        if "json" in text[: start + 10].lower():
            start = text.find("\n", start) + 1
        end = text.find("```", start)
        if end == -1:
            end = len(text)
        text = text[start:end]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _parse_batch_response(text: str, expected_len: int) -> list[dict[str, Any]]:
    """Parse LLM response as JSON array; return list of dicts (or empty if parse/count wrong)."""
    raw = _parse_json_from_response(text)
    if raw is None:
        return []
    if isinstance(raw, list) and len(raw) == expected_len:
        return [x if isinstance(x, dict) else {} for x in raw]
    if isinstance(raw, dict) and expected_len == 1:
        return [raw]
    return []


def call_llm_for_intent(prompt: str, api_key: str | None = None) -> dict[str, Any] | None:
    """Call LLM (OpenAI or Google with key rotation) for intent analysis. Returns parsed JSON."""
    from .llm_client import call_llm, has_llm_config
    if not has_llm_config():
        return None
    text = call_llm(prompt, temperature=0.2, api_key=api_key)
    return _parse_json_from_response(text) if text else None


def score_lead(lead: CanonicalLead, keywords_master: dict, api_key: str | None = None) -> dict[str, Any] | None:
    """Run AI intent scoring for one lead (fallback when batch fails). Returns {intentScore, confidence, intentType} or None."""
    prompt = _build_analysis_prompt(lead, keywords_master)
    return call_llm_for_intent(prompt, api_key)


def _score_batch(leads: list[CanonicalLead], api_key: str | None = None) -> list[dict[str, Any] | None]:
    """Score multiple leads in one LLM call (post content only). Returns list of result dicts or None per lead."""
    from .llm_client import call_llm, has_llm_config
    if not has_llm_config() or not leads:
        return [None] * len(leads)
    prompt = _build_batch_prompt(leads)
    text = call_llm(prompt, temperature=0.2, api_key=api_key)
    results = _parse_batch_response(text or "", len(leads))
    if len(results) != len(leads):
        log = logging.getLogger("pipeline")
        log.warning("AI batch returned %s results for %s leads, falling back to single calls", len(results), len(leads))
        return [score_lead(lead, {}, api_key) for lead in leads]
    return results


# Default threshold for qualifying (only above this go to email stage)
AI_SCORE_THRESHOLD = 60


def _apply_result_to_lead(
    raw_posts, qualified_coll, lead: CanonicalLead, result: dict[str, Any], thresh: float
) -> tuple[bool, bool]:
    """Update raw_posts and optionally qualified_leads. Returns (qualified, not_qualified)."""
    from datetime import datetime
    now = datetime.utcnow()
    intent_score = result.get("intentScore") or result.get("intent_score", 0)
    confidence = result.get("confidence", "low")
    intent_type = result.get("intentType") or result.get("intent_type", "other")
    raw_posts.update_one(
        {"_id": lead.id},
        {"$set": {"aiScore": intent_score, "intentLabel": intent_type, "confidence": confidence, "updatedAt": now}},
    )
    if intent_score >= thresh:
        raw_posts.update_one({"_id": lead.id}, {"$set": {"status": "qualified", "updatedAt": now}})
        doc_copy = raw_posts.find_one({"_id": lead.id})
        if doc_copy:
            doc_copy["updatedAt"] = now  # systematic: every write has updatedAt
            # Dedup: upsert by _id so re-running filter/AI never creates duplicate qualified_leads
            qualified_coll.replace_one({"_id": lead.id}, doc_copy, upsert=True)
        log_audit("ai_scoring", "qualified", lead.id, platform=lead.platform, post_id=lead.post_id)
        return (True, False)
    raw_posts.update_one({"_id": lead.id}, {"$set": {"status": "ai_rejected", "updatedAt": now}})
    log_audit("ai_scoring", "ai_rejected", lead.id, platform=lead.platform, post_id=lead.post_id)
    return (False, True)


def apply_ai_scoring(
    mongo_db,
    keywords_master: dict | None = None,
    api_key: str | None = None,
    threshold: float | None = None,
    limit: int = 50,
    batch_size: int | None = None,
) -> dict[str, Any]:
    """
    Read raw_posts with status=filtered, run AI scoring in batches (post content only), update status.
    If intentScore >= threshold, set status=qualified and copy to qualified_leads.
    Returns: processed, qualified, not_qualified.
    """
    import logging
    _log = logging.getLogger("pipeline.ai_scoring")
    km = keywords_master or load_keywords_master()
    raw_posts = mongo_db.raw_posts if hasattr(mongo_db, "raw_posts") else mongo_db["raw_posts"]
    qualified_coll = mongo_db.qualified_leads if hasattr(mongo_db, "qualified_leads") else mongo_db["qualified_leads"]
    thresh = threshold if threshold is not None else AI_SCORE_THRESHOLD
    batch = batch_size if batch_size is not None else AI_SCORE_BATCH_SIZE

    # Pre-check: only process status=filtered; log what we are skipping (never re-score qualified/ai_rejected)
    n_filtered = raw_posts.count_documents({"status": "filtered"})
    n_qualified = raw_posts.count_documents({"status": "qualified"})
    n_ai_rejected = raw_posts.count_documents({"status": "ai_rejected"})
    _log.info(
        "AI scoring pre-check: to_process=%s (status=filtered only). Skipping: already qualified=%s already ai_rejected=%s",
        min(n_filtered, limit), n_qualified, n_ai_rejected,
    )
    if n_filtered == 0:
        return {"processed": 0, "qualified": 0, "not_qualified": 0}

    cursor = list(raw_posts.find({"status": "filtered"}).limit(limit))
    processed = qualified = not_qualified = 0
    for i in range(0, len(cursor), batch):
        chunk = cursor[i : i + batch]
        leads = [CanonicalLead.from_doc(doc) for doc in chunk]
        results = _score_batch(leads, api_key)
        for lead, result in zip(leads, results):
            processed += 1
            if not result:
                continue
            q, nq = _apply_result_to_lead(raw_posts, qualified_coll, lead, result, thresh)
            if q:
                qualified += 1
            elif nq:
                not_qualified += 1
    return {"processed": processed, "qualified": qualified, "not_qualified": not_qualified}
