#!/usr/bin/env python3
"""
Quick test for post-content-fetcher: resolve by name, run with a URL, print result.
Run from project root. Needs APIFY_TOKEN in .env.
"""
import os
import sys
from pathlib import Path

# Project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def main():
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        print("Set APIFY_TOKEN in .env")
        return 1
    from apify_client import ApifyClient
    client = ApifyClient(token)
    # Resolve by name (same as pipeline)
    actors = client.actors().list().items
    actor_id = None
    for actor in actors:
        if actor.get("name") == "post-content-fetcher":
            actor_id = actor["id"]
            break
    if not actor_id:
        print("Actor 'post-content-fetcher' not found. Deploy it first: python deploy_and_test.py post-content-fetcher")
        return 1
    print(f"Found actor: {actor_id}")
    print("Calling with url=https://example.com, useProxy=False ...")
    run = client.actor(actor_id).call(
        run_input={"url": "https://example.com", "useProxy": False},
        timeout_secs=90,
        memory_mbytes=1024,
    )
    status = run.get("status")
    print(f"Run status: {status}")
    if status != "SUCCEEDED":
        print("Run failed. Check Apify console for logs.")
        return 1
    dataset_id = run.get("defaultDatasetId")
    if not dataset_id:
        print("No dataset")
        return 1
    items = list(client.dataset(dataset_id).iterate_items())
    if not items:
        print("No output items")
        return 1
    first = items[0]
    text = first.get("text") or first.get("content") or ""
    print(f"Output: text length={len(text)}, preview={repr(text[:200])}...")
    if len(text) < 50:
        print("WARN: Very little text extracted")
    else:
        print("OK: post-content-fetcher works.")
    # Write result to output for inspection
    out_dir = Path(__file__).resolve().parent.parent / "output"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "post_content_fetcher_test_result.json"
    import json
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"status": status, "text_length": len(text), "text_preview": text[:500], "full_item": first}, f, indent=2)
    print(f"Result saved to: {out_file}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
