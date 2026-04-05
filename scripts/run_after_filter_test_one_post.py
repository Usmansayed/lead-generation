#!/usr/bin/env python3
"""
Run the after-filter workflow on ONE post (no qualification filter applied).
Use a lead from the database (qualified_leads or raw_posts), a built-in test post, or a URL you provide.
Saves the output of EVERY step into one JSON file for inspection.

Output: output/after_filter_workflow_test.json
  - lead_source: "db_qualified" | "db_raw_posts" | "fallback" | "url"
  - lead: the lead used
  - step1_full_post_fetch, step2_research, step3_profile_fetch, step4_web_research,
    step5_contact, step6_email: full data at each step
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# Fallback post when DB has no leads
FALLBACK_POST_URL = "https://www.reddit.com/r/SideProject/comments/1r3psn4/i_built_a_free_triangle_of_talent_assessment/"
FALLBACK_POST_TEXT = """I built a free "Triangle of Talent" assessment based on Shaan Puri's framework

Shaan Puri shared this framework on My First Million - your talent level depends on two things: how good you are at finding the right problems and how good you are at solving them. Your overall level is capped by whichever is weaker.

I turned it into a quick 12-question quiz that scores you on both axes and places you at one of 5 levels (from "Useless" to "Superstar").

No signup, no email, just take it and see where you land. Would love feedback on the questions."""
FALLBACK_AUTHOR_HANDLE = "usamaejazch"
FALLBACK_PROFILE_URL = "https://www.reddit.com/user/usamaejazch"


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


def get_one_lead_from_db(db):
    """Get one lead from qualified_leads, then raw_posts. Returns (lead, source) or (None, None)."""
    from pipeline.models import CanonicalLead
    qual = db.qualified_leads if hasattr(db, "qualified_leads") else db["qualified_leads"]
    raw = db.raw_posts if hasattr(db, "raw_posts") else db["raw_posts"]
    doc = qual.find_one({"status": "qualified"})
    if doc:
        return CanonicalLead.from_doc(doc), "db_qualified"
    doc = qual.find_one()
    if doc:
        return CanonicalLead.from_doc(doc), "db_qualified"
    doc = raw.find_one()
    if doc:
        return CanonicalLead.from_doc(doc), "db_raw_posts"
    return None, None


def build_fallback_lead():
    """Build a CanonicalLead for the fallback Reddit post."""
    from pipeline.models import CanonicalLead, Author
    import hashlib
    lead_id = hashlib.sha256(f"reddit_{FALLBACK_POST_URL}".encode()).hexdigest()
    return CanonicalLead(
        id=lead_id,
        platform="reddit",
        post_id="1r3psn4",
        post_text=FALLBACK_POST_TEXT,
        author=Author(name=FALLBACK_AUTHOR_HANDLE, handle=FALLBACK_AUTHOR_HANDLE, profile_url=FALLBACK_PROFILE_URL),
        post_url=FALLBACK_POST_URL,
        timestamp=datetime.now(timezone.utc),
        keywords_matched=["building", "launched"],
        static_score=70,
        ai_score=0.85,
        intent_label="new_business_or_launch",
        status="qualified",
    )


def lead_to_serializable(lead):
    """Minimal dict for JSON (no datetime objects)."""
    a = lead.author
    return {
        "id": lead.id,
        "platform": lead.platform,
        "post_id": lead.post_id,
        "post_url": lead.post_url,
        "post_text": (lead.post_text or "")[:500],
        "author": {
            "name": a.name if a else "",
            "handle": a.handle if a else "",
            "profile_url": a.profile_url if a else None,
        },
        "status": lead.status,
    }


def main():
    out_path = ROOT / "output" / "after_filter_workflow_test.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    db = get_db()
    lead = None
    lead_source = "fallback"
    if db is not None:
        lead, lead_source = get_one_lead_from_db(db)
    if lead is None:
        lead = build_fallback_lead()
        lead_source = "fallback"
        print("No lead in DB; using built-in Reddit test post.")
    else:
        print(f"Using lead from DB: {lead_source}")

    print(f"Lead: {lead.platform} | {lead.post_url[:60]}...")
    print(f"Output file: {out_path}")
    print()

    result = {
        "lead_source": lead_source,
        "lead": lead_to_serializable(lead),
        "step1_full_post_fetch": None,
        "step2_research": None,
        "step3_profile_fetch": None,
        "step4_web_research": None,
        "step5_contact": None,
        "step6_email": None,
    }

    # --- Step 1: Full post fetch ---
    print("[1/6] Full post fetch...")
    from pipeline.full_post_fetch import fetch_full_post
    step1 = fetch_full_post(lead, db)
    result["step1_full_post_fetch"] = {
        "from_cache": step1.get("from_cache"),
        "full_post_text_length": len(step1.get("full_post_text", "")),
        "full_post_text": step1.get("full_post_text", ""),
    }
    print(f"      from_cache={step1.get('from_cache')}, len={result['step1_full_post_fetch']['full_post_text_length']}")

    full_post_text = step1.get("full_post_text", "")

    # --- Step 2: Business research ---
    print("[2/6] Business research...")
    from pipeline.business_research import research_lead
    step2 = research_lead(lead.post_text or "", full_post_text)
    result["step2_research"] = dict(step2)
    print(f"      business_type={step2.get('business_type')}, should_skip_email={step2.get('should_skip_email')}")

    # --- Step 3: Profile fetch ---
    print("[3/6] Profile fetch...")
    from pipeline.profile_enrichment import enrich_lead_profile
    profile_data = enrich_lead_profile(lead, db)
    result["step3_profile_fetch"] = {
        "from_cache": profile_data.get("from_cache"),
        "profile_url": profile_data.get("profile_url", ""),
        "profile_text_length": len(profile_data.get("profile_text") or ""),
        "profile_text": profile_data.get("profile_text") or "",
    }
    print(f"      from_cache={profile_data.get('from_cache')}, profile_text_len={result['step3_profile_fetch']['profile_text_length']}")

    # --- Step 4: Web research ---
    print("[4/6] Web research...")
    from pipeline.web_research import web_search_lead, has_web_search_config
    web_context = web_search_lead(
        lead,
        full_post_text=full_post_text,
        profile_text=profile_data.get("profile_text") or "",
    )
    result["step4_web_research"] = {
        "has_web_search_config": has_web_search_config(),
        "web_context_length": len(web_context),
        "web_context": web_context,
    }
    print(f"      config={result['step4_web_research']['has_web_search_config']}, len={len(web_context)}")

    # --- Step 5: Contact discovery ---
    print("[5/6] Contact discovery...")
    from pipeline.contact_discovery import get_contact_for_lead
    to_email = get_contact_for_lead(lead, profile_data)
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
    result["step5_contact"] = {
        "method": contact_method,
        "value": contact_value,
    }
    print(f"      {contact_method}={contact_value[:50]}...")

    # --- Step 6: Email generation ---
    print("[6/6] Email generation...")
    from pipeline.email_personalization import generate_email
    from pipeline.llm_client import has_llm_config
    email_payload = None
    if has_llm_config():
        email_payload = generate_email(
            lead,
            profile_data=profile_data,
            full_post_text=full_post_text,
            business_type=step2.get("business_type", ""),
            suggested_offers=step2.get("suggested_offers"),
            web_context=web_context,
        )
    result["step6_email"] = {
        "has_llm_config": has_llm_config(),
        "subject": email_payload.get("subject", "") if email_payload else "",
        "bodyText": email_payload.get("bodyText", "") if email_payload else "",
        "bodyHtml": email_payload.get("bodyHtml", "") if email_payload else "",
    }
    print(f"      has_llm={result['step6_email']['has_llm_config']}, subject_len={len(result['step6_email']['subject'])}")

    # --- Write one file with all steps ---
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print()
    print(f"Done. All steps saved to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
