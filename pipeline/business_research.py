"""
Business research: classify lead by type/size, detect if they have a website,
and decide what software to offer. Used after full fetch for email personalization.
- Small cafe/restaurant with website -> skip (only needed a site).
- Medium+ or other business types (firms, shops, retail) -> offer POS, CRM, booking, etc. per type.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

import yaml

from .config_loader import PROJECT_ROOT

CONFIG_DIR = PROJECT_ROOT / "config"
BUSINESS_OFFERS_PATH = CONFIG_DIR / "business_offers.yaml"

# Phrases that suggest they already have a website (from post or full fetch)
HAS_WEBSITE_PHRASES = [
    "our website", "their website", "from their website", "from our website",
    "check out our website", "visit our website", "on our website",
    "website is live", "launched our website", "new website",
    "official website", "official site",
]

# Business type keywords (order matters: more specific first)
TYPE_SIGNALS = [
    ("law_firm", ["law firm", "law office", "attorney", "legal practice", "barrister"]),
    ("consulting_firm", ["consulting firm", "consultancy", "consulting practice"]),
    ("architecture_firm", ["architecture firm", "architectural practice"]),
    ("medical_practice", ["medical practice", "clinic", "dental", "physician", "health practice"]),
    ("real_estate", ["real estate", "realtor", "property", "realty"]),
    ("auto_dealership", ["dealership", "auto mart", "car dealer"]),
    ("gym", ["gym", "fitness", "yoga studio", "crossfit"]),
    ("salon", ["salon", "barbershop", "spa", "hair salon", "nail salon"]),
    ("restaurant", ["restaurant", "eatery", "bistro", "dining", "kitchen"]),
    ("cafe", ["cafe", "coffee shop", "coffee house", "bakery"]),
    ("retail", ["retail", "store", "shop", "boutique", "outlet"]),
    ("shop", ["shop", "store", "gallery"]),
]


def _load_business_offers() -> dict[str, Any]:
    if not BUSINESS_OFFERS_PATH.exists():
        return {}
    with open(BUSINESS_OFFERS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _detect_has_website(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(p.lower() in t for p in HAS_WEBSITE_PHRASES)


def _classify_business_type(text: str) -> str:
    """Return business type key from config (cafe, restaurant, law_firm, etc.) or 'default'."""
    if not text:
        return "default"
    t = text.lower()
    for key, phrases in TYPE_SIGNALS:
        if any(p in t for p in phrases):
            return key
    return "default"


def _classify_size(text: str, business_type: str) -> str:
    """Return 'small' or 'medium_plus'. Heuristics: multiple locations, team, 'our team', 'locations' -> medium_plus."""
    if not text:
        return "small"
    t = text.lower()
    medium_signals = [
        "second location", "new location", "multiple locations", "our locations",
        "our team", "the team", "expanding", "grand opening", "ribbon cutting",
        "headquarters", "flagship", "chain", "franchise",
    ]
    if any(s in t for s in medium_signals):
        return "medium_plus"
    return "small"


def get_suggested_offers(business_type: str, size: str) -> list[str]:
    """Return list of services/software to offer for this type/size from config."""
    cfg = _load_business_offers()
    offers_map = cfg.get("offers_by_type") or {}
    # Normalize: cafe/restaurant use same as restaurant if not separate
    key = business_type
    if key not in offers_map and business_type == "cafe":
        key = "cafe"
    if key not in offers_map:
        key = "restaurant" if business_type in ("cafe", "restaurant") else "default"
    return list(offers_map.get(key, offers_map.get("default", ["website", "booking or scheduling"])))


def should_skip_email(has_website: bool, business_type: str, size: str) -> bool:
    """
    Skip email only when: they have a website AND are a small cafe/restaurant (only needed a site).
    Medium+ or any other business type (firms, shops, retail) -> do not skip; offer other software.
    """
    if not has_website:
        return False
    small_website_only = _load_business_offers().get("small_website_only_types") or []
    skip_key = f"small_{business_type}" if size == "small" else None
    if skip_key and skip_key in small_website_only:
        return True
    # Also skip small_cafe / small_restaurant if we classify that way
    if size == "small" and business_type in ("cafe", "restaurant"):
        return True
    return False


def research_lead(post_text: str, full_post_text: str = "") -> dict[str, Any]:
    """
    Classify lead: business_type, size, has_website, suggested_offers, should_skip.
    Uses post_text + full_post_text (from full fetch) for better detection.
    """
    combined = f"{post_text or ''}\n{full_post_text or ''}".strip()
    business_type = _classify_business_type(combined)
    size = _classify_size(combined, business_type)
    has_website = _detect_has_website(combined)
    suggested_offers = get_suggested_offers(business_type, size)
    skip = should_skip_email(has_website, business_type, size)
    return {
        "business_type": business_type,
        "business_size": size,
        "has_website": has_website,
        "suggested_offers": suggested_offers,
        "should_skip_email": skip,
    }
