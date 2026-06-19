import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class AppUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    role: str


class AppUserGrant(BaseModel):
    email: str


class VisibilityUpdate(BaseModel):
    visibility: str

    @field_validator("visibility")
    @classmethod
    def valid_visibility(cls, v: str) -> str:
        if v not in ("private", "public"):
            raise ValueError("visibility must be 'private' or 'public'")
        return v


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
    visibility: str = "private"
    public_flagged_at: Optional[datetime] = None
    allowed_users: list[uuid.UUID] = []
    rejection: Optional[RejectionFeedback] = None
