#!/usr/bin/env python3
"""
Run the Phase 1 lead generation pipeline: ingest (5 platforms) -> static filter -> AI scoring -> email queue.
Usage:
  python -m pipeline.run_pipeline                    # full pipeline
  python -m pipeline.run_pipeline --ingest-only      # only run actors + store raw_posts
  python -m pipeline.run_pipeline --filter-only      # only static filter
  python -m pipeline.run_pipeline --ai-only          # only AI scoring
  python -m pipeline.run_pipeline --platforms reddit twitter  # limit platforms
  python -m pipeline.run_pipeline --send-email                # send queued emails via AWS SES (direct)
"""
from __future__ import annotations
import argparse
import logging
import os
import sys

# Add project root
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

# Load .env from project root so it works when run from API (subprocess cwd may differ)
_env_path = os.path.join(_project_root, ".env")
try:
    from dotenv import load_dotenv
    load_dotenv(_env_path)
except ImportError:
    pass
# Fallback: if MONGODB_URI still missing (e.g. dotenv not installed in subprocess), read .env manually
if not (os.environ.get("MONGODB_URI") or "").strip():
    try:
        with open(_env_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip() == "MONGODB_URI" and v.strip():
                        os.environ["MONGODB_URI"] = v.strip().strip('"').strip("'")
                        break
    except Exception:
        pass

from pipeline.ingestion import run_ingestion
from pipeline.static_filter import apply_static_filter
from pipeline.ai_scoring import apply_ai_scoring
from pipeline.email_personalization import generate_email
from pipeline.email_queue import add_to_queue, get_list_unsubscribe_value, append_unsubscribe_footer
from pipeline.suppression import is_suppressed
from pipeline.profile_enrichment import enrich_lead_profile
from pipeline.contact_discovery import get_contact_for_lead
from pipeline.email_verification import verify_email
from pipeline.full_post_fetch import fetch_full_post
from pipeline.business_research import research_lead
from pipeline.ses_sender import send_queued_emails
from pipeline.config_loader import load_keywords_master
from pipeline.models import CanonicalLead
from pipeline.db import ensure_indexes
from pipeline.export_json import export_raw_posts_and_qualified
from pipeline.logger import set_run_id, get_run_id, get_logger, log_info, log_warning, log_error
from pipeline.llm_client import has_llm_config
from pipeline.leads_no_email import add_lead_no_email, get_collection as get_leads_no_email_coll
from pipeline.audit_log import log_audit, ensure_audit_indexes, get_audit_db


class _PipelineFormatter(logging.Formatter):
    """Inject run_id into the record so format can use it."""
    def format(self, record: logging.LogRecord) -> str:
        record.run_id = getattr(record, "run_id", None) or get_run_id() or "-"
        return super().format(record)


class _JsonFormatter(logging.Formatter):
    """Structured JSON log output (one JSON object per line). Set LOG_JSON=1 to enable."""
    def format(self, record: logging.LogRecord) -> str:
        import json
        run_id = getattr(record, "run_id", None) or get_run_id() or "-"
        msg = record.getMessage()
        obj = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "run_id": run_id,
            "message": msg,
        }
        if record.exc_info:
            obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(obj)


def _setup_logging() -> logging.Logger:
    """Configure pipeline logger; return it. Set LOG_JSON=1 for JSON output."""
    log = get_logger("pipeline")
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if os.environ.get("LOG_JSON", "").strip() in ("1", "true", "yes"):
            handler.setFormatter(_JsonFormatter())
        else:
            handler.setFormatter(_PipelineFormatter("[%(run_id)s] %(levelname)s: %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    return log


def _validate_env(args) -> list[str]:
    """Validate required env for the requested run. Return list of error messages."""
    errors = []
    filter_and_prepare = getattr(args, "filter_and_prepare", False)
    need_ingest = not args.filter_only and not args.ai_only and not args.list_leads and not filter_and_prepare
    need_db = not args.list_leads
    need_llm = (not args.ingest_only and not args.filter_only) or filter_and_prepare

    if need_ingest and not os.environ.get("APIFY_TOKEN", "").strip():
        errors.append("APIFY_TOKEN is required for ingestion. Set it in .env or environment.")
    if need_db:
        uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/").strip()
        if not uri or uri == "your_mongodb_uri":
            errors.append("MONGODB_URI should be set for filter/AI/email. Use .env or environment.")
    if need_llm and not has_llm_config():
        errors.append("No LLM config. Set AWS_BEDROCK_API in .env (Bedrock API key), or AWS_* / AWS2_* IAM credentials for Bedrock.")
    return errors


def get_mongo_db():
    """Connect to MongoDB for main pipeline data (lead_discovery DB). Uses MONGODB_URI."""
    from urllib.parse import urlparse
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
    path = (urlparse(uri).path or "").strip("/").split("?")[0]
    db_name = path if path else "lead_discovery"
    try:
        from pymongo import MongoClient
        client = MongoClient(uri)
        return client.get_database(db_name)
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        return None


def _safe_ascii(s: str) -> str:
    """Avoid Windows console Unicode errors when printing."""
    return s.encode("ascii", errors="replace").decode("ascii") if s else ""


def _list_leads(db):
    """Print raw_posts and qualified_leads so the user can see what was ingested and why some were processed."""
    if db is None:
        print("No MongoDB connection. Cannot list leads.")
        return
    # Where the data lives (safe: no password printed)
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
    db_name = db.name if hasattr(db, "name") else "lead_discovery"
    if "@" in uri:
        host_part = uri.split("@")[-1].split("/")[0].split("?")[0]
    else:
        host_part = uri.replace("mongodb://", "").split("/")[0].split("?")[0]
    print("Data location: MongoDB")
    print(f"  Database: {db_name}")
    print(f"  Host:     {host_part}")
    print("  Collections: raw_posts (all leads), qualified_leads (AI-approved), email_queue (outbound)")
    print("  View in: MongoDB Compass, mongosh, or this command: python -m pipeline.run_pipeline --list-leads")
    print()
    raw = db.raw_posts if hasattr(db, "raw_posts") else db["raw_posts"]
    qualified_coll = db.qualified_leads if hasattr(db, "qualified_leads") else db["qualified_leads"]

    print("--- raw_posts (ingested leads) ---")
    by_status = {}
    for doc in raw.find().sort("createdAt", -1).limit(100):
        status = doc.get("status", "?")
        by_status[status] = by_status.get(status, 0) + 1
        text = _safe_ascii((doc.get("postText") or "")[:100].replace("\n", " "))
        score = doc.get("staticScore")
        score_str = str(score) if score is not None else "-"
        reason = _safe_ascii(doc.get("rejectReason") or "")
        author = (doc.get("author") or {})
        name = _safe_ascii(author.get("name") or author.get("handle") or "?")
        print(f"  [{str(doc['_id'])[:12]}...] {doc.get('platform', '?')} | status={status} | staticScore={score_str} | {name}")
        print(f"    \"{text}...\"")
        if reason:
            print(f"    rejectReason: {reason}")
        print()
    print("Count by status:", by_status)
    print()
    print("--- qualified_leads (AI-qualified, for email) ---")
    n = 0
    for doc in qualified_coll.find().sort("createdAt", -1).limit(20):
        n += 1
        text = (doc.get("postText") or "")[:80].replace("\n", " ")
        text = text.encode("ascii", errors="replace").decode("ascii")
        print(f"  {doc.get('platform')} | aiScore={doc.get('aiScore')} | {text}...")
    if n == 0:
        print("  (none)")
    print("Pipeline list-leads done.")


def main():
    ap = argparse.ArgumentParser(description="Phase 1 Lead Gen Pipeline")
    ap.add_argument("--ingest-only", action="store_true", help="Only run ingestion (actors + store)")
    ap.add_argument("--filter-only", action="store_true", help="Only run static filter")
    ap.add_argument("--ai-only", action="store_true", help="Only run AI scoring")
    ap.add_argument("--platforms", nargs="*", help="Limit to these platforms (default: all 5)")
    ap.add_argument("--no-email", action="store_true", help="Skip email personalization + queue")
    ap.add_argument("--ai-limit", type=int, default=50, help="Max leads to AI score (default 50)")
    ap.add_argument("--list-leads", action="store_true", help="List raw_posts and qualified_leads then exit")
    ap.add_argument("--send-email", action="store_true", help="Send pending queue via AWS SES (direct, no Lambda)")
    ap.add_argument("--send-only", action="store_true", help="Only send pending queue via SES then exit (no ingest/filter/AI)")
    ap.add_argument("--dry-run", action="store_true", help="With --send-only: validate config and show pending count, no actual send")
    ap.add_argument("--after-filter-only", action="store_true", help="Only run after-filter (fetch post/profile, research, contact, generate email, add to queue or no-email); no ingest/filter/AI/send")
    ap.add_argument("--filter-and-prepare", action="store_true", help="Run static filter + AI scoring + email generation in one step (no ingest, no send). Raw posts → qualified → queue or no-email.")
    ap.add_argument("--after-filter-limit", type=int, default=200, help="Max qualified leads to process in Step 4 (default 200)")
    ap.add_argument("--export-json", metavar="FILE", help="After run, export raw_posts and qualified_leads to this JSON file")
    args = ap.parse_args()
    filter_and_prepare = getattr(args, "filter_and_prepare", False)

    print("Pipeline started.", flush=True)
    set_run_id()
    log = _setup_logging()
    log_info(log, "Pipeline started.")

    db = get_mongo_db()
    log_info(log, "DEBUG cwd", cwd=os.getcwd())
    log_info(log, "DEBUG MONGODB_URI set", value=bool(os.environ.get("MONGODB_URI", "").strip()))
    # Log which DB we use (masked) so you can verify it matches the dashboard
    _uri = (os.environ.get("MONGODB_URI") or "").strip()
    if _uri:
        if "mongodb+srv://" in _uri and "@" in _uri:
            _hint = "mongodb+srv://***@" + _uri.split("@")[-1].split("/")[0].split("?")[0]
        elif "mongodb://" in _uri:
            _host = _uri.replace("mongodb://", "").split("/")[0].split("?")[0]
            _hint = "mongodb://***@" + _host if "@" in _host else "mongodb://" + _host
        else:
            _hint = "***"
        log_info(log, "DEBUG MongoDB connection hint", hint=_hint)
    log_info(log, "DEBUG get_mongo_db() result", db_is_none=(db is None), db_name=(db.name if db is not None else None))

    if args.send_only:
        if db is None:
            log_error(log, "No MongoDB; cannot send queue")
            return 1
        if args.dry_run:
            log_info(log, "SES dry run (no emails sent)...")
            send_result = send_queued_emails(db, dry_run=True)
        else:
            log_info(log, "Sending queued emails via SES (send-only)...")
            send_result = send_queued_emails(db)  # limit=None: use app_config.send_batch_size
        extra = {"sent": send_result.get("sent", 0), "failed": send_result.get("failed", 0), "skipped_no_email": send_result.get("skipped_no_email", 0), "skipped_cap": send_result.get("skipped_cap", 0)}
        if send_result.get("skipped_paused", 0) == -1:
            extra["skipped_paused"] = True
        if send_result.get("dry_run"):
            extra["would_send"] = send_result.get("would_send", 0)
        log_info(log, "SES dry run done" if args.dry_run else "SES send done", **extra)
        return 0

    if args.list_leads:
        _list_leads(db)
        if args.export_json and db is not None:
            d = os.path.dirname(os.path.abspath(args.export_json))
            if d:
                os.makedirs(d, exist_ok=True)
            out = export_raw_posts_and_qualified(db, args.export_json)
            log_info(log, "Exported to JSON", path=out["path"], raw_count=out["raw_count"], qualified_count=out["qualified_count"])
        return 0

    # Validate env for requested steps
    env_errors = _validate_env(args)
    if env_errors:
        for err in env_errors:
            log_error(log, err)
        return 1

    if db is not None:
        try:
            ensure_indexes(db)
        except Exception as e:
            log_warning(log, "Index creation (optional) failed", error=str(e))
    try:
        ensure_audit_indexes(get_audit_db())
    except Exception:
        pass  # Audit log is best-effort; pipeline continues without it

    # Summary counters for end-of-run log
    summary = {
        "ingested": 0,
        "inserted": 0,
        "static_processed": 0,
        "static_passed": 0,
        "ai_processed": 0,
        "ai_qualified": 0,
        "email_queued": 0,
        "no_email_added": 0,
        "email_sent": 0,
        "email_failed": 0,
    }

    # --- Ingestion ---
    if not args.filter_only and not args.ai_only and not getattr(args, "after_filter_only", False) and not filter_and_prepare:
        if db is None:
            log_error(log, "MongoDB not connected. Cannot run ingestion (leads would not be stored). Set MONGODB_URI in project root .env and ensure the pipeline subprocess receives it (e.g. run from same env as dashboard).")
            return 1
        log_info(log, "Step 1: Ingestion (run Apify actors, normalize, store)...")
        # None = all platforms; [] = none (e.g. dashboard "All off")
        platforms = args.platforms
        out = run_ingestion(mongo_db=db, platforms=platforms)
        if not out.get("ok"):
            log_error(log, "Ingestion failed", error=out.get("error", out))
            return 1
        summary["ingested"] = out.get("total_leads", 0)
        summary["inserted"] = out.get("inserted", 0)
        log_info(log, "Ingestion done", total_leads=summary["ingested"], inserted=summary["inserted"])
        if summary["ingested"] > 0 and summary["inserted"] == 0:
            log_info(log, "All fetched leads were already in the database (deduplication). No new rows. Run again later for new posts or add more platforms.")
            log_info(log, "If the dashboard shows 0 raw posts, compare the 'MongoDB connection hint' above with MONGODB_URI in .env (pipeline and dashboard must use the same URI).")
        if args.ingest_only:
            if args.export_json and db is not None:
                d = os.path.dirname(os.path.abspath(args.export_json))
                if d:
                    os.makedirs(d, exist_ok=True)
                out_exp = export_raw_posts_and_qualified(db, args.export_json)
                log_info(log, "Exported to JSON", path=out_exp["path"], raw_count=out_exp["raw_count"], qualified_count=out_exp["qualified_count"])
            log_info(log, "Pipeline summary", **summary)
            return 0

    # --- Static filter ---
    if filter_and_prepare or (not args.ai_only and not getattr(args, "after_filter_only", False)):
        log_info(log, "Step 2: Static filter...")
        if db is None:
            log_info(log, "Static filter skipped (no MongoDB)")
        else:
            counts = apply_static_filter(db)
            summary["static_processed"] = counts["processed"]
            summary["static_passed"] = counts["passed"]
            log_info(log, "Static filter done", processed=counts["processed"], passed=counts["passed"], rejected=counts["rejected"])

    # --- AI scoring ---
    if filter_and_prepare or not getattr(args, "after_filter_only", False):
        log_info(log, "Step 3: AI intent scoring...")
        if db is None:
            log_info(log, "AI scoring skipped (no MongoDB)")
        else:
            ai_out = apply_ai_scoring(db, limit=args.ai_limit)
            summary["ai_processed"] = ai_out["processed"]
            summary["ai_qualified"] = ai_out["qualified"]
            log_info(log, "AI scoring done", processed=ai_out["processed"], qualified=ai_out["qualified"], not_qualified=ai_out["not_qualified"])

    # --- Email personalization + queue (or no-email for manual outreach) ---
    # Every qualified lead ends up in email_queue (if email found) or leads_no_email (if not).
    if (filter_and_prepare or not args.no_email or getattr(args, "after_filter_only", False)) and db is not None:
        step4_limit = getattr(args, "after_filter_limit", 200)
        log_info(log, "Step 4: Full fetch + research + contact + email -> queue or no-email...")
        qualified_coll = db.qualified_leads if hasattr(db, "qualified_leads") else db["qualified_leads"]
        queue_coll = db.email_queue if hasattr(db, "email_queue") else db["email_queue"]
        no_email_coll = get_leads_no_email_coll(db)
        # Pre-check: only process qualified leads not already in email_queue or leads_no_email — log so we never blindly add then dedupe
        already_queued = set(
            str(doc["leadId"]) for doc in queue_coll.find({}, {"leadId": 1})
            if doc.get("leadId")
        )
        already_no_email = set(str(doc["_id"]) for doc in no_email_coll.find({}, {"_id": 1}))
        already_done = already_queued | already_no_email
        all_qualified = list(qualified_coll.find({"status": "qualified"}).sort("createdAt", -1).limit(step4_limit * 2))
        qualified = [d for d in all_qualified if str(d.get("_id")) not in already_done][:step4_limit]
        n_total = len(all_qualified)
        n_in_queue = len(already_queued)
        n_in_no_email = len(already_no_email)
        n_skipped = n_total - len(qualified)
        log_info(log, "Step 4 pre-check: qualified total, already in queue, already no_email, skipping, to_process", n_total=n_total, already_in_queue=n_in_queue, already_no_email=n_in_no_email, skipping=n_skipped, to_process=len(qualified))
        list_unsubscribe = get_list_unsubscribe_value()
        from pipeline.web_research import web_search_lead
        queued = 0
        no_email_added = 0
        skipped_suppressed = 0
        skipped_has_website_small = 0
        for doc in qualified:
            lead = CanonicalLead.from_doc(doc)
            if is_suppressed(db, lead_id=lead.id):
                skipped_suppressed += 1
                continue
            post_fetch = fetch_full_post(lead, db)
            full_post_text = post_fetch.get("full_post_text", "")
            research = research_lead(lead.post_text or "", full_post_text)
            profile_data = enrich_lead_profile(lead, db)
            web_context = web_search_lead(
                lead,
                full_post_text=full_post_text,
                profile_text=profile_data.get("profile_text") or "",
            )
            to_email = get_contact_for_lead(lead, profile_data, web_context)
            contact_value = to_email or ""
            if not contact_value:
                profile_url = profile_data.get("profile_url") or (lead.author.profile_url if lead.author else None)
                contact_value = profile_url or lead.post_url or ""

            # Generate message (for queue or for no-email copy-paste)
            email_payload = None
            if not research.get("should_skip_email") and has_llm_config():
                email_payload = generate_email(
                    lead,
                    profile_data=profile_data,
                    full_post_text=full_post_text,
                    business_type=research.get("business_type", ""),
                    suggested_offers=research.get("suggested_offers"),
                    web_context=web_context,
                )

            if research.get("should_skip_email"):
                skipped_has_website_small += 1
                # Still add to no-email so lead is not orphaned (manual outreach)
                add_lead_no_email(
                    db,
                    lead_id=lead.id,
                    platform=lead.platform or "",
                    post_url=lead.post_url or "",
                    author_handle=lead.author.handle if lead.author else "",
                    contact_value=contact_value,
                    subject="",
                    body_text="",
                )
                log_audit("research_queue", "no_email", lead.id, platform=lead.platform, post_id=lead.post_id)
                no_email_added += 1
                continue

            if to_email:
                verify_result = verify_email(to_email)
                if verify_result.get("skip") or verify_result.get("valid"):
                    if email_payload:
                        body_text = email_payload.get("bodyText", "")
                        body_html = email_payload.get("bodyHtml", "")
                        body_text, body_html = append_unsubscribe_footer(body_text, body_html, list_unsubscribe)
                        ok, action = add_to_queue(
                            db,
                            lead.id,
                            email_payload.get("subject", ""),
                            body_text,
                            body_html,
                            to_email=to_email,
                            list_unsubscribe=list_unsubscribe,
                        )
                        if ok and action == "added":
                            log_audit("research_queue", "queued", lead.id, platform=lead.platform, post_id=lead.post_id, extra={"toEmail": to_email, "subject": email_payload.get("subject", "")})
                            queued += 1
                        elif ok and action.startswith("skipped_"):
                            log_info(log, "Step 4: lead already in queue/sent, skipping (no duplicate)", lead_id=lead.id[:16] + "...", reason=action)
                else:
                    # Email found but verification failed → no-email so user can try manually
                    add_lead_no_email(
                        db,
                        lead_id=lead.id,
                        platform=lead.platform or "",
                        post_url=lead.post_url or "",
                        author_handle=lead.author.handle if lead.author else "",
                        contact_value=contact_value,
                        subject=email_payload.get("subject", "") if email_payload else "",
                        body_text=email_payload.get("bodyText", "") if email_payload else "",
                    )
                    log_audit("research_queue", "no_email", lead.id, platform=lead.platform, post_id=lead.post_id)
                    no_email_added += 1
            else:
                # No email found → always add to no-email for manual DM
                add_lead_no_email(
                    db,
                    lead_id=lead.id,
                    platform=lead.platform or "",
                    post_url=lead.post_url or "",
                    author_handle=lead.author.handle if lead.author else "",
                    contact_value=contact_value,
                    subject=email_payload.get("subject", "") if email_payload else "",
                    body_text=email_payload.get("bodyText", "") if email_payload else "",
                )
                log_audit("research_queue", "no_email", lead.id, platform=lead.platform, post_id=lead.post_id)
                no_email_added += 1
        summary["email_queued"] = queued
        summary["no_email_added"] = no_email_added
        extra = {}
        if no_email_added:
            extra["no_email_added"] = no_email_added
        if skipped_suppressed:
            extra["skipped_suppressed"] = skipped_suppressed
        if skipped_has_website_small:
            extra["skipped_has_website_small"] = skipped_has_website_small
        if extra:
            log_info(log, "Step 4 done", queued=queued, **extra)
        else:
            log_info(log, "Step 4 done", queued=queued)
    else:
        log_info(log, "Step 4: Skipped (--no-email or no DB)")

    if filter_and_prepare:
        log_info(log, "Pipeline done (filter-and-prepare). Summary", **summary)
        return 0

    if args.send_email and db is not None and not getattr(args, "after_filter_only", False):
        log_info(log, "Step 5: Sending queued emails via SES...")
        send_result = send_queued_emails(db)  # limit=None: use app_config.send_batch_size
        extra = {"sent": send_result["sent"], "failed": send_result["failed"], "skipped_no_email": send_result["skipped_no_email"], "skipped_cap": send_result["skipped_cap"]}
        if send_result.get("skipped_paused", 0) == -1:
            extra["skipped_paused"] = True
        log_info(log, "SES send done", **extra)
        summary["email_sent"] = send_result["sent"]
        summary["email_failed"] = send_result["failed"]

    if args.export_json and db is not None:
        d = os.path.dirname(os.path.abspath(args.export_json))
        if d:
            os.makedirs(d, exist_ok=True)
        out = export_raw_posts_and_qualified(db, args.export_json)
        log_info(log, "Exported to JSON", path=out["path"], raw_count=out["raw_count"], qualified_count=out["qualified_count"])

    log_info(log, "Pipeline done. Summary", **summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
