"""
Minimal Apify ingestion test: 1 platform (Reddit), 1 subreddit, 5 posts.
Use this to verify the full ingestion path with minimal credits.
Run: python -m pipeline.tests.test_ingestion_minimal
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    if not os.environ.get("APIFY_TOKEN", "").strip():
        print("APIFY_TOKEN not set. Set it in .env and retry.")
        return 1
    os.environ["APIFY_MINIMAL_TEST"] = "1"
    from pipeline.ingestion import run_ingestion
    from pipeline.run_pipeline import get_mongo_db
    db = get_mongo_db()
    print("Running minimal ingestion (Reddit, r/startups, 5 posts)...")
    try:
        out = run_ingestion(mongo_db=db, platforms=["reddit"])
        if not out.get("ok"):
            print("FAIL:", out.get("error", out))
            return 1
        print("OK. Leads:", out.get("total_leads", 0), "Inserted:", out.get("inserted", 0))
        return 0
    except Exception as e:
        print("FAIL:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
