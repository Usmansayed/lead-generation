#!/usr/bin/env python3
"""Run and test all 15 deployed Apify actors via the API with FULL resources."""
import json
import sys
import time
from apify_client import ApifyClient

TOKEN = os.environ["APIFY_TOKEN"]

ACTOR_TESTS = {
    # Previously Failing Actors (Priority)
    "linkedin-lead-scraper": {
        "keywords": ["hiring python developer", "startup looking for cto"],
        "maxResults": 15,
    },
    "twitter-lead-scraper": {
        "keywords": ["hiring python developer"],
        "maxResults": 15,
    },
    "quora-lead-scraper": {
        "keywords": ["hiring developer"],
        "maxResults": 15,
    },
    "upwork-lead-scraper": {
        "keywords": ["python developer"],
        "maxResults": 15,
    },
    "craigslist-lead-scraper": {
        "keywords": ["web developer"],
        "cities": ["newyork", "sfbay", "austin"],
        "maxResults": 15,
    },
    "indiehackers-lead-scraper": {
        "keywords": ["cofounder", "developer needed"],
        "maxResults": 15,
    },
    
    # Previously Working Actors (Regression Test)
    "stackoverflow-lead-scraper": {"keywords": ["looking for developer"], "maxQuestions": 5},
    "hackernews-lead-scraper": {"keywords": ["hiring"], "maxItems": 5},
    "github-lead-scraper": {"keywords": ["help wanted"], "maxItems": 5},
    "devto-lead-scraper": {"keywords": ["hiring"], "maxResults": 5},
    "freelancer-lead-scraper": {"keywords": ["python"], "maxJobs": 5},
    "reddit-lead-scraper": {"subreddits": ["forhire"], "keywords": ["hiring"], "maxPosts": 5},
    "medium-lead-scraper": {"keywords": ["startup hiring"], "maxResults": 5},
    "producthunt-lead-scraper": {"keywords": ["developer tool"], "maxPosts": 5},
    "angellist-lead-scraper": {"keywords": ["software engineer"], "maxResults": 5},
}


def main():
    client = ApifyClient(TOKEN)
    print(f"🚀 Starting Full Verification Suite (Memory: 4096MB, Timeout: 300s)...")
    
    # Get list of actors
    actors = client.actors().list().items
    actor_map = {a["name"]: a["id"] for a in actors}
    
    to_test = sys.argv[1:] if len(sys.argv) > 1 else list(ACTOR_TESTS.keys())
    results = {}

    for i, name in enumerate(to_test, 1):
        if name not in actor_map:
            print(f"[{i}/{len(to_test)}] {name}: NOT FOUND")
            continue

        actor_id = actor_map[name]
        test_input = ACTOR_TESTS.get(name, {})
        print(f"[{i}/{len(to_test)}] testing {name}...", end=" ", flush=True)

        try:
            # Run with FULL resources
            run = client.actor(actor_id).call(
                run_input=test_input,
                timeout_secs=300,
                memory_mbytes=4096,  # 4GB Memory
                wait_secs=300,
            )

            status = run.get("status", "UNKNOWN")
            dataset_id = run.get("defaultDatasetId", "")
            items = list(client.dataset(dataset_id).iterate_items()) if dataset_id else []
            hq = sum(1 for item in items if item.get("quality_score", 0) >= 40)
            
            tag = "✅ PASS" if status == "SUCCEEDED" and len(items) > 0 else "❌ FAIL"
            print(f"{tag} ({len(items)} leads, {hq} HQ)")
            
            # Print error if failed
            if status != "SUCCEEDED" or len(items) == 0:
                run_id = run.get("id")
                try:
                    log = client.run(run_id).get_log() or ""
                    print(f"    Run ID: {run_id}")
                    # Print last error lines
                    lines = log.strip().split("\n")
                    errs = [l for l in lines if "error" in l.lower() or "warn" in l.lower()]
                    for e in errs[-3:]:
                        print(f"    Log: {e[:120]}")
                except:
                    pass

            results[name] = {
                "status": status,
                "leads": len(items),
                "hq": hq,
                "datasetId": dataset_id
            }

        except Exception as e:
            print(f"❌ ERR: {e}")
            results[name] = {"status": "ERROR", "error": str(e)}

    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    total_leads = 0
    passed = []
    failed = []
    
    for name, r in results.items():
        leads = r.get("leads", 0)
        total_leads += leads
        status = r.get("status")
        if status == "SUCCEEDED" and leads > 0:
            passed.append(name)
            print(f"✅ {name:<30} | {leads:>3} leads | {r.get('hq', 0):>2} HQ")
        else:
            failed.append(name)
            print(f"❌ {name:<30} | {leads:>3} leads | Status: {status}")

    print("-" * 60)
    print(f"Total Leads Generated: {total_leads}")
    print(f"Passed: {len(passed)}/{len(to_test)}")
    print(f"Failed: {len(failed)}/{len(to_test)}")
    
    # Save results
    with open("final_verification_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
