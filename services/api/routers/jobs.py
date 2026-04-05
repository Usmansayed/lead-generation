"""Pipeline jobs: start, list, cancel."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any

from db import get_mongo_db
from serialize import serialize_doc
from job_runner import create_job, start_job, cancel_job, get_running_job_ids

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class StartJobBody(BaseModel):
    jobType: str
    options: dict[str, Any] | None = None


def _db():
    d = get_mongo_db()
    if d is None:
        raise HTTPException(status_code=503, detail="MongoDB not available")
    return d


JOB_TYPES = ["ingest", "filter_and_prepare", "send_email"]


@router.get("")
def list_jobs(
    job_type: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
):
    """List pipeline jobs (recent first)."""
    db = _db()
    coll = db.pipeline_jobs if hasattr(db, "pipeline_jobs") else db["pipeline_jobs"]
    q = {}
    if job_type:
        q["jobType"] = job_type
    if status:
        q["status"] = status
    total = coll.count_documents(q)
    cursor = coll.find(q).sort("createdAt", -1).skip(skip).limit(limit)
    items = [serialize_doc(x) for x in cursor]
    running_ids = get_running_job_ids()
    return {"items": items, "total": total, "skip": skip, "limit": limit, "runningIds": running_ids}


@router.get("/running")
def running_jobs():
    """Return list of job IDs currently running."""
    return {"jobIds": get_running_job_ids()}


@router.get("/{job_id}")
def get_job(job_id: str):
    """Get one job by ID."""
    db = _db()
    coll = db.pipeline_jobs if hasattr(db, "pipeline_jobs") else db["pipeline_jobs"]
    doc = coll.find_one({"_id": job_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_doc(doc)


@router.post("")
def start_new_job(body: StartJobBody):
    """Create and start a pipeline job. Body: { \"jobType\": \"ingest\", \"options\": { \"platforms\": [\"reddit\"] } }."""
    if body.jobType not in JOB_TYPES:
        raise HTTPException(status_code=400, detail=f"jobType must be one of {JOB_TYPES}")
    db = _db()
    job = create_job(db, body.jobType, body.options)
    start_job(db, job["_id"])
    return serialize_doc(job)


@router.post("/{job_id}/cancel")
def cancel_job_endpoint(job_id: str):
    """Cancel a running job (kills the process)."""
    db = _db()
    cancelled = cancel_job(db, job_id)
    return {"cancelled": cancelled, "jobId": job_id}
