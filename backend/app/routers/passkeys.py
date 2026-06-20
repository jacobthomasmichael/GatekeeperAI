"""
Passkey (WebAuthn) endpoints — Story 1 stubs.

Story 2 will implement register/begin + register/complete (py-webauthn attestation).
Story 3 will implement authenticate/begin + authenticate/complete (py-webauthn assertion).
"""
import uuid
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth/passkey", tags=["passkeys"])


class RegisterBeginRequest(BaseModel):
    device_label: str | None = None


class RegisterCompleteRequest(BaseModel):
    credential: dict
    device_label: str | None = None


class AuthenticateBeginRequest(BaseModel):
    email: str


class AuthenticateCompleteRequest(BaseModel):
    credential: dict


@router.post("/register/begin", status_code=status.HTTP_200_OK)
async def passkey_register_begin(
    body: RegisterBeginRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Generate a WebAuthn registration challenge for the authenticated user."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


@router.post("/register/complete", status_code=status.HTTP_201_CREATED)
async def passkey_register_complete(
    body: RegisterCompleteRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Verify attestation and store the new passkey credential."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented yet")


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
