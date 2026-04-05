#!/usr/bin/env python3
"""
Test AWS Bedrock using API key auth only (no IAM credentials).

Run from project root:
  python scripts/test_bedrock_api_key.py

Required in .env:
  AWS_BEDROCK_API
Optional:
  AWS_REGION (default: us-east-1)
  MODEL_ID (default: amazon.nova-pro-v1:0)
"""
from __future__ import annotations

import os
import sys
import importlib.util
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ENV_FILE = ROOT / ".env"
LLM_CLIENT_FILE = ROOT / "pipeline" / "llm_client.py"

try:
    from dotenv import load_dotenv

    load_dotenv(ENV_FILE, override=True)
except Exception:
    # Continue if python-dotenv is unavailable.
    pass


def _mask_secret(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}...{value[-keep:]}"


def main() -> int:
    spec = importlib.util.spec_from_file_location("llm_client_standalone", LLM_CLIENT_FILE)
    if spec is None or spec.loader is None:
        print(f"FAIL: Could not load {LLM_CLIENT_FILE}")
        return 1
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    BEDROCK_BEARER_ENV = module.BEDROCK_BEARER_ENV
    _get_bedrock_api_key = module._get_bedrock_api_key
    _get_bedrock_model_id = module._get_bedrock_model_id
    _get_bedrock_region = module._get_bedrock_region

    api_key = _get_bedrock_api_key()
    region = _get_bedrock_region()
    model_id = _get_bedrock_model_id(True)

    print("Bedrock API key auth test (IAM disabled)")
    print(f".env: {ENV_FILE} (exists: {ENV_FILE.exists()})")
    print(f"Region: {region}")
    print(f"Model: {model_id}")

    if not api_key:
        print("FAIL: AWS_BEDROCK_API is missing. Add it to .env and retry.")
        return 1

    print(f"API key detected: {_mask_secret(api_key)}")

    # Force API key path and ensure IAM env vars do not affect this test.
    os.environ[BEDROCK_BEARER_ENV] = api_key
    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS2_ACCESS_KEY_ID",
        "AWS2_SECRET_ACCESS_KEY",
        "CLAUDE_ACCESS_KEY_ID",
        "CLAUDE_SECRET_ACCESS_KEY",
    ):
        os.environ.pop(name, None)

    prompt = "Reply with exactly OK and nothing else."
    print("Sending test prompt...")

    endpoint = f"https://bedrock-runtime.{region}.amazonaws.com/model/{quote(model_id, safe='')}/converse"
    payload = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 16, "temperature": 0},
    }

    try:
        req = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urlopen(req, timeout=45) as response:
            resp = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        print(f"FAIL: Bedrock API call failed with HTTP {exc.code}: {body}")
        print("Hint: verify AWS_BEDROCK_API, AWS_REGION, MODEL_ID, and model access for API key auth.")
        return 1
    except URLError as exc:
        print(f"FAIL: Network error calling Bedrock: {exc}")
        return 1
    except Exception as exc:
        print(f"FAIL: Bedrock API call failed: {exc}")
        print("Hint: verify AWS_BEDROCK_API, AWS_REGION, MODEL_ID, and Bedrock model access.")
        return 1

    output = (resp.get("output") or {}).get("message") or {}
    content = output.get("content") or []
    text = (content[0].get("text") if content and isinstance(content[0], dict) else "") or ""
    reply = text.strip()

    if not reply:
        print("FAIL: Empty response from model.")
        return 1

    print(f"Model reply: {reply!r}")
    print("PASS: Bedrock API-key authentication is working.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
