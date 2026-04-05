#!/usr/bin/env python3
"""
Run the email detective on a text snippet (e.g. company tagline or post).
Usage: python scripts/find_email_from_snippet.py "Your snippet here"
       python scripts/find_email_from_snippet.py --verbose "Your snippet"
Or edit SNIPPET below and run without args.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# Default snippet (or pass as first arg)
SNIPPET = """SOFTWARE
ENGINEERED
FOR GROWTH
We design and build products that earn trust before revenue. From research to release, every decision is intentional."""


def main():
    args = [a for a in sys.argv[1:] if a != "--verbose" and not a.startswith("-")]
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    snippet = args[0].strip() if args else SNIPPET.strip()
    if not snippet:
        print("Provide a snippet as first argument or edit SNIPPET in the script.")
        return 1

    lead = {
        "postText": snippet,
        "platform": "snippet",
        "author": {"handle": "", "name": ""},
    }

    print("Running email detective on snippet:")
    print("-" * 50)
    print(snippet[:500])
    print("-" * 50)

    from pipeline.email_research import (
        has_email_research_config,
        _extract_lead_intelligence,
        _discover_domain,
        _build_search_plan,
        _run_searches,
        _scrape_company_emails,
        _build_evidence_bundle,
        _detective_verdict,
    )

    if not has_email_research_config():
        print("Web search not available (install duckduckgo-search or set TAVILY_API_KEY).")
        return 1

    post_text = snippet
    profile_text = ""
    web_context = ""
    author_handle = ""
    platform = "snippet"

    # Step 1: Intel
    print("\n[1] Extracting intelligence...")
    intel = _extract_lead_intelligence(post_text, profile_text, web_context, author_handle, platform)
    if verbose:
        for k, v in intel.items():
            if v:
                print(f"    {k}: {v}")

    # Step 2: Domain
    domain = _discover_domain(intel, post_text, profile_text, web_context)
    print(f"    domain: {domain or '(none)'}")

    # Step 3: Search plan + run
    queries = _build_search_plan(intel, domain, author_handle)
    print(f"[2] Running {len(queries)} search queries...")
    if verbose and queries:
        for q in queries[:8]:
            print(f"    - {q[:70]}...")
    search_results = _run_searches(queries)
    search_emails = list({e for e, _ in search_results})
    print(f"    emails from search: {len(search_emails)}")

    # Step 4: Scrape (if domain)
    scraped = []
    if domain:
        print(f"[3] Scraping domain {domain}...")
        scraped = _scrape_company_emails(domain)
        scraped_emails = list({e for e, _ in scraped})
        print(f"    emails from scrape: {len(scraped_emails)}")
    else:
        print("[3] No domain to scrape.")

    all_emails = list({e for e, _ in search_results + scraped})
    if not all_emails:
        print("\nNo emails found from search or scrape. Try adding company name or URL to the snippet.")
        return 0

    # Step 5: Verdict
    evidence = _build_evidence_bundle(intel, search_results, scraped, domain)
    best, suggested = _detective_verdict(evidence, post_text, all_emails)
    if suggested:
        print(f"[4] Detective suggested extra search: {suggested[:60]}...")

    if best:
        print(f"\nFound email: {best}")
    else:
        print(f"\nBest candidate (first of {len(all_emails)}): {all_emails[0]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
