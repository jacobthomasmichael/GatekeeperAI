import logging
import re
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_db, get_current_user, require_admin
from app.models.sso_configuration import SSOConfiguration
from app.models.user import User
from app.schemas.sso import (
    AppGroupGrant,
    SSOConfigCreate,
    SSOConfigResponse,
    SSOExchangeRequest,
    SSOPublicConfig,
    SSOTestRequest,
)
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    map_groups_to_role,
    store_refresh_jti,
)
from app.services.oidc_service import (
    build_authorization_url,
    consume_sso_exchange,
    decrypt_client_secret,
    encrypt_client_secret,
    exchange_code,
    fetch_discovery_document,
    invalidate_discovery_cache,
    store_sso_exchange,
)

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth/sso", tags=["sso"])
admin_router = APIRouter(prefix="/admin/sso", tags=["sso-admin"])

_REDIRECT_URI_PATH = "/api/v1/auth/sso/callback"


def _redirect_uri() -> str:
    return settings.APP_BASE_URL.rstrip("/") + _REDIRECT_URI_PATH


def _safe_next(next_url: str | None) -> str:
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/dashboard"


async def _get_active_config(db: AsyncSession) -> SSOConfiguration | None:
    result = await db.execute(
        select(SSOConfiguration).where(SSOConfiguration.is_enabled == True).limit(1)
    )
    return result.scalar_one_or_none()


# ── Public endpoints ──────────────────────────────────────────────────────────

@auth_router.get("/config", response_model=SSOPublicConfig)
async def get_public_sso_config(db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(SSOConfiguration).limit(1))
    config = result.scalar_one_or_none()
    return {
        "enabled": config.is_enabled if config else False,
        "provider_name": config.provider_name if config else None,
    }


@auth_router.get("/authorize")
async def sso_authorize(
    next: str = Query(default="/dashboard"),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    config = await _get_active_config(db)
    if not config:
        raise HTTPException(status_code=404, detail="SSO is not configured")

    next_url = _safe_next(next)
    try:
        auth_url = await build_authorization_url(
            config.discovery_url,
            config.client_id,
            _redirect_uri(),
            next_url,
        )
    except Exception as exc:
        logger.error("SSO authorize error: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to reach identity provider")

    return RedirectResponse(url=auth_url, status_code=302)


@auth_router.get("/callback")
async def sso_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    config = await _get_active_config(db)
    if not config:
        error_url = settings.APP_BASE_URL.rstrip("/") + "/login?error=sso_not_configured"
        return RedirectResponse(url=error_url, status_code=302)

    try:
        claims = await exchange_code(
            config.discovery_url,
            config.client_id,
            config.encrypted_client_secret,
            config.group_claim_key,
            code,
            state,
            _redirect_uri(),
        )
    except ValueError as exc:
        logger.warning("SSO callback validation error: %s", exc)
        error_url = settings.APP_BASE_URL.rstrip("/") + "/login?error=sso_failed"
        return RedirectResponse(url=error_url, status_code=302)
    except Exception as exc:
        logger.error("SSO callback unexpected error: %s", exc)
        error_url = settings.APP_BASE_URL.rstrip("/") + "/login?error=sso_failed"
        return RedirectResponse(url=error_url, status_code=302)

    sub = claims["sub"]
    email = claims["email"].lower().strip()
    groups: list[str] = claims.get("groups", [])
    name = claims.get("name", email.split("@")[0])
    next_url = _safe_next(claims.get("next"))

    user = await _provision_user(db, sub, email, name, groups, config)

    refresh_token = create_refresh_token(str(user.id))
    token_data = decode_token(refresh_token)
    store_refresh_jti(token_data["jti"], str(user.id))
    access_token = create_access_token(str(user.id), user.email, user.role)

    exchange_code_key = await store_sso_exchange(access_token, refresh_token)
    redirect_url = (
        settings.APP_BASE_URL.rstrip("/")
        + f"/login?sso_code={exchange_code_key}&next={next_url}"
    )
    return RedirectResponse(url=redirect_url, status_code=302)


async def _provision_user(
    db: AsyncSession,
    sub: str,
    email: str,
    name: str,
    groups: list[str],
    config: SSOConfiguration,
) -> User:
    from sqlalchemy.exc import IntegrityError

    # 1. Look up by sso_subject
    result = await db.execute(select(User).where(User.sso_subject == sub))
    user = result.scalar_one_or_none()

    # 2. Fall back to email
    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if user:
        user.sso_subject = sub
        user.sso_groups = groups if groups else None
        # Admin lockout guard: don't override role for local accounts
        if user.hashed_password is None:
            mappings = config.role_mappings or {}
            user.role = map_groups_to_role(groups, mappings, config.default_role)
        try:
            await db.commit()
            await db.refresh(user)
        except Exception:
            await db.rollback()
            raise
        return user

    # 3. Create new user
    username = _slugify_email(email)
    new_user = User(
        email=email,
        username=username,
        hashed_password=None,
        role=map_groups_to_role(groups, config.role_mappings or {}, config.default_role),
        sso_subject=sub,
        sso_groups=groups if groups else None,
    )
    db.add(new_user)
    try:
        await db.flush()
        await db.refresh(new_user)
    except IntegrityError:
        await db.rollback()
        # Collision on username — append id fragment
        new_user.username = f"{username[:44]}{str(new_user.id)[:6]}"
        db.add(new_user)
        await db.flush()
        await db.refresh(new_user)

    try:
        await db.commit()
        await db.refresh(new_user)
    except IntegrityError:
        await db.rollback()
        # Race condition: another request created the user simultaneously — re-fetch
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        raise

    return new_user


def _slugify_email(email: str) -> str:
    local = email.split("@")[0]
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", local)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")[:50]
    return slug or "user"


@auth_router.post("/exchange")
async def sso_exchange(body: SSOExchangeRequest) -> dict:
    tokens = await consume_sso_exchange(body.code)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO exchange code expired or already used",
        )
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
    }


# ── Admin endpoints ───────────────────────────────────────────────────────────

@admin_router.get("", response_model=SSOConfigResponse)
async def get_sso_config(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SSOConfiguration:
    result = await db.execute(select(SSOConfiguration).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="SSO not configured")
    return config


@admin_router.post("", response_model=SSOConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_sso_config(
    payload: SSOConfigCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SSOConfiguration:
    result = await db.execute(select(SSOConfiguration).limit(1))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="SSO configuration already exists — use PUT to update")

    config = SSOConfiguration(
        provider_name=payload.provider_name,
        discovery_url=payload.discovery_url,
        client_id=payload.client_id,
        encrypted_client_secret=encrypt_client_secret(payload.client_secret),
        group_claim_key=payload.group_claim_key,
        default_role=payload.default_role,
        role_mappings=payload.role_mappings or None,
        is_enabled=payload.is_enabled,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@admin_router.put("", response_model=SSOConfigResponse)
async def update_sso_config(
    payload: SSOConfigCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SSOConfiguration:
    result = await db.execute(select(SSOConfiguration).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="No SSO configuration to update — use POST to create")

    old_discovery_url = config.discovery_url
    config.provider_name = payload.provider_name
    config.discovery_url = payload.discovery_url
    config.client_id = payload.client_id
    config.encrypted_client_secret = encrypt_client_secret(payload.client_secret)
    config.group_claim_key = payload.group_claim_key
    config.default_role = payload.default_role
    config.role_mappings = payload.role_mappings or None
    config.is_enabled = payload.is_enabled

    await db.commit()
    await db.refresh(config)

    # Invalidate discovery cache if URL changed
    if old_discovery_url != config.discovery_url:
        await invalidate_discovery_cache(old_discovery_url)
    await invalidate_discovery_cache(config.discovery_url)

    return config


@admin_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sso_config(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(SSOConfiguration).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="SSO not configured")
    await db.delete(config)
    await db.commit()


@admin_router.post("/test")
async def test_sso_config(
    payload: SSOTestRequest,
    _: User = Depends(require_admin),
) -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(payload.discovery_url)
            resp.raise_for_status()
            doc = resp.json()
        return {"ok": True, "issuer": doc.get("issuer", "unknown")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
