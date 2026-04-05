"""
Dashboard API: read pipeline data, run jobs, config, email control.
Run from services/api: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from contextlib import asynccontextmanager

from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from db import get_mongo_db
from serialize import serialize_doc
from routers import jobs, config, email_control


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup: ensure MongoDB indexes exist (handles fresh/empty DB)."""
    db = get_mongo_db()
    if db is not None:
        try:
            from pipeline.db import ensure_indexes
            ensure_indexes(db)
        except Exception:
            pass  # Non-fatal; collections work without indexes
    yield


app = FastAPI(title="Lead Gen Dashboard API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def db():
    d = get_mongo_db()
    if d is None:
        raise HTTPException(status_code=503, detail="MongoDB not available. Set MONGODB_URI.")
    return d


@app.get("/api/health")
def health():
    d = get_mongo_db()
    return {"ok": d is not None}


@app.get("/api/stats")
def get_stats():
    """Dashboard stats: counts by status, platform, queue, pipeline state, job summary."""
    d = db()
    raw = d.raw_posts if hasattr(d, "raw_posts") else d["raw_posts"]
    qual = d.qualified_leads if hasattr(d, "qualified_leads") else d["qualified_leads"]
    queue = d.email_queue if hasattr(d, "email_queue") else d["email_queue"]
    state_coll = d.pipeline_state if hasattr(d, "pipeline_state") else d["pipeline_state"]
    supp = d.suppression_list if hasattr(d, "suppression_list") else d["suppression_list"]
    jobs_coll = d.pipeline_jobs if hasattr(d, "pipeline_jobs") else d["pipeline_jobs"]
    seen = d.seen_post_hashes if hasattr(d, "seen_post_hashes") else d["seen_post_hashes"]

    by_status = {}
    by_platform_raw = {}
    for doc in raw.find({}, {"status": 1, "platform": 1}):
        s = doc.get("status", "?")
        by_status[s] = by_status.get(s, 0) + 1
        p = doc.get("platform") or "unknown"
        by_platform_raw[p] = by_platform_raw.get(p, 0) + 1

    by_platform_qual = {}
    for doc in qual.find({"status": "qualified"}, {"platform": 1}):
        p = doc.get("platform") or "unknown"
        by_platform_qual[p] = by_platform_qual.get(p, 0) + 1

    queue_pending = queue.count_documents({"status": "pending"})
    queue_sent = queue.count_documents({"status": "sent"})
    queue_failed = queue.count_documents({"status": "failed"})

    state_doc = state_coll.find_one({"_id": "ingestion"})
    last_run = None
    cursors = {}
    if state_doc:
        last_run = state_doc.get("lastRunAt")
        cursors = state_doc.get("cursors") or {}
    if last_run and hasattr(last_run, "isoformat"):
        last_run = last_run.isoformat() + "Z"

    job_by_stage_status: list[dict] = []
    seen_jt_st: dict[tuple[str, str], int] = {}
    for doc in jobs_coll.find({}, {"jobType": 1, "status": 1}):
        jt = doc.get("jobType") or "unknown"
        st = doc.get("status") or "unknown"
        seen_jt_st[(jt, st)] = seen_jt_st.get((jt, st), 0) + 1
    for (jt, st), cnt in seen_jt_st.items():
        job_by_stage_status.append({"jobType": jt, "status": st, "count": cnt})

    seen_count = seen.count_documents({}) if seen is not None else 0

    # leads_no_email (manual outreach when email not found)
    lne = d.leads_no_email if hasattr(d, "leads_no_email") else d["leads_no_email"]
    leads_no_email_pending = lne.count_documents({"messageSent": False})
    leads_no_email_sent = lne.count_documents({"messageSent": True})
    leads_no_email_total = lne.count_documents({})

    # Raw posts: total vs pending (status=raw = not yet run through static filter)
    raw_total = raw.count_documents({})
    raw_pending_filter = by_status.get("raw", 0)

    # Qualified breakdown: where do the 37 (or N) qualified leads actually sit?
    qualified_total = qual.count_documents({"status": "qualified"})
    in_queue_pending = queue_pending
    in_queue_sent = queue_sent
    in_no_email = leads_no_email_total
    # Qualified not yet run through research/queue step (no row in email_queue or leads_no_email)
    qualified_to_process = max(
        0,
        qualified_total - in_queue_pending - in_queue_sent - in_no_email,
    )

    # Staleness: raw_posts and qualified_leads older than 30 days (not refreshed)
    cutoff = datetime.utcnow() - timedelta(days=30)
    raw_stale_count = raw.count_documents({"createdAt": {"$lt": cutoff}})
    qualified_stale_count = qual.count_documents({"status": "qualified", "createdAt": {"$lt": cutoff}})

    return {
        "raw_posts": {
            "total": raw_total,
            "pending_filter": raw_pending_filter,
            "by_status": by_status,
            "by_platform": by_platform_raw,
        },
        "qualified_leads_count": qualified_total,
        "qualified_breakdown": {
            "in_queue_pending": in_queue_pending,
            "in_queue_sent": in_queue_sent,
            "in_no_email": in_no_email,
            "to_process": qualified_to_process,
        },
        "qualified_leads_by_platform": by_platform_qual,
        "email_queue": {"pending": queue_pending, "sent": queue_sent, "failed": queue_failed},
        "suppression_count": supp.count_documents({}),
        "seen_post_hashes_count": seen_count,
        "stale": {
            "raw_stale_count": raw_stale_count,
            "qualified_stale_count": qualified_stale_count,
        },
        "pipeline_state": {"lastRunAt": last_run, "cursors": cursors},
        "job_summary": job_by_stage_status,
        "leads_no_email": {"pending": leads_no_email_pending, "sent": leads_no_email_sent},
    }


@app.get("/api/raw_posts")
def list_raw_posts(
    status: str | None = Query(None),
    platform: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """Paginated raw_posts with optional status/platform filter."""
    d = db()
    raw = d.raw_posts if hasattr(d, "raw_posts") else d["raw_posts"]
    q = {}
    if status:
        q["status"] = status
    if platform:
        q["platform"] = platform
    total = raw.count_documents(q)
    cursor = raw.find(q).sort("createdAt", -1).skip(skip).limit(limit)
    items = [serialize_doc(x) for x in cursor]
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@app.get("/api/raw_posts/{lead_id}")
def get_raw_post(lead_id: str):
    """Single raw_posts document by _id."""
    d = db()
    raw = d.raw_posts if hasattr(d, "raw_posts") else d["raw_posts"]
    doc = raw.find_one({"_id": lead_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return serialize_doc(doc)


@app.get("/api/qualified_leads")
def list_qualified_leads(
    platform: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """Paginated qualified_leads with optional platform filter."""
    d = db()
    qual = d.qualified_leads if hasattr(d, "qualified_leads") else d["qualified_leads"]
    q = {"status": "qualified"}
    if platform:
        q["platform"] = platform
    total = qual.count_documents(q)
    cursor = qual.find(q).sort("createdAt", -1).skip(skip).limit(limit)
    items = [serialize_doc(x) for x in cursor]
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@app.get("/api/qualified_leads/{lead_id}")
def get_qualified_lead(lead_id: str):
    d = db()
    qual = d.qualified_leads if hasattr(d, "qualified_leads") else d["qualified_leads"]
    doc = qual.find_one({"_id": lead_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return serialize_doc(doc)


@app.get("/api/email_queue")
def list_email_queue(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """Paginated email_queue with optional status filter."""
    d = db()
    queue = d.email_queue if hasattr(d, "email_queue") else d["email_queue"]
    q = {"status": status} if status else {}
    total = queue.count_documents(q)
    cursor = queue.find(q).sort("createdAt", -1).skip(skip).limit(limit)
    items = [serialize_doc(x) for x in cursor]
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@app.get("/api/pipeline_state")
def get_pipeline_state():
    d = db()
    state_coll = d.pipeline_state if hasattr(d, "pipeline_state") else d["pipeline_state"]
    doc = state_coll.find_one({"_id": "ingestion"})
    if not doc:
        return {"lastRunAt": None, "cursors": {}}
    return serialize_doc(doc)


@app.get("/api/leads_no_email")
def list_leads_no_email(
    message_sent: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """Leads whose email was not found; for manual outreach (copy username/message, mark sent)."""
    d = db()
    coll = d.leads_no_email if hasattr(d, "leads_no_email") else d["leads_no_email"]
    q = {}
    if message_sent is not None:
        q["messageSent"] = message_sent
    total = coll.count_documents(q)
    cursor = coll.find(q).sort("createdAt", -1).skip(skip).limit(limit)
    items = [serialize_doc(x) for x in cursor]
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@app.patch("/api/leads_no_email/{lead_id}/mark_sent")
def mark_lead_no_email_sent(lead_id: str):
    """Mark this lead's manual message as sent (updates database)."""
    from pipeline.leads_no_email import mark_message_sent
    d = db()
    ok = mark_message_sent(d, lead_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Lead not found or already marked sent")
    return {"ok": True, "messageSent": True}


@app.get("/api/suppression_list")
def list_suppression(
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
):
    d = db()
    supp = d.suppression_list if hasattr(d, "suppression_list") else d["suppression_list"]
    total = supp.count_documents({})
    cursor = supp.find({}).sort("createdAt", -1).skip(skip).limit(limit)
    items = [serialize_doc(x) for x in cursor]
    return {"items": items, "total": total, "skip": skip, "limit": limit}


# Job control, config, email control
app.include_router(jobs.router)
app.include_router(config.router)
app.include_router(email_control.router)
