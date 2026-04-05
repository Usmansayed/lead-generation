#!/usr/bin/env python3
"""
Run full after-filter pipeline (post fetch, profile fetch, research, contact, email) on real posts
from all 5 platforms: Reddit, Twitter, Instagram, Facebook, LinkedIn.
Saves one file: output/all_platforms_test_result.json with per-platform results and errors.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from pipeline.models import CanonicalLead, Author

# Real or realistic public post URLs per platform (some may 403/block when scraped)
PLATFORM_LEADS = [
    {
        "platform": "reddit",
        "post_url": "https://www.reddit.com/r/SideProject/comments/1r3psn4/i_built_a_free_triangle_of_talent_assessment/",
        "post_text": "I built a free Triangle of Talent assessment. Shaan Puri shared this framework. Would love feedback.",
        "author_handle": "usamaejazch",
        "author_name": "usamaejazch",
        "profile_url": "https://www.reddit.com/user/usamaejazch",
        "post_id": "1r3psn4",
    },
    {
        "platform": "twitter",
        "post_url": "https://twitter.com/PythonTip/status/1849876543210123456",
        "post_text": "Just launched our new small business tool. Looking for feedback from other founders.",
        "author_handle": "PythonTip",
        "author_name": "Python Tip",
        "profile_url": "https://twitter.com/PythonTip",
        "post_id": "1849876543210123456",
    },
    {
        "platform": "instagram",
        "post_url": "https://www.instagram.com/p/C5abc123/",
        "post_text": "Grand opening of our new cafe this weekend! Come visit us.",
        "author_handle": "example_cafe",
        "author_name": "Example Cafe",
        "profile_url": "https://www.instagram.com/example_cafe/",
        "post_id": "C5abc123",
    },
    {
        "platform": "facebook",
        "post_url": "https://www.facebook.com/share/p/1234567890/",
        "post_text": "We just opened our new law practice. Excited to serve the community.",
        "author_handle": "examplelaw",
        "author_name": "Example Law",
        "profile_url": "https://www.facebook.com/examplelaw",
        "post_id": "1234567890",
    },
    {
        "platform": "linkedin",
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7123456789/",
        "post_text": "Proud to announce the launch of our consulting firm. New beginnings.",
        "author_handle": "john-doe",
        "author_name": "John Doe",
        "profile_url": "https://www.linkedin.com/in/john-doe/",
        "post_id": "7123456789",
    },
]


def build_lead(entry: dict) -> CanonicalLead:
    lead_id = hashlib.sha256(f"{entry['platform']}_{entry['post_url']}".encode()).hexdigest()
    return CanonicalLead(
        id=lead_id,
        platform=entry["platform"],
        post_id=entry.get("post_id", "unknown"),
        post_text=entry.get("post_text", ""),
        author=Author(
            name=entry.get("author_name", ""),
            handle=entry.get("author_handle", ""),
            profile_url=entry.get("profile_url"),
        ),
        post_url=entry["post_url"],
        timestamp=datetime.now(timezone.utc),
        keywords_matched=[],
        static_score=70,
        ai_score=0.85,
        status="qualified",
    )


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


def run_one_platform(lead: CanonicalLead, db) -> dict:
    """Run full pipeline for one lead. Return result dict with keys: success, error, and all step outputs."""
    out = {
        "platform": lead.platform,
        "post_url": lead.post_url,
        "success": False,
        "error": None,
        "full_post_fetch": None,
        "research": None,
        "profile_fetch": None,
        "contact": None,
        "email": None,
    }
    try:
        from pipeline.full_post_fetch import fetch_full_post
        from pipeline.business_research import research_lead
        from pipeline.profile_enrichment import enrich_lead_profile
        from pipeline.contact_discovery import get_contact_for_lead
        from pipeline.email_personalization import generate_email
        from pipeline.llm_client import has_llm_config

        # 1) Full post fetch
        post_fetch = fetch_full_post(lead, db)
        full_post_text = post_fetch.get("full_post_text", "")
        out["full_post_fetch"] = {
            "from_cache": post_fetch.get("from_cache", False),
            "length": len(full_post_text),
            "preview": full_post_text[:300] if full_post_text else "",
        }

        # 2) Research
        research = research_lead(lead.post_text or "", full_post_text)
        out["research"] = research

        # 3) Profile fetch
        profile_data = enrich_lead_profile(lead, db)
        out["profile_fetch"] = {
            "from_cache": profile_data.get("from_cache", False),
            "profile_url": profile_data.get("profile_url", ""),
            "profile_text_length": len(profile_data.get("profile_text") or ""),
            "profile_text_preview": (profile_data.get("profile_text") or "")[:200],
        }

        # 4) Contact
        to_email = get_contact_for_lead(lead, profile_data)
        if to_email:
            contact_method, contact_value = "email", to_email
        else:
            profile_url = profile_data.get("profile_url") or (lead.author.profile_url if lead.author else None)
            if profile_url:
                contact_method, contact_value = "profile", profile_url
            else:
                contact_method, contact_value = "post", lead.post_url or ""
        out["contact"] = {"method": contact_method, "value": contact_value}

        # 5) Email
        if has_llm_config():
            email_payload = generate_email(
                lead,
                profile_data=profile_data,
                full_post_text=full_post_text,
                business_type=research.get("business_type", ""),
                suggested_offers=research.get("suggested_offers"),
            )
            if email_payload:
                out["email"] = {
                    "subject": email_payload.get("subject", ""),
                    "bodyText": email_payload.get("bodyText", ""),
                    "bodyHtml": email_payload.get("bodyHtml", ""),
                }
            else:
                out["email"] = None
        else:
            out["email"] = None

        out["success"] = True
    except Exception as e:
        out["error"] = str(e)
        out["traceback"] = traceback.format_exc()
    return out


def main():
    print("=" * 60)
    print("ALL PLATFORMS TEST (Reddit, Twitter, Instagram, Facebook, LinkedIn)")
    print("=" * 60)
    db = get_db()
    if db is not None:
        print("[DB] MongoDB connected.")
    else:
        print("[DB] No MongoDB; cache skipped.")
    print()

    results = []
    for i, entry in enumerate(PLATFORM_LEADS, 1):
        platform = entry["platform"]
        print(f"[{i}/5] {platform.upper()} ... ", end="", flush=True)
        lead = build_lead(entry)
        r = run_one_platform(lead, db)
        results.append(r)
        if r.get("error"):
            print(f"ERROR: {r['error'][:60]}")
        else:
            pf = r.get("full_post_fetch") or {}
            contact = r.get("contact") or {}
            print(f"post_len={pf.get('length', 0)}, contact={contact.get('method', '?')}={str(contact.get('value', ''))[:40]}...")
    print()

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "all_platforms_test_result.json"
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "platforms_tested": 5,
        "success_count": sum(1 for r in results if r.get("success")),
        "results": results,
        "platform_notes": {
            "reddit": "Full post and profile often work with residential proxy. Pipeline uses post_text when fetch empty.",
            "twitter": "Post/profile may return JS-disabled page (HTML only). Pipeline still uses lead.post_text for research and email.",
            "instagram": "Often returns login wall or 0 content without auth. Use lead.post_text; contact = profile URL for DM.",
            "facebook": "Fake or invalid URLs return 400. Real posts may need auth. Contact = profile URL.",
            "linkedin": "Often returns 999/502 (anti-scrape). Use lead.post_text; contact = profile URL.",
        },
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Results saved to: {out_file}")
    print()
    print("Summary:")
    for r in results:
        status = "OK" if r.get("success") else f"FAIL: {r.get('error', '')[:50]}"
        print(f"  {r['platform']}: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
