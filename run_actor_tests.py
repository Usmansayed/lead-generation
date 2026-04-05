#!/usr/bin/env python3
"""Run and test all 15 deployed Apify actors via the API."""
import json
import sys
import time
from apify_client import ApifyClient

TOKEN = os.environ["APIFY_TOKEN"]

ACTOR_TESTS = {
    "stackoverflow-lead-scraper": {
        "keywords": ["looking for developer", "need help building"],
        "tags": ["python", "javascript"],
        "maxQuestions": 10,
    },
    "hackernews-lead-scraper": {
        "keywords": ["hiring", "looking for", "need developer"],
        "maxItems": 10,
    },
    "github-lead-scraper": {
        "keywords": ["help wanted", "bounty"],
        "maxItems": 10,
    },
    "devto-lead-scraper": {
        "keywords": ["hiring", "startup", "developer"],
    },
    "freelancer-lead-scraper": {
        "keywords": ["python developer", "web development"],
        "maxJobs": 10,
    },
    "reddit-lead-scraper": {
        "subreddits": ["Entrepreneur", "startups"],
        "keywords": ["looking for developer", "hiring"],
        "maxPosts": 10,
    },
    "medium-lead-scraper": {
        "keywords": ["startup hiring", "developer"],
    },
    "indiehackers-lead-scraper": {
        "keywords": ["cofounder", "developer needed"],
        "maxResults": 10,
    },
    "producthunt-lead-scraper": {
        "keywords": ["developer tool", "saas"],
        "maxPosts": 10,
    },
    "linkedin-lead-scraper": {
        "keywords": ["hiring developer", "startup hiring"],
        "maxResults": 10,
    },
    "twitter-lead-scraper": {
        "keywords": ["hiring developer"],
        "maxResults": 10,
    },
    "quora-lead-scraper": {
        "keywords": ["hire developer"],
        "maxResults": 10,
    },
    "upwork-lead-scraper": {
        "keywords": ["python developer"],
        "maxResults": 10,
    },
    "angellist-lead-scraper": {
        "keywords": ["software engineer"],
        "maxResults": 10,
    },
    "craigslist-lead-scraper": {
        "keywords": ["web developer"],
        "cities": ["newyork", "sfbay"],
        "maxResults": 10,
    },
}


def main():
    client = ApifyClient(TOKEN)
    me = client.user("me").get()
    username = me.get("username", "unknown")
    print(f"Connected as: {username}")

    # Get list of actors
    actors = client.actors().list().items
    actor_map = {a["name"]: a["id"] for a in actors}
    print(f"Found {len(actor_map)} actors on account")

    # Determine which actors to test
    to_test = sys.argv[1:] if len(sys.argv) > 1 else list(ACTOR_TESTS.keys())
    print(f"Testing {len(to_test)} actors\n")

    results = {}

    for i, name in enumerate(to_test, 1):
        if name not in actor_map:
            print(f"[{i}/{len(to_test)}] {name}: NOT FOUND on Apify")
            results[name] = {"status": "NOT_FOUND", "leads": 0, "hq": 0}
            continue

        actor_id = actor_map[name]
        test_input = ACTOR_TESTS.get(name, {})
        print(f"[{i}/{len(to_test)}] {name} ({actor_id})...")

        try:
            run = client.actor(actor_id).call(
                run_input=test_input,
                timeout_secs=180,
                memory_mbytes=1024,
            )

            status = run.get("status", "UNKNOWN")
            dataset_id = run.get("defaultDatasetId", "")
            items = list(client.dataset(dataset_id).iterate_items()) if dataset_id else []
            hq = sum(1 for item in items if item.get("quality_score", 0) >= 40)

            # Get last part of log for errors
            run_id = run.get("id", "")
            error_msg = ""
            if status != "SUCCEEDED" and run_id:
                try:
                    log = client.run(run_id).get_log() or ""
                    lines = log.strip().split("\n")
                    error_lines = [l for l in lines[-20:] if "error" in l.lower() or "traceback" in l.lower() or "failed" in l.lower()]
                    error_msg = error_lines[-1][:120] if error_lines else lines[-1][:120] if lines else ""
                except Exception:
                    pass

            results[name] = {"status": status, "leads": len(items), "hq": hq, "error": error_msg}
            tag = "OK" if status == "SUCCEEDED" and items else "WARN" if status == "SUCCEEDED" else "FAIL"
            err_detail = f" | {error_msg}" if error_msg else ""
            print(f"  [{tag}] {status} - {len(items)} leads ({hq} HQ){err_detail}")

            # Print sample lead titles
            for item in items[:2]:
                title = item.get("title", item.get("name", ""))[:60]
                qs = item.get("quality_score", 0)
                print(f"    - {title} (Q:{qs})")

        except Exception as e:
            results[name] = {"status": "ERROR", "leads": 0, "hq": 0, "error": str(e)[:120]}
            print(f"  [ERR] {str(e)[:100]}")

        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    ok = warn = fail = 0
    total_leads = total_hq = 0
    for name, r in results.items():
        s = r["status"]
        leads = r["leads"]
        hq = r["hq"]
        err = r.get("error", "")
        total_leads += leads
        total_hq += hq
        if s == "SUCCEEDED" and leads > 0:
            ok += 1
            tag = "OK  "
        elif s == "SUCCEEDED":
            warn += 1
            tag = "WARN"
        else:
            fail += 1
            tag = "FAIL"
        err_str = f" | {err[:50]}" if err else ""
        print(f"  [{tag}] {name}: {s} ({leads} leads, {hq} HQ){err_str}")

    print(f"\nResults: {ok} OK / {warn} WARN / {fail} FAIL")
    print(f"Total: {total_leads} leads ({total_hq} high-quality)")

    # Save JSON results
    with open("actor_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to actor_test_results.json")


if __name__ == "__main__":
    main()
