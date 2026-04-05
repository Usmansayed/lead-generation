#!/usr/bin/env python3
"""
Run after start.bat / start_all.py to verify API, MongoDB, and dashboard are working.
Usage: python scripts/check_services.py [--wait 15] [--api-url http://localhost:8000]
Exit code: 0 if all checks pass, 1 otherwise.
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.request
import urllib.error

# Defaults
DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_DASHBOARD_URL = "http://localhost:3000"
DEFAULT_WAIT_SEC = 12


def check(url: str, timeout: float = 10) -> tuple[bool, str]:
    """GET url; return (success, message)."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code = r.getcode()
            if code == 200:
                return True, f"OK ({code})"
            return False, f"unexpected status {code}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, str(e.reason) if getattr(e, "reason", None) else str(e)
    except Exception as e:
        return False, str(e)


def get_json(url: str, timeout: float = 10) -> tuple[bool, dict | None, str]:
    """GET url, parse JSON; return (success, data or None, error_message)."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            import json
            data = json.loads(r.read().decode())
            return True, data, ""
    except urllib.error.HTTPError as e:
        return False, None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, None, str(e.reason) if getattr(e, "reason", None) else str(e)
    except Exception as e:
        return False, None, str(e)


def main() -> int:
    ap = argparse.ArgumentParser(description="Check API, MongoDB, and dashboard after start.bat")
    ap.add_argument("--wait", type=int, default=DEFAULT_WAIT_SEC, help="Seconds to wait for services to be ready")
    ap.add_argument("--api-url", default=DEFAULT_API_URL, help="API base URL")
    ap.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL, help="Dashboard URL")
    ap.add_argument("--skip-dashboard", action="store_true", help="Do not check dashboard")
    args = ap.parse_args()

    api = args.api_url.rstrip("/")
    dashboard = args.dashboard_url.rstrip("/")

    print("[check_services] Waiting {}s for services to start...".format(args.wait))
    time.sleep(args.wait)

    failed: list[str] = []
    passed: list[str] = []

    # 1. API health
    ok, data, err = get_json(f"{api}/api/health", timeout=15)
    if not ok:
        failed.append("API health: " + err)
    else:
        if data and data.get("ok") is True:
            passed.append("API health: OK (MongoDB connected)")
        else:
            failed.append("API health: MongoDB not connected (ok=false)")

    # 2. API stats (requires MongoDB)
    ok, data, err = get_json(f"{api}/api/stats", timeout=10)
    if not ok:
        failed.append("API stats: " + err)
    else:
        passed.append("API stats: OK")

    # 3. API jobs list
    ok, data, err = get_json(f"{api}/api/jobs?limit=1", timeout=10)
    if not ok:
        failed.append("API jobs: " + err)
    else:
        passed.append("API jobs: OK")

    # 4. Dashboard (optional)
    if not args.skip_dashboard:
        ok, msg = check(dashboard, timeout=10)
        if ok:
            passed.append("Dashboard: OK")
        else:
            failed.append("Dashboard: " + msg)

    # Summary
    print()
    for s in passed:
        print("  [PASS]", s)
    for s in failed:
        print("  [FAIL]", s)
    print()

    if failed:
        print("[check_services] Some checks failed. Fix the issues above and restart.")
        return 1
    print("[check_services] All checks passed. Everything is working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
