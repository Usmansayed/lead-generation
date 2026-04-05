"""
Email verification: optional Hunter.io Email Verifier integration.
Reduces bounces and protects SES sender reputation.
Set HUNTER_API_KEY in .env to enable. Hunter free tier: 25 verifications/month.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("pipeline")

HUNTER_API_KEY_ENV = "HUNTER_API_KEY"
# Skip verification for these (test domains, etc.)
SKIP_VERIFY_DOMAINS = {"example.com", "test.com", "mailinator.com"}


def verify_email(email: str) -> dict:
    """
    Verify email deliverability via Hunter Email Verifier API (optional).
    Returns { valid: bool, confidence: str | None, skip: bool }.
    skip=True if verification was skipped (no API key, or domain in skip list).
    """
    result = {"valid": True, "confidence": None, "skip": True}
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        result["valid"] = False
        return result

    domain = email.split("@")[-1].lower()
    if domain in SKIP_VERIFY_DOMAINS:
        return result

    api_key = os.environ.get(HUNTER_API_KEY_ENV, "").strip()
    if not api_key:
        result["skip"] = True
        return result

    try:
        import urllib.request
        import urllib.parse
        import json

        params = urllib.parse.urlencode({"email": email, "api_key": api_key})
        url = f"https://api.hunter.io/v2/email-verifier?{params}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.warning("Hunter email verification failed for %s: %s", email[:30], e)
        result["skip"] = True
        return result

    result["skip"] = False
    d = data.get("data") or {}
    status = (d.get("status") or "").lower()
    result["confidence"] = d.get("result") or status
    # Hunter: valid = deliverable; risky = maybe; invalid = undeliverable
    if status in ("invalid", "disposable", "unknown"):
        result["valid"] = False
    elif status in ("valid", "accept_all"):
        result["valid"] = True
    else:
        # risky, etc. - allow but flag
        result["valid"] = status != "invalid"
    return result
