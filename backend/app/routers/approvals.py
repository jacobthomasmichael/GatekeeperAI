import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, require_approver, require_admin
from app.models.approval import Approval
from app.models.app_submission import AppSubmission
from app.models.audit_log import AuditLog
from app.models.scan import Scan, ScanResult
from app.models.user import User
from app.schemas.approval import (
    ApprovalDecide,
    ApprovalDetailResponse,
    ApprovalResponse,
    ApprovalStats,
    ScanResultSummary,
)
from app.services import approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/stats", response_model=ApprovalStats)
async def get_stats(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ApprovalStats:
    now = datetime.now(timezone.utc)

    total = await db.scalar(select(func.count()).select_from(Approval))
    pending = await db.scalar(
        select(func.count()).select_from(Approval).where(Approval.decision.is_(None))
    )
    approved = await db.scalar(
        select(func.count()).select_from(Approval).where(Approval.decision == "approved")
    )
    rejected = await db.scalar(
        select(func.count()).select_from(Approval).where(Approval.decision == "rejected")
    )
    overdue = await db.scalar(
        select(func.count())
        .select_from(Approval)
        .where(Approval.decision.is_(None), Approval.sla_deadline < now)
    )

    return ApprovalStats(
        total=total or 0,
        pending=pending or 0,
        approved=approved or 0,
        rejected=rejected or 0,
        overdue=overdue or 0,
    )


@router.get("/", response_model=list[ApprovalDetailResponse])
async def list_approvals(
    pending_only: bool = True,
    current_user: User = Depends(require_approver),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    query = select(Approval).order_by(Approval.created_at.desc())
    if pending_only:
        query = query.where(Approval.decision.is_(None))

    result = await db.execute(query)
    approvals = list(result.scalars().all())
    return [await _build_detail(a, db) for a in approvals]


@router.get("/{approval_id}", response_model=ApprovalDetailResponse)
async def get_approval(
    approval_id: uuid.UUID,
    current_user: User = Depends(require_approver),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return await _build_detail(approval, db)


@router.post("/{approval_id}/decide", response_model=ApprovalResponse)
async def decide_approval(
    approval_id: uuid.UUID,
    payload: ApprovalDecide,
    current_user: User = Depends(require_approver),
    db: AsyncSession = Depends(get_db),
) -> Approval:
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.decision is not None:
        raise HTTPException(status_code=409, detail="This approval has already been decided")

    scan = await db.get(Scan, approval.scan_id)
    submission = await db.get(AppSubmission, scan.submission_id)

    await approval_service.process_decision(
        approval=approval,
        decision=payload.decision,
        comment=payload.comment,
        approver_id=current_user.id,
        scan=scan,
        submission=submission,
        db=db,
    )

    # Audit log
    db.add(AuditLog(
        actor_id=current_user.id,
        actor_email=current_user.email,
        action=f"approval.{payload.decision}",
        resource_type="approval",
        resource_id=approval_id,
        metadata_={
            "app_name": submission.name,
            "risk_tier": scan.risk_tier,
            "comment": payload.comment,
        },
    ))

    await db.flush()
    await db.refresh(approval)
    return approval


async def _build_detail(approval: Approval, db: AsyncSession) -> dict:
    scan = await db.get(Scan, approval.scan_id)
    submission = await db.get(AppSubmission, scan.submission_id)

    results_q = await db.execute(
        select(ScanResult).where(ScanResult.scan_id == scan.id)
    )
    scan_results = [
        ScanResultSummary.model_validate(r)
        for r in results_q.scalars().all()
    ]

    return {
        "id": approval.id,
        "scan_id": approval.scan_id,
        "approver_id": approval.approver_id,
        "decision": approval.decision,
        "comment": approval.comment,
        "sla_deadline": approval.sla_deadline,
        "decided_at": approval.decided_at,
        "created_at": approval.created_at,
        "app_name": submission.name,
        "app_description": submission.description,
        "submitter_id": submission.submitter_id,
        "commit_sha": scan.commit_sha,
        "risk_tier": scan.risk_tier,
        "risk_score": scan.risk_score,
        "scan_results": scan_results,
    }
