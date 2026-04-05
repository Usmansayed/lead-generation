# Data and evolution: keeping the platform stable as we improve

As we add features and change behavior, stored data and logs must stay **usable and stable**. This doc describes how we achieve that.

## 1. Schema versioning (MongoDB documents)

- **Where**: `pipeline/schema.py` defines `SCHEMA_VERSION_*` constants per collection.
- **Written**: Every document we write includes `_schemaVersion` (or `schemaVersion` for pipeline_state) set to the current constant. Collections: `raw_posts`, `qualified_leads`, `email_queue`, `pipeline_state`, `suppression_list`, `enriched_profiles`.
- **Read**: Readers treat **missing** version as legacy (version 1). They never assume a document has the latest shape.
- **When you change a collection’s shape**: Bump the corresponding `SCHEMA_VERSION_*` in `schema.py`. Keep readers backward-compatible: support both old and new formats (e.g. with `.get()` and defaults). Optionally add a one-off migration script to backfill or transform old documents.

**Rules:**

- **Add new fields as optional.** Use `.get("field", default)` when reading; old docs without the field keep working.
- **Do not remove fields** from the stored shape without a migration (or only after a migration has run and you no longer need to read old docs).
- **Renaming a field** is a breaking change unless you write both old and new keys during a transition and read from both in code (then migrate and drop the old key later).

## 2. Backward-compatible readers

- **CanonicalLead.from_doc** (in `pipeline/models.py`): Tolerates missing or extra fields. Uses safe defaults for all fields except identity; ignores unknown keys. So old or partial documents still parse.
- **Email queue / pipeline state / suppression**: Code that reads from MongoDB uses `.get()` with sensible defaults. Consumers (e.g. SES sender, dashboard API) use `.get()` on job/docs so new fields in the doc don’t break them.
- **Extra fields**: Documents may contain extra keys (e.g. from future versions). Readers should ignore them; only use the keys they need.

## 3. Logging

- **Format**: Structured, key=value style (see `pipeline/logger.py`). Optional `run_id` in `extra` for tracing a full run.
- **Evolution**: Log format is **additive**. New keys can be added (e.g. `stage`, `platform`, `schema_version`) without breaking existing log parsing. Do not remove or change the meaning of existing keys; deprecate by adding a new key and documenting the change.
- **Levels**: Use standard levels (info, warning, error). Avoid logging secrets; redact or omit tokens and emails in hot paths if needed.
- **Configuration**: Python logging can be configured at startup (e.g. JSON for production, level, handlers). The pipeline does not mandate a specific backend so you can plug in rotation/retention later without changing call sites.

## 4. Config versioning

- **YAML configs** (e.g. `search_strategy.yaml`, `relevance_keywords.yaml`, `filters.yaml`, `prompts.yaml`) can include an optional `version` or `configVersion` field.
- **Behavior**: When we add incompatible config changes, we can branch in code on that version (or on presence of new keys) so old configs still run with legacy behavior. Prefer **additive** config: new optional keys with defaults so existing YAML files keep working.

## 5. Migrations (when needed)

- For a **breaking schema change** (e.g. rename a field, split a collection):
  1. Bump the schema version in `schema.py`.
  2. Update writers to write the new shape (and optionally the old key during transition).
  3. Update readers to support both old and new (using version or presence of keys).
  4. Run a **one-off migration script** (e.g. in `scripts/` or `pipeline/`) that reads each document, transforms it, and writes back (or into a new collection). Prefer doing this in batches and with idempotency so it can be re-run safely.
  5. After migration, optionally simplify readers to only support the new shape and stop writing the old key.

## 6. Summary

| Area           | Practice |
|----------------|----------|
| **Documents**  | Version with `_schemaVersion` / `schemaVersion`; readers assume missing = v1 and use `.get()` with defaults. |
| **New fields** | Add as optional; never require them for old docs. |
| **Removes**    | Don’t remove fields without migration + version bump. |
| **Logging**    | Additive key=value; add new keys as needed; don’t break existing parsers. |
| **Config**     | Prefer additive YAML; optional version field for future compatibility branching. |
| **Migrations** | One-off scripts, version-aware readers, then simplify when old data is migrated. |

This keeps the system stable as we improve: existing data stays readable, and new code can coexist with old data and config.
