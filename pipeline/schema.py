"""
Schema versioning for stored data. Ensures improvements over time don't break existing data.
- Every document we write includes _schemaVersion (or schemaVersion) so we can evolve readers.
- Readers treat missing version as 1 and ignore unknown fields.
- Add new fields as optional with defaults; never remove fields without a migration.
"""
from __future__ import annotations
from typing import Any

# Bump when you change the shape of documents in that collection. Old docs remain readable.
SCHEMA_VERSION_RAW_POSTS = 1
SCHEMA_VERSION_QUALIFIED_LEADS = 1
SCHEMA_VERSION_EMAIL_QUEUE = 1
SCHEMA_VERSION_PIPELINE_STATE = 1
SCHEMA_VERSION_SUPPRESSION_LIST = 1
SCHEMA_VERSION_ENRICHED_PROFILES = 1
SCHEMA_VERSION_ENRICHED_POSTS = 1
SCHEMA_VERSION_AUDIT_LOG = 1

# Default when reading a doc with no version (legacy data)
DEFAULT_SCHEMA_VERSION = 1


def with_schema_version(doc: dict[str, Any], version: int, key: str = "_schemaVersion") -> dict[str, Any]:
    """Return a copy of doc with schema version set. Use when writing to MongoDB."""
    out = dict(doc)
    out[key] = version
    return out


def get_schema_version(doc: dict[str, Any], key: str = "_schemaVersion") -> int:
    """Return schema version from doc, or DEFAULT_SCHEMA_VERSION if missing (backward compat)."""
    if not doc:
        return DEFAULT_SCHEMA_VERSION
    v = doc.get(key)
    if v is None:
        return DEFAULT_SCHEMA_VERSION
    try:
        return int(v)
    except (TypeError, ValueError):
        return DEFAULT_SCHEMA_VERSION
