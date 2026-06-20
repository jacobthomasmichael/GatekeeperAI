"""
Passkey (WebAuthn) endpoints.

Story 2: register/begin + register/complete (attestation).
Story 3: authenticate/begin + authenticate/complete (assertion) — still 501.
"""
import json
import uuid
from urllib.parse import urlparse

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import generate_registration_options, options_to_json, verify_registration_response
from webauthn.helpers.exceptions import InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import settings
from app.deps import get_current_user, get_db
from app.models.passkey import Passkey
from app.models.user import User

router = APIRouter(prefix="/auth/passkey", tags=["passkeys"])

_CHALLENGE_TTL = 300  # seconds — registration window


def _rp_id() -> str:
    return urlparse(settings.APP_BASE_URL).hostname or "localhost"


def _origin() -> str:
    return settings.APP_BASE_URL.rstrip("/")


# ── Request / response schemas ────────────────────────────────────────────────

class RegisterBeginRequest(BaseModel):
    device_label: str | None = None


class RegisterCompleteRequest(BaseModel):
    credential: dict
    device_label: str | None = None


class AuthenticateBeginRequest(BaseModel):
    email: str


class AuthenticateCompleteRequest(BaseModel):
    credential: dict


# ── Registration ──────────────────────────────────────────────────────────────

@router.post("/register/begin", status_code=status.HTTP_200_OK)
async def passkey_register_begin(
    body: RegisterBeginRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a WebAuthn registration challenge for the authenticated user."""
    # Fetch existing passkeys to exclude (prevents re-registering the same device)
    result = await db.execute(select(Passkey).where(Passkey.user_id == current_user.id))
    existing_passkeys = result.scalars().all()

    exclude_credentials = [
        PublicKeyCredentialDescriptor(
            type=PublicKeyCredentialType.PUBLIC_KEY,
            id=pk.credential_id,
        )
        for pk in existing_passkeys
    ]

    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name="GatekeeperAI",
        user_id=str(current_user.id).encode(),
        user_name=current_user.email,
        user_display_name=current_user.username,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )

    r = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    try:
        await r.setex(f"passkey:reg:{current_user.id}", _CHALLENGE_TTL, options.challenge)
    finally:
        await r.aclose()

    return json.loads(options_to_json(options))


@router.post("/register/complete", status_code=status.HTTP_201_CREATED)
async def passkey_register_complete(
    body: RegisterCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify attestation and store the new passkey credential."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    try:
        challenge: bytes | None = await r.getdel(f"passkey:reg:{current_user.id}")
    finally:
        await r.aclose()

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration session expired — please start over",
        )

    try:
        verification = verify_registration_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            require_user_verification=True,
        )
    except InvalidRegistrationResponse as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Guard against duplicate credentials (e.g. concurrent registration attempts)
    dup = await db.execute(
        select(Passkey).where(Passkey.credential_id == verification.credential_id)
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Credential already registered")

    passkey = Passkey(
        user_id=current_user.id,
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        device_label=body.device_label,
    )
    db.add(passkey)
    await db.commit()
    await db.refresh(passkey)

    return {
        "id": str(passkey.id),
        "device_label": passkey.device_label,
        "created_at": passkey.created_at.isoformat(),
    }


# ── Authentication (Story 3) ──────────────────────────────────────────────────

@router.post("/authenticate/begin", status_code=status.HTTP_200_OK)
async def passkey_authenticate_begin(
    body: AuthenticateBeginRequest,
) -> dict:
    """Generate a WebAuthn authentication challenge for the given email."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/authenticate/complete", status_code=status.HTTP_200_OK)
async def passkey_authenticate_complete(
    body: AuthenticateCompleteRequest,
) -> dict:
    """Verify assertion and return access + refresh tokens."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")
