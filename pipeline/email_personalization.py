"""
AI email personalization: generate subject + body from qualified lead + scraped profile + full post + business research.
No fixed template — AI gets full context and room to personalize. Only rules: body must start with "Hey" and end with
a short casual sign-off followed by the sender name (default Usman Sayed; set OUTREACH_SENDER_NAME in .env). Tone: casual, human.
Output is fully complete with no placeholders (e.g. no [your name here]) — ready to copy-paste or send as-is.
"""
from __future__ import annotations
import json
import os
import re
from typing import Any

# Sender name at end of email (copy-paste ready). Set OUTREACH_SENDER_NAME in .env to override.
DEFAULT_SENDER_NAME = "Usman Sayed"

# Placeholder patterns to replace with actual sender name (so email is always ready to send).
_PLACEHOLDER_PATTERNS = [
    re.compile(r"\[your name\]", re.I),
    re.compile(r"\[name\]", re.I),
    re.compile(r"\[sender\]", re.I),
    re.compile(r"\[insert name\]", re.I),
    re.compile(r"\[sender name\]", re.I),
    re.compile(r"your name here", re.I),
    re.compile(r"<your name>", re.I),
    re.compile(r"<name>", re.I),
    re.compile(r"\{sender_name\}", re.I),
    re.compile(r"\{name\}", re.I),
]


def _sender_name() -> str:
    return (os.environ.get("OUTREACH_SENDER_NAME") or "").strip() or DEFAULT_SENDER_NAME


def _strip_placeholders(text: str, sender: str) -> str:
    """Replace common placeholder phrases with the actual sender name so the email is ready to send."""
    if not text or not isinstance(text, str):
        return text or ""
    out = text
    for pat in _PLACEHOLDER_PATTERNS:
        out = pat.sub(sender, out)
    return out

from .models import CanonicalLead
from . import schema


def _build_prompt(
    lead: CanonicalLead,
    profile_data: dict[str, Any] | None = None,
    full_post_text: str = "",
    business_type: str = "",
    suggested_offers: list[str] | None = None,
    web_context: str = "",
) -> str:
    # Prefer full post if we have it (from full fetch), else snippet
    body_text = (full_post_text or lead.post_text or "").strip()
    if not body_text:
        body_text = (lead.post_text or "")[:800]
    else:
        body_text = body_text[:1200]
    body_text = body_text.replace('"', "'")
    author = lead.author.name or lead.author.handle or "Unknown"
    platform = lead.platform or ""

    profile_block = ""
    if profile_data and profile_data.get("profile_text"):
        profile_block = f"""
PROFILE / ABOUT THEM (use to personalize; reference specific details):
\"\"\"
{(profile_data.get('profile_text') or '')[:1500]}
\"\"\"
"""

    offers_block = ""
    if suggested_offers:
        offers_str = ", ".join(suggested_offers[:5])
        offers_block = f"""
WHAT TO OFFER THEM (pick 1–2 that fit; do NOT only say "website" unless it's first): {offers_str}
Research shows this type of business often needs these. Mention the most relevant one naturally.
"""

    business_block = f"\nBUSINESS CONTEXT: {business_type.replace('_', ' ')}. " if business_type else ""

    web_block = ""
    if web_context and web_context.strip():
        web_block = f"""
EXTRA CONTEXT FROM WEB (use to personalize if relevant; don't force it):
\"\"\"
{web_context.strip()[:2000]}
\"\"\"
"""

    return f"""Write ONE short outreach email from someone at Scubiee (we build sites, dashboards, and internal tools for founders and businesses). Use the context below to personalize — there is no fixed template. You have room to be creative: structure the email however it fits this person, reference what stands out from their post or profile, and offer help in a way that feels natural to their situation.

CONTEXT ABOUT THIS PERSON / THEIR POST:
\"\"\"
{body_text}
\"\"\"
Author: {author}, Platform: {platform}.{business_block}
{profile_block}
{web_block}
{offers_block}

GUIDANCE (tone, not a strict template):
- Sound like a real person writing to a fellow founder — casual, conversational, no corporate or marketing speak.
- Focus on them first (what they're working on, what they said). Offer help in context, not as a service checklist.
- Mention that they can reach out to team@scubiee.com or scubiee.com if they want to chat — keep it relaxed. Leave the next step up to them (no pressure).
- Keep it short (~130 words), natural phrasing, small paragraphs.

FIXED RULES (must follow):
1. The email body must START with "Hey" (e.g. "Hey —" or "Hey," then whatever fits).
2. End with a short, casual sign-off on its own line, then on the next line the sender name: {_sender_name()}. Example:
   All the best,

   {_sender_name()}
3. The output must be 100% complete and ready to send. Do NOT use any placeholders such as [your name], [Name], [sender], [insert name], "your name here", or similar. Every part of the subject and body must be real text — the recipient must see a finished email with no brackets or fill-in-the-blanks.

Everything in between is up to you — personalize and vary the middle based on the lead.

Return JSON only, no other text:
{{"subject": "...", "bodyText": "...", "bodyHtml": "<p>...</p>"}}
"""


def generate_email(
    lead: CanonicalLead,
    profile_data: dict[str, Any] | None = None,
    full_post_text: str = "",
    business_type: str = "",
    suggested_offers: list[str] | None = None,
    web_context: str = "",
    api_key: str | None = None,
) -> dict[str, Any] | None:
    """Generate subject, bodyText, bodyHtml. Uses post + full fetch + profile + business research + optional web context for hyper-personalized, human-like email."""
    from .llm_client import call_llm, has_llm_config
    if not has_llm_config():
        return None
    prompt = _build_prompt(
        lead,
        profile_data,
        full_post_text=full_post_text,
        business_type=business_type,
        suggested_offers=suggested_offers or [],
        web_context=web_context or "",
    )
    text = call_llm(prompt, temperature=0.5, api_key=api_key)
    if not text:
        return None
    text = text.strip()
    if "```" in text:
        start = text.find("```")
        if "json" in text[: start + 10].lower():
            start = text.find("\n", start) + 1
        end = text.find("```", start)
        if end == -1:
            end = len(text)
        text = text[start:end]
    try:
        payload = json.loads(text)
        if not isinstance(payload, dict):
            return None
        # Ensure no placeholders remain — replace any with actual sender name so email is ready to send
        sender = _sender_name()
        for key in ("subject", "bodyText", "bodyHtml"):
            if key in payload and payload[key]:
                payload[key] = _strip_placeholders(str(payload[key]), sender)
        return payload
    except json.JSONDecodeError:
        return None


def enqueue_lead_for_email(mongo_db, lead_id: str, email_payload: dict, to_email: str | None = None) -> tuple[bool, str]:
    """Push to email_queue via add_to_queue (dedup: no duplicate emails per lead). Returns (success, action)."""
    from .email_queue import add_to_queue
    return add_to_queue(
        mongo_db,
        lead_id,
        email_payload.get("subject", ""),
        email_payload.get("bodyText", ""),
        email_payload.get("bodyHtml", ""),
        to_email=to_email,
    )
