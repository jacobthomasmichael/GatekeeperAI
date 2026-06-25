import logging
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import redis as sync_redis
from jose import jwt, JWTError

from app.config import settings

ALGORITHM = "HS256"
_REFRESH_KEY_PREFIX = "refresh_jti:"
logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, email: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "email": email, "role": role, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "jti": jti, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e


def _redis() -> sync_redis.Redis:
    return sync_redis.from_url(settings.REDIS_URL, decode_responses=True)


def store_refresh_jti(jti: str, user_id: str) -> None:
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    try:
        r = _redis()
        r.setex(f"{_REFRESH_KEY_PREFIX}{jti}", ttl, user_id)
        r.close()
    except Exception as exc:
        logger.warning("Redis unavailable — refresh token rotation disabled: %s", exc)


def consume_refresh_jti(jti: str) -> str | None:
    """Atomically fetch-and-delete the JTI. Returns user_id or None if not found."""
    try:
        r = _redis()
        key = f"{_REFRESH_KEY_PREFIX}{jti}"
        value = r.getdel(key)
        r.close()
        return value
    except Exception as exc:
        logger.warning("Redis unavailable — cannot consume refresh JTI: %s", exc)
        return None


_ROLE_PRIORITY: dict[str, int] = {"admin": 3, "approver": 2, "ic": 1}


def map_groups_to_role(
    groups: list[str],
    mappings: dict[str, str],
    default: str = "ic",
) -> str:
    """Return the highest-priority role found across the user's SSO groups."""
    best = default
    for group in groups:
        mapped = mappings.get(group)
        if mapped and _ROLE_PRIORITY.get(mapped, 0) > _ROLE_PRIORITY.get(best, 0):
            best = mapped
    return best


def revoke_refresh_jti(jti: str) -> None:
    try:
        r = _redis()
        r.delete(f"{_REFRESH_KEY_PREFIX}{jti}")
        r.close()
    except Exception:
        pass
