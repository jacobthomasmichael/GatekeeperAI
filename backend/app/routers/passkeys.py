"""
Passkey (WebAuthn) endpoints.

Story 2: register/begin + register/complete (attestation).
Story 3: authenticate/begin + authenticate/complete (assertion).
"""
import base64
import json
import uuid
from urllib.parse import urlparse

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
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
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    store_refresh_jti,
)

router = APIRouter(prefix="/auth/passkey", tags=["passkeys"])

_CHALLENGE_TTL = 300  # seconds


def _rp_id() -> str:
    return urlparse(settings.APP_BASE_URL).hostname or "localhost"


def _origin() -> str:
    return settings.APP_BASE_URL.rstrip("/")


def _b64url_decode(s: str) -> bytes:
    s = s.replace("-", "+").replace("_", "/")
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.b64decode(s)


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
    result = await db.execute(select(Passkey).where(Passkey.user_id == current_user.id))
    existing_passkeys = result.scalars().all()

    exclude_credentials = [
        PublicKeyCredentialDescriptor(type=PublicKeyCredentialType.PUBLIC_KEY, id=pk.credential_id)
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


# ── Passkey management ────────────────────────────────────────────────────────

@router.get("/", status_code=status.HTTP_200_OK)
async def list_passkeys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all passkeys enrolled by the current user."""
    result = await db.execute(
        select(Passkey).where(Passkey.user_id == current_user.id).order_by(Passkey.created_at)
    )
    return [
        {"id": str(pk.id), "device_label": pk.device_label, "created_at": pk.created_at.isoformat()}
        for pk in result.scalars().all()
    ]


@router.delete("/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_passkey(
    passkey_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove one of the current user's passkeys."""
    result = await db.execute(
        select(Passkey).where(Passkey.id == passkey_id, Passkey.user_id == current_user.id)
    )
    passkey = result.scalar_one_or_none()
    if not passkey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Passkey not found")
    await db.delete(passkey)
    await db.commit()


# ── Authentication ────────────────────────────────────────────────────────────

@router.post("/authenticate/begin", status_code=status.HTTP_200_OK)
async def passkey_authenticate_begin(
    body: AuthenticateBeginRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a WebAuthn authentication challenge for the given email."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No account found with that email")

    result = await db.execute(select(Passkey).where(Passkey.user_id == user.id))
    passkeys = result.scalars().all()
    if not passkeys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No passkeys registered for this account",
        )

    allow_credentials = [
        PublicKeyCredentialDescriptor(type=PublicKeyCredentialType.PUBLIC_KEY, id=pk.credential_id)
        for pk in passkeys
    ]

    options = generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    r = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    try:
        await r.setex(f"passkey:auth:{user.id}", _CHALLENGE_TTL, options.challenge)
    finally:
        await r.aclose()

    return json.loads(options_to_json(options))


@router.post("/authenticate/complete", status_code=status.HTTP_200_OK)
async def passkey_authenticate_complete(
    body: AuthenticateCompleteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify assertion, update sign count, and return access + refresh tokens."""
    try:
        cred_id_bytes = _b64url_decode(body.credential["id"])
    except (KeyError, Exception):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credential format")

    result = await db.execute(select(Passkey).where(Passkey.credential_id == cred_id_bytes))
    passkey = result.scalar_one_or_none()
    if not passkey:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credential not recognized")

    r = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    try:
        challenge: bytes | None = await r.getdel(f"passkey:auth:{passkey.user_id}")
    finally:
        await r.aclose()

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication session expired — please start over",
        )

    try:
        verification = verify_authentication_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Update sign count — protects against cloned authenticators
    passkey.sign_count = verification.new_sign_count
    await db.commit()

    user = await db.get(User, passkey.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    refresh_token = create_refresh_token(str(user.id))
    token_data = decode_token(refresh_token)
    store_refresh_jti(token_data["jti"], str(user.id))
    access_token = create_access_token(str(user.id), user.email, user.role)

    return {"access_token": access_token, "refresh_token": refresh_token}
