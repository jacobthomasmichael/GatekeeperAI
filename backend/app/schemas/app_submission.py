import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class AppCreate(BaseModel):
    name: str
    description: str

    @field_validator("name")
    @classmethod
    def name_must_be_slug_safe(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$", v):
            raise ValueError("name must be 3-50 lowercase alphanumeric characters and hyphens")
        return v

    @field_validator("description")
    @classmethod
    def description_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Description must be at least 10 characters")
        if len(v) > 2000:
            raise ValueError("Description must be 2000 characters or fewer")
        return v


class RejectionFeedback(BaseModel):
    decision: str
    comment: str
    decided_at: datetime


class AppResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submitter_id: uuid.UUID
    name: str
    description: str
    repo_path: str
    repo_url: str
    status: str
    risk_tier: Optional[str]
    commit_sha: Optional[str]
    created_at: datetime
    updated_at: datetime
    rejection: Optional[RejectionFeedback] = None
