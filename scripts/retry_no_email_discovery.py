#!/usr/bin/env python3
"""
Re-run email discovery for leads that are in the "no email" list.
Loads each lead from qualified_leads (or raw_posts), runs full fetch + profile + web research +
contact discovery. If an email is found, verifies it, generates the email, adds to email_queue,
and removes the lead from leads_no_email.

Usage:
  python scripts/retry_no_email_discovery.py                    # all pending no-email leads
  python scripts/retry_no_email_discovery.py --limit 20          # first 20
  python scripts/retry_no_email_discovery.py --all              # include already-sent (e.g. re-check)
  python scripts/retry_no_email_discovery.py --dry-run           # don't queue or remove, just report
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings

# Suppress noisy warnings from pipeline deps (before importing pipeline)
warnings.simplefilter("ignore", category=RuntimeWarning)
warnings.simplefilter("ignore", category=DeprecationWarning)
warnings.simplefilter("ignore", category=ResourceWarning)

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

_env_path = os.path.join(_project_root, ".env")
try:
    from dotenv import load_dotenv
    load_dotenv(_env_path)
except ImportError:
    pass
if not (os.environ.get("MONGODB_URI") or "").strip():
    try:
        with open(_env_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip() == "MONGODB_URI" and v.strip():
                        os.environ["MONGODB_URI"] = v.strip().strip('"').strip("'")
                        break
    except Exception:
        pass

# Import after path and env so pipeline sees MONGODB_URI; warnings already filtered above
from pipeline.db import ensure_indexes
from pipeline.leads_no_email import get_collection as get_leads_no_email_coll
from pipeline.models import CanonicalLead
from pipeline.full_post_fetch import fetch_full_post
from pipeline.business_research import research_lead
from pipeline.profile_enrichment import enrich_lead_profile
from pipeline.web_research import web_search_lead
from pipeline.contact_discovery import get_contact_for_lead
from pipeline.email_verification import verify_email
from pipeline.email_personalization import generate_email
from pipeline.email_queue import add_to_queue, get_list_unsubscribe_value, append_unsubscribe_footer
from pipeline.llm_client import has_llm_config


def get_db():
    """Connect to MongoDB. Returns (client, db) so caller can close client when done."""
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
    db_name = "lead_discovery"
    if "/" in uri.rstrip("/"):
        db_name = uri.rstrip("/").split("/")[-1].split("?")[0] or db_name
    try:
        from pymongo import MongoClient
        client = MongoClient(uri)
        return client, client.get_database(db_name)
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        return None, None


def _get_full_lead(db, lead_id: str) -> CanonicalLead | None:
    """Load lead by id from qualified_leads, then raw_posts."""
    qual = db.qualified_leads if hasattr(db, "qualified_leads") else db["qualified_leads"]
    raw = db.raw_posts if hasattr(db, "raw_posts") else db["raw_posts"]
    doc = qual.find_one({"_id": lead_id})
    if not doc:
        doc = raw.find_one({"_id": lead_id})
    if not doc:
        return None
    return CanonicalLead.from_doc(doc)


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-run email discovery for no-email leads")
    ap.add_argument("--limit", type=int, default=None, help="Max number of no-email leads to process")
    ap.add_argument("--all", action="store_true", help="Include leads already marked messageSent (default: pending only)")
    ap.add_argument("--dry-run", action="store_true", help="Do not add to queue or remove from leads_no_email")
    args = ap.parse_args()

    client, db = get_db()
    if db is None:
        print("MONGODB_URI not set or DB unavailable. Exiting.")
        return 1
    ensure_indexes(db)

    no_email_coll = get_leads_no_email_coll(db)
    query = {} if args.all else {"messageSent": False}
    cursor = no_email_coll.find(query).sort("createdAt", 1)
    if args.limit:
        cursor = cursor.limit(args.limit)
    docs = list(cursor)

    if not docs:
        print("No leads to process in leads_no_email.")
        print("Success.")
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        return 0

    print(f"Processing {len(docs)} no-email lead(s)...")
    if args.dry_run:
        print("(dry-run: will not queue or remove from leads_no_email)")

    found_count = 0
    queued_count = 0
    removed_count = 0
    no_lead_count = 0
    skip_email_count = 0

    list_unsubscribe = get_list_unsubscribe_value()

    for i, doc in enumerate(docs):
        lead_id = doc.get("_id") or doc.get("leadId")
        if not lead_id:
            continue
        lead_id = str(lead_id)
        author_handle = doc.get("authorHandle", "")

        lead = _get_full_lead(db, lead_id)
        if not lead:
            no_lead_count += 1
            print(f"  [{i+1}] {lead_id} ({author_handle}): no full lead in qualified_leads/raw_posts, skipping")
            continue

        post_fetch = fetch_full_post(lead, db)
        full_post_text = post_fetch.get("full_post_text", "")
        research = research_lead(lead.post_text or "", full_post_text)
        profile_data = enrich_lead_profile(lead, db)
        web_context = web_search_lead(
            lead,
            full_post_text=full_post_text,
            profile_text=profile_data.get("profile_text") or "",
        )
        to_email = get_contact_for_lead(lead, profile_data, web_context)

        if not to_email:
            print(f"  [{i+1}] {lead_id} ({author_handle}): still no email found")
            continue

        found_count += 1

        if research.get("should_skip_email"):
            skip_email_count += 1
            print(f"  [{i+1}] {lead_id} ({author_handle}): email found {to_email!r} but research says skip (small/website-only)")
            continue

        if args.dry_run:
            print(f"  [{i+1}] {lead_id} ({author_handle}): would queue {to_email!r}")
            continue

        verify_result = verify_email(to_email)
        if verify_result.get("skip") or verify_result.get("valid"):
            email_payload = None
            if has_llm_config():
                email_payload = generate_email(
                    lead,
                    profile_data=profile_data,
                    full_post_text=full_post_text,
                    business_type=research.get("business_type", ""),
                    suggested_offers=research.get("suggested_offers"),
                    web_context=web_context,
                )
            if email_payload:
                body_text = email_payload.get("bodyText", "")
                body_html = email_payload.get("bodyHtml", "")
                body_text, body_html = append_unsubscribe_footer(body_text, body_html, list_unsubscribe)
                ok, action = add_to_queue(
                    db,
                    lead.id,
                    email_payload.get("subject", ""),
                    body_text,
                    body_html,
                    to_email=to_email,
                    list_unsubscribe=list_unsubscribe,
                )
                if ok and action == "added":
                    queued_count += 1
                    no_email_coll.delete_one({"_id": lead_id})
                    removed_count += 1
                    print(f"  [{i+1}] {lead_id} ({author_handle}): queued {to_email!r}, removed from no-email")
                elif ok and action.startswith("skipped_"):
                    print(f"  [{i+1}] {lead_id} ({author_handle}): already in queue/sent ({action}), skipping")
                else:
                    print(f"  [{i+1}] {lead_id} ({author_handle}): email found but add_to_queue failed")
            else:
                print(f"  [{i+1}] {lead_id} ({author_handle}): email found but no LLM config to generate message")
        else:
            print(f"  [{i+1}] {lead_id} ({author_handle}): email {to_email!r} failed verification")

    print()
    print("Summary:")
    print(f"  Processed: {len(docs)}")
    print(f"  No full lead (skip): {no_lead_count}")
    print(f"  Email found: {found_count}")
    print(f"  Skipped (research): {skip_email_count}")
    print(f"  Queued: {queued_count}")
    print(f"  Removed from no-email: {removed_count}")
    if args.dry_run and found_count:
        print("  (Run without --dry-run to queue and remove from no-email.)")
    print("Success.")
    if client is not None:
        try:
            client.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
