import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import auth, apps, scans, approvals, deployments, secrets, setup, admin, passkeys, sso
from app.telemetry import setup_telemetry

_logger = logging.getLogger("gatekeeper.startup")


def _get_client_ip(request: Request) -> str:
    # nginx sets X-Real-IP to $remote_addr (the actual client IP).
    # Fall back to X-Forwarded-For, then direct connection IP for dev.
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_get_client_ip)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    issues = []
    if len(settings.SECRET_KEY) < 32:
        issues.append("SECRET_KEY is too short (must be ≥ 32 chars)")
    if settings.SECRET_KEY in ("changeme", "secret", "dev", "development", ""):
        issues.append("SECRET_KEY looks like a default/placeholder value")
    if len(settings.SECRET_ENCRYPTION_KEY) < 32:
        issues.append("SECRET_ENCRYPTION_KEY is too short (must be ≥ 32 chars)")
    if settings.is_production and settings.ENVIRONMENT == "production":
        if not settings.HOOK_SECRET:
            issues.append("HOOK_SECRET is not set — git hook endpoints are unprotected")
        if not settings.APP_BASE_URL.startswith("https://"):
            issues.append("APP_BASE_URL should use https:// in production")
    for issue in issues:
        _logger.warning("SECURITY: %s", issue)
    yield


app = FastAPI(
    title="GatekeeperAI",
    description="Secure enterprise app runtime",
    version="0.1.0",
    lifespan=_lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

setup_telemetry(app)

app.add_middleware(SecurityHeadersMiddleware)
_cors_origins = [settings.APP_BASE_URL]
if settings.ENVIRONMENT == "development" and "http://localhost:3000" not in _cors_origins:
    _cors_origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)


API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(apps.router, prefix=API_PREFIX)
app.include_router(scans.router, prefix=API_PREFIX)
app.include_router(approvals.router, prefix=API_PREFIX)
app.include_router(deployments.router, prefix=API_PREFIX)
app.include_router(secrets.router, prefix=API_PREFIX)
app.include_router(setup.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)
app.include_router(passkeys.router, prefix=API_PREFIX)
app.include_router(sso.auth_router, prefix=API_PREFIX)
app.include_router(sso.admin_router, prefix=API_PREFIX)


@app.get("/health")
async def health() -> dict:
    import redis as sync_redis
    services: dict[str, str] = {}
    try:
        r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.ping()
        r.close()
        services["redis"] = "ok"
    except Exception:
        services["redis"] = "error"

    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "services": services,
    }
