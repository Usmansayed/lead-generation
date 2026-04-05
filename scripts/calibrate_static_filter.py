#!/usr/bin/env python3
"""
Calibrate the static filter using test data with known expected outcomes.

Loads tests/fixtures/calibration_leads.json (50 leads with expected_should_pass),
runs the relevance engine + current threshold, and reports:
  - Accuracy vs expected (true/false positives and negatives)
  - Mismatches (expected pass but failed, or expected fail but passed)
  - Score distribution so you can tune minimum_threshold and filter rules

Run from project root:
  python scripts/calibrate_static_filter.py
  python scripts/calibrate_static_filter.py --threshold 5   # try a different threshold
  python scripts/calibrate_static_filter.py --verbose        # show every lead
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

FIXTURES_DIR = ROOT / "tests" / "fixtures"
CALIBRATION_FILE = FIXTURES_DIR / "calibration_leads.json"


def load_calibration_data() -> list[dict]:
    """Load calibration leads JSON."""
    if not CALIBRATION_FILE.exists():
        print(f"ERROR: Calibration file not found: {CALIBRATION_FILE}")
        sys.exit(1)
    with open(CALIBRATION_FILE, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print("ERROR: calibration_leads.json must be a JSON array")
        sys.exit(1)
    return data


def load_threshold(override: int | None) -> int:
    """Current threshold from static_scoring_rules.yaml or override."""
    if override is not None:
        return override
    try:
        import yaml
        rules_path = ROOT / "config" / "static_scoring_rules.yaml"
        if rules_path.exists():
            with open(rules_path, encoding="utf-8") as f:
                rules = yaml.safe_load(f) or {}
            return int(rules.get("minimum_threshold", 5))
    except Exception:
        pass
    return 5


def main() -> int:
    ap = argparse.ArgumentParser(description="Calibrate static filter with test data")
    ap.add_argument("--threshold", type=int, default=None, help="Override minimum_threshold (default: from config)")
    ap.add_argument("--verbose", "-v", action="store_true", help="Print result for every lead")
    args = ap.parse_args()

    leads = load_calibration_data()
    threshold = load_threshold(args.threshold)

    from pipeline.relevance import compute_relevance

    results = []
    for item in leads:
        lead_id = item.get("id", "?")
        post_text = item.get("post_text", "")
        platform = item.get("platform", "reddit")
        expected = bool(item.get("expected_should_pass", False))
        note = item.get("note", "")

        rel = compute_relevance(post_text, platform, None, None)
        score = rel.get("score", 0)
        passed_relevance = rel.get("passed", False)
        # Static filter: must pass relevance AND score >= threshold
        actual_pass = passed_relevance and score >= threshold
        reject_reason = rel.get("reject_reason")

        results.append({
            "id": lead_id,
            "expected": expected,
            "actual_pass": actual_pass,
            "score": score,
            "passed_relevance": passed_relevance,
            "reject_reason": reject_reason,
            "note": note,
        })

    # Summary
    tp = sum(1 for r in results if r["expected"] and r["actual_pass"])
    tn = sum(1 for r in results if not r["expected"] and not r["actual_pass"])
    fp = sum(1 for r in results if not r["expected"] and r["actual_pass"])
    fn = sum(1 for r in results if r["expected"] and not r["actual_pass"])
    n = len(results)

    print("Static filter calibration")
    print("=" * 60)
    print(f"  Data: {CALIBRATION_FILE} ({n} leads)")
    print(f"  Threshold: {threshold} (from config/static_scoring_rules.yaml)")
    print()
    print("  Expected pass -> Actual pass:  True positives  ", tp)
    print("  Expected fail -> Actual fail:   True negatives  ", tn)
    print("  Expected fail -> Actual pass:  False positives ", fp, "  (noise sent to AI)")
    print("  Expected pass -> Actual fail:  False negatives ", fn, "  (good leads rejected)")
    print()
    if n:
        acc = (tp + tn) / n * 100
        print(f"  Accuracy: {tp + tn}/{n} = {acc:.1f}%")
    print()

    # Mismatches
    false_negatives = [r for r in results if r["expected"] and not r["actual_pass"]]
    false_positives = [r for r in results if not r["expected"] and r["actual_pass"]]

    if false_negatives:
        print("  FALSE NEGATIVES (expected pass, rejected) — consider loosening threshold or adding phrases:")
        for r in false_negatives:
            print(f"    {r['id']}  score={r['score']}  reason={r['reject_reason'] or 'below threshold'}")
            if args.verbose and r.get("note"):
                print(f"      note: {r['note']}")
        print()

    if false_positives:
        print("  FALSE POSITIVES (expected fail, passed) — consider tightening threshold or negative patterns:")
        for r in false_positives:
            print(f"    {r['id']}  score={r['score']}  reason={r['reject_reason'] or 'n/a'}")
            if args.verbose and r.get("note"):
                print(f"      note: {r['note']}")
        print()

    # Score distribution
    scores_pass = [r["score"] for r in results if r["expected"]]
    scores_fail = [r["score"] for r in results if not r["expected"]]
    print("  Score distribution (expected pass vs expected fail):")
    if scores_pass:
        print(f"    Expected pass: min={min(scores_pass)} max={max(scores_pass)} avg={sum(scores_pass)/len(scores_pass):.1f}")
    if scores_fail:
        print(f"    Expected fail: min={min(scores_fail)} max={max(scores_fail)} avg={sum(scores_fail)/len(scores_fail):.1f}")
    print()
    print("  To tune: edit config/static_scoring_rules.yaml (minimum_threshold) and")
    print("          config/filters.yaml (negative_patterns) / config/relevance_keywords.yaml (phrases).")
    print("  Re-run with --threshold N to try a threshold without editing the file.")

    if args.verbose:
        print()
        print("  Per-lead (id, expected, actual_pass, score, reject_reason):")
        for r in results:
            print(f"    {r['id']}  expected={r['expected']}  actual={r['actual_pass']}  score={r['score']}  reason={r['reject_reason']}")

    return 0 if (fp == 0 and fn == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
