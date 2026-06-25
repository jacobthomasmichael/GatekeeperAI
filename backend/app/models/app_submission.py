import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppSubmission(Base):
    __tablename__ = "app_submissions"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submitter_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    repo_path: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    repo_url: Mapped[str] = mapped_column(String(512), nullable=False)
    detected_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # pending_scan | scanning | awaiting_approval | approved | rejected | deployed | failed
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_scan")
    risk_tier: Mapped[str | None] = mapped_column(String(10), nullable=True)  # green | yellow | red
    allowed_users: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)), nullable=True)
    allowed_groups: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # set at first deployment, reused for all updates to keep URL stable
    stable_external_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stable_container_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # private = requires GatekeeperAI login; public = open but flagged for review
    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="private")
    public_flagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
