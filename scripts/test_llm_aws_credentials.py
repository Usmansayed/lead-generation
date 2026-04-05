#!/usr/bin/env python3
"""
Test Bedrock Nova Lite using AWS_* credentials instead of AWS2_*.

Usage:
  python scripts/test_llm_aws_credentials.py

Uses AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY and AWS_REGION (or AWS_DEFAULT_REGION).
Does not use AWS2_* or CLAUDE_*. Run from repo root; loads .env if python-dotenv is present.
"""
from __future__ import annotations

import os
import sys

# Load .env so we can test with same env as the app
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Ensure pipeline is importable
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _get_aws_credentials() -> tuple[str, str]:
    """Standard AWS (not AWS2)."""
    ak = (os.environ.get("AWS_ACCESS_KEY_ID") or "").strip()
    sk = (os.environ.get("AWS_SECRET_ACCESS_KEY") or "").strip()
    return ak, sk


def call_bedrock_with_aws(prompt: str, temperature: float = 0.2) -> str | None:
    """Call Bedrock Nova Lite using AWS_* credentials only."""
    ak, sk = _get_aws_credentials()
    if not ak or not sk:
        print("ERROR: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required (AWS_*, not AWS2_*)")
        return None
    try:
        import boto3
        region = (
            os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or os.environ.get("AWS_BEDROCK_REGION")
            or "us-east-1"
        ).strip()
        print(f"Using region: {region}")
        client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
        )
        from pipeline.llm_client import BEDROCK_NOVA_LITE_MODEL_ID
        resp = client.converse(
            modelId=BEDROCK_NOVA_LITE_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 2048, "temperature": temperature},
        )
        output = resp.get("output") or {}
        message = output.get("message") or {}
        content = message.get("content") or []
        text = content[0].get("text", "") if content else ""
        return text.strip() or None
    except Exception as e:
        print(f"Bedrock call failed: {e}")
        return None


def main() -> None:
    print("=" * 60)
    print("Test: Bedrock Nova Lite with AWS_* (not AWS2_*)")
    print("=" * 60)

    ak, sk = _get_aws_credentials()
    if not ak or not sk:
        print("Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env or environment.")
        sys.exit(1)

    print("Credentials: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY found.")
    prompt = "Reply with exactly: OK"
    print(f"Prompt: {prompt!r}")
    print("Calling Bedrock...")

    out = call_bedrock_with_aws(prompt, temperature=0.0)
    if out:
        print("SUCCESS. Response:", repr(out))
    else:
        print("FAILED: No text returned (or exception above).")
        sys.exit(1)


if __name__ == "__main__":
    main()
