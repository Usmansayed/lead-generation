#!/usr/bin/env python3
"""
Run the lead-gen pipeline on a schedule for ongoing internal lead generation (daily or every N hours).
Resilient: one platform failure doesn't stop the run; state is saved incrementally so a crash doesn't lose progress.

Usage:
  python run_continuous.py
  python run_continuous.py --interval-hours 24 --send-email   # daily, with email
  python run_continuous.py --interval-hours 6 --no-email      # every 6h, no email
  python run_continuous.py --interval-hours 24 --max-runs 7  # daily for 1 week (then exit)

Requires: .env with APIFY_TOKEN, MONGODB_URI, and Bedrock (AWS_BEDROCK_API or AWS2_* / CLAUDE_*).
"""
from __future__ import annotations
import argparse
import os
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(
        description="Run pipeline continuously (internal daily lead gen)",
    )
    ap.add_argument("--interval-hours", type=float, default=24.0, help="Hours between runs (default 24 = daily)")
    ap.add_argument("--no-email", action="store_true", help="Skip email queue step")
    ap.add_argument("--send-email", action="store_true", help="Send queued emails after each run (SES)")
    ap.add_argument("--platforms", nargs="*", help="Limit platforms (default: all)")
    ap.add_argument("--ai-limit", type=int, default=100, help="Max leads to AI score per run")
    ap.add_argument("--max-runs", type=int, default=0, help="Stop after N runs (0 = run forever)")
    args = ap.parse_args()

    from pipeline.run_pipeline import main as pipeline_main

    interval_secs = max(60, int(args.interval_hours * 3600))
    pipeline_args = []
    if args.no_email:
        pipeline_args.append("--no-email")
    if args.send_email:
        pipeline_args.append("--send-email")
    if args.platforms:
        pipeline_args += ["--platforms"] + args.platforms
    pipeline_args += ["--ai-limit", str(args.ai_limit)]

    print(f"Pipeline will run every {args.interval_hours}h ({interval_secs}s).")
    if args.max_runs:
        print(f"Will stop after {args.max_runs} runs.")
    print("First run starting now.\n")

    run = 0
    while True:
        run += 1
        print(f"\n--- Run #{run} ---")
        sys.argv = ["run_pipeline"] + pipeline_args
        try:
            code = pipeline_main()
            if code == 0:
                print(f"Run #{run} completed. Next run in {args.interval_hours}h.")
            else:
                print(f"Run #{run} exited with code {code}. Next run in {args.interval_hours}h.")
        except KeyboardInterrupt:
            print("\nStopped by user.")
            return 0
        except Exception as e:
            print(f"Run #{run} error: {e}")
            print(f"Next run in {args.interval_hours}h.")

        if args.max_runs and run >= args.max_runs:
            print(f"Reached max runs ({args.max_runs}). Exiting.")
            return 0
        time.sleep(interval_secs)


if __name__ == "__main__":
    sys.exit(main())
