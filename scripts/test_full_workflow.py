#!/usr/bin/env python3
"""
End-to-end workflow test: promote raw_posts for testing, run pipeline steps,
export generated emails to file. Use when you want to verify the full flow
without SES. Requires: MongoDB, APIFY_TOKEN, and Bedrock (AWS_BEDROCK_API or AWS2_* / CLAUDE_* in .env).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def main():
    from pymongo import MongoClient

    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/").strip()
    db_name = "lead_discovery"
    if "/" in uri.rstrip("/"):
        db_name = uri.rstrip("/").split("/")[-1].split("?")[0] or db_name
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    db = client.get_database(db_name)
    raw = db.raw_posts

    # 1. Promote 2 posts to raw (rejected or static_rejected) so they flow through static filter
    ids = [
        d["_id"]
        for d in raw.find({"status": {"$in": ["rejected", "static_rejected"]}}).limit(2)
    ]
    if not ids:
        ids = [d["_id"] for d in raw.find({}).limit(2)]
    if not ids:
        print("No raw_posts. Run ingestion first: python -m pipeline.run_pipeline --platforms reddit")
        return 1
    raw.update_many(
        {"_id": {"$in": ids}},
        {"$set": {"status": "raw", "staticScore": 10}},
    )
    print(f"Promoted {len(ids)} raw_posts to status=raw for testing")

    # 2. Run static filter only (not full --filter-only which also runs AI)
    from pipeline.static_filter import apply_static_filter
    apply_static_filter(db)
    print("Static filter done")

    # 3. Promote filtered to qualified for testing (skip AI to force email gen)
    qual = db.qualified_leads if hasattr(db, "qualified_leads") else db["qualified_leads"]
    filtered = list(raw.find({"status": "filtered"}).limit(2))
    for d in filtered:
        lead_id = d.get("_id")
        d2 = dict(d)
        d2["status"] = "qualified"
        d2["aiScore"] = 0.8
        qual.replace_one({"_id": lead_id}, d2, upsert=True)
    if filtered:
        print(f"Promoted {len(filtered)} filtered leads to qualified (for testing)")
    else:
        print("No filtered leads. Cannot test email generation.")
        return 1

    # 4. Generate emails and write to file (no SES)
    r3 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_full_after_filter_to_emails.py"), "--limit", "5", "--no-skip"],
        cwd=ROOT,
        timeout=180,
    )
    if r3.returncode != 0:
        return r3.returncode

    print(f"\nGenerated emails written to {ROOT / 'output' / 'full_workflow_emails.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
