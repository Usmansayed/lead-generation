"""
Pipeline job runner: start pipeline stages as subprocesses, support cancel.
Streams stdout to the job document so the dashboard can show live progress.

Subprocess env: we always load .env from project root and pass it to the pipeline
so the pipeline uses the same MongoDB/APIFY_TOKEN as the dashboard (no matter how
the API was started).
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# Project root (lead-generation)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_ENV_FILE = PROJECT_ROOT / ".env"


def _read_env_file(path: Path) -> dict[str, str]:
    """Fallback: parse .env manually so we don't depend on python-dotenv in the API process (e.g. when started via start.bat)."""
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k:
                        out[k] = v
    except Exception:
        pass
    return out


def _subprocess_env() -> dict[str, str]:
    """Build env for pipeline subprocess: inherit current process, then overlay project .env so pipeline uses same DB/keys as dashboard.
    When the API is started via start.bat, the subprocess might not inherit .env; we always load from PROJECT_ROOT/.env here.
    """
    # Force API's .env to be loaded into this process so os.environ has MONGODB_URI before we copy (e.g. first request)
    try:
        import db as _api_db  # noqa: F401  # loads .env in services/api/db.py
    except Exception:
        pass
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["PYTHONUNBUFFERED"] = "1"
    dotenv_keys = 0
    if _ENV_FILE.exists():
        try:
            from dotenv import dotenv_values
            dotenv_vars = dotenv_values(_ENV_FILE)
            for k, v in dotenv_vars.items():
                if v is not None and k and not k.startswith("#"):
                    env[k] = str(v)
                    dotenv_keys += 1
        except Exception as e:
            print(f"[job_runner] DEBUG dotenv overlay failed: {e}, using fallback", flush=True)
        # Fallback: if no keys loaded (e.g. dotenv not installed in API env), read .env manually
        if dotenv_keys == 0:
            fallback = _read_env_file(_ENV_FILE)
            for k, v in fallback.items():
                env[k] = v
                dotenv_keys += 1
            if fallback:
                print(f"[job_runner] DEBUG fallback .env read: {len(fallback)} keys", flush=True)
    # Always set MONGODB_URI, APIFY_TOKEN, and optional AWS2_* (Bedrock Nova Lite) from project .env so the subprocess uses the same config as when you run the pipeline manually.
    _file_vars = _read_env_file(_ENV_FILE) if _ENV_FILE.exists() else {}
    if (_file_vars.get("MONGODB_URI") or "").strip():
        env["MONGODB_URI"] = (_file_vars.get("MONGODB_URI") or "").strip()
    if (_file_vars.get("APIFY_TOKEN") or "").strip():
        env["APIFY_TOKEN"] = (_file_vars.get("APIFY_TOKEN") or "").strip()
    # Bedrock: AWS_BEDROCK_API or AWS2_* / CLAUDE_* (llm_client accepts both)
    for key in ("AWS2_ACCESS_KEY_ID", "AWS2_SECRET_ACCESS_KEY", "AWS2_REGION",
                "CLAUDE_ACCESS_KEY_ID", "CLAUDE_SECRET_ACCESS_KEY"):
        v = (_file_vars.get(key) or "").strip()
        if v:
            env[key] = v
    print(f"[job_runner] DEBUG PROJECT_ROOT={PROJECT_ROOT}", flush=True)
    print(f"[job_runner] DEBUG .env exists={_ENV_FILE.exists()}, path={_ENV_FILE}", flush=True)
    print(f"[job_runner] DEBUG env keys from .env={dotenv_keys}", flush=True)
    print(f"[job_runner] DEBUG MONGODB_URI in env={('MONGODB_URI' in env and bool(env.get('MONGODB_URI', '').strip()))}", flush=True)
    print(f"[job_runner] DEBUG APIFY_TOKEN in env={('APIFY_TOKEN' in env and bool(env.get('APIFY_TOKEN', '').strip()))}", flush=True)
    return env

# Max chars to store for live/final stdout (keep last N for very long runs)
STDOUT_MAX = 12000

# In-memory: job_id -> subprocess.Popen for running jobs (so we can kill on cancel)
_running: dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


def _coll(db):
    if db is None:
        return None
    return db.pipeline_jobs if hasattr(db, "pipeline_jobs") else db["pipeline_jobs"]


def _build_cmd(job_type: str, options: dict[str, Any]) -> list[str]:
    """Build argv for pipeline.run_pipeline. Three steps: ingest, filter_and_prepare, send_email."""
    base = [sys.executable, "-m", "pipeline.run_pipeline"]
    if job_type == "ingest":
        base.append("--ingest-only")
        platforms = (options or {}).get("platforms")
        if platforms is not None:
            # Dashboard/config can send a single string (e.g. "reddit"); list("reddit") would break
            if isinstance(platforms, str):
                platforms = [platforms]
            base.extend(["--platforms"] + list(platforms))
    elif job_type == "filter_and_prepare":
        base.append("--filter-and-prepare")
        limit = (options or {}).get("after_filter_limit", 200)
        base.extend(["--after-filter-limit", str(limit)])
        # Use same limit for AI so one "raw to filter" cap controls the run
        ai_limit = (options or {}).get("ai_limit", limit)
        base.extend(["--ai-limit", str(ai_limit)])
    elif job_type == "send_email":
        base.append("--send-only")
    else:
        raise ValueError(f"Unknown job type: {job_type}")
    return base


def create_job(db, job_type: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Insert a pending job doc; return the doc with _id."""
    coll = _coll(db)
    if coll is None:
        raise RuntimeError("MongoDB not available")
    job_id = str(uuid.uuid4())
    now = datetime.utcnow()
    doc = {
        "_id": job_id,
        "jobType": job_type,
        "status": "pending",
        "options": options or {},
        "createdAt": now,
        "startedAt": None,
        "finishedAt": None,
        "result": None,
        "error": None,
    }
    coll.insert_one(doc)
    return {**doc, "result": None}


def start_job(db, job_id: str) -> None:
    """Run the job in a background thread (subprocess). Updates doc to running, then completed/failed/cancelled."""
    coll = _coll(db)
    if coll is None:
        return
    doc = coll.find_one({"_id": job_id})
    if not doc or doc.get("status") != "pending":
        return

    job_type = doc.get("jobType", "")
    options = doc.get("options") or {}

    def run():
        now = datetime.utcnow()
        coll.update_one(
            {"_id": job_id},
            {"$set": {"status": "running", "startedAt": now, "result": {"returncode": None, "stdout": ""}}},
        )
        cmd = _build_cmd(job_type, options)
        print(f"[job_runner] DEBUG Starting job {job_id} cmd={cmd}", flush=True)
        env = _subprocess_env()
        print(f"[job_runner] DEBUG subprocess cwd={PROJECT_ROOT}", flush=True)
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            with _lock:
                _running[job_id] = proc

            buffer: list[str] = []
            last_update = [0.0]  # use list so reader thread can mutate

            def reader():
                for line in iter(proc.stdout.readline, ""):
                    buffer.append(line)
                    try:
                        sys.stdout.write(line)
                        sys.stdout.flush()
                    except Exception:
                        pass
                    # Update DB every 0.5s so frontend sees progress
                    if time.time() - last_update[0] >= 0.5:
                        last_update[0] = time.time()
                        text = "".join(buffer)
                        if len(text) > STDOUT_MAX:
                            text = text[-STDOUT_MAX:]
                        coll.update_one(
                            {"_id": job_id},
                            {"$set": {"result": {"returncode": None, "stdout": text}}},
                        )

            reader_thread = threading.Thread(target=reader, daemon=True)
            reader_thread.start()
            proc.wait()
            # One final read in case there was more after last line
            if proc.stdout:
                try:
                    remainder = proc.stdout.read()
                    if remainder:
                        buffer.append(remainder)
                        try:
                            sys.stdout.write(remainder)
                            sys.stdout.flush()
                        except Exception:
                            pass
                except Exception:
                    pass
            reader_thread.join(timeout=2)

            with _lock:
                _running.pop(job_id, None)
            finished = datetime.utcnow()
            out_snippet = "".join(buffer)
            if len(out_snippet) > STDOUT_MAX:
                out_snippet = out_snippet[-STDOUT_MAX:]
            if proc.returncode == 0:
                coll.update_one(
                    {"_id": job_id},
                    {"$set": {"status": "completed", "finishedAt": finished, "result": {"returncode": 0, "stdout": out_snippet}}},
                )
            else:
                coll.update_one(
                    {"_id": job_id},
                    {"$set": {"status": "failed", "finishedAt": finished, "error": out_snippet[-2000:] if out_snippet else f"exit {proc.returncode}", "result": {"returncode": proc.returncode, "stdout": out_snippet}}},
                )
        except Exception as e:
            with _lock:
                _running.pop(job_id, None)
            coll.update_one(
                {"_id": job_id},
                {"$set": {"status": "failed", "finishedAt": datetime.utcnow(), "error": str(e)}},
            )

    t = threading.Thread(target=run, daemon=True)
    t.start()


def cancel_job(db, job_id: str) -> bool:
    """If job is running, kill the subprocess and set status to cancelled. Return True if we killed it."""
    coll = _coll(db)
    with _lock:
        proc = _running.get(job_id)
    if proc is not None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        with _lock:
            _running.pop(job_id, None)
        if coll is not None:
            coll.update_one(
                {"_id": job_id},
                {"$set": {"status": "cancelled", "finishedAt": datetime.utcnow()}},
            )
        return True
    if coll is not None:
        doc = coll.find_one({"_id": job_id})
        if doc and doc.get("status") == "running":
            coll.update_one(
                {"_id": job_id},
                {"$set": {"status": "cancelled", "finishedAt": datetime.utcnow()}},
            )
            return True
    return False


def get_running_job_ids() -> list[str]:
    with _lock:
        return list(_running.keys())
