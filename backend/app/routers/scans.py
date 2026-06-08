import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_db, get_current_user
from app.models.app_submission import AppSubmission
from app.models.scan import Scan, ScanResult
from app.models.user import User
from app.schemas.scan import ScanTriggerRequest, ScanResponse, ScanResultResponse

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post("/trigger/{app_id}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    app_id: uuid.UUID,
    payload: ScanTriggerRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Called by the post-receive git hook after each push to main."""
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    scan = Scan(
        submission_id=app_id,
        commit_sha=payload.commit_sha,
        status="queued",
    )
    db.add(scan)

    app.commit_sha = payload.commit_sha
    app.status = "scanning"
    await db.flush()
    await db.refresh(scan)

    # Enqueue Celery pipeline task
    from app.scanners.pipeline import run_scan_pipeline
    task = run_scan_pipeline.delay(str(scan.id))
    scan.celery_task_id = task.id

    await db.commit()
    return {"scan_id": str(scan.id), "status": "queued"}


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    results_q = await db.execute(
        select(ScanResult).where(ScanResult.scan_id == scan_id)
    )
    scan_results = list(results_q.scalars().all())

    return {
        "id": scan.id,
        "submission_id": scan.submission_id,
        "commit_sha": scan.commit_sha,
        "status": scan.status,
        "risk_tier": scan.risk_tier,
        "risk_score": scan.risk_score,
        "started_at": scan.started_at,
        "completed_at": scan.completed_at,
        "created_at": scan.created_at,
        "results": scan_results,
    }


@router.get("/{scan_id}/stream")
async def stream_scan_events(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE stream of real-time scanner progress events."""
    import redis.asyncio as aioredis

    async def event_generator():
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        channel = f"scan:{scan_id}:events"
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
                    data = json.loads(message["data"])
                    if data.get("event") in ("complete", "error"):
                        break
        finally:
            await pubsub.unsubscribe(channel)
            await r.aclose()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/app/{app_id}", response_model=list[ScanResponse])
async def list_app_scans(
    app_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list:
    result = await db.execute(
        select(Scan)
        .where(Scan.submission_id == app_id)
        .order_by(Scan.created_at.desc())
    )
    scans = list(result.scalars().all())
    return [
        {
            "id": s.id,
            "submission_id": s.submission_id,
            "commit_sha": s.commit_sha,
            "status": s.status,
            "risk_tier": s.risk_tier,
            "risk_score": s.risk_score,
            "started_at": s.started_at,
            "completed_at": s.completed_at,
            "created_at": s.created_at,
            "results": [],
        }
        for s in scans
    ]
