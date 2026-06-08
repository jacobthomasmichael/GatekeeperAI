from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval
from app.models.scan import Scan
from app.services import notification_service

if TYPE_CHECKING:
    from app.models.app_submission import AppSubmission

_YELLOW_RED_SLA_HOURS = 24


async def route_after_scan(
    scan: Scan,
    submission: "AppSubmission",
    db: AsyncSession,
) -> Approval | None:
    """Create an Approval record for Yellow/Red scans; no-op for Green."""
    if scan.risk_tier == "green":
        return None

    deadline = datetime.now(timezone.utc) + timedelta(hours=_YELLOW_RED_SLA_HOURS)
    approval = Approval(scan_id=scan.id, sla_deadline=deadline)
    db.add(approval)
    await db.flush()
    await db.refresh(approval)

    notification_service.notify_approvers(
        app_name=submission.name,
        risk_tier=scan.risk_tier or "unknown",
        approval_id=str(approval.id),
        sla_deadline=deadline.isoformat(),
    )

    return approval


async def process_decision(
    approval: Approval,
    decision: str,
    comment: str,
    approver_id: str,
    scan: Scan,
    submission: "AppSubmission",
    db: AsyncSession,
) -> None:
    """Record the approver's decision and update submission status."""
    approval.decision = decision
    approval.comment = comment
    approval.approver_id = approver_id
    approval.decided_at = datetime.now(timezone.utc)

    if decision == "approved":
        submission.status = "approved"
        from worker.deploy_task import deploy_approved_app
        deploy_approved_app.delay(str(approval.id))
    else:
        submission.status = "rejected"

    notification_service.notify_submitter_decision(
        submitter_email="",  # populated from user lookup at call site
        app_name=submission.name,
        decision=decision,
        comment=comment,
    )
