#!/usr/bin/env python3
"""
Test AWS Bedrock LLM (filtering, scoring, personalization).
Run from project root:  python scripts/test_bedrock_nova.py

Uses either:
  - AWS_BEDROCK_API (single Bedrock API key) + MODEL_ID + AWS_REGION, or
  - IAM: AWS2_ACCESS_KEY_ID + AWS2_SECRET_ACCESS_KEY (or CLAUDE_* or AWS_*).
Optional: AWS2_REGION or AWS_BEDROCK_REGION (default us-east-1)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_env_file = ROOT / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(_env_file, override=True)
except ImportError:
    pass


def main() -> int:
    from pipeline.llm_client import (
        has_llm_config,
        call_llm,
        _get_bedrock_api_key,
        _get_bedrock_credentials,
        _get_bedrock_region,
        _get_bedrock_model_id,
    )

    print("Testing AWS Bedrock LLM\n")
    print("  .env path:", _env_file, "(exists:", _env_file.exists(), ")")
    api_key = _get_bedrock_api_key()
    ak, sk = _get_bedrock_credentials()
    if api_key:
        print("  Auth: AWS_BEDROCK_API (single API key)")
        print("  Model:", _get_bedrock_model_id(True))
    else:
        cred_source = "AWS_*" if (os.environ.get("AWS_ACCESS_KEY_ID") or "").strip() else ("AWS2_*" if (os.environ.get("AWS2_ACCESS_KEY_ID") or "").strip() else ("CLAUDE_*" if (ak and sk) else "none"))
        print("  Auth: IAM (" + cred_source + ")")
        print("  Model:", _get_bedrock_model_id(False))
    print("  Region:", _get_bedrock_region())
    print("  has_llm_config():", has_llm_config())
    print()

    if not has_llm_config():
        print("FAIL: Set AWS_BEDROCK_API in .env, or AWS2_ACCESS_KEY_ID + AWS2_SECRET_ACCESS_KEY (or CLAUDE_* / AWS_*)")
        return 1

    prompt = "Reply with exactly the word OK and nothing else."
    print("Sending prompt:", repr(prompt))
    print("Calling Bedrock...")
    response = call_llm(prompt, temperature=0)
    print()

    if response is None:
        print("FAIL: No response (check API key/credentials, region, and Bedrock access)")
        return 1

    print("Response:", repr(response))
    print()
    print("PASS: Bedrock is working.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
