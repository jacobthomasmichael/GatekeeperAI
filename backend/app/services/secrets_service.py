import base64
import hashlib

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.secret_store import SecretStore


def _fernet() -> Fernet:
    raw = settings.SECRET_ENCRYPTION_KEY.encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return Fernet(key)


async def set_secret(
    submission_id: str,
    key_name: str,
    value: str,
    created_by: str,
    db: AsyncSession,
) -> SecretStore:
    encrypted = _fernet().encrypt(value.encode()).decode()
    result = await db.execute(
        select(SecretStore).where(
            SecretStore.submission_id == submission_id,
            SecretStore.key_name == key_name,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.encrypted_value = encrypted
        await db.flush()
        return existing

    secret = SecretStore(
        submission_id=submission_id,
        key_name=key_name,
        encrypted_value=encrypted,
        created_by=created_by,
    )
    db.add(secret)
    await db.flush()
    return secret


async def list_secret_keys(submission_id: str, db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(SecretStore.key_name).where(SecretStore.submission_id == submission_id)
    )
    return list(result.scalars().all())


async def delete_secret(submission_id: str, key_name: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(SecretStore).where(
            SecretStore.submission_id == submission_id,
            SecretStore.key_name == key_name,
        )
    )
    secret = result.scalar_one_or_none()
    if not secret:
        return False
    await db.delete(secret)
    await db.flush()
    return True


async def decrypt_all(submission_id: str, db: AsyncSession) -> dict[str, str]:
    result = await db.execute(
        select(SecretStore).where(SecretStore.submission_id == submission_id)
    )
    f = _fernet()
    return {
        s.key_name: f.decrypt(s.encrypted_value.encode()).decode()
        for s in result.scalars().all()
    }
