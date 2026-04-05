"""
Relevance engine: keyword matching + scoring to surface the best posts (highest potential customers).
Design: phrase-first matching with intent tiers, synonyms, negative gate, quality signals, recency.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

# Default platform weights (B2B signal strength)
PLATFORM_WEIGHTS = {
    "linkedin": 3,
    "twitter": 1,
    "reddit": 2,
    "facebook": 1,
    "instagram": 0,
}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _flatten_negative_patterns(filters: dict) -> list[str]:
    """Extract all negative pattern strings from filters.yaml. Longest first so specific reasons win."""
    out: list[str] = []
    neg = filters.get("negative_patterns") or {}
    for category_phrases in neg.values():
        if isinstance(category_phrases, list):
            out.extend(p.strip().lower() for p in category_phrases if p and isinstance(p, str))
    uniq = list(dict.fromkeys(out))
    # Sort by length descending so "launched our website" is tried before "our website"
    uniq.sort(key=len, reverse=True)
    return uniq


# When a negative phrase matches, skip rejection if text contains any of these (client intent, not noise)
NEGATIVE_EXCEPTIONS: dict[str, list[str]] = {
    "our website": ["create our website", "build our website", "our website redesign", "website redesign", "we need a website", "need a website", "create a website", "build a website", "rebuild our website", "redesign our website"],
    "our platform": ["develop our platform", "build our platform", "we need a platform", "need a platform", "build a platform"],
    "our api": ["integrate with our api", "integrate our api", "we need api", "need api integration"],
}


def _expand_phrase_with_synonyms(phrase: str, synonyms: dict[str, list]) -> list[str]:
    """Return phrase and variants with synonym substitution (for matching)."""
    phrase_lower = phrase.lower().strip()
    variants = [phrase_lower]
    words = re.findall(r"\b\w+\b", phrase_lower)
    for i, word in enumerate(words):
        for canonical, syns in (synonyms or {}).items():
            if canonical == word or word in (syns if isinstance(syns, list) else []):
                for syn in (syns if isinstance(syns, list) else []):
                    if syn == word:
                        continue
                    new_words = words[:i] + [str(syn)] + words[i + 1:]
                    variants.append(" ".join(new_words))
    return list(dict.fromkeys(variants))


class RelevanceEngine:
    """
    Single source of truth for "is this post a good lead?".
    Uses config/relevance_keywords.yaml and config/filters.yaml.
    """

    def __init__(
        self,
        relevance_path: Path | None = None,
        filters_path: Path | None = None,
    ):
        self.relevance_path = relevance_path or (CONFIG_DIR / "relevance_keywords.yaml")
        self.filters_path = filters_path or (CONFIG_DIR / "filters.yaml")
        self._relevance = _load_yaml(self.relevance_path)
        self._filters = _load_yaml(self.filters_path)
        self._negative_phrases = _flatten_negative_patterns(self._filters)
        self._synonyms = self._relevance.get("synonyms") or {}
        # Build tier phrases with weights (announcement_intent first = highest priority)
        self._tiers: list[tuple[str, int, list[str]]] = []  # (tier_name, weight, phrases)
        for tier_name in ("announcement_intent", "high_intent", "medium_intent", "soft_intent"):
            block = self._relevance.get(tier_name)
            if isinstance(block, dict):
                w = block.get("weight", 1)
                phrases = block.get("phrases") or []
                if isinstance(phrases, list):
                    self._tiers.append((tier_name, w, [p.strip().lower() for p in phrases if p]))
            elif isinstance(block, list):
                self._tiers.append((tier_name, 2, [p.strip().lower() for p in block if p]))
        self._quality = self._relevance.get("quality_signals") or {}
        self._min_gate = self._relevance.get("minimum_gate") or {}
        self._min_intent_points = int(self._min_gate.get("min_intent_points", 5))
        self._require_high_or_medium = self._min_gate.get("require_high_or_medium", True)
        self._require_announcement_or_high = self._min_gate.get("require_announcement_or_high", True)
        self._allow_soft_combo = self._min_gate.get("allow_soft_combo", False)
        self._allow_medium_with_min_points = int(self._min_gate.get("allow_medium_with_min_points", 0))

    def match_negative(self, text: str) -> tuple[bool, str | None]:
        """
        Return (True, reason) if text should be rejected (negative pattern matched).
        Otherwise (False, None). Single-word patterns use word boundary so e.g. "rant" doesn't match "restaurant".
        If a phrase is in NEGATIVE_EXCEPTIONS and text contains any exception substring, that match is skipped (client intent).
        """
        if not text:
            return False, None
        text_lower = text.lower()
        for phrase in self._negative_phrases:
            if not phrase:
                continue
            matched = False
            if " " in phrase:
                if phrase in text_lower:
                    matched = True
            else:
                if re.search(r"\b" + re.escape(phrase) + r"\b", text_lower):
                    matched = True
            if matched:
                # Allow client-intent phrasing to pass (e.g. "create our website", "develop our platform")
                exceptions = NEGATIVE_EXCEPTIONS.get(phrase)
                if exceptions and any(exc in text_lower for exc in exceptions):
                    continue
                return True, phrase
        # Minimum length (from filters) — only if we have enough content to judge
        min_words = self._filters.get("minimum_word_count")
        if min_words and len(text.strip().split()) < min_words:
            return True, "below_minimum_word_count"
        return False, None

    def match_intent_phrases(self, text: str) -> list[tuple[str, str, int]]:
        """
        Match text against tiered phrases (phrase-first, with synonym expansion).
        Returns list of (matched_phrase, tier_name, weight).
        """
        if not text:
            return []
        text_lower = text.lower()
        matched: list[tuple[str, str, int]] = []
        seen_phrase: set[str] = set()

        for tier_name, weight, phrases in self._tiers:
            for phrase in phrases:
                # Exact phrase match
                if phrase in text_lower:
                    if phrase not in seen_phrase:
                        matched.append((phrase, tier_name, weight))
                        seen_phrase.add(phrase)
                    continue
                # Synonym-expanded variants
                for variant in _expand_phrase_with_synonyms(phrase, self._synonyms):
                    if variant != phrase and variant in text_lower and phrase not in seen_phrase:
                        matched.append((phrase, tier_name, weight))
                        seen_phrase.add(phrase)
                        break
        return matched

    def intent_score_from_matches(self, matches: list[tuple[str, str, int]]) -> int:
        """Sum weight for each matched phrase (dedupe by phrase)."""
        seen: set[str] = set()
        total = 0
        for phrase, _tier, weight in matches:
            if phrase not in seen:
                seen.add(phrase)
                total += weight
        return total

    def passes_intent_gate(self, matches: list[tuple[str, str, int]], intent_points: int) -> bool:
        """Gate: must have announcement or high intent phrase + enough points; optional medium-only with high points."""
        has_announcement_or_high = any(
            t in ("high_intent", "announcement_intent") for _, t, _ in matches
        )
        has_medium = any(t == "medium_intent" for _, t, _ in matches)
        has_soft = any(t == "soft_intent" for _, t, _ in matches)
        # Optional: allow medium-only if points are high enough (reduces false negatives)
        if self._allow_medium_with_min_points and has_medium and intent_points >= self._allow_medium_with_min_points:
            if intent_points >= self._min_intent_points:
                return True
        # Strict: require at least one lead-grade phrase (announcement or explicit need for dev)
        if self._require_announcement_or_high and not has_announcement_or_high:
            return False
        # Must also have enough intent points
        if intent_points < self._min_intent_points:
            return False
        if has_announcement_or_high:
            return True
        # Legacy: if not requiring announcement/high, allow medium with enough points
        if not self._require_announcement_or_high and has_medium:
            return True
        if self._allow_soft_combo and has_soft and (has_medium or intent_points >= 1):
            return True
        return False

    def quality_signal_score(self, text: str, raw_item: dict | None = None) -> tuple[int, dict[str, int]]:
        """
        Compute bonus points from quality signals (contact, budget, urgency, decision_maker).
        Returns (total_bonus, breakdown).
        """
        if not text:
            return 0, {}
        text_lower = text.lower()
        breakdown: dict[str, int] = {}
        total = 0
        for signal_name, config in self._quality.items():
            if not isinstance(config, dict):
                continue
            points = int(config.get("points", 0))
            patterns = config.get("patterns") or []
            for pat in patterns:
                try:
                    if pat.startswith("[") and "]" in pat:
                        if re.search(pat, text_lower):
                            breakdown[signal_name] = points
                            total += points
                            break
                    elif pat.lower() in text_lower:
                        breakdown[signal_name] = points
                        total += points
                        break
                except re.error:
                    if pat.lower() in text_lower:
                        breakdown[signal_name] = points
                        total += points
                        break
        # Contact: email regex (if not already matched)
        if "contact" not in breakdown and re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", text_lower):
            p = int((self._quality.get("contact") or {}).get("points", 4))
            breakdown["contact"] = p
            total += p
        return total, breakdown

    def recency_score(self, timestamp: datetime | None, max_hours: int = 168) -> int:
        """Return points for recency (0–5). Newer = more points. 12h=5, 24h=4, 48h=3, 7d=2, 14d=1, older=0."""
        if not timestamp:
            return 0
        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        delta = now - timestamp
        hours = delta.total_seconds() / 3600
        if hours <= 12:
            return 5
        if hours <= 24:
            return 4
        if hours <= 48:
            return 3
        if hours <= 168:  # 7 days
            return 2
        if hours <= 336:  # 14 days
            return 1
        return 0

    def engagement_score(self, raw_item: dict | None) -> int:
        """0–2 points for engagement (upvotes, comments, quality_score from actor)."""
        if not raw_item:
            return 0
        score = 0
        if raw_item.get("num_comments", 0) > 0 or raw_item.get("score", 0) > 0:
            score += 1
        if (raw_item.get("quality_score") or 0) >= 50:
            score += 1
        return min(2, score)

    def platform_weight(self, platform: str) -> int:
        """Extra points by platform (B2B strength)."""
        return PLATFORM_WEIGHTS.get(platform.lower(), 0)

    def compute(
        self,
        post_text: str,
        platform: str,
        timestamp: datetime | None = None,
        raw_item: dict | None = None,
    ) -> dict[str, Any]:
        """
        Full relevance computation for one post.
        Returns:
          - passed: bool (False if negative match or failed intent gate)
          - reject_reason: str | None
          - score: int (0–100+)
          - matched_keywords: list[str]
          - matched_tiers: list[str]
          - intent_points: int
          - quality_bonus: int
          - recency_bonus: int
          - platform_bonus: int
        """
        result: dict[str, Any] = {
            "passed": False,
            "reject_reason": None,
            "score": 0,
            "matched_keywords": [],
            "matched_tiers": [],
            "intent_points": 0,
            "quality_bonus": 0,
            "recency_bonus": 0,
            "platform_bonus": 0,
            "engagement_bonus": 0,
        }
        # 1) Negative gate
        neg_match, reason = self.match_negative(post_text or "")
        if neg_match:
            result["reject_reason"] = reason
            return result
        # 2) Intent phrase matching
        matches = self.match_intent_phrases(post_text or "")
        result["matched_keywords"] = list(dict.fromkeys(p for p, _, _ in matches))
        result["matched_tiers"] = list(dict.fromkeys(t for _, t, _ in matches))
        intent_pts = self.intent_score_from_matches(matches)
        result["intent_points"] = intent_pts
        if not self.passes_intent_gate(matches, intent_pts):
            result["reject_reason"] = "intent_gate_failed"
            return result
        # 3) Quality signals
        q_bonus, _ = self.quality_signal_score(post_text, raw_item)
        result["quality_bonus"] = q_bonus
        # 4) Recency
        result["recency_bonus"] = self.recency_score(timestamp)
        # 5) Platform
        result["platform_bonus"] = self.platform_weight(platform)
        # 6) Engagement
        result["engagement_bonus"] = self.engagement_score(raw_item)
        # Total score (cap at 100 for readability; can allow over)
        total = (
            intent_pts
            + result["quality_bonus"]
            + result["recency_bonus"]
            + result["platform_bonus"]
            + result["engagement_bonus"]
        )
        result["score"] = min(100, total)
        result["passed"] = True
        return result


# Singleton for reuse
_engine: RelevanceEngine | None = None


def get_engine() -> RelevanceEngine:
    global _engine
    if _engine is None:
        _engine = RelevanceEngine()
    return _engine


def compute_relevance(
    post_text: str,
    platform: str,
    timestamp: datetime | None = None,
    raw_item: dict | None = None,
) -> dict[str, Any]:
    """Convenience: compute relevance using default engine."""
    return get_engine().compute(post_text, platform, timestamp, raw_item)
