import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.app_submission import AppSubmission
from app.models.scan import Scan
from app.schemas.scan import ScanTriggerRequest, ScanResponse

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

    # Phase 3: enqueue Celery task here
    # from app.worker.celery_app import run_scan_pipeline
    # run_scan_pipeline.delay(str(scan.id))

    return {"scan_id": str(scan.id), "status": "queued"}


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Scan:
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan
