#!/usr/bin/env python3
"""
Export pending/sent emails from email_queue to a JSON file.
Use after running the pipeline to verify generated emails without sending.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def serialize_doc(doc):
    """Convert MongoDB doc to JSON-serializable dict."""
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat() + "Z"
        else:
            out[k] = v
    return out


def main():
    output = ROOT / "output" / "generated_emails.json"
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/").strip()
    db_name = "lead_discovery"
    if "/" in uri.rstrip("/"):
        db_name = uri.rstrip("/").split("/")[-1].split("?")[0] or db_name
    try:
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db = client.get_database(db_name)
    except Exception as e:
        print(f"MongoDB not available: {e}")
        return 1

    queue = db.email_queue if hasattr(db, "email_queue") else db["email_queue"]
    # Export pending first; if none, include sent
    items = list(queue.find({"status": "pending"}).sort("createdAt", -1))
    if not items:
        items = list(queue.find({"status": "sent"}).sort("sentAt", -1).limit(50))
    if not items:
        items = list(queue.find({}).sort("createdAt", -1).limit(50))

    serialized = [serialize_doc(d) for d in items]
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump({"count": len(serialized), "emails": serialized}, f, indent=2, default=str)

    print(f"Exported {len(serialized)} email(s) to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
