"""
LLM client: AWS Bedrock for filtering, scoring, personalization.
- Prefer single Bedrock API key: AWS_BEDROCK_API (uses MODEL_ID, AWS_REGION). No IAM keys needed.
- Fallback: IAM credentials AWS_* or AWS2_* / CLAUDE_* with Nova Lite (BEDROCK_NOVA_LITE_MODEL_ID) or MODEL_ID.
"""
from __future__ import annotations
import logging
import os
import time
from typing import Callable

_LLM_MAX_RETRIES = 3
_LLM_BACKOFF_SECS = (1, 2, 3)

# Env keys for single Bedrock API key (Bearer token); see AWS docs: api-keys-use.html
BEDROCK_API_KEY_ENV = "AWS_BEDROCK_API"
BEDROCK_BEARER_ENV = "AWS_BEARER_TOKEN_BEDROCK"
MODEL_ID_ENV = "MODEL_ID"
DEFAULT_MODEL_API_KEY = "amazon.nova-pro-v1:0"
# Official AWS Bedrock model IDs (see docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html)
BEDROCK_NOVA_LITE_MODEL_ID = "amazon.nova-lite-v1:0"  # Nova Lite technical name
DEFAULT_MODEL_IAM = BEDROCK_NOVA_LITE_MODEL_ID


def _get_bedrock_api_key() -> str:
    """Return Bedrock API key if set (single-key auth)."""
    return (os.environ.get(BEDROCK_API_KEY_ENV) or os.environ.get(BEDROCK_BEARER_ENV) or "").strip()


def _get_bedrock_credentials() -> tuple[str, str]:
    """Return (access_key, secret_key) for Bedrock IAM. Prefer AWS_*, then AWS2_*, then CLAUDE_*."""
    ak = (
        os.environ.get("AWS_ACCESS_KEY_ID")
        or os.environ.get("AWS2_ACCESS_KEY_ID")
        or os.environ.get("CLAUDE_ACCESS_KEY_ID")
        or ""
    ).strip()
    sk = (
        os.environ.get("AWS_SECRET_ACCESS_KEY")
        or os.environ.get("AWS2_SECRET_ACCESS_KEY")
        or os.environ.get("CLAUDE_SECRET_ACCESS_KEY")
        or ""
    ).strip()
    return ak, sk


def _get_bedrock_region() -> str:
    """Region for Bedrock."""
    return (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("AWS2_REGION")
        or os.environ.get("AWS_BEDROCK_REGION")
        or "us-east-1"
    ).strip()


def _get_bedrock_model_id(use_api_key: bool) -> str:
    """Model ID: from MODEL_ID env, or default by auth type."""
    mid = (os.environ.get(MODEL_ID_ENV) or "").strip()
    if mid:
        return mid
    return DEFAULT_MODEL_API_KEY if use_api_key else DEFAULT_MODEL_IAM


def _has_bedrock_config() -> bool:
    """True if Bedrock is configured: AWS_BEDROCK_API (single key) or IAM (AWS_*, AWS2_*, CLAUDE_*)."""
    if _get_bedrock_api_key():
        return True
    ak, sk = _get_bedrock_credentials()
    return bool(ak and sk)


def _call_bedrock(prompt: str, temperature: float = 0.2) -> str | None:
    """Call AWS Bedrock Converse API. Uses AWS_BEDROCK_API (bearer) if set, else IAM credentials."""
    log = logging.getLogger("pipeline")
    api_key = _get_bedrock_api_key()
    use_api_key = bool(api_key)
    ak, sk = _get_bedrock_credentials()
    if not use_api_key and (not ak or not sk):
        return None

    try:
        import boto3
        region = _get_bedrock_region()
        model_id = _get_bedrock_model_id(use_api_key)

        if use_api_key:
            # Single Bedrock API key: set bearer token so boto3 uses it (no IAM creds)
            os.environ[BEDROCK_BEARER_ENV] = api_key
            client = boto3.client("bedrock-runtime", region_name=region)
        else:
            client = boto3.client(
                "bedrock-runtime",
                region_name=region,
                aws_access_key_id=ak,
                aws_secret_access_key=sk,
            )

        resp = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 2048, "temperature": temperature},
        )
        output = resp.get("output") or {}
        message = output.get("message") or {}
        content = message.get("content") or []
        text = content[0].get("text", "") if content else ""
        result = text.strip() or None
        if result is None and content:
            log.debug("Bedrock returned %s content block(s) but no text in first block; keys: %s", len(content), list(content[0].keys()) if content[0] else [])
        return result
    except Exception as e:
        log.warning("Bedrock call failed: %s", e)
        return None


def _call_with_retry(fn: Callable[[], str | None]) -> str | None:
    """Run fn up to _LLM_MAX_RETRIES times with backoff; return first non-None or None."""
    log = logging.getLogger("pipeline")
    for attempt in range(_LLM_MAX_RETRIES):
        out = fn()
        if out is not None:
            return out
        if attempt < _LLM_MAX_RETRIES - 1:
            delay = _LLM_BACKOFF_SECS[attempt] if attempt < len(_LLM_BACKOFF_SECS) else 2
            log.warning("LLM call returned no text, retry in %ss (attempt %s/%s)", delay, attempt + 1, _LLM_MAX_RETRIES)
            time.sleep(delay)
    log.warning("LLM call failed after %s attempts", _LLM_MAX_RETRIES)
    return None


def call_llm(prompt: str, temperature: float = 0.2, api_key: str | None = None) -> str | None:
    """
    Call LLM: AWS Bedrock. Prefers AWS_BEDROCK_API (single key + MODEL_ID), else IAM (AWS_* / AWS2_* / CLAUDE_*).
    Retries with backoff. Returns response text or None.
    """
    if not _has_bedrock_config():
        return None
    return _call_with_retry(lambda: _call_bedrock(prompt, temperature))


def has_llm_config() -> bool:
    """True when Bedrock is configured (AWS_BEDROCK_API or IAM credentials)."""
    return _has_bedrock_config()
