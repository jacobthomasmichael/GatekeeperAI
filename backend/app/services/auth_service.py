import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import redis as sync_redis
from jose import jwt, JWTError

from app.config import settings

ALGORITHM = "HS256"
_REFRESH_KEY_PREFIX = "refresh_jti:"


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
    except Exception:
        pass  # Redis unavailable — rotation degrades gracefully


def consume_refresh_jti(jti: str) -> str | None:
    """Atomically fetch-and-delete the JTI. Returns user_id or None if not found."""
    try:
        r = _redis()
        key = f"{_REFRESH_KEY_PREFIX}{jti}"
        pipe = r.pipeline()
        pipe.get(key)
        pipe.delete(key)
        results = pipe.execute()
        r.close()
        return results[0]  # user_id stored at key, or None
    except Exception:
        return None


def revoke_refresh_jti(jti: str) -> None:
    try:
        r = _redis()
        r.delete(f"{_REFRESH_KEY_PREFIX}{jti}")
        r.close()
    except Exception:
        pass
