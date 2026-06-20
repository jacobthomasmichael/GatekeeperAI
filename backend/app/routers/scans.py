import hmac
import json
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_db, get_current_user
from app.models.app_submission import AppSubmission
from app.models.scan import Scan, ScanResult
from app.models.user import User
from app.schemas.scan import ScanTriggerRequest, ScanResponse, ScanResultResponse
from app.services.auth_service import decode_token

_bearer_optional = HTTPBearer(auto_error=False)


async def _get_user_for_stream(
    token: str | None = Query(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Auth for SSE endpoints: accepts token via query param (EventSource) or Authorization header."""
    raw = token or (credentials.credentials if credentials else None)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(raw)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post("/trigger/{app_id}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    app_id: uuid.UUID,
    payload: ScanTriggerRequest,
    x_hook_secret: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Called by the post-receive git hook after each push to main."""
    if settings.HOOK_SECRET:
        if not x_hook_secret or not hmac.compare_digest(x_hook_secret, settings.HOOK_SECRET):
            raise HTTPException(status_code=401, detail="Invalid hook secret")

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
    current_user: User = Depends(_get_user_for_stream),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE stream of real-time scanner progress events."""
    import redis.asyncio as aioredis

    async def event_generator():
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        channel = f"scan:{scan_id}:events"

        # Subscribe BEFORE checking DB so we don't miss an event published
        # between the DB read and the subscribe call.
        await pubsub.subscribe(channel)

        try:
            # If the scan already finished before we connected, Redis pubsub
            # won't replay the complete event. Detect this and synthesize one.
            result = await db.execute(select(Scan).where(Scan.id == scan_id))
            scan = result.scalar_one_or_none()
            if scan and scan.status in ("complete", "failed"):
                evt = json.dumps({
                    "event": scan.status if scan.status == "failed" else "complete",
                    "risk_tier": scan.risk_tier,
                    "risk_score": scan.risk_score,
                })
                yield f"data: {evt}\n\n"
                return

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
