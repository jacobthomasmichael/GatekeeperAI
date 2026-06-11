from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import auth, apps, scans, approvals, deployments, secrets, setup

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="GatekeeperAI",
    description="Secure enterprise app runtime",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
