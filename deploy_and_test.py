#!/usr/bin/env python3
"""
Deploy & Test All 15 Apify Actors
Pushes source code to Apify platform and runs each actor with test inputs.
"""
import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Optional
from apify_client import ApifyClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Prefer APIFY_TOKEN from .env; fallback for CI/CLI
TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
USERNAME = os.environ.get("APIFY_USERNAME", "brilliant_quince")

ACTORS_DIR = Path(__file__).parent / "services" / "apify-actors"

# Actor configs: folder name -> (display name, test input)
ACTOR_CONFIGS = {
    "reddit-lead-scraper": {
        "name": "Reddit Lead Scraper",
        "input": {
            "subreddits": ["Entrepreneur", "startups", "SaaS"],
            "keywords": ["looking for developer", "need help building", "hiring"],
            "maxPosts": 15,
        },
    },
    "hackernews-lead-scraper": {
        "name": "HackerNews Lead Scraper",
        "input": {
            "keywords": ["hiring", "looking for", "need developer"],
            "maxItems": 15,
        },
    },
    "freelancer-lead-scraper": {
        "name": "Freelancer Lead Scraper",
        "input": {
            "keywords": ["python developer", "web development", "react"],
            "maxJobs": 15,
        },
    },
    "github-lead-scraper": {
        "name": "GitHub Lead Scraper",
        "input": {
            "keywords": ["help wanted", "looking for contributor", "bounty"],
            "maxItems": 15,
        },
    },
    "stackoverflow-lead-scraper": {
        "name": "Stack Overflow Lead Scraper",
        "input": {
            "keywords": ["looking for developer", "need help building", "hiring"],
            "tags": ["python", "javascript"],
            "maxQuestions": 15,
        },
    },
    "devto-lead-scraper": {
        "name": "Dev.to Lead Scraper",
        "input": {
            "keywords": ["hiring", "startup", "developer"],
        },
    },
    "medium-lead-scraper": {
        "name": "Medium Lead Scraper",
        "input": {
            "keywords": ["startup hiring", "developer opportunity"],
        },
    },
    "indiehackers-lead-scraper": {
        "name": "Indie Hackers Lead Scraper",
        "input": {
            "keywords": ["cofounder", "developer needed", "hiring"],
            "maxResults": 15,
        },
    },
    "producthunt-lead-scraper": {
        "name": "Product Hunt Lead Scraper",
        "input": {
            "keywords": ["developer tool", "saas", "api"],
            "maxPosts": 15,
        },
    },
    "linkedin-lead-scraper": {
        "name": "LinkedIn Lead Scraper",
        "input": {
            "keywords": ["hiring developer", "startup hiring"],
            "maxResults": 15,
        },
    },
    "twitter-lead-scraper": {
        "name": "Twitter/X Lead Scraper",
        "input": {
            "keywords": ["hiring developer", "looking for engineer"],
            "maxResults": 15,
        },
    },
    "instagram-lead-scraper": {
        "name": "Instagram Lead Scraper",
        "input": {
            "keywords": ["hiring developer", "looking for engineer"],
            "maxResults": 15,
        },
    },
    "facebook-lead-scraper": {
        "name": "Facebook Lead Scraper",
        "input": {
            "keywords": ["hiring developer", "looking for engineer"],
            "maxResults": 15,
        },
    },
    "quora-lead-scraper": {
        "name": "Quora Lead Scraper",
        "input": {
            "keywords": ["hire developer", "find freelancer"],
            "maxResults": 15,
        },
    },
    "upwork-lead-scraper": {
        "name": "Upwork Lead Scraper",
        "input": {
            "keywords": ["python developer", "react developer"],
            "maxResults": 15,
        },
    },
    "angellist-lead-scraper": {
        "name": "AngelList/YC Lead Scraper",
        "input": {
            "keywords": ["software engineer", "founding engineer"],
            "maxResults": 15,
        },
    },
    "post-content-fetcher": {
        "name": "Post Content Fetcher",
        "input": {
            "url": "https://example.com",
            "useProxy": False,
        },
    },
}


def get_or_create_actor(client: ApifyClient, actor_name: str, folder_name: str) -> str:
    """Get existing actor ID or create a new one. Returns actor ID."""
    # List existing actors
    actors = client.actors().list().items
    full_name = f"{USERNAME}/{folder_name}"
    
    for actor in actors:
        if actor.get("name") == folder_name:
            print(f"  [FOUND] Existing actor: {actor['id']}")
            return actor["id"]
    
    # Create new actor
    print(f"  [CREATE] Actor: {folder_name}")
    try:
        new_actor = client.actors().create(
            name=folder_name,
            title=actor_name,
            is_public=False,
            default_run_options={
                "build": "latest",
                "memory_mbytes": 1024,
                "timeout_secs": 300,
            },
        )
    except TypeError:
        new_actor = client.actors().create(
            name=folder_name,
            title=actor_name,
            is_public=False,
        )
    print(f"  [OK] Created: {new_actor['id']}")
    return new_actor["id"]


def push_actor(folder_name: str) -> bool:
    """Push actor source code to Apify using CLI."""
    actor_dir = ACTORS_DIR / folder_name
    if not actor_dir.exists():
        print(f"  [ERR] Directory not found: {actor_dir}")
        return False

    def find_apify_cli() -> Optional[str]:
        apify_cmd = shutil.which("apify")
        if apify_cmd:
            return apify_cmd
        if os.name == "nt":
            appdata = os.environ.get("APPDATA", "")
            for candidate in ("apify.cmd", "apify-cli.cmd"):
                path = Path(appdata) / "npm" / candidate
                if path.exists():
                    return str(path)
        return None

    apify_cmd = find_apify_cli()
    if not apify_cmd:
        print("  [ERR] Apify CLI not found in PATH or APPDATA\\npm.")
        return False

    import subprocess
    result = subprocess.run(
        [apify_cmd, "push"],
        cwd=str(actor_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    
    if result.returncode == 0:
        print("  [OK] Pushed successfully")
        return True
    else:
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        if "Skipping push" in output and "Use --force" in output:
            force_result = subprocess.run(
                [apify_cmd, "push", "--force"],
                cwd=str(actor_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            if force_result.returncode == 0:
                print("  [OK] Pushed successfully (forced)")
                return True
            print("  [WARN] Forced push failed")
            print(f"     stderr: {force_result.stderr[:200]}")
            return False

        # Check if it needs init first
        print("  [WARN] Push failed, trying with actor init first...")
        print(f"     stderr: {result.stderr[:200]}")
        return False


def run_actor_test(client: ApifyClient, actor_id: str, test_input: dict, actor_name: str) -> dict:
    """Run an actor and wait for results."""
    print(f"  [RUN] {actor_name}...")

    def wait_for_latest_build(timeout_secs: int = 240, poll_secs: int = 5) -> str | None:
        start = time.time()
        build_triggered = False
        while time.time() - start < timeout_secs:
            try:
                builds = client.actor(actor_id).builds().list(limit=1).items
                if builds:
                    build = builds[0]
                    status = build.get("status")
                    if status == "SUCCEEDED":
                        return build.get("id")
                    if status in ("FAILED", "ABORTED"):
                        return None
                else:
                    if not build_triggered:
                        try:
                            client.actor(actor_id).build()
                            build_triggered = True
                        except Exception:
                            pass
            except Exception:
                pass
            time.sleep(poll_secs)
        return None

    for attempt in range(2):
        try:
            run = client.actor(actor_id).call(
                run_input=test_input,
                timeout_secs=180,
                memory_mbytes=1024,
            )

            status = run.get("status", "UNKNOWN")

            # Get dataset items
            dataset_id = run.get("defaultDatasetId", "")
            items = []
            if dataset_id:
                items = list(client.dataset(dataset_id).iterate_items())

            # Get log
            log = ""
            run_id = run.get("id", "")
            if run_id:
                try:
                    log = client.run(run_id).get_log()
                    if log and len(log) > 1000:
                        log = log[-1000:]  # Last 1000 chars
                except:
                    pass

            result = {
                "status": status,
                "leads_found": len(items),
                "high_quality": sum(1 for i in items if i.get("quality_score", 0) >= 40),
                "sample_leads": items[:3],
                "run_id": run_id,
                "log_tail": log,
                "error": None,
            }

            if status == "SUCCEEDED":
                print(f"  [OK] {status} - {len(items)} leads ({result['high_quality']} HQ)")
            else:
                print(f"  [FAIL] {status}")
                if log:
                    # Extract error from log
                    for line in log.split("\n"):
                        if "error" in line.lower():
                            result["error"] = line.strip()
                            break

            return result
        except Exception as e:
            if "Build with tag" in str(e) and attempt == 0:
                print("  [WAIT] Build not ready, waiting for build to finish...")
                build_id = wait_for_latest_build()
                if build_id:
                    try:
                        run = client.actor(actor_id).call(
                            run_input=test_input,
                            timeout_secs=180,
                            memory_mbytes=1024,
                            build=build_id,
                        )

                        status = run.get("status", "UNKNOWN")

                        dataset_id = run.get("defaultDatasetId", "")
                        items = []
                        if dataset_id:
                            items = list(client.dataset(dataset_id).iterate_items())

                        log = ""
                        run_id = run.get("id", "")
                        if run_id:
                            try:
                                log = client.run(run_id).get_log()
                                if log and len(log) > 1000:
                                    log = log[-1000:]
                            except:
                                pass

                        result = {
                            "status": status,
                            "leads_found": len(items),
                            "high_quality": sum(1 for i in items if i.get("quality_score", 0) >= 40),
                            "sample_leads": items[:3],
                            "run_id": run_id,
                            "log_tail": log,
                            "error": None,
                        }

                        if status == "SUCCEEDED":
                            print(f"  [OK] {status} - {len(items)} leads ({result['high_quality']} HQ)")
                        else:
                            print(f"  [FAIL] {status}")
                            if log:
                                for line in log.split("\n"):
                                    if "error" in line.lower():
                                        result["error"] = line.strip()
                                        break

                        return result
                    except Exception:
                        pass
                else:
                    continue
            print(f"  [ERR] Error: {e}")
            return {
                "status": "ERROR",
                "leads_found": 0,
                "high_quality": 0,
                "sample_leads": [],
                "run_id": "",
                "log_tail": "",
                "error": str(e),
            }


def main():
    print("=" * 80)
    print("APIFY ACTOR DEPLOYMENT & TESTING")
    print("=" * 80)
    
    client = ApifyClient(TOKEN)
    
    # Verify connection
    try:
        me = client.user("me").get()
        print(f"[OK] Connected as: {me.get('username', 'unknown')}")
    except Exception as e:
        print(f"[ERR] Failed to connect: {e}")
        sys.exit(1)
    
    # Check which actors to test
    actors_to_test = sys.argv[1:] if len(sys.argv) > 1 else list(ACTOR_CONFIGS.keys())
    
    print(f"\nTesting {len(actors_to_test)} actors\n")
    
    results = {}
    
    for i, folder_name in enumerate(actors_to_test, 1):
        if folder_name not in ACTOR_CONFIGS:
            print(f"\n[WARN] Unknown actor: {folder_name}")
            continue
            
        config = ACTOR_CONFIGS[folder_name]
        print(f"\n{'='*60}")
        print(f"[{i}/{len(actors_to_test)}] {config['name']}")
        print(f"{'='*60}")
        
        # Step 1: Get or create actor
        try:
            actor_id = get_or_create_actor(client, config["name"], folder_name)
        except Exception as e:
            print(f"  [ERR] Failed to get/create actor: {e}")
            results[folder_name] = {"status": "SETUP_ERROR", "error": str(e), "leads_found": 0, "high_quality": 0}
            continue
        
        # Step 2: Push source code
        pushed = push_actor(folder_name)
        if not pushed:
            print("  [WARN] Push may have failed, trying to run anyway...")
        
        # Wait for build
        print("  [WAIT] Waiting for build...")
        time.sleep(10)
        
        # Step 3: Run test
        result = run_actor_test(client, actor_id, config["input"], config["name"])
        results[folder_name] = result
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)
    
    succeeded = failed = errored = 0
    total_leads = total_hq = 0
    
    for name, result in results.items():
        status = result["status"]
        leads = result["leads_found"]
        hq = result["high_quality"]
        
        if status == "SUCCEEDED" and leads > 0:
            icon = "[OK]"
            succeeded += 1
        elif status == "SUCCEEDED":
            icon = "[WARN]"
            succeeded += 1
        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
            icon = "[FAIL]"
            failed += 1
        else:
            icon = "[ERR]"
            errored += 1
        
        total_leads += leads
        total_hq += hq
        
        display_name = ACTOR_CONFIGS.get(name, {}).get("name", name)
        error_msg = f" - {result.get('error', '')[:60]}" if result.get("error") else ""
        print(f"  {icon} {display_name}: {status} ({leads} leads, {hq} HQ){error_msg}")
    
    print("\nTotals:")
    print(f"   [OK] Succeeded: {succeeded}/{len(results)}")
    print(f"   [FAIL] Failed: {failed}/{len(results)}")
    print(f"   [ERR] Errors: {errored}/{len(results)}")
    print(f"   [SUM] Total leads: {total_leads} ({total_hq} high-quality)")
    
    # Save results
    report_file = Path(__file__).parent / "actor_test_results.json"
    with open(report_file, "w") as f:
        # Remove non-serializable items
        clean_results = {}
        for k, v in results.items():
            clean_results[k] = {kk: vv for kk, vv in v.items() if kk != "sample_leads"}
            clean_results[k]["sample_count"] = len(v.get("sample_leads", []))
        json.dump(clean_results, f, indent=2, default=str)
    print(f"\nFull results saved to: {report_file}")


if __name__ == "__main__":
    main()
