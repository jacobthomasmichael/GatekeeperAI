import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class SSOPublicConfig(BaseModel):
    enabled: bool
    provider_name: str | None


class SSOConfigCreate(BaseModel):
    provider_name: str
    discovery_url: str
    client_id: str
    client_secret: str
    group_claim_key: str = "groups"
    default_role: str = "ic"
    role_mappings: dict[str, str] = {}
    is_enabled: bool = True

    @field_validator("default_role")
    @classmethod
    def valid_role(cls, v: str) -> str:
        if v not in ("ic", "approver", "admin"):
            raise ValueError("default_role must be 'ic', 'approver', or 'admin'")
        return v

    @field_validator("role_mappings")
    @classmethod
    def valid_role_mappings(cls, v: dict[str, str]) -> dict[str, str]:
        for group, role in v.items():
            if role not in ("ic", "approver", "admin"):
                raise ValueError(f"Invalid role '{role}' for group '{group}'")
        return v


class SSOConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_name: str
    discovery_url: str
    client_id: str
    group_claim_key: str
    default_role: str
    role_mappings: dict[str, str] | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class SSOExchangeRequest(BaseModel):
    code: str


class AppGroupGrant(BaseModel):
    group_name: str


class SSOTestRequest(BaseModel):
    discovery_url: str
    client_id: str
    client_secret: str
