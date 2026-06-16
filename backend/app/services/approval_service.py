from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.approval import Approval
from app.models.scan import Scan
from app.models.user import User
from app.services import notification_service

if TYPE_CHECKING:
    from app.models.app_submission import AppSubmission

_YELLOW_RED_SLA_HOURS = 24
_EXPEDITED_SLA_HOURS = 4

_RISK_ORDER = {"green": 0, "yellow": 1, "red": 2}


def _is_same_or_lower_risk(new_tier: str | None, previous_tier: str | None) -> bool:
    return _RISK_ORDER.get(new_tier or "", 99) <= _RISK_ORDER.get(previous_tier or "", 0)


async def _approver_emails(db: AsyncSession) -> list[str]:
    """Return emails of all active approver and admin users."""
    result = await db.execute(
        select(User.email).where(
            User.role.in_(["approver", "admin"]),
            User.is_active.is_(True),
        )
    )
    emails = list(result.scalars().all())
    # Merge in any statically configured fallback addresses
    if settings.APPROVER_EMAILS:
        for addr in settings.APPROVER_EMAILS.split(","):
            addr = addr.strip()
            if addr and addr not in emails:
                emails.append(addr)
    return emails


async def route_after_scan(
    scan: Scan,
    submission: "AppSubmission",
    db: AsyncSession,
) -> Approval | None:
    """Create an Approval record after a scan completes.

    - Green initial scans: no approval needed (auto-deploy path).
    - Update scans with same/lower risk: expedited approval (4hr SLA).
    - All other yellow/red scans: standard approval (24hr SLA).
    """
    # Determine if this update qualifies for expedited review
    if scan.scan_type == "update" and scan.previous_scan_id:
        prev = await db.get(Scan, scan.previous_scan_id)
        if prev and _is_same_or_lower_risk(scan.risk_tier, prev.risk_tier):
            scan.is_expedited = True

    # Green initial scans skip the queue entirely
    if scan.risk_tier == "green" and scan.scan_type == "initial":
        return None

    sla_hours = _EXPEDITED_SLA_HOURS if scan.is_expedited else _YELLOW_RED_SLA_HOURS
    deadline = datetime.now(timezone.utc) + timedelta(hours=sla_hours)
    approval = Approval(scan_id=scan.id, sla_deadline=deadline)
    db.add(approval)
    await db.flush()
    await db.refresh(approval)

    approver_emails = await _approver_emails(db)
    notification_service.notify_approvers(
        app_name=submission.name,
        risk_tier=scan.risk_tier or "unknown",
        approval_id=str(approval.id),
        sla_deadline=deadline.strftime("%Y-%m-%d %H:%M UTC"),
        approver_emails=approver_emails,
    )

    return approval


async def process_decision(
    approval: Approval,
    decision: str,
    comment: str,
    approver_id: str,
    scan: Scan,
    submission: "AppSubmission",
    submitter_email: str,
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
        submitter_email=submitter_email,
        app_name=submission.name,
        decision=decision,
        comment=comment,
    )
