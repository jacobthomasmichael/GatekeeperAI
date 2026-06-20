"""
Story 1 tests: passkeys table, nullable hashed_password, and stub endpoints.

These tests verify the scaffolding is correct before Stories 2 and 3 implement
the actual WebAuthn attestation and assertion flows.
"""
import uuid

import pytest
from sqlalchemy import inspect, text

from sqlalchemy import select

from app.models.passkey import Passkey
from app.models.user import User
from app.services.auth_service import hash_password


# ── Schema tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_passkeys_table_exists(db):
    """passkeys table must exist with the expected columns."""
    result = await db.execute(
        text("SELECT column_name FROM information_schema.columns WHERE table_name='passkeys' ORDER BY column_name")
    )
    cols = {row[0] for row in result.fetchall()}
    assert cols == {"id", "user_id", "credential_id", "public_key", "sign_count", "device_label", "created_at"}


@pytest.mark.asyncio
async def test_passkeys_credential_id_is_unique(db):
    """credential_id must have a unique constraint."""
    result = await db.execute(text(
        "SELECT indexname FROM pg_indexes WHERE tablename='passkeys' AND indexname='ix_passkeys_credential_id'"
    ))
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_hashed_password_is_nullable(db):
    """Users table must allow NULL hashed_password for passkey-only accounts."""
    result = await db.execute(text(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_name='users' AND column_name='hashed_password'"
    ))
    is_nullable = result.scalar_one()
    assert is_nullable == "YES"


# ── ORM model tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_can_create_passkey_only_user(db):
    """A user with no hashed_password should persist successfully."""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"passkey_{suffix}@example.com",
        username=f"passkey_{suffix}",
        hashed_password=None,
        role="ic",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    assert user.id is not None
    assert user.hashed_password is None


@pytest.mark.asyncio
async def test_can_create_and_retrieve_passkey_row(db):
    """Passkey model should round-trip through the DB correctly."""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"pk_{suffix}@example.com",
        username=f"pk_{suffix}",
        hashed_password=None,
        role="ic",
    )
    db.add(user)
    await db.flush()

    cred_id = b"fake-credential-id-" + suffix.encode()
    pub_key = b"fake-public-key-" + suffix.encode()
    passkey = Passkey(
        user_id=user.id,
        credential_id=cred_id,
        public_key=pub_key,
        sign_count=0,
        device_label="MacBook Touch ID",
    )
    db.add(passkey)
    await db.commit()
    await db.refresh(passkey)

    assert passkey.id is not None
    assert passkey.user_id == user.id
    assert passkey.credential_id == cred_id
    assert passkey.public_key == pub_key
    assert passkey.sign_count == 0
    assert passkey.device_label == "MacBook Touch ID"
    assert passkey.created_at is not None


@pytest.mark.asyncio
async def test_passkey_deleted_on_user_delete(db):
    """CASCADE delete: removing a user should remove their passkeys."""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"del_{suffix}@example.com",
        username=f"del_{suffix}",
        hashed_password=None,
        role="ic",
    )
    db.add(user)
    await db.flush()

    passkey = Passkey(
        user_id=user.id,
        credential_id=b"cred-" + suffix.encode(),
        public_key=b"pubkey-" + suffix.encode(),
        sign_count=0,
    )
    db.add(passkey)
    await db.commit()

    passkey_id = passkey.id
    await db.delete(user)
    await db.commit()
    # Expire the session identity map so the next query hits the DB, not the cache
    db.expire_all()

    result = await db.execute(select(Passkey).where(Passkey.id == passkey_id))
    assert result.scalar_one_or_none() is None


# ── Stub endpoint tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_passkey_authenticate_begin_returns_501(client):
    """No auth required — but must return 501 until Story 3 is implemented."""
    resp = await client.post(
        "/api/v1/auth/passkey/authenticate/begin",
        json={"email": "anyone@example.com"},
    )
    assert resp.status_code == 501
    assert resp.json()["detail"] == "Not implemented yet"


@pytest.mark.asyncio
async def test_passkey_authenticate_complete_returns_501(client):
    resp = await client.post(
        "/api/v1/auth/passkey/authenticate/complete",
        json={"credential": {}},
    )
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_passkey_register_begin_requires_auth(client):
    """register/begin must be protected — unauthenticated calls get 401."""
    resp = await client.post(
        "/api/v1/auth/passkey/register/begin",
        json={"device_label": "My Mac"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_passkey_register_begin_returns_501_when_authed(client, ic_token):
    resp = await client.post(
        "/api/v1/auth/passkey/register/begin",
        json={"device_label": "My Mac"},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 501
    assert resp.json()["detail"] == "Not implemented yet"


@pytest.mark.asyncio
async def test_passkey_register_complete_requires_auth(client):
    resp = await client.post(
        "/api/v1/auth/passkey/register/complete",
        json={"credential": {}},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_passkey_register_complete_returns_501_when_authed(client, ic_token):
    resp = await client.post(
        "/api/v1/auth/passkey/register/complete",
        json={"credential": {}},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 501
