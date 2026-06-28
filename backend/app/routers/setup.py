import logging
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)
from pydantic import BaseModel, EmailStr, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.models.user import User
from app.services.auth_service import hash_password

router = APIRouter(prefix="/setup", tags=["setup"])

_limiter = Limiter(key_func=get_remote_address)

_ENV_FILE_PATH = os.environ.get("ENV_FILE_PATH", ".env")


class SetupPayload(BaseModel):
    company_name: str
    server_url: str
    admin_email: EmailStr
    admin_username: str
    admin_password: str
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    @field_validator("company_name")
    @classmethod
    def company_name_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Company name must be at least 2 characters")
        return v

    @field_validator("server_url")
    @classmethod
    def server_url_valid(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^https?://", v):
            raise ValueError("Server URL must start with http:// or https://")
        return v

    @field_validator("admin_username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[a-zA-Z0-9_-]{3,50}$", v):
            raise ValueError("Username must be 3-50 characters: letters, numbers, hyphens, underscores")
        return v

    @field_validator("admin_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


def _patch_env_file(updates: dict[str, str]) -> None:
    """Read the .env file, update matching KEY= lines, append missing keys."""
    try:
        with open(_ENV_FILE_PATH, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    written_keys: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        match = re.match(r"^([A-Z0-9_]+)=", line)
        if match:
            key = match.group(1)
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                written_keys.add(key)
                continue
        new_lines.append(line)

    for key, value in updates.items():
        if key not in written_keys:
            new_lines.append(f"{key}={value}\n")

    try:
        with open(_ENV_FILE_PATH, "w") as f:
            f.writelines(new_lines)
    except PermissionError:
        # In Kubernetes the root filesystem is read-only; config is managed via
        # Helm values/Secrets instead of a .env file. Log and continue — the
        # admin user was already written to the database.
        logger.warning("Cannot write %s (read-only filesystem); skipping env file update", _ENV_FILE_PATH)


@router.get("/status")
@_limiter.limit("30/minute")
async def setup_status(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(User).where(User.role == "admin").limit(1))
    admin = result.scalar_one_or_none()
    return {"complete": admin is not None}


@router.post("/complete")
@_limiter.limit("5/hour")
async def setup_complete(request: Request, payload: SetupPayload, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(User).where(User.role == "admin").limit(1))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Setup already complete")

    user = User(
        email=payload.admin_email,
        username=payload.admin_username,
        hashed_password=hash_password(payload.admin_password),
        role="admin",
    )
    db.add(user)
    await db.flush()

    _patch_env_file({
        "APP_BASE_URL": payload.server_url,
        "SMTP_HOST": payload.smtp_host,
        "SMTP_PORT": str(payload.smtp_port),
        "SMTP_USERNAME": payload.smtp_username,
        "SMTP_PASSWORD": payload.smtp_password,
        "SMTP_FROM_EMAIL": payload.smtp_from_email,
        "SMTP_USE_TLS": "true" if payload.smtp_use_tls else "false",
    })

    return {"ok": True}
