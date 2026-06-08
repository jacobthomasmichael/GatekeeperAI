import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ApprovalDecide(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str

    @field_validator("comment")
    @classmethod
    def comment_required(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("Comment must be at least 10 characters")
        return v.strip()


class ScanResultSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    scanner_name: str
    status: str
    severity: Optional[str]
    findings: Optional[Any]
    duration_ms: Optional[int]


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    scan_id: uuid.UUID
    approver_id: Optional[uuid.UUID]
    decision: Optional[str]
    comment: Optional[str]
    sla_deadline: Optional[datetime]
    decided_at: Optional[datetime]
    created_at: datetime


class ApprovalDetailResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    approver_id: Optional[uuid.UUID]
    decision: Optional[str]
    comment: Optional[str]
    sla_deadline: Optional[datetime]
    decided_at: Optional[datetime]
    created_at: datetime
    # Embedded scan + submission context
    app_name: str
    app_description: str
    submitter_id: uuid.UUID
    commit_sha: str
    risk_tier: Optional[str]
    risk_score: Optional[int]
    scan_results: list[ScanResultSummary]


class ApprovalStats(BaseModel):
    total: int
    pending: int
    approved: int
    rejected: int
    overdue: int
