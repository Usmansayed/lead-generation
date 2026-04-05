#!/usr/bin/env python3
"""
Test AWS Bedrock API connectivity and basic inference.

Uses the official Nova Lite model ID: amazon.nova-lite-v1:0
(see pipeline.llm_client.BEDROCK_NOVA_LITE_MODEL_ID and AWS model-ids docs).

Run from project root:
  python tests/test_bedrock_api.py
  pytest tests/test_bedrock_api.py -v

Requires in .env one of:
  - AWS_BEDROCK_API (single API key) + MODEL_ID + AWS_REGION, or
  - AWS2_ACCESS_KEY_ID + AWS2_SECRET_ACCESS_KEY (or AWS_* / CLAUDE_*)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_env_file = ROOT / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(_env_file, override=True)
except ImportError:
    pass


def test_bedrock_config_present():
    """Bedrock is configured via API key or IAM credentials."""
    from pipeline.llm_client import has_llm_config
    assert has_llm_config(), (
        "Set AWS_BEDROCK_API in .env, or AWS2_ACCESS_KEY_ID + AWS2_SECRET_ACCESS_KEY (or AWS_* / CLAUDE_*)"
    )


def test_bedrock_simple_completion():
    """Bedrock Converse API returns a non-empty text response."""
    from pipeline.llm_client import has_llm_config, call_llm
    if not has_llm_config():
        raise AssertionError("Bedrock not configured; skip or set .env")
    prompt = "Reply with exactly the word OK and nothing else."
    response = call_llm(prompt, temperature=0.0)
    assert response is not None, "Bedrock returned None (check key/region/model access)"
    assert isinstance(response, str), "Response should be a string"
    assert len(response.strip()) > 0, "Response should not be empty"


def test_bedrock_region_and_model_resolved():
    """Region and model ID are resolved from env (Nova Lite = amazon.nova-lite-v1:0)."""
    from pipeline.llm_client import (
        _get_bedrock_region,
        _get_bedrock_model_id,
        _get_bedrock_api_key,
        BEDROCK_NOVA_LITE_MODEL_ID,
    )
    region = _get_bedrock_region()
    assert region and len(region) >= 2, "AWS region should be set (e.g. us-east-1)"
    use_api_key = bool(_get_bedrock_api_key())
    model_id = _get_bedrock_model_id(use_api_key)
    # Must be a known Bedrock model ID (Nova Lite technical name or MODEL_ID override)
    assert model_id and model_id.startswith("amazon."), (
        f"Model ID should be set (e.g. {BEDROCK_NOVA_LITE_MODEL_ID} or amazon.nova-pro-v1:0)"
    )


def test_bedrock_short_reply():
    """Model can produce a short structured reply (sanity check)."""
    from pipeline.llm_client import has_llm_config, call_llm
    if not has_llm_config():
        raise AssertionError("Bedrock not configured")
    prompt = "Say hello in one short sentence."
    response = call_llm(prompt, temperature=0.3)
    assert response is not None
    assert len(response) <= 500, "Short reply should be under 500 chars"


def main() -> int:
    """Run tests and print results (no pytest)."""
    print("Bedrock API tests\n")
    print("  .env:", _env_file, "(exists:", _env_file.exists(), ")")
    failures = 0
    for name, fn in [
        ("config present", test_bedrock_config_present),
        ("region/model resolved", test_bedrock_region_and_model_resolved),
        ("simple completion", test_bedrock_simple_completion),
        ("short reply", test_bedrock_short_reply),
    ]:
        try:
            fn()
            print(f"  OK  {name}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            failures += 1
    print()
    if failures:
        print(f"Result: {failures} failure(s)")
        return 1
    print("Result: all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
