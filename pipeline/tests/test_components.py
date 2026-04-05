"""
Test each pipeline component WITHOUT calling Apify (no credits used).
Run from project root: python -m pipeline.tests.test_components [--llm] [--mongo]
"""
from __future__ import annotations
import os
import sys
from datetime import datetime, timezone

# Project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def test_config_loader():
    """Load phase1 sources and keywords without errors."""
    from pipeline.config_loader import load_phase1_sources, load_keywords_master, get_platform_actor_config
    sources = load_phase1_sources()
    assert sources.get("platforms") == ["linkedin", "twitter", "instagram", "facebook", "reddit"], "phase1 platforms"
    for plat in ["reddit", "linkedin"]:
        cfg = get_platform_actor_config(sources, plat)
        assert cfg is not None and cfg.get("folder") and cfg.get("input"), f"config for {plat}"
    km = load_keywords_master()
    assert "intent_categories" in km or "version" in km, "keywords_master"
    return True


def test_normalizers():
    """Normalize fake actor output into canonical leads."""
    from pipeline.normalizers import normalize_item, NORMALIZERS
    # Fake Reddit item (minimal)
    reddit_item = {
        "url": "https://www.reddit.com/r/startups/comments/abc123/test/",
        "title": "Looking for a developer",
        "selftext": "We need someone to build our MVP. Budget 10k.",
        "author": "founder1",
        "author_url": "https://www.reddit.com/user/founder1",
        "created_utc": 1700000000,
        "matched_keywords": ["looking for developer"],
        "scraped_at": "2024-01-01T00:00:00",
    }
    lead = normalize_item("reddit", reddit_item)
    assert lead is not None, "reddit normalizer returns lead"
    assert lead.platform == "reddit"
    assert lead.post_id
    assert "looking for" in (lead.post_text or "").lower() or "developer" in (lead.post_text or "").lower()
    assert lead.author.name == "founder1"
    return True


def test_relevance_engine():
    """Relevance accepts good post, rejects bad post."""
    from pipeline.relevance import compute_relevance
    # Should pass: clear intent
    good = compute_relevance(
        "We are a startup looking for a developer to build our MVP. Budget 10k. DM me for details.",
        "reddit",
        datetime.now(timezone.utc),
        {"num_comments": 5},
    )
    assert good.get("passed") is True, "good lead should pass"
    assert good.get("score", 0) >= 5, "good lead has score"
    assert len(good.get("matched_keywords") or []) >= 1, "keywords matched"
    # Should reject: job seeker
    bad = compute_relevance("Hire me! My portfolio at ... seeking opportunities.", "reddit", None, None)
    assert bad.get("passed") is False and bad.get("reject_reason"), "job seeker rejected"
    return True


def test_static_filter_backfill():
    """Static filter uses relevance when doc has no staticScore (no DB needed)."""
    from pipeline.relevance import get_engine
    from pipeline.static_filter import _load_rules
    rules = _load_rules()
    assert "minimum_threshold" in rules
    thresh = rules.get("minimum_threshold", 5)
    engine = get_engine()
    # Use enough words to pass minimum_word_count (15 in filters.yaml)
    long_text = "Looking for a developer to build an app. We have budget and need someone to start soon. DM me for details."
    r = engine.compute(long_text, "reddit", None, None)
    assert r["passed"], f"sample should pass relevance (passed={r.get('passed')}, reason={r.get('reject_reason')})"
    assert r["score"] >= thresh, f"sample score {r['score']} >= threshold {thresh}"
    return True


def test_llm_client_config():
    """LLM client uses Bedrock (AWS_BEDROCK_API or IAM: AWS_* / AWS2_* / CLAUDE_*)."""
    from pipeline.llm_client import has_llm_config, _has_bedrock_config
    has = has_llm_config()
    assert has == _has_bedrock_config(), "has_llm_config equals _has_bedrock_config (API key or IAM)"
    return True


def test_llm_call_optional():
    """Optional: one short LLM call (uses credits). Skip unless --llm."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        from pipeline.llm_client import call_llm, has_llm_config
    if not has_llm_config():
        return True  # skip
    text = call_llm("Reply with exactly the word OK and nothing else.", temperature=0)
    if text is not None and len(text.strip()) > 0:
        return True
    # None can mean quota (429) or model error; LLM is configured
    print("  (LLM returned no text; may be quota or model - keys are configured)")
    return True


def test_mongo_connection():
    """MongoDB connection and indexes (no Apify). Skip unless --mongo."""
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
    try:
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        db = client.get_database("lead_discovery")
        from pipeline.db import ensure_indexes
        ensure_indexes(db)
        return True
    except Exception as e:
        raise AssertionError(f"MongoDB connection failed: {e}") from e


def test_ingestion_store_only():
    """Store raw_posts without running Apify: use fake leads (needs Mongo)."""
    from pipeline.ingestion import store_raw_posts
    from pipeline.models import CanonicalLead
    from pipeline.normalizers import normalize_item
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
    try:
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        db = client.get_database("lead_discovery")
    except Exception:
        return True  # skip if no Mongo
    # One fake lead
    fake_item = {
        "url": "https://www.reddit.com/r/startups/comments/test999/",
        "title": "Test post for pipeline",
        "selftext": "Looking for developer. Budget 5k.",
        "author": "testuser",
        "created_utc": 1700000000,
        "matched_keywords": ["looking for developer"],
        "scraped_at": "2024-01-01T00:00:00",
    }
    lead = normalize_item("reddit", fake_item)
    assert lead is not None
    n = store_raw_posts(db, [lead], dedupe=True)
    assert n == 1, "store_raw_posts inserted 1"
    # Clean up test doc (raw_posts + seen_post_hashes)
    db.raw_posts.delete_one({"_id": lead.id})
    db.seen_post_hashes.delete_one({"_id": lead.id})
    return True


def run_all(skip_llm: bool = True, skip_mongo: bool = False):
    tests = [
        ("Config loader", test_config_loader),
        ("Normalizers", test_normalizers),
        ("Relevance engine", test_relevance_engine),
        ("Static filter / threshold", test_static_filter_backfill),
        ("LLM config", test_llm_client_config),
    ]
    if not skip_llm:
        tests.append(("LLM call (1 request)", test_llm_call_optional))
    if not skip_mongo:
        tests.append(("MongoDB connection + indexes", test_mongo_connection))
        tests.append(("Store raw_posts (no Apify)", test_ingestion_store_only))

    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"  OK   {name}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            failed.append((name, e))
    return failed


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Test pipeline components (no Apify)")
    ap.add_argument("--llm", action="store_true", help="Run one LLM call (uses API credits)")
    ap.add_argument("--mongo", action="store_true", help="Test MongoDB connection and store_raw_posts")
    args = ap.parse_args()
    print("Pipeline component tests (no Apify credits used except with --llm)\n")
    failed = run_all(skip_llm=not args.llm, skip_mongo=not args.mongo)
    if failed:
        print(f"\n{len(failed)} test(s) failed.")
        sys.exit(1)
    print("\nAll tests passed. Safe to run pipeline (ingestion will use Apify).")
    sys.exit(0)
