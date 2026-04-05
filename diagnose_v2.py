"""Diagnostic script to pull Apify run logs for failing actors."""
import os
import httpx
import sys

TOKEN = os.environ["APIFY_TOKEN"]
base = "https://api.apify.com/v2"
headers = {"Authorization": f"Bearer {TOKEN}"}

r = httpx.get(f"{base}/acts", headers=headers, params={"limit": 50})
actors = {a["name"]: a["id"] for a in r.json()["data"]["items"]}

failing = [
    "twitter-lead-scraper",
    "quora-lead-scraper",
    "upwork-lead-scraper",
    "craigslist-lead-scraper",
    "indiehackers-lead-scraper",
    "medium-lead-scraper",
]

for name in failing:
    if name not in actors:
        print(f"=== {name}: NOT FOUND ===")
        continue
    aid = actors[name]
    r = httpx.get(f"{base}/acts/{aid}/runs", headers=headers, params={"limit": 1})
    runs = r.json().get("data", {}).get("items", [])
    if not runs:
        continue
    run = runs[0]
    rid = run["id"]
    status = run["status"]
    mem = run.get("options", {}).get("memoryMbytes", "N/A")
    print(f"--- {name} | {status} | {mem}MB ---")

    r2 = httpx.get(
        f"{base}/actor-runs/{rid}/log",
        headers=headers,
        params={"format": "text"},
    )
    if r2.status_code == 200:
        lines = r2.text.strip().split("\n")
        print(f"  Total log lines: {len(lines)}")
        # Get error-related lines
        err_lines = [
            l
            for l in lines
            if any(
                kw in l.lower()
                for kw in ["error", "traceback", "exception", "failed", "blocked", "captcha", "forbidden"]
            )
        ]
        print(f"  Error lines: {len(err_lines)}")
        for el in err_lines[-5:]:
            safe = el[:180].encode("ascii", "replace").decode()
            print(f"  ERR: {safe}")
        print("  LAST 10:")
        for l in lines[-10:]:
            safe = l[:180].encode("ascii", "replace").decode()
            print(f"  > {safe}")
    print()
