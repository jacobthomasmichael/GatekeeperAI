"""
Passkey tests — Story 1 (schema/stubs) and Story 2 (registration flow).
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from webauthn.helpers.structs import (
    AttestationFormat,
    CredentialDeviceType,
    PublicKeyCredentialType,
)
from webauthn.registration.verify_registration_response import VerifiedRegistration

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
async def test_passkey_register_begin_requires_auth(client):
    """register/begin must be protected — unauthenticated calls get 401."""
    resp = await client.post(
        "/api/v1/auth/passkey/register/begin",
        json={"device_label": "My Mac"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_passkey_register_complete_requires_auth(client):
    resp = await client.post(
        "/api/v1/auth/passkey/register/complete",
        json={"credential": {}},
    )
    assert resp.status_code == 401


# ── Story 2: registration flow ────────────────────────────────────────────────

def _mock_redis(setex_side_effect=None, getdel_return=None):
    """Return a (factory_mock, client_mock) pair for patching aioredis.from_url."""
    mock_r = AsyncMock()
    mock_r.setex = AsyncMock(side_effect=setex_side_effect)
    mock_r.getdel = AsyncMock(return_value=getdel_return)
    mock_r.aclose = AsyncMock()
    factory = MagicMock(return_value=mock_r)
    return factory, mock_r


@pytest.mark.asyncio
async def test_register_begin_returns_options_shape(client, ic_token):
    """begin must return a dict with challenge, rp, and user fields."""
    factory, mock_r = _mock_redis()
    with patch("app.routers.passkeys.aioredis.from_url", factory):
        resp = await client.post(
            "/api/v1/auth/passkey/register/begin",
            json={},
            headers={"Authorization": f"Bearer {ic_token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "challenge" in body
    assert "rp" in body
    assert body["rp"]["name"] == "GatekeeperAI"
    assert "user" in body


@pytest.mark.asyncio
async def test_register_begin_stores_challenge_in_redis(client, ic_token):
    """begin must store the challenge bytes in Redis with TTL=300."""
    factory, mock_r = _mock_redis()
    with patch("app.routers.passkeys.aioredis.from_url", factory):
        resp = await client.post(
            "/api/v1/auth/passkey/register/begin",
            json={},
            headers={"Authorization": f"Bearer {ic_token}"},
        )

    assert resp.status_code == 200
    mock_r.setex.assert_called_once()
    key, ttl, _ = mock_r.setex.call_args[0]
    assert key.startswith("passkey:reg:")
    assert ttl == 300


@pytest.mark.asyncio
async def test_register_begin_excludes_existing_credential(client, ic_token, ic_user, db):
    """begin must include existing passkeys in exclude_credentials."""
    suffix = uuid.uuid4().hex[:8]
    pk = Passkey(
        user_id=ic_user.id,
        credential_id=b"existing-cred-" + suffix.encode(),
        public_key=b"existing-pubkey",
        sign_count=0,
    )
    db.add(pk)
    await db.commit()

    captured_options = {}

    def fake_gen(**kwargs):
        captured_options.update(kwargs)
        from webauthn import generate_registration_options as real_gen
        return real_gen(**kwargs)

    factory, mock_r = _mock_redis()
    with patch("app.routers.passkeys.aioredis.from_url", factory), \
         patch("app.routers.passkeys.generate_registration_options", side_effect=fake_gen):
        resp = await client.post(
            "/api/v1/auth/passkey/register/begin",
            json={},
            headers={"Authorization": f"Bearer {ic_token}"},
        )

    assert resp.status_code == 200
    excl = captured_options.get("exclude_credentials", [])
    assert any(e.id == pk.credential_id for e in excl)


def _fake_verification(credential_id: bytes = b"new-cred-id") -> VerifiedRegistration:
    return VerifiedRegistration(
        credential_id=credential_id,
        credential_public_key=b"fake-public-key",
        sign_count=0,
        aaguid="00000000-0000-0000-0000-000000000000",
        fmt=AttestationFormat.NONE,
        credential_type=PublicKeyCredentialType.PUBLIC_KEY,
        user_verified=True,
        attestation_object=b"fake-ao",
        credential_device_type=CredentialDeviceType.SINGLE_DEVICE,
        credential_backed_up=False,
    )


@pytest.mark.asyncio
async def test_register_complete_happy_path(client, ic_token, db):
    """complete must save a Passkey row and return id + device_label."""
    factory, mock_r = _mock_redis(getdel_return=b"fake-challenge")
    verification = _fake_verification(credential_id=b"happy-path-cred")

    with patch("app.routers.passkeys.aioredis.from_url", factory), \
         patch("app.routers.passkeys.verify_registration_response", return_value=verification):
        resp = await client.post(
            "/api/v1/auth/passkey/register/complete",
            json={"credential": {}, "device_label": "My MacBook"},
            headers={"Authorization": f"Bearer {ic_token}"},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["device_label"] == "My MacBook"
    assert "created_at" in body

    # Passkey row must exist in DB
    result = await db.execute(
        text("SELECT credential_id FROM passkeys WHERE credential_id = :cid"),
        {"cid": b"happy-path-cred"},
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_register_complete_expired_challenge(client, ic_token):
    """complete returns 400 when no challenge is found in Redis."""
    factory, _ = _mock_redis(getdel_return=None)
    with patch("app.routers.passkeys.aioredis.from_url", factory):
        resp = await client.post(
            "/api/v1/auth/passkey/register/complete",
            json={"credential": {}},
            headers={"Authorization": f"Bearer {ic_token}"},
        )

    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_complete_invalid_credential(client, ic_token):
    """complete returns 400 when the webauthn library rejects the credential."""
    from webauthn.helpers.exceptions import InvalidRegistrationResponse

    factory, _ = _mock_redis(getdel_return=b"fake-challenge")
    with patch("app.routers.passkeys.aioredis.from_url", factory), \
         patch("app.routers.passkeys.verify_registration_response",
               side_effect=InvalidRegistrationResponse("bad signature")):
        resp = await client.post(
            "/api/v1/auth/passkey/register/complete",
            json={"credential": {}},
            headers={"Authorization": f"Bearer {ic_token}"},
        )

    assert resp.status_code == 400
    assert "bad signature" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_complete_duplicate_credential(client, ic_token, ic_user, db):
    """complete returns 409 when the same credential is registered twice."""
    suffix = uuid.uuid4().hex[:8]
    cred_id = b"dup-cred-" + suffix.encode()

    # Pre-insert the credential as already registered
    pk = Passkey(
        user_id=ic_user.id,
        credential_id=cred_id,
        public_key=b"existing-pubkey",
        sign_count=0,
    )
    db.add(pk)
    await db.commit()

    factory, _ = _mock_redis(getdel_return=b"fake-challenge")
    verification = _fake_verification(credential_id=cred_id)

    with patch("app.routers.passkeys.aioredis.from_url", factory), \
         patch("app.routers.passkeys.verify_registration_response", return_value=verification):
        resp = await client.post(
            "/api/v1/auth/passkey/register/complete",
            json={"credential": {}},
            headers={"Authorization": f"Bearer {ic_token}"},
        )

    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_register_complete_challenge_consumed(client, ic_token):
    """complete uses getdel so the challenge cannot be replayed."""
    factory, mock_r = _mock_redis(getdel_return=b"fake-challenge")
    verification = _fake_verification(credential_id=b"consumed-cred")

    with patch("app.routers.passkeys.aioredis.from_url", factory), \
         patch("app.routers.passkeys.verify_registration_response", return_value=verification):
        await client.post(
            "/api/v1/auth/passkey/register/complete",
            json={"credential": {}},
            headers={"Authorization": f"Bearer {ic_token}"},
        )

    # getdel must have been called (atomic fetch-and-delete)
    mock_r.getdel.assert_called_once()


# ── Story 3: authentication flow ──────────────────────────────────────────────

import base64
import dataclasses
from webauthn.authentication.verify_authentication_response import VerifiedAuthentication
from webauthn.helpers.structs import CredentialDeviceType


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _seeded_passkey(user_id: uuid.UUID, cred_id: bytes) -> Passkey:
    return Passkey(
        user_id=user_id,
        credential_id=cred_id,
        public_key=b"stored-public-key",
        sign_count=5,
        device_label="Test Device",
    )


def _fake_auth_verification(new_sign_count: int = 6) -> VerifiedAuthentication:
    return VerifiedAuthentication(
        credential_id=b"auth-cred-id",
        new_sign_count=new_sign_count,
        credential_device_type=CredentialDeviceType.SINGLE_DEVICE,
        credential_backed_up=False,
        user_verified=True,
    )


@pytest.mark.asyncio
async def test_authenticate_begin_unknown_email(client):
    """begin returns 404 for an email that has no account."""
    resp = await client.post(
        "/api/v1/auth/passkey/authenticate/begin",
        json={"email": "ghost@example.com"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_authenticate_begin_no_passkeys(client, ic_user):
    """begin returns 400 when the user exists but has no passkeys enrolled."""
    factory, _ = _mock_redis()
    with patch("app.routers.passkeys.aioredis.from_url", factory):
        resp = await client.post(
            "/api/v1/auth/passkey/authenticate/begin",
            json={"email": ic_user.email},
        )
    assert resp.status_code == 400
    assert "no passkeys" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_authenticate_begin_returns_options_shape(client, ic_user, db):
    """begin returns a dict with challenge and allowCredentials."""
    cred_id = b"auth-begin-cred"
    db.add(_seeded_passkey(ic_user.id, cred_id))
    await db.commit()

    factory, _ = _mock_redis()
    with patch("app.routers.passkeys.aioredis.from_url", factory):
        resp = await client.post(
            "/api/v1/auth/passkey/authenticate/begin",
            json={"email": ic_user.email},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "challenge" in body
    assert "allowCredentials" in body
    assert len(body["allowCredentials"]) == 1


@pytest.mark.asyncio
async def test_authenticate_begin_stores_challenge_in_redis(client, ic_user, db):
    """begin must store the challenge in Redis under passkey:auth:{user_id}."""
    db.add(_seeded_passkey(ic_user.id, b"begin-store-cred"))
    await db.commit()

    factory, mock_r = _mock_redis()
    with patch("app.routers.passkeys.aioredis.from_url", factory):
        resp = await client.post(
            "/api/v1/auth/passkey/authenticate/begin",
            json={"email": ic_user.email},
        )

    assert resp.status_code == 200
    mock_r.setex.assert_called_once()
    key, ttl, _ = mock_r.setex.call_args[0]
    assert key == f"passkey:auth:{ic_user.id}"
    assert ttl == 300


@pytest.mark.asyncio
async def test_authenticate_complete_happy_path(client, ic_user, db):
    """complete verifies assertion, updates sign_count, and returns tokens."""
    cred_id = b"complete-happy-cred"
    passkey = _seeded_passkey(ic_user.id, cred_id)
    db.add(passkey)
    await db.commit()

    factory, _ = _mock_redis(getdel_return=b"fake-challenge")
    verification = _fake_auth_verification(new_sign_count=6)

    with patch("app.routers.passkeys.aioredis.from_url", factory), \
         patch("app.routers.passkeys.verify_authentication_response", return_value=verification):
        resp = await client.post(
            "/api/v1/auth/passkey/authenticate/complete",
            json={"credential": {"id": _b64url_encode(cred_id)}},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body

    # sign_count must be updated
    await db.refresh(passkey)
    assert passkey.sign_count == 6


@pytest.mark.asyncio
async def test_authenticate_complete_expired_challenge(client, ic_user, db):
    """complete returns 400 when no challenge found in Redis."""
    cred_id = b"expired-chal-cred"
    db.add(_seeded_passkey(ic_user.id, cred_id))
    await db.commit()

    factory, _ = _mock_redis(getdel_return=None)
    with patch("app.routers.passkeys.aioredis.from_url", factory):
        resp = await client.post(
            "/api/v1/auth/passkey/authenticate/complete",
            json={"credential": {"id": _b64url_encode(cred_id)}},
        )

    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_authenticate_complete_unknown_credential(client):
    """complete returns 400 when the credential_id isn't in the DB."""
    factory, _ = _mock_redis(getdel_return=b"fake-challenge")
    with patch("app.routers.passkeys.aioredis.from_url", factory):
        resp = await client.post(
            "/api/v1/auth/passkey/authenticate/complete",
            json={"credential": {"id": _b64url_encode(b"no-such-cred")}},
        )

    assert resp.status_code == 400
    assert "not recognized" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_authenticate_complete_invalid_assertion(client, ic_user, db):
    """complete returns 400 when the webauthn library rejects the assertion."""
    from webauthn.helpers.exceptions import InvalidAuthenticationResponse

    cred_id = b"bad-assertion-cred"
    db.add(_seeded_passkey(ic_user.id, cred_id))
    await db.commit()

    factory, _ = _mock_redis(getdel_return=b"fake-challenge")
    with patch("app.routers.passkeys.aioredis.from_url", factory), \
         patch("app.routers.passkeys.verify_authentication_response",
               side_effect=InvalidAuthenticationResponse("signature mismatch")):
        resp = await client.post(
            "/api/v1/auth/passkey/authenticate/complete",
            json={"credential": {"id": _b64url_encode(cred_id)}},
        )

    assert resp.status_code == 400
    assert "signature mismatch" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_authenticate_complete_disabled_user(client, db):
    """complete returns 403 when the account is disabled."""
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"disabled_{suffix}@example.com",
        username=f"disabled_{suffix}",
        hashed_password=None,
        role="ic",
        is_active=False,
    )
    db.add(user)
    await db.flush()

    cred_id = b"disabled-user-cred-" + suffix.encode()
    db.add(_seeded_passkey(user.id, cred_id))
    await db.commit()

    factory, _ = _mock_redis(getdel_return=b"fake-challenge")
    verification = _fake_auth_verification()
    with patch("app.routers.passkeys.aioredis.from_url", factory), \
         patch("app.routers.passkeys.verify_authentication_response", return_value=verification):
        resp = await client.post(
            "/api/v1/auth/passkey/authenticate/complete",
            json={"credential": {"id": _b64url_encode(cred_id)}},
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_authenticate_complete_challenge_consumed(client, ic_user, db):
    """complete uses getdel — challenge cannot be replayed."""
    cred_id = b"consumed-auth-cred"
    db.add(_seeded_passkey(ic_user.id, cred_id))
    await db.commit()

    factory, mock_r = _mock_redis(getdel_return=b"fake-challenge")
    verification = _fake_auth_verification()
    with patch("app.routers.passkeys.aioredis.from_url", factory), \
         patch("app.routers.passkeys.verify_authentication_response", return_value=verification):
        await client.post(
            "/api/v1/auth/passkey/authenticate/complete",
            json={"credential": {"id": _b64url_encode(cred_id)}},
        )

    mock_r.getdel.assert_called_once()
    key = mock_r.getdel.call_args[0][0]
    assert key == f"passkey:auth:{ic_user.id}"


@pytest.mark.asyncio
async def test_authenticate_complete_tokens_are_valid(client, ic_user, db):
    """Tokens returned by complete must pass /auth/me verification."""
    cred_id = b"token-valid-cred"
    db.add(_seeded_passkey(ic_user.id, cred_id))
    await db.commit()

    factory, _ = _mock_redis(getdel_return=b"fake-challenge")
    verification = _fake_auth_verification()
    with patch("app.routers.passkeys.aioredis.from_url", factory), \
         patch("app.routers.passkeys.verify_authentication_response", return_value=verification):
        resp = await client.post(
            "/api/v1/auth/passkey/authenticate/complete",
            json={"credential": {"id": _b64url_encode(cred_id)}},
        )

    access_token = resp.json()["access_token"]
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == ic_user.email
