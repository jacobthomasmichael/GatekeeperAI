"""Celery Beat task: fires every 15 minutes, notifies on overdue approvals."""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings
from app.models.approval import Approval
from app.models.app_submission import AppSubmission
from app.models.scan import Scan
from app.services.notification_service import notify_approvers
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def check_sla_deadlines() -> None:
    asyncio.run(_async_check())


async def _async_check() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Approval).where(
                    Approval.decision.is_(None),
                    Approval.sla_deadline < now,
                )
            )
            overdue = result.scalars().all()
            if not overdue:
                logger.info("SLA check: no overdue approvals")
                return

            logger.warning("SLA check: %d overdue approval(s)", len(overdue))
            for approval in overdue:
                scan = await db.get(Scan, approval.scan_id)
                submission = await db.get(AppSubmission, scan.submission_id)
                hours_over = (now - approval.sla_deadline).total_seconds() / 3600
                logger.warning(
                    "OVERDUE approval=%s app=%s tier=%s %.1fh past deadline",
                    approval.id, submission.name, scan.risk_tier, hours_over,
                )
                notify_approvers(
                    app_name=submission.name,
                    risk_tier=scan.risk_tier or "unknown",
                    approval_id=str(approval.id),
                    sla_deadline=f"OVERDUE by {hours_over:.1f}h",
                )
    finally:
        await engine.dispose()
