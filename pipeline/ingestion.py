"""
Ingestion: run Phase 1 Apify actors, fetch dataset items, normalize to canonical schema,
deduplicate, and store in MongoDB raw_posts.
"""
from __future__ import annotations
import os
import time
from datetime import datetime
from typing import Any

from apify_client import ApifyClient

from .config_loader import load_phase1_sources, get_platform_actor_config
from .models import CanonicalLead
from .normalizers import normalize_item, get_hash_id_for_item
from .relevance import compute_relevance
from .search_builder import build_run_input, SEARCH_STRATEGY_PATH, KEYWORD_ROTATION_CHUNK
from .state import (
    get_pipeline_state,
    save_pipeline_state,
    get_cursor_from_raw_posts,
    merge_cursor_into_run_input,
    merge_since_date_into_run_input,
)
from .apify_cache import get_cached, set_cached
from .audit_log import log_audit
from .keywords_config import get_keywords_override, merge_keywords_override
from .logger import get_logger, log_info as _log_info


def _llm_relevance_override(post_text: str) -> bool:
    """
    Optional: use a small LLM to give a second chance to posts that failed the intent gate only.
    Set USE_LLM_RELEVANCE_OVERRIDE=1 in .env to enable. Uses AWS2 Bedrock Nova Lite (same as other LLM steps).
    """
    if not post_text or len(post_text.strip()) < 20:
        return False
    if os.environ.get("USE_LLM_RELEVANCE_OVERRIDE", "").strip().lower() not in ("1", "true", "yes"):
        return False
    try:
        from .llm_client import call_llm, has_llm_config
        if not has_llm_config():
            return False
        snippet = (post_text.strip()[:600] + "…") if len(post_text) > 600 else post_text.strip()
        prompt = (
            "Is this post from someone who recently started a business or might need "
            "software, website, agency, or developer help? Reply YES or NO only.\n\nPost:\n\"\"\"%s\"\"\""
        ) % snippet
        out = call_llm(prompt, temperature=0.1)
        return out is not None and "yes" in out.lower()
    except Exception:
        return False


def _resolve_actor_id(client: ApifyClient, folder_name: str) -> str | None:
    """Resolve actor folder name to full actor ID (username/name)."""
    actors = client.actors().list().items
    for actor in actors:
        if actor.get("name") == folder_name:
            return actor["id"]
    return None


def run_actor_and_fetch(
    client: ApifyClient,
    actor_id: str,
    run_input: dict[str, Any],
    timeout_secs: int = 300,
    memory_mbytes: int = 1024,
) -> tuple[str, list[dict]]:
    """Run actor by ID, wait for completion, return (run_id, dataset_items). Uses Redis cache if REDIS_URL set."""
    cached = get_cached(actor_id, run_input)
    if cached is not None:
        return ("cached", cached)
    run = client.actor(actor_id).call(
        run_input=run_input,
        timeout_secs=timeout_secs,
        memory_mbytes=memory_mbytes,
    )
    run_id = run.get("id", "")
    status = run.get("status", "UNKNOWN")
    if status != "SUCCEEDED":
        return run_id, []
    dataset_id = run.get("defaultDatasetId", "")
    if not dataset_id:
        return run_id, []
    items = list(client.dataset(dataset_id).iterate_items())
    set_cached(actor_id, run_input, items)
    return run_id, items


def _filter_already_in_raw(
    items: list[dict],
    platform: str,
    mongo_db,
    skipped_callback=None,
) -> list[dict]:
    """
    Dedup (stage 1): skip items we already have in raw_posts so we don't re-process.
    We do NOT filter by seen_post_hashes here, so if raw_posts was cleared or is empty,
    we still process and store everything we fetch (no wasted Apify credits).
    If skipped_callback(lead_id, platform, post_id) is given, call it for each skipped item (for audit log).
    """
    if mongo_db is None or not items:
        return items
    raw_coll = mongo_db.raw_posts if hasattr(mongo_db, "raw_posts") else mongo_db["raw_posts"]
    pairs: list[tuple[str, dict]] = []
    for item in items:
        h = get_hash_id_for_item(platform, item)
        if h:
            pairs.append((h, item))
    if not pairs:
        return items
    unique_hashes = list({h for h, _ in pairs})
    already_in_raw = {doc["_id"] for doc in raw_coll.find({"_id": {"$in": unique_hashes}}, {"_id": 1})}
    for h, item in pairs:
        if h in already_in_raw and skipped_callback:
            post_id = (item.get("id") or item.get("url") or "")[:120]
            skipped_callback(h, platform, post_id)
    return [item for h, item in pairs if h not in already_in_raw]


def ingest_platform(
    client: ApifyClient,
    platform: str,
    actor_id: str,
    run_input: dict[str, Any],
    run_relevance: bool = True,
    mongo_db=None,
    timeout_secs: int = 300,
    memory_mbytes: int = 1024,
) -> tuple[int, list[CanonicalLead]]:
    """Run one platform's actor, normalize, run relevance engine, return (count, canonical_leads)."""
    _log = get_logger("pipeline")
    run_id, items = run_actor_and_fetch(
        client, actor_id, run_input,
        timeout_secs=timeout_secs,
        memory_mbytes=memory_mbytes,
    )
    fetched_count = len(items)

    def _on_skipped(lead_id: str, plat: str, post_id: str) -> None:
        log_audit("ingest", "skipped_already_in_raw", lead_id, platform=plat, post_id=post_id or None)

    items = _filter_already_in_raw(items, platform, mongo_db, skipped_callback=_on_skipped)
    after_dedup = len(items)
    skipped = fetched_count - after_dedup
    _log_info(_log, "Ingest pre-check: fetched, already_in_raw_posts (skipping), to_process", platform=platform, fetched=fetched_count, already_in_raw=skipped, to_process=after_dedup)
    leads: list[CanonicalLead] = []
    for item in items:
        lead = normalize_item(platform, item)
        if not lead:
            continue
        if run_relevance:
            rel = compute_relevance(
                lead.post_text,
                platform,
                lead.timestamp,
                raw_item=lead.raw or item,
            )
            # Only reject on clear junk (negative pattern / too short). Never reject on weak intent.
            if not rel.get("passed") and rel.get("reject_reason") == "intent_gate_failed":
                rel = {**rel, "passed": True, "reject_reason": None, "score": max(3, rel.get("score", 0))}
            # Optional: LLM second chance for any other borderline case (e.g. strict negative phrase)
            elif not rel.get("passed") and os.environ.get("USE_LLM_RELEVANCE_OVERRIDE", "").strip().lower() in ("1", "true", "yes"):
                if _llm_relevance_override(lead.post_text or ""):
                    rel = {**rel, "passed": True, "reject_reason": None, "score": max(3, rel.get("score", 0))}
            lead.static_score = rel.get("score", 0)
            lead.keywords_matched = rel.get("matched_keywords") or []
            if rel.get("passed"):
                lead.status = "raw"
                lead.reject_reason = None
            else:
                lead.status = "rejected"
                lead.reject_reason = rel.get("reject_reason") or "relevance_failed"
        leads.append(lead)
    return len(items), leads


def store_raw_posts(mongo_db, leads: list[CanonicalLead], dedupe: bool = True) -> int:
    """
    Dedup (stage 1): insert leads into raw_posts. If dedupe, use replace_one with upsert (idempotent by _id).
    Also writes hash to seen_post_hashes. Same lead_id = update, never duplicate rows.
    """
    _slog = get_logger("pipeline")
    _log_info(_slog, "DEBUG store_raw_posts called", leads_count=len(leads), mongo_db_is_none=(mongo_db is None), dedupe=dedupe)
    if mongo_db is None:
        _log_info(_slog, "DEBUG store_raw_posts returning 0 (no mongo_db)")
        return 0
    raw = mongo_db.raw_posts if hasattr(mongo_db, "raw_posts") else mongo_db["raw_posts"]
    seen = mongo_db.seen_post_hashes if hasattr(mongo_db, "seen_post_hashes") else mongo_db["seen_post_hashes"]
    inserted = 0
    now = datetime.utcnow()
    for lead in leads:
        doc = lead.to_doc()
        doc["updatedAt"] = now  # systematic: every write has updatedAt
        hash_id = doc["_id"]
        try:
            if dedupe:
                raw.replace_one({"_id": hash_id}, doc, upsert=True)
            else:
                raw.insert_one(doc)
            seen.replace_one(
                {"_id": hash_id},
                {"_id": hash_id, "firstSeenAt": now, "platform": lead.platform},
                upsert=True,
            )
            log_audit("ingest", "scraped", hash_id, platform=lead.platform or None, post_id=lead.post_id or None)
            inserted += 1
        except Exception:
            if not dedupe:
                pass
            else:
                raise
    _log_info(_slog, "DEBUG store_raw_posts done", inserted=inserted)
    return inserted


def run_ingestion(
    mongo_db=None,
    apify_token: str | None = None,
    apify_username: str | None = None,
    platforms: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run all Phase 1 actors (or given platforms), normalize, dedupe, store in MongoDB.
    Uses env APIFY_TOKEN if apify_token not provided.
    """
    _log = get_logger("pipeline")
    _log_info(_log, "DEBUG run_ingestion called", mongo_db_is_none=(mongo_db is None))
    token = apify_token or os.environ.get("APIFY_TOKEN")
    if not token:
        _log_info(_log, "DEBUG run_ingestion early exit: APIFY_TOKEN not set")
        return {"ok": False, "error": "APIFY_TOKEN not set", "results": {}}
    if mongo_db is None:
        _log_info(_log, "DEBUG run_ingestion early exit: MongoDB not connected")
        return {"ok": False, "error": "MongoDB not connected. Set MONGODB_URI in .env and ensure MongoDB is running.", "results": {}}

    sources = load_phase1_sources()
    actor_configs = sources.get("actors") or {}
    # None = run all platforms; [] = run none (user turned all off in dashboard)
    platforms_to_run = list(actor_configs.keys()) if platforms is None else platforms
    client = ApifyClient(token)

    # Optional: incremental cursor so next run can fetch only posts after this time
    state = get_pipeline_state(mongo_db)
    cursors = (state.get("cursors") or {}).copy()
    # Bootstrap cursor from raw_posts when state has none (e.g. first run after DB restore) — retention
    for platform in platforms_to_run if platforms_to_run else []:
        if cursors.get(platform) is None and mongo_db is not None:
            boot = get_cursor_from_raw_posts(mongo_db, platform)
            if boot is not None:
                cursors[platform] = boot
                _log_info(_log, "DEBUG retention: bootstrapped cursor from raw_posts", platform=platform, after_utc=boot)

    results: dict[str, Any] = {}
    all_leads: list[CanonicalLead] = []
    final_cursors = dict(state.get("cursors") or {})
    keyword_offset = state.get("keyword_offset") or 0
    total_keywords_for_rotation: int | None = None
    # Persist bootstrapped cursors so next run has them even if this run returns no new leads
    for platform, val in cursors.items():
        if val is not None and final_cursors.get(platform) is None:
            final_cursors[platform] = val
    delay_between_actors = max(0, int(os.environ.get("INGEST_DELAY_SECONDS", "1")))
    retry_failed_once = os.environ.get("INGEST_RETRY_FAILED", "1").strip().lower() in ("1", "true", "yes")

    for platform in platforms_to_run:
        cfg = get_platform_actor_config(sources, platform)
        if not cfg:
            results[platform] = {"skipped": True, "reason": "no_config"}
            continue
        folder = cfg.get("folder") or f"{platform}-lead-scraper"
        actor_id = _resolve_actor_id(client, folder)
        if not actor_id:
            results[platform] = {"skipped": True, "reason": "actor_not_found", "folder": folder}
            continue
        # Cap at 10 min so batches finish in time (INGEST_ACTOR_TIMEOUT_SECS or 600)
        _timeout = int(cfg.get("timeout_secs") or os.environ.get("INGEST_ACTOR_TIMEOUT_SECS", "600"))
        timeout_secs = min(600, max(60, _timeout))
        memory_mbytes = int(cfg.get("memory_mbytes") or os.environ.get("INGEST_ACTOR_MEMORY_MB", "1024"))
        base_input = (cfg.get("input") or {}).copy()
        # Build run_input from search_strategy.yaml when present (keywords, subreddits)
        # keyword_offset rotates which keywords are used so each run gets different posts.
        if SEARCH_STRATEGY_PATH.exists():
            run_input = build_run_input(platform, base_input, merge_keywords=True, keyword_offset=keyword_offset)
        else:
            run_input = base_input
        if run_input.get("_total_keywords") is not None:
            total_keywords_for_rotation = run_input.pop("_total_keywords")
        # Merge database keyword overrides (dashboard-editable)
        overrides = get_keywords_override(mongo_db)
        if run_input.get("keywords"):
            run_input["keywords"] = merge_keywords_override(
                run_input["keywords"], platform, overrides
            )
        # Reddit: pass after_utc so we only fetch posts after last run (retention — no re-scraping same posts)
        if cursors.get(platform) is not None:
            run_input = merge_cursor_into_run_input(run_input, platform, cursors[platform])
            if run_input.get("after_utc") is not None:
                _log_info(_log, "Retention: passing after_utc to actor (only new posts)", platform=platform, after_utc=run_input["after_utc"])
        # Twitter/IG/FB/LinkedIn: pass since date from last run when supported (latest only, avoid duplicates)
        last_run = state.get("lastRunAt")
        if last_run is not None:
            run_input = merge_since_date_into_run_input(run_input, platform, last_run)
        # Minimal test mode: reduce Apify usage (set APIFY_MINIMAL_TEST=1)
        if os.environ.get("APIFY_MINIMAL_TEST") and platform == "reddit":
            run_input = {
                "subreddits": ["startups"],
                "keywords": ["just launched", "new business"],
                "maxPosts": 5,
                "sortBy": "new",
                "timeFilter": "week",
            }
        def _run():
            return ingest_platform(
                client, platform, actor_id, run_input,
                mongo_db=mongo_db,
                timeout_secs=timeout_secs,
                memory_mbytes=memory_mbytes,
            )

        try:
            item_count, leads = _run()
            _log_info(_log, "DEBUG platform done", platform=platform, item_count=item_count, leads_count=len(leads))
            results[platform] = {"item_count": item_count, "leads_count": len(leads), "ok": True}
            all_leads.extend(leads)
            # Incremental state save: update cursor for this platform so a crash doesn't lose progress.
            # When we get no new leads, still advance cursor to "now" so next run fetches only newer posts (avoids duplicate posts).
            if mongo_db is not None:
                if leads:
                    new_cursors: dict[str, int] = {}
                    for lead in leads:
                        ts = lead.timestamp.timestamp() if hasattr(lead.timestamp, "timestamp") else None
                        if ts is not None and lead.platform:
                            cur = new_cursors.get(lead.platform)
                            new_cursors[lead.platform] = max(cur, int(ts)) if cur is not None else int(ts)
                    final_cursors.update(new_cursors)
                elif platform.lower() in ("reddit",):
                    now_ts = int(datetime.utcnow().timestamp())
                    final_cursors[platform] = max(final_cursors.get(platform) or 0, now_ts)
                    _log_info(_log, "Retention: no new leads; advancing cursor to now so next run gets fresh posts", platform=platform)
                save_pipeline_state(mongo_db, cursors=final_cursors, update_last_run_at=False)
        except Exception as e:
            if retry_failed_once:
                time.sleep(5)
                try:
                    item_count, leads = _run()
                    results[platform] = {"item_count": item_count, "leads_count": len(leads), "ok": True, "retried": True}
                    all_leads.extend(leads)
                    if mongo_db is not None:
                        if leads:
                            new_cursors = {}
                            for lead in leads:
                                ts = lead.timestamp.timestamp() if hasattr(lead.timestamp, "timestamp") else None
                                if ts is not None and lead.platform:
                                    cur = new_cursors.get(lead.platform)
                                    new_cursors[lead.platform] = max(cur, int(ts)) if cur is not None else int(ts)
                            final_cursors.update(new_cursors)
                        elif platform.lower() in ("reddit",):
                            now_ts = int(datetime.utcnow().timestamp())
                            final_cursors[platform] = max(final_cursors.get(platform) or 0, now_ts)
                        save_pipeline_state(mongo_db, cursors=final_cursors, update_last_run_at=False)
                except Exception as e2:
                    results[platform] = {"ok": False, "error": str(e2), "retried": True}
            else:
                results[platform] = {"ok": False, "error": str(e)}
        time.sleep(delay_between_actors)

    # Store in MongoDB (uses seen_post_hashes so retention deletes don't allow re-fetching)
    inserted = 0
    _log_info(_log, "DEBUG before store: all_leads count", count=len(all_leads), mongo_db_is_none=(mongo_db is None))
    if mongo_db is not None and all_leads:
        inserted = store_raw_posts(mongo_db, all_leads, dedupe=True)
        _log_info(_log, "DEBUG after store_raw_posts", inserted=inserted)
    else:
        reason = "all_leads empty" if not all_leads else "mongo_db is None (pipeline has no MongoDB connection)"
        _log_info(_log, "DEBUG skip store", reason=reason)
        if all_leads and mongo_db is None:
            _log_info(_log, "NOT STORED: pipeline subprocess had no MongoDB. Set MONGODB_URI in .env; ensure dashboard and pipeline use the same URI (see job_runner DEBUG logs).")

    # Final state save: update lastRunAt, cursors, and keyword_offset for next run (different keywords = different posts).
    if mongo_db is not None:
        next_keyword_offset = keyword_offset
        if total_keywords_for_rotation is not None and total_keywords_for_rotation > 0:
            next_keyword_offset = (keyword_offset + KEYWORD_ROTATION_CHUNK) % total_keywords_for_rotation
            _log_info(_log, "Keyword rotation: next run will use offset", next_offset=next_keyword_offset, total=total_keywords_for_rotation)
        save_pipeline_state(
            mongo_db,
            last_run_at=datetime.utcnow(),
            cursors=final_cursors,
            update_last_run_at=True,
            keyword_offset=next_keyword_offset,
        )

    return {
        "ok": True,
        "results": results,
        "total_leads": len(all_leads),
        "inserted": inserted,
    }
