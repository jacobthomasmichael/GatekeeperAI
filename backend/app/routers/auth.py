import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.user import UserLogin, UserResponse, TokenResponse, RefreshRequest
from app.services.auth_service import (
    verify_password,
    create_access_token, create_refresh_token, decode_token,
    store_refresh_jti, consume_refresh_jti, revoke_refresh_jti,
)

_COOKIE = "gka_session"
_SECURE = settings.APP_BASE_URL.startswith("https://")

router = APIRouter(prefix="/auth", tags=["auth"])
_limiter = Limiter(key_func=get_remote_address)


@router.post("/login", response_model=TokenResponse)
@_limiter.limit("20/minute")
async def login(request: Request, payload: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    refresh_token = create_refresh_token(str(user.id))
    token_data = decode_token(refresh_token)
    store_refresh_jti(token_data["jti"], str(user.id))

    access_token = create_access_token(str(user.id), user.email, user.role)
    token_resp = TokenResponse(access_token=access_token, refresh_token=refresh_token)
    response = JSONResponse(content=token_resp.model_dump())
    response.set_cookie(
        key=_COOKIE,
        value=access_token,
        httponly=True,
        secure=_SECURE,
        samesite="lax",
        path="/",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@router.post("/refresh", response_model=TokenResponse)
@_limiter.limit("30/minute")
async def refresh(request: Request, payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    try:
        token_data = decode_token(payload.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if token_data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    jti = token_data.get("jti")
    if jti:
        user_id = consume_refresh_jti(jti)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Refresh token already used or expired")

    result = await db.execute(select(User).where(User.id == token_data["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    new_refresh = create_refresh_token(str(user.id))
    new_jti = decode_token(new_refresh)["jti"]
    store_refresh_jti(new_jti, str(user.id))

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.email, user.role),
        refresh_token=new_refresh,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest | None = None) -> Response:
    if payload:
        try:
            token_data = decode_token(payload.refresh_token)
            jti = token_data.get("jti")
            if jti:
                revoke_refresh_jti(jti)
        except ValueError:
            pass
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(_COOKIE, path="/", httponly=True, samesite="lax")
    return response


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/verify/{app}", status_code=200, include_in_schema=False)
async def verify_session(
    request: Request,
    app: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Called by nginx auth_request to gate access to deployed apps.

    `app` is the safe_name of the app. Checks that the authenticated user is
    the owner or is in the app's allowed_users list. Admins and approvers
    bypass the per-app check entirely.
    """
    token = request.cookies.get(_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Admins and approvers always have access; skip the DB lookup.
    role = payload.get("role", "ic")
    if role in ("admin", "approver"):
        return {"ok": True}

    # Look up the deployed submission by its safe_name prefix on stable_container_name.
    from app.models.app_submission import AppSubmission
    result = await db.execute(
        select(AppSubmission).where(
            AppSubmission.stable_container_name.like(f"gka-{app}-%"),
            AppSubmission.status == "deployed",
        ).limit(1)
    )
    submission = result.scalar_one_or_none()

    # Unknown app — fail open so misconfigured nginx doesn't permanently lock
    # users out of an app whose DB record is missing.
    if not submission:
        return {"ok": True}

    user_id = _uuid.UUID(payload["sub"])
    if submission.submitter_id == user_id:
        return {"ok": True}
    if submission.allowed_users and user_id in submission.allowed_users:
        return {"ok": True}

    raise HTTPException(status_code=403, detail="Access denied")
