import uuid

from pydantic import BaseModel, field_validator


class SecretCreate(BaseModel):
    key_name: str
    value: str

    @field_validator("key_name")
    @classmethod
    def validate_key_name(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("key_name must be alphanumeric with _ or - only")
        return v.upper()


class SecretKeyResponse(BaseModel):
    key_name: str
    submission_id: uuid.UUID
