from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import AsyncSessionLocal
from app.models.audit_log import AuditLog

_SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


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
                    metadata_={"status_code": response.status_code},
                )
                session.add(log)
                await session.commit()
        except Exception:
            pass  # never let audit logging break a real request

        return response
