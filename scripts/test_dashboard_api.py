"""
Quick test for dashboard API: health and stats shape (including pending_filter, qualified_breakdown).
Run from project root. Start API first: cd services/api && uvicorn main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations
import os
import sys

try:
    import requests
except ImportError:
    print("SKIP: requests not installed (pip install requests)")
    sys.exit(0)

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")

def test_health():
    r = requests.get(f"{BASE}/api/health", timeout=5)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "ok" in data
    print("  OK /api/health")

def test_stats():
    r = requests.get(f"{BASE}/api/stats", timeout=5)
    if r.status_code == 503:
        print("  SKIP /api/stats (MongoDB not available)")
        return
    assert r.status_code == 200, r.text
    data = r.json()
    raw = data.get("raw_posts") or {}
    assert "total" in raw
    assert "pending_filter" in raw, "stats should include raw_posts.pending_filter"
    assert "qualified_breakdown" in data, "stats should include qualified_breakdown"
    br = data["qualified_breakdown"]
    for k in ("in_queue_pending", "in_queue_sent", "in_no_email", "to_process"):
        assert k in br, f"qualified_breakdown.{k}"
    print("  OK /api/stats (pending_filter, qualified_breakdown)")

def main():
    print("Dashboard API tests")
    try:
        test_health()
        test_stats()
        print("All passed.")
    except requests.exceptions.ConnectionError:
        print("SKIP: API not running. Start with: cd services/api && uvicorn main:app --port 8000")
        sys.exit(0)
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
