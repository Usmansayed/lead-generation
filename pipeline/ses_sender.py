"""
Production-grade AWS SES email sender. Manages everything locally via MongoDB.
Reads app_config (sending_paused, send_delay_ms, send_batch_size) from dashboard.
Respects daily cap, suppression list, retries transient SES errors with exponential backoff.
Adds Reply-To, Message-ID, X-Mailer headers. Auto-suppresses on permanent SES errors (bounce/complaint).
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from .audit_log import log_audit

log = logging.getLogger("pipeline")

# Env: AWS creds (or default), SES region, verified from-address, daily cap
SES_REGION_ENV = "AWS_REGION"
SES_FROM_ENV = "SES_FROM_EMAIL"
SES_REPLY_TO_ENV = "SES_REPLY_TO_EMAIL"
SES_DAILY_CAP_ENV = "SES_DAILY_CAP"
SES_ENDPOINT_ENV = "AWS_SES_ENDPOINT_URL"  # For LocalStack: http://localhost:4566
DEFAULT_DAILY_CAP = 100
MAX_RETRIES = 3
RETRY_BASE_SEC = 2  # Exponential backoff: 2, 4, 8 seconds
X_MAILER = "LeadGen-SES/1.0"


def _get_app_config(mongo_db) -> dict:
    """Read app_config from MongoDB (dashboard settings)."""
    try:
        from .app_config_reader import get_app_config
        return get_app_config(mongo_db) or {}
    except Exception:
        return {}


def _get_sent_today_count(mongo_db) -> int:
    """Count emails marked sent today (UTC)."""
    if mongo_db is None:
        return 0
    queue = mongo_db.email_queue if hasattr(mongo_db, "email_queue") else mongo_db["email_queue"]
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return queue.count_documents({"status": "sent", "sentAt": {"$gte": today_start}})


def _build_raw_message(
    from_email: str,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str,
    list_unsubscribe: str | None,
    reply_to: str | None = None,
) -> str:
    """Build MIME message with List-Unsubscribe, Reply-To, Message-ID, X-Mailer."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg["X-Mailer"] = X_MAILER
    msg["Message-ID"] = f"<{uuid.uuid4().hex}@leadgen.local>"
    if list_unsubscribe:
        msg["List-Unsubscribe"] = list_unsubscribe
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html or body_text.replace("\n", "<br>\n"), "html", "utf-8"))
    return msg.as_string()


def _is_transient_error(err: Exception) -> bool:
    """Check if SES error is transient (worth retrying)."""
    s = str(err).lower()
    return "throttl" in s or "rate" in s or "timeout" in s or "service unavailable" in s


def _is_permanent_error(err: Exception) -> bool:
    """Check if SES error indicates bounce/complaint (add to suppression)."""
    s = str(err).lower()
    return (
        "bounce" in s
        or "complaint" in s
        or "message rejected" in s
        or "invalid" in s
        or "does not exist" in s
        or "address" in s
        and ("rejected" in s or "invalid" in s)
    )


def send_queued_emails(
    mongo_db,
    *,
    limit: int | None = None,
    daily_cap: int | None = None,
    from_email: str | None = None,
    region: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Read pending jobs from email_queue, send via AWS SES, mark sent/failed.
    Honors app_config: sending_paused, send_delay_ms, send_batch_size.
    Returns { sent, failed, skipped_paused, skipped_no_email, skipped_cap }.
    """
    result = {
        "sent": 0,
        "failed": 0,
        "skipped_paused": 0,
        "skipped_no_email": 0,
        "skipped_cap": 0,
    }
    if mongo_db is None:
        return result

    # Read dashboard config
    config = _get_app_config(mongo_db)
    sending_paused = config.get("sending_paused") is True
    if sending_paused:
        log.info("Sending is paused (app_config.sending_paused=True); skipping send")
        result["skipped_paused"] = -1  # Sentinel: all skipped due to pause
        return result

    send_delay_ms = config.get("send_delay_ms")
    if send_delay_ms is not None and not isinstance(send_delay_ms, (int, float)):
        send_delay_ms = int(send_delay_ms) if send_delay_ms else 0
    send_delay_sec = (send_delay_ms or 0) / 1000.0

    batch_size = config.get("send_batch_size")
    if batch_size is not None and isinstance(batch_size, (int, float)):
        batch_size = max(1, int(batch_size))
    if limit is None:
        limit = batch_size or int(os.environ.get(SES_DAILY_CAP_ENV, "") or DEFAULT_DAILY_CAP)

    from_email = from_email or os.environ.get(SES_FROM_ENV, "").strip()
    if not from_email and not dry_run:
        log.warning("SES_FROM_EMAIL not set; cannot send")
        return result

    region = region or os.environ.get(SES_REGION_ENV, "").strip() or "us-east-1"
    cap = daily_cap if daily_cap is not None else int(os.environ.get(SES_DAILY_CAP_ENV, "") or DEFAULT_DAILY_CAP)
    sent_today = _get_sent_today_count(mongo_db)
    remaining = max(0, cap - sent_today)
    if remaining <= 0:
        log.info("SES daily cap reached (sent_today=%s, cap=%s)", sent_today, cap)
        result["skipped_cap"] = limit
        return result

    limit = min(limit, remaining)

    if dry_run:
        queue = mongo_db.email_queue if hasattr(mongo_db, "email_queue") else mongo_db["email_queue"]
        pending_count = queue.count_documents({"status": "pending"})
        log.info("DRY RUN: would send up to %s of %s pending (delay=%sms)", limit, pending_count, send_delay_ms or 0)
        return {**result, "dry_run": True, "would_send": min(limit, pending_count)}

    reply_to = os.environ.get(SES_REPLY_TO_ENV, "").strip() or None

    try:
        import boto3
        client_kw: dict[str, Any] = {"region_name": region}
        endpoint = os.environ.get(SES_ENDPOINT_ENV, "").strip()
        if endpoint:
            client_kw["endpoint_url"] = endpoint
        client = boto3.client("ses", **client_kw)
    except ImportError:
        log.error("boto3 not installed; pip install boto3")
        return result
    except Exception as e:
        log.error("SES client failed: %s", e)
        return result

    queue = mongo_db.email_queue if hasattr(mongo_db, "email_queue") else mongo_db["email_queue"]
    from .email_queue import mark_sent, mark_failed
    from .suppression import is_suppressed, add_to_suppression_list

    pending = list(queue.find({"status": "pending"}).sort("createdAt", 1).limit(limit))

    for i, job in enumerate(pending):
        to_email = (job.get("toEmail") or "").strip()
        if not to_email:
            result["skipped_no_email"] += 1
            mark_failed(mongo_db, job["_id"], "no toEmail")
            log_audit("send", "failed", job.get("leadId", ""), extra={"error": "no toEmail"})
            result["failed"] += 1
            continue

        if is_suppressed(mongo_db, email=to_email):
            result["skipped_no_email"] += 1
            queue.update_one({"_id": job["_id"]}, {"$set": {"status": "skipped", "error": "suppressed"}})
            continue

        subject = job.get("subject", "")
        body_text = job.get("bodyText", "")
        body_html = job.get("bodyHtml", "") or body_text.replace("\n", "<br>\n")
        list_unsubscribe = job.get("listUnsubscribe")
        raw = _build_raw_message(from_email, to_email, subject, body_text, body_html, list_unsubscribe, reply_to)

        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                client.send_raw_email(
                    Source=from_email,
                    Destinations=[to_email],
                    RawMessage={"Data": raw.encode("utf-8")},
                )
                mark_sent(mongo_db, job["_id"])
                log_audit("send", "sent", job.get("leadId", ""), extra={"toEmail": to_email, "subject": job.get("subject", "")})
                result["sent"] += 1
                log.info("Sent to %s", to_email[:30] + "…" if len(to_email) > 30 else to_email)
                last_err = None
                break
            except Exception as e:
                last_err = e
                if _is_transient_error(e) and attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_SEC ** (attempt + 1)
                    log.warning("SES transient error (attempt %s/%s), retrying in %ss: %s", attempt + 1, MAX_RETRIES, delay, e)
                    time.sleep(delay)
                else:
                    err = str(e)
                    log.warning("SES send failed for %s: %s", to_email[:20], err)
                    if _is_permanent_error(e):
                        add_to_suppression_list(mongo_db, email=to_email, reason="ses_permanent")
                        log.info("Added %s to suppression (permanent SES error)", to_email[:30])
                    mark_failed(mongo_db, job["_id"], err)
                    log_audit("send", "failed", job.get("leadId", ""), extra={"toEmail": to_email, "error": err[:200]})
                    result["failed"] += 1
                    break

        # Delay between emails (dashboard-controlled)
        if send_delay_sec > 0 and i < len(pending) - 1:
            time.sleep(send_delay_sec)

    return result


def send_test_email(to_email: str, *, subject: str | None = None, body_text: str | None = None) -> dict[str, Any]:
    """
    Send a single test email via SES. No MongoDB required.
    Returns { ok: bool, message_id?: str, error?: str }.
    """
    from_email = os.environ.get(SES_FROM_ENV, "").strip()
    if not from_email:
        return {"ok": False, "error": "SES_FROM_EMAIL not set"}
    to_email = (to_email or "").strip()
    if not to_email or "@" not in to_email:
        return {"ok": False, "error": "Invalid to_email"}
    region = os.environ.get(SES_REGION_ENV, "").strip() or "us-east-1"
    reply_to = os.environ.get(SES_REPLY_TO_ENV, "").strip() or None
    subject = subject or "Lead Gen Test Email"
    body_text = body_text or "This is a test email from the Lead Generation SES sender."
    body_html = f"<p>{body_text}</p>"
    raw = _build_raw_message(from_email, to_email, subject, body_text, body_html, None, reply_to)
    try:
        import boto3
        client_kw: dict[str, Any] = {"region_name": region}
        endpoint = os.environ.get(SES_ENDPOINT_ENV, "").strip()
        if endpoint:
            client_kw["endpoint_url"] = endpoint
        client = boto3.client("ses", **client_kw)
        resp = client.send_raw_email(
            Source=from_email,
            Destinations=[to_email],
            RawMessage={"Data": raw.encode("utf-8")},
        )
        msg_id = resp.get("MessageId", "")
        return {"ok": True, "message_id": msg_id}
    except ImportError:
        return {"ok": False, "error": "boto3 not installed; pip install boto3"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
