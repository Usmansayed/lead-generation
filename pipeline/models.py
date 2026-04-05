"""
Canonical data model for the lead generation platform.
All platforms normalize into this unified schema (see leadGeneration-project.md).
Schema versioned for evolution: old documents remain readable (see pipeline/schema.py).

Supports dynamic typing: use `raw` for full original payload and `extra` for any
flexible/platform-specific or future fields without schema changes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from . import schema as _schema

# Top-level keys we own; anything else is stored in `extra` for flexibility.
_CANONICAL_KEYS = frozenset({
    "_id", "_schemaVersion", "platform", "postId", "postText", "author",
    "postUrl", "timestamp", "keywordsMatched", "staticScore", "aiScore",
    "intentLabel", "status", "emailStatus", "rejectReason", "createdAt",
    "raw", "extra",
})


@dataclass
class Author:
    name: str
    handle: str
    profile_url: Optional[str] = None


@dataclass
class CanonicalLead:
    """Unified lead schema stored in raw_posts / qualified_leads.
    Use `raw` for full original payload; use `extra` for dynamic/flexible fields
    (platform-specific or future keys) so we don't drop data when schema evolves.
    """
    id: str  # SHA256(platform + postId) or fallback
    platform: str  # LinkedIn | Twitter | Instagram | Facebook | Reddit
    post_id: str  # Native ID from platform
    post_text: str
    author: Author
    post_url: str
    timestamp: datetime
    keywords_matched: list[str] = field(default_factory=list)
    static_score: int = 0
    ai_score: Optional[float] = None
    intent_label: Optional[str] = None
    status: str = "raw"  # raw | filtered | qualified | emailed | rejected
    email_status: Optional[str] = None
    reject_reason: Optional[str] = None  # from relevance engine when status=rejected
    created_at: datetime = field(default_factory=datetime.utcnow)
    # Optional: keep original payload for debugging
    raw: Optional[dict[str, Any]] = None
    # Dynamic/flexible: any extra fields (platform-specific or future); preserved round-trip.
    extra: Optional[dict[str, Any]] = None

    def to_doc(self) -> dict[str, Any]:
        """MongoDB document (use datetime for createdAt). Includes _schemaVersion for evolution-safe reads.
        Writes `extra` so dynamic fields are persisted.
        """
        doc: dict[str, Any] = {
            "_id": self.id,
            "_schemaVersion": _schema.SCHEMA_VERSION_RAW_POSTS,
            "platform": self.platform,
            "postId": self.post_id,
            "postText": self.post_text,
            "author": {
                "name": self.author.name,
                "handle": self.author.handle,
                "profileUrl": self.author.profile_url,
            },
            "postUrl": self.post_url,
            "timestamp": self.timestamp,
            "keywordsMatched": self.keywords_matched,
            "staticScore": self.static_score,
            "aiScore": self.ai_score,
            "intentLabel": self.intent_label,
            "status": self.status,
            "emailStatus": self.email_status,
            "createdAt": self.created_at,
            **({"rejectReason": self.reject_reason} if self.reject_reason else {}),
            **({"raw": self.raw} if self.raw else {}),
            **({"extra": self.extra} if self.extra else {}),
        }
        return doc

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "CanonicalLead":
        """Parse MongoDB doc into CanonicalLead. Tolerates missing/extra fields (evolution-safe).
        Unknown top-level keys are collected into `extra` so nothing is dropped.
        """
        if not doc:
            raise ValueError("from_doc requires a non-empty doc")
        a = doc.get("author") or {}

        def _dt(v, default: datetime | None = None):
            d = default or datetime.utcnow()
            if v is None:
                return d
            if isinstance(v, datetime):
                return v
            return d

        def _str(x: Any, default: str = "") -> str:
            return x if isinstance(x, str) else (str(x) if x is not None else default)

        # Dynamic extra: prefer stored "extra", else collect any unknown top-level keys
        extra: Optional[dict[str, Any]] = None
        if doc.get("extra") is not None and isinstance(doc["extra"], dict):
            extra = dict(doc["extra"])
        else:
            unknown = {k: v for k, v in doc.items() if k not in _CANONICAL_KEYS}
            if unknown:
                extra = unknown

        return cls(
            id=_str(doc.get("_id"), "unknown"),
            platform=_str(doc.get("platform"), "unknown"),
            post_id=_str(doc.get("postId")),
            post_text=_str(doc.get("postText")),
            author=Author(
                name=a.get("name", "") or "",
                handle=a.get("handle", "") or "",
                profile_url=a.get("profileUrl"),
            ),
            post_url=_str(doc.get("postUrl")),
            timestamp=_dt(doc.get("timestamp")),
            keywords_matched=doc.get("keywordsMatched") if isinstance(doc.get("keywordsMatched"), list) else [],
            static_score=int(doc.get("staticScore", 0)) if doc.get("staticScore") is not None else 0,
            ai_score=doc.get("aiScore"),
            intent_label=doc.get("intentLabel"),
            status=_str(doc.get("status"), "raw"),
            email_status=doc.get("emailStatus"),
            reject_reason=doc.get("rejectReason"),
            created_at=_dt(doc.get("createdAt")),
            raw=doc.get("raw") if isinstance(doc.get("raw"), dict) else None,
            extra=extra,
        )
