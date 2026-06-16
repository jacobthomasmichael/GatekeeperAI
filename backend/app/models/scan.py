import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Boolean, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("app_submissions.id"), nullable=False, index=True)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    # queued | running | complete | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    risk_tier: Mapped[str | None] = mapped_column(String(10), nullable=True)  # green | yellow | red
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # initial | update
    scan_type: Mapped[str] = mapped_column(String(10), nullable=False, default="initial")
    # for updates: the last approved scan this version is replacing
    previous_scan_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("scans.id"), nullable=True)
    # true when update risk is same or lower than previous approved version
    is_expedited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScanResult(Base):
    __tablename__ = "scan_results"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("scans.id"), nullable=False, index=True)
    # secrets | dependency | egress | pii | llm
    scanner_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # pending | running | passed | flagged | error
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # none | low | medium | high | critical
    severity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    findings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
