from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import AsyncSessionLocal
from app.models.audit_log import AuditLog

_SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def _extract_sub(auth_header: str | None):
    """Extract sub claim from JWT without verifying signature (already done by deps)."""
    import base64, json, uuid as _uuid
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    try:
        parts = auth_header.split(".")
        if len(parts) != 3:
            return None
        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        sub = payload.get("sub")
        return _uuid.UUID(sub) if sub else None
    except Exception:
        return None


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if request.url.path in _SKIP_PATHS or request.method == "GET":
            return response

        action = f"{request.method.lower()}.{request.url.path.strip('/').replace('/', '.')}"
        ip = request.client.host if request.client else None

        try:
            async with AsyncSessionLocal() as session:
                log = AuditLog(
                    action=action,
                    ip_address=ip,
                    actor_id=_extract_sub(request.headers.get("Authorization")),
                    metadata_={"status_code": response.status_code},
                )
                session.add(log)
                await session.commit()
        except Exception:
            pass  # never let audit logging break a real request

        return response
