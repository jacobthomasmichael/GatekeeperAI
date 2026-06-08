import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("app_submissions.id"), nullable=False)
    scan_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("scans.id"), nullable=False)
    container_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    container_name: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    image_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # starting | running | stopped | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="starting")
    internal_port: Mapped[int] = mapped_column(Integer, nullable=False, default=8080)
    external_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    public_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    allowed_egress_urls: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    env_vars_injected: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
