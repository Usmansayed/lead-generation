#!/usr/bin/env python3
"""
Full after-filter workflow: for each qualified lead run
  full post fetch -> research -> profile fetch -> contact discovery -> personalized email.
  When contact email is found: add to email_queue (ready for SES).
  Also write ALL results to output/full_workflow_emails.json.

Output: output/full_workflow_emails.json
  - List of entries: lead_id, platform, post_url, author_handle, contact (method + value), email (subject, bodyText, bodyHtml).
  - When no email address is found, contact = profile URL or post URL (so you can DM/comment).
  - When research says should_skip_email, entry has skipped_reason and no email body (saves LLM cost).
"""
from __future__ import annotations

import argparse
import json
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
    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        return None
    try:
        from pymongo import MongoClient
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        return client.get_database()
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="Run full after-filter workflow and write all emails to one JSON file.")
    ap.add_argument("--limit", type=int, default=20, help="Max qualified leads to process (default 20)")
    ap.add_argument("--output", default=None, help="Output JSON path (default: output/full_workflow_emails.json)")
    ap.add_argument("--no-skip", action="store_true", help="Generate email even when research says should_skip_email (for testing)")
    args = ap.parse_args()

    db = get_db()
    if db is None:
        print("MONGODB_URI not set or unreachable. Cannot read qualified_leads.")
        sys.exit(1)

    from pipeline.models import CanonicalLead
    qualified_coll = db.qualified_leads if hasattr(db, "qualified_leads") else db["qualified_leads"]
    cursor = qualified_coll.find({"status": "qualified"}).limit(args.limit)
    leads = [CanonicalLead.from_doc(d) for d in cursor]
    if not leads:
        print("No qualified leads found. Run pipeline steps 1–3 first to qualify leads.")
        sys.exit(0)

    print(f"Processing {len(leads)} qualified lead(s). Full fetch -> research -> profile -> contact -> email.")
    print()

    from pipeline.full_post_fetch import fetch_full_post
    from pipeline.business_research import research_lead
    from pipeline.profile_enrichment import enrich_lead_profile
    from pipeline.contact_discovery import get_contact_for_lead
    from pipeline.email_personalization import generate_email
    from pipeline.email_queue import add_to_queue, append_unsubscribe_footer, get_list_unsubscribe_value
    from pipeline.suppression import is_suppressed
    from pipeline.email_verification import verify_email
    from pipeline.web_research import web_search_lead
    from pipeline.llm_client import has_llm_config

    has_llm = has_llm_config()
    list_unsubscribe = get_list_unsubscribe_value()
    if not has_llm:
        print("Warning: No LLM config (AWS2_* or CLAUDE_* for Bedrock Nova Lite). Email bodies will be empty.")

    results = []
    queued_count = 0
    for i, lead in enumerate(leads, 1):
        print(f"[{i}/{len(leads)}] {lead.platform} | {lead.post_url[:60]}...")
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
        contact_method = "email"
        contact_value = to_email or ""
        if not contact_value:
            profile_url = profile_data.get("profile_url") or (lead.author.profile_url if lead.author else None)
            if profile_url:
                contact_method = "profile"
                contact_value = profile_url
            else:
                contact_method = "post"
                contact_value = lead.post_url or ""

        skipped_reason = None
        if research.get("should_skip_email") and not args.no_skip:
            skipped_reason = "research_should_skip_email"
        email_payload = None
        if not skipped_reason and has_llm:
            email_payload = generate_email(
                lead,
                profile_data=profile_data,
                full_post_text=full_post_text,
                business_type=research.get("business_type", ""),
                suggested_offers=research.get("suggested_offers"),
                web_context=web_context,
            )

        entry = {
            "lead_id": lead.id,
            "platform": lead.platform,
            "post_url": lead.post_url,
            "author_handle": lead.author.handle if lead.author else None,
            "contact": {
                "method": contact_method,
                "value": contact_value,
            },
            "email": {
                "subject": email_payload.get("subject", "") if email_payload else "",
                "bodyText": email_payload.get("bodyText", "") if email_payload else "",
                "bodyHtml": email_payload.get("bodyHtml", "") if email_payload else "",
            } if email_payload else None,
        }
        if skipped_reason:
            entry["skipped_reason"] = skipped_reason
        results.append(entry)

        # Add to email_queue when we have an email (ready for SES)
        if to_email and email_payload and not is_suppressed(db, lead_id=lead.id):
            verify_result = verify_email(to_email)
            if verify_result.get("skip") or verify_result.get("valid"):
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
                    entry["queued"] = True
                    queued_count += 1
                    print(f"    contact={contact_method} | queued | subject={email_payload.get('subject', '')[:50]}...")
                elif ok and action.startswith("skipped_"):
                    print(f"    contact={contact_method} | {action} (no duplicate) | subject={email_payload.get('subject', '')[:50]}...")
                else:
                    print(f"    contact={contact_method} | subject={email_payload.get('subject', '')[:50]}...")
            else:
                print(f"    contact={contact_method} | skipped (email invalid) | subject={email_payload.get('subject', '')[:50]}...")
        elif email_payload:
            print(f"    contact={contact_method} | subject={email_payload.get('subject', '')[:50]}...")
            # Store for manual outreach (no email found; user can copy message and DM)
            if not to_email:
                from pipeline.leads_no_email import add_lead_no_email
                add_lead_no_email(
                    db,
                    lead_id=lead.id,
                    platform=lead.platform or "",
                    post_url=lead.post_url or "",
                    author_handle=lead.author.handle if lead.author else "",
                    contact_value=contact_value,
                    subject=email_payload.get("subject", ""),
                    body_text=email_payload.get("bodyText", ""),
                )
        else:
            print(f"    contact={contact_method} | skipped={skipped_reason or 'no_llm'}")


    out_path = Path(args.output) if args.output else ROOT / "output" / "full_workflow_emails.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"count": len(results), "emails": results}, f, indent=2, default=str)
    print()
    print(f"Done. All {len(results)} entries (contact + email) written to: {out_path}")
    if queued_count:
        print(f"Queued {queued_count} email(s) to email_queue (ready for SES).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
