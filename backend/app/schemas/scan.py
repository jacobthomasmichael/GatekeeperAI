import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict


class ScanTriggerRequest(BaseModel):
    commit_sha: str


class ScanResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scanner_name: str
    status: str
    severity: Optional[str]
    findings: Optional[Any]
    duration_ms: Optional[int]
    created_at: datetime


class ScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: uuid.UUID
    commit_sha: str
    status: str
    risk_tier: Optional[str]
    risk_score: Optional[int]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    results: list[ScanResultResponse] = []
