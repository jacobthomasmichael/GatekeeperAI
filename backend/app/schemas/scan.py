import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, ConfigDict, field_validator


class ScanTriggerRequest(BaseModel):
    commit_sha: str

    @field_validator("commit_sha")
    @classmethod
    def commit_sha_format(cls, v: str) -> str:
        import re
        if not re.match(r"^[0-9a-f]{40}$", v):
            raise ValueError("commit_sha must be a 40-character hex SHA")
        return v


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
