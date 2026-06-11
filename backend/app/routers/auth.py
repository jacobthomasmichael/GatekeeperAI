from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.user import UserLogin, UserResponse, TokenResponse, RefreshRequest
from app.services.auth_service import (
    verify_password,
    create_access_token, create_refresh_token, decode_token,
    store_refresh_jti, consume_refresh_jti, revoke_refresh_jti,
)

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

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.email, user.role),
        refresh_token=refresh_token,
    )


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
async def logout(payload: RefreshRequest | None = None) -> None:
    if payload:
        try:
            token_data = decode_token(payload.refresh_token)
            jti = token_data.get("jti")
            if jti:
                revoke_refresh_jti(jti)
        except ValueError:
            pass


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
