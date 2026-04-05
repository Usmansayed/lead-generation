#!/usr/bin/env python3
"""
Start the API and the dashboard with one command.
Run from project root:  python start_all.py

Starts:
  1. Dashboard API (uvicorn) on http://localhost:8000
  2. Dashboard UI (Vite) on http://localhost:3000

Press Ctrl+C to stop both.

Alternatively: double-click Start.bat (Windows) or run  python start_all.py
First time: ensure deps are installed:
  pip install -r pipeline/requirements.txt
  pip install -r services/api/requirements.txt
  cd services/dashboard && npm install
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def load_dotenv():
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv as _load
            _load(env_file)
        except ImportError:
            pass


def main():
    load_dotenv()
    # Debug: so user sees in start.bat terminal that .env was loaded (pipeline subprocess uses same)
    mongo_set = bool(os.environ.get("MONGODB_URI", "").strip())
    apify_set = bool(os.environ.get("APIFY_TOKEN", "").strip())
    print(f"[start_all] DEBUG .env loaded: MONGODB_URI={'yes' if mongo_set else 'NO'}, APIFY_TOKEN={'yes' if apify_set else 'NO'}")
    api_dir = PROJECT_ROOT / "services" / "api"
    dashboard_dir = PROJECT_ROOT / "services" / "dashboard"

    if not api_dir.is_dir():
        print("Error: services/api not found. Run from project root.")
        sys.exit(1)
    if not dashboard_dir.is_dir():
        print("Error: services/dashboard not found. Run from project root.")
        sys.exit(1)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    # Start API (uvicorn from services/api so db, main, job_runner are found)
    api_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(api_dir),
        env=env,
    )
    print("[start_all] API starting on http://localhost:8000 ...")

    # Start dashboard (npm run dev)
    shell = sys.platform == "win32"
    dash_proc = subprocess.Popen(
        "npm run dev",
        cwd=str(dashboard_dir),
        shell=shell,
        env=env,
    )
    print("[start_all] Dashboard starting on http://localhost:3000 ...")

    # Run service check after a short delay (API and dashboard need time to start)
    check_script = PROJECT_ROOT / "scripts" / "check_services.py"
    if check_script.exists():
        print("[start_all] Waiting for services, then running health check ...")
        time.sleep(2)
        try:
            result = subprocess.run(
                [sys.executable, str(check_script), "--wait", "10"],
                cwd=str(PROJECT_ROOT),
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                timeout=35,
            )
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            if result.returncode != 0:
                print("[start_all] Health check reported issues. See above.")
            else:
                print("[start_all] Health check passed.")
        except subprocess.TimeoutExpired:
            print("[start_all] Health check timed out (services may still be starting).")
        except Exception as e:
            print(f"[start_all] Health check error: {e}")

    def kill_both(sig=None, frame=None):
        api_proc.terminate()
        dash_proc.terminate()
        api_proc.wait(timeout=5)
        dash_proc.wait(timeout=5)
        sys.exit(0)

    signal.signal(signal.SIGINT, kill_both)
    signal.signal(signal.SIGTERM, kill_both)

    print("\n[start_all] Both running. API: http://localhost:8000  Dashboard: http://localhost:3000")
    print("Press Ctrl+C to stop both.\n")

    try:
        api_proc.wait()
    except KeyboardInterrupt:
        pass
    kill_both()


if __name__ == "__main__":
    main()
