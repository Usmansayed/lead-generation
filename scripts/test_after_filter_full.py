#!/usr/bin/env python3
"""
End-to-end test: find contact → full post fetch → profile fetch → research → personalized email.
Single output file with everything; end product = way of contact + full email.
Result: output/after_filter_result.json (one file).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# Real Reddit post (public) - "I built a free Triangle of Talent assessment..."
REAL_POST_URL = "https://www.reddit.com/r/SideProject/comments/1r3psn4/i_built_a_free_triangle_of_talent_assessment/"
REAL_POST_TEXT = """I built a free "Triangle of Talent" assessment based on Shaan Puri's framework

Shaan Puri shared this framework on My First Million - your talent level depends on two things: how good you are at finding the right problems and how good you are at solving them. Your overall level is capped by whichever is weaker.

I turned it into a quick 12-question quiz that scores you on both axes and places you at one of 5 levels (from "Useless" to "Superstar").

No signup, no email, just take it and see where you land. Would love feedback on the questions."""

AUTHOR_HANDLE = "usamaejazch"
AUTHOR_PROFILE_URL = "https://www.reddit.com/user/usamaejazch"


def build_test_lead():
    """Build a CanonicalLead for the real post (simulating a qualified lead)."""
    from pipeline.models import CanonicalLead, Author
    import hashlib
    lead_id = hashlib.sha256(f"reddit_{REAL_POST_URL}".encode()).hexdigest()
    return CanonicalLead(
        id=lead_id,
        platform="reddit",
        post_id="1r3psn4",
        post_text=REAL_POST_TEXT,
        author=Author(name=AUTHOR_HANDLE, handle=AUTHOR_HANDLE, profile_url=AUTHOR_PROFILE_URL),
        post_url=REAL_POST_URL,
        timestamp=datetime.now(timezone.utc),
        keywords_matched=["building", "launched"],
        static_score=70,
        ai_score=0.85,
        intent_label="new_business_or_launch",
        status="qualified",
    )


def get_db():
    """Connect to MongoDB if available."""
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
    print("=" * 60)
    print("AFTER-FILTER FULL TEST (real post URL)")
    print("=" * 60)

    lead = build_test_lead()
    print(f"Lead: {lead.platform} | {lead.post_url[:60]}...")
    print()

    db = get_db()
    if db is not None:
        print("[DB] MongoDB connected.")
    else:
        print("[DB] No MongoDB; cache will be skipped (full fetch & profile will still run).")
    print()

    # 1) Full post fetch
    print("[1/6] Full post fetch (Apify post-content-fetcher)...")
    from pipeline.full_post_fetch import fetch_full_post
    post_fetch = fetch_full_post(lead, db)
    full_post_text = post_fetch.get("full_post_text", "")
    from_cache = post_fetch.get("from_cache", False)
    print(f"      from_cache={from_cache}, len(full_post_text)={len(full_post_text)}")
    if full_post_text:
        print(f"      preview: {full_post_text[:150]}...")
    else:
        print("      (empty - Apify may have failed or URL blocked)")
    print()

    # 2) Business research
    print("[2/6] Business research (type, size, has_website, suggested_offers, should_skip)...")
    from pipeline.business_research import research_lead
    research = research_lead(lead.post_text or "", full_post_text)
    print(f"      business_type={research.get('business_type')}, size={research.get('business_size')}, "
          f"has_website={research.get('has_website')}, should_skip_email={research.get('should_skip_email')}")
    print(f"      suggested_offers={research.get('suggested_offers')}")
    print()

    if research.get("should_skip_email"):
        print("      [SKIP] would_skip (small cafe/restaurant with website); continuing for test.")

    # 3) Profile fetch
    print("[3/6] Profile fetch (Apify post-content-fetcher on profile URL)...")
    from pipeline.profile_enrichment import enrich_lead_profile
    profile_data = enrich_lead_profile(lead, db)
    print(f"      from_cache={profile_data.get('from_cache')}, len(profile_text)={len(profile_data.get('profile_text') or '')}")
    if profile_data.get("profile_text"):
        print(f"      preview: {(profile_data['profile_text'] or '')[:120]}...")
    print()

    # 4) Web research (free DuckDuckGo search, or Tavily if TAVILY_API_KEY set)
    print("[4/6] Web research (DuckDuckGo free, or Tavily if TAVILY_API_KEY set)...")
    from pipeline.web_research import web_search_lead, has_web_search_config
    web_context = web_search_lead(
        lead,
        full_post_text=full_post_text,
        profile_text=profile_data.get("profile_text") or "",
    )
    print(f"      has_web_search={has_web_search_config()}, web_context_len={len(web_context)}")
    if web_context:
        print(f"      preview: {web_context[:150]}...")
    print()

    # 5) Contact discovery – way to reach the lead (email or profile/message link)
    print("[5/6] Contact discovery (email from post or profile)...")
    from pipeline.contact_discovery import get_contact_for_lead
    to_email = get_contact_for_lead(lead, profile_data)
    contact_method = "email"
    contact_value = to_email
    if not to_email:
        # Fallback: profile or post URL so they can be reached (DM, comment, etc.)
        profile_url = profile_data.get("profile_url") or (lead.author.profile_url if lead.author else None)
        if profile_url:
            contact_method = "profile"
            contact_value = profile_url
        else:
            contact_method = "post"
            contact_value = lead.post_url or ""
        print(f"      (no email found – way of contact: {contact_method} = {contact_value[:50]}...)")
    else:
        print(f"      found: email = {to_email}")
    print()

    # 6) Personalized email (post + profile + research + web context → LLM)
    print("[6/6] Generating personalized email (LLM; post + profile + research + web context)...")
    from pipeline.email_personalization import generate_email
    from pipeline.llm_client import has_llm_config
    if not has_llm_config():
        print("      [WARN] No LLM config (AWS2_* or CLAUDE_* for Bedrock Nova Lite). Skip email generation.")
        email_payload = None
    else:
        email_payload = generate_email(
            lead,
            profile_data=profile_data,
            full_post_text=full_post_text,
            business_type=research.get("business_type", ""),
            suggested_offers=research.get("suggested_offers"),
            web_context=web_context,
        )
        if email_payload:
            print(f"      subject: {email_payload.get('subject', '')[:60]}...")
            print(f"      body length: {len(email_payload.get('bodyText', ''))} chars")
        else:
            print("      [WARN] LLM returned no email.")
    print()

    # ---- One file: pipeline data + END PRODUCT (contact + email) ----
    out = {
        "lead": {
            "id": lead.id,
            "platform": lead.platform,
            "post_url": lead.post_url,
            "post_text_preview": (lead.post_text or "")[:400],
            "author_handle": lead.author.handle,
            "author_profile_url": lead.author.profile_url if lead.author else None,
        },
        "full_post_fetch": {
            "from_cache": from_cache,
            "full_post_text_length": len(full_post_text),
            "full_post_text": full_post_text,
        },
        "research": research,
        "profile_fetch": {
            "from_cache": profile_data.get("from_cache"),
            "profile_url": profile_data.get("profile_url", ""),
            "profile_text_length": len(profile_data.get("profile_text") or ""),
            "profile_text": profile_data.get("profile_text") or "",
        },
        "web_research": {
            "used": bool(web_context),
            "web_context_length": len(web_context),
            "web_context": web_context or "",
        },
        # ----- END PRODUCT: way of contact + full email -----
        "contact": {
            "method": contact_method,
            "value": contact_value,
            "description": "email" if contact_method == "email" else "reach via profile/post (no email found)",
        },
        "email": {
            "subject": email_payload.get("subject", "") if email_payload else "",
            "bodyText": email_payload.get("bodyText", "") if email_payload else "",
            "bodyHtml": email_payload.get("bodyHtml", "") if email_payload else "",
        } if email_payload else None,
    }

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "after_filter_result.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"Result saved to: {out_file}")
    print()
    print("=" * 60)
    print("END PRODUCT (contact + email)")
    print("=" * 60)
    print("Contact:", contact_method, "=", contact_value)
    print()
    if email_payload:
        print("Subject:", email_payload.get("subject", ""))
        print("-" * 40)
        print(email_payload.get("bodyText", ""))
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
