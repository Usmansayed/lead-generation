#!/usr/bin/env python3
"""
Test the AWS SES email sender locally.
- --dry-run: validate env/config, show pending count, no actual send
- --send-one TO_EMAIL: send one test email to verify SES works (no queue)
Requires: SES_FROM_EMAIL, AWS_REGION (or default us-east-1), AWS creds (env or ~/.aws/credentials)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


def get_db():
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/").strip()
    if not uri or uri == "your_mongodb_uri":
        return None
    try:
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client.get_default_database()
        client.admin.command("ping")
        return db
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="Test SES sender: dry-run or send one test email")
    ap.add_argument("--dry-run", action="store_true", help="Validate env, show config and pending count; no send")
    ap.add_argument("--send-one", metavar="TO_EMAIL", help="Send one test email to this address")
    args = ap.parse_args()

    if not args.dry_run and not args.send_one:
        ap.error("Use --dry-run or --send-one TO_EMAIL")

    from pipeline.ses_sender import (
        SES_REGION_ENV,
        SES_FROM_ENV,
        SES_REPLY_TO_ENV,
        SES_DAILY_CAP_ENV,
        SES_ENDPOINT_ENV,
        send_queued_emails,
        send_test_email,
    )

    region = os.environ.get(SES_REGION_ENV, "").strip() or "us-east-1"
    from_email = os.environ.get(SES_FROM_ENV, "").strip()
    reply_to = os.environ.get(SES_REPLY_TO_ENV, "").strip() or None
    cap = int(os.environ.get(SES_DAILY_CAP_ENV, "") or 100)
    endpoint = os.environ.get(SES_ENDPOINT_ENV, "").strip() or None

    has_key = bool(os.environ.get("AWS_ACCESS_KEY_ID", "").strip())
    has_secret = bool(os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip())
    creds_status = "set (API key + secret)" if (has_key and has_secret) else "not set" if not (has_key or has_secret) else "incomplete"

    print("=== SES Sender Test ===\n")
    print("Environment:")
    print(f"  AWS credentials:  {creds_status}")
    print(f"  AWS_REGION:       {region}")
    print(f"  SES_FROM_EMAIL:   {from_email or '(not set)'}")
    print(f"  SES_REPLY_TO:     {reply_to or '(not set)'}")
    print(f"  SES_DAILY_CAP:    {cap}")
    print(f"  AWS_SES_ENDPOINT: {endpoint or '(default - real AWS)'}")
    print()

    if not from_email:
        print("ERROR: SES_FROM_EMAIL must be set. Add to .env:")
        print("  SES_FROM_EMAIL=notifications@yourdomain.com")
        return 1

    if args.send_one and (not has_key or not has_secret):
        print("ERROR: For sending, set in .env: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY (IAM user with SES permissions)")
        return 1

    if args.dry_run:
        db = get_db()
        if db is None:
            print("MongoDB: (not connected - MONGODB_URI not set or unreachable)")
            print("  Pending emails: N/A (connect MongoDB to see queue)")
        else:
            print("MongoDB: connected")
            result = send_queued_emails(db, dry_run=True)
            pending = result.get("would_send", "N/A")
            print(f"  Pending emails:   {pending}")
            if result.get("skipped_paused") == -1:
                print("  Sending: PAUSED (app_config.sending_paused=True)")
            else:
                print("  Sending: active (would send up to batch_size/cap)")
        print("\nDRY RUN complete. No emails sent.")
        return 0

    if args.send_one:
        to = args.send_one.strip()
        if "@" not in to:
            print(f"ERROR: Invalid email: {to}")
            return 1
        print(f"Sending test email to {to}...")
        result = send_test_email(to)
        if result.get("ok"):
            print(f"SUCCESS. MessageId: {result.get('message_id', '—')}")
            return 0
        else:
            print(f"FAILED: {result.get('error', 'unknown')}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
