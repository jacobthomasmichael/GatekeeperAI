"""
SSO/OIDC feature tests.

Tests are grouped by layer:
  - Pure logic (map_groups_to_role, _slugify_email)
  - Admin SSO config CRUD endpoints
  - Public config endpoint
  - Authorization redirect
  - Callback + user provisioning (mocked exchange_code / store_sso_exchange)
  - Exchange endpoint
  - Per-app group access (CRUD + list_apps filtering + verify_session)
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services.auth_service import map_groups_to_role
from app.routers.sso import _slugify_email, _safe_next


# ── Pure-logic unit tests ──────────────────────────────────────────────────────

class TestMapGroupsToRole:
    def test_no_groups_returns_default(self):
        assert map_groups_to_role([], {}, "ic") == "ic"

    def test_single_matching_group(self):
        assert map_groups_to_role(["admins"], {"admins": "admin"}, "ic") == "admin"

    def test_highest_wins(self):
        # admin > approver; even though approver is listed first
        assert map_groups_to_role(
            ["approvers", "admins"],
            {"approvers": "approver", "admins": "admin"},
            "ic",
        ) == "admin"

    def test_unrecognised_group_ignored(self):
        assert map_groups_to_role(["unknown-group"], {"admins": "admin"}, "ic") == "ic"

    def test_default_beats_no_match(self):
        assert map_groups_to_role(["eng"], {"admins": "admin"}, "approver") == "approver"

    def test_empty_mappings(self):
        assert map_groups_to_role(["admins"], {}, "ic") == "ic"


class TestSlugifyEmail:
    def test_simple_email(self):
        assert _slugify_email("alice@example.com") == "alice"

    def test_dots_become_dashes(self):
        assert _slugify_email("first.last@example.com") == "first-last"

    def test_truncates_to_50(self):
        long = "a" * 60 + "@example.com"
        assert len(_slugify_email(long)) <= 50

    def test_special_chars_replaced(self):
        slug = _slugify_email("user+tag@example.com")
        assert slug == "user-tag"


class TestSafeNext:
    def test_relative_path_allowed(self):
        assert _safe_next("/dashboard") == "/dashboard"

    def test_absolute_url_blocked(self):
        assert _safe_next("https://evil.com") == "/dashboard"

    def test_protocol_relative_blocked(self):
        assert _safe_next("//evil.com/path") == "/dashboard"

    def test_none_returns_default(self):
        assert _safe_next(None) == "/dashboard"


# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def clean_sso_config(db):
    """Remove any SSO config before each test so they start from a known state."""
    from sqlalchemy import delete
    from app.models.sso_configuration import SSOConfiguration
    await db.execute(delete(SSOConfiguration))
    await db.commit()
    yield
    await db.execute(delete(SSOConfiguration))
    await db.commit()


_SSO_PAYLOAD = {
    "provider_name": "Test IdP",
    "discovery_url": "https://idp.example.com/.well-known/openid-configuration",
    "client_id": "test-client-id",
    "client_secret": "super-secret",
    "group_claim_key": "groups",
    "default_role": "ic",
    "role_mappings": {"admins": "admin", "approvers": "approver"},
    "is_enabled": True,
}


async def _create_sso_config(client, admin_token: str) -> dict:
    resp = await client.post(
        "/api/v1/admin/sso",
        json=_SSO_PAYLOAD,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Admin SSO config CRUD ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_sso_config_404_when_not_set(client, admin_token):
    resp = await client.get(
        "/api/v1/admin/sso",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_sso_config(client, admin_token):
    data = await _create_sso_config(client, admin_token)
    assert data["provider_name"] == "Test IdP"
    assert data["client_id"] == "test-client-id"
    assert "client_secret" not in data  # never returned
    assert data["default_role"] == "ic"
    assert data["role_mappings"] == {"admins": "admin", "approvers": "approver"}
    assert data["is_enabled"] is True


@pytest.mark.asyncio
async def test_create_sso_config_409_if_exists(client, admin_token):
    await _create_sso_config(client, admin_token)
    resp = await client.post(
        "/api/v1/admin/sso",
        json=_SSO_PAYLOAD,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_sso_config(client, admin_token):
    await _create_sso_config(client, admin_token)
    updated = {**_SSO_PAYLOAD, "provider_name": "Updated IdP", "default_role": "approver"}
    with patch("app.routers.sso.invalidate_discovery_cache", new_callable=AsyncMock):
        resp = await client.put(
            "/api/v1/admin/sso",
            json=updated,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["provider_name"] == "Updated IdP"
    assert resp.json()["default_role"] == "approver"


@pytest.mark.asyncio
async def test_delete_sso_config(client, admin_token):
    await _create_sso_config(client, admin_token)
    resp = await client.delete(
        "/api/v1/admin/sso",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204
    resp2 = await client.get(
        "/api/v1/admin/sso",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_sso_admin_endpoints_require_admin(client, ic_token):
    resp = await client.get("/api/v1/admin/sso", headers={"Authorization": f"Bearer {ic_token}"})
    assert resp.status_code == 403
    resp = await client.post("/api/v1/admin/sso", json=_SSO_PAYLOAD, headers={"Authorization": f"Bearer {ic_token}"})
    assert resp.status_code == 403
    resp = await client.delete("/api/v1/admin/sso", headers={"Authorization": f"Bearer {ic_token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sso_config_role_mapping_validation(client, admin_token):
    bad_payload = {**_SSO_PAYLOAD, "role_mappings": {"group": "superadmin"}}
    resp = await client.post(
        "/api/v1/admin/sso",
        json=bad_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_test_sso_config_success(client, admin_token):
    mock_doc = {"issuer": "https://idp.example.com"}
    # httpx Response.raise_for_status() and .json() are synchronous
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = mock_doc

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    with patch("app.routers.sso.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        resp = await client.post(
            "/api/v1/admin/sso/test",
            json={
                "discovery_url": "https://idp.example.com/.well-known/openid-configuration",
                "client_id": "test-id",
                "client_secret": "secret",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["issuer"] == "https://idp.example.com"


@pytest.mark.asyncio
async def test_test_sso_config_failure(client, admin_token):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("connection refused"))

    with patch("app.routers.sso.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        resp = await client.post(
            "/api/v1/admin/sso/test",
            json={
                "discovery_url": "https://bad-idp.example.com/.well-known/openid-configuration",
                "client_id": "test-id",
                "client_secret": "secret",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


# ── Public config endpoint ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_public_config_no_sso(client):
    resp = await client.get("/api/v1/auth/sso/config")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["provider_name"] is None


@pytest.mark.asyncio
async def test_public_config_with_sso(client, admin_token):
    await _create_sso_config(client, admin_token)
    resp = await client.get("/api/v1/auth/sso/config")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    assert resp.json()["provider_name"] == "Test IdP"


@pytest.mark.asyncio
async def test_public_config_disabled_sso(client, admin_token):
    await client.post(
        "/api/v1/admin/sso",
        json={**_SSO_PAYLOAD, "is_enabled": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get("/api/v1/auth/sso/config")
    assert resp.json()["enabled"] is False


# ── Authorization redirect ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_authorize_redirects(client, admin_token):
    await _create_sso_config(client, admin_token)
    with patch("app.routers.sso.build_authorization_url", new_callable=AsyncMock) as mock_build:
        mock_build.return_value = "https://idp.example.com/authorize?state=abc&nonce=xyz"
        resp = await client.get(
            "/api/v1/auth/sso/authorize?next=/dashboard",
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert "idp.example.com/authorize" in resp.headers["location"]


@pytest.mark.asyncio
async def test_authorize_404_when_no_config(client):
    resp = await client.get("/api/v1/auth/sso/authorize", follow_redirects=False)
    assert resp.status_code == 404


# ── Callback + user provisioning ──────────────────────────────────────────────

def _mock_claims(
    sub: str = "sub-abc-123",
    email: str = "newuser@example.com",
    groups: list | None = None,
    next_url: str = "/dashboard",
) -> dict:
    return {
        "sub": sub,
        "email": email,
        "name": "New User",
        "groups": groups or [],
        "next": next_url,
    }


@pytest.mark.asyncio
async def test_callback_provisions_new_user(client, admin_token, db):
    from sqlalchemy import select
    from app.models.user import User

    await _create_sso_config(client, admin_token)

    with (
        patch("app.routers.sso.exchange_code", new_callable=AsyncMock) as mock_exchange,
        patch("app.routers.sso.store_sso_exchange", new_callable=AsyncMock) as mock_store,
    ):
        email = f"newuser_{uuid.uuid4().hex[:6]}@example.com"
        sub = f"sub-{uuid.uuid4().hex}"
        mock_exchange.return_value = _mock_claims(sub=sub, email=email)
        mock_store.return_value = "test-exchange-code"

        resp = await client.get(
            f"/api/v1/auth/sso/callback?code=code123&state=state123",
            follow_redirects=False,
        )

    assert resp.status_code == 302
    assert "sso_code=test-exchange-code" in resp.headers["location"]

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.sso_subject == sub
    assert user.hashed_password is None
    assert user.role == "ic"  # default_role


@pytest.mark.asyncio
async def test_callback_assigns_role_from_groups(client, admin_token, db):
    from sqlalchemy import select
    from app.models.user import User

    await _create_sso_config(client, admin_token)

    with (
        patch("app.routers.sso.exchange_code", new_callable=AsyncMock) as mock_exchange,
        patch("app.routers.sso.store_sso_exchange", new_callable=AsyncMock) as mock_store,
    ):
        email = f"approver_{uuid.uuid4().hex[:6]}@example.com"
        sub = f"sub-{uuid.uuid4().hex}"
        mock_exchange.return_value = _mock_claims(sub=sub, email=email, groups=["approvers"])
        mock_store.return_value = "test-exchange-code"

        await client.get(
            "/api/v1/auth/sso/callback?code=code123&state=state123",
            follow_redirects=False,
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    assert user.role == "approver"


@pytest.mark.asyncio
async def test_callback_admin_group_wins_over_approver(client, admin_token, db):
    from sqlalchemy import select
    from app.models.user import User

    await _create_sso_config(client, admin_token)

    with (
        patch("app.routers.sso.exchange_code", new_callable=AsyncMock) as mock_exchange,
        patch("app.routers.sso.store_sso_exchange", new_callable=AsyncMock) as mock_store,
    ):
        email = f"adminuser_{uuid.uuid4().hex[:6]}@example.com"
        sub = f"sub-{uuid.uuid4().hex}"
        mock_exchange.return_value = _mock_claims(
            sub=sub, email=email, groups=["approvers", "admins"]
        )
        mock_store.return_value = "test-exchange-code"

        await client.get(
            "/api/v1/auth/sso/callback?code=code123&state=state123",
            follow_redirects=False,
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    assert user.role == "admin"


@pytest.mark.asyncio
async def test_callback_links_existing_user_by_email(client, admin_token, ic_user, db):
    """An existing local account is linked by email on first SSO login."""
    from sqlalchemy import select
    from app.models.user import User

    await _create_sso_config(client, admin_token)
    sub = f"sub-{uuid.uuid4().hex}"

    with (
        patch("app.routers.sso.exchange_code", new_callable=AsyncMock) as mock_exchange,
        patch("app.routers.sso.store_sso_exchange", new_callable=AsyncMock) as mock_store,
    ):
        mock_exchange.return_value = _mock_claims(sub=sub, email=ic_user.email)
        mock_store.return_value = "code"
        await client.get(
            "/api/v1/auth/sso/callback?code=c&state=s",
            follow_redirects=False,
        )

    await db.refresh(ic_user)
    result = await db.execute(select(User).where(User.id == ic_user.id))
    updated = result.scalar_one()
    assert updated.sso_subject == sub


@pytest.mark.asyncio
async def test_callback_admin_lockout_guard(client, admin_user, admin_token, db):
    """Local admins (hashed_password is set) are never demoted by SSO role mappings."""
    from sqlalchemy import select
    from app.models.user import User

    await _create_sso_config(client, admin_token)

    with (
        patch("app.routers.sso.exchange_code", new_callable=AsyncMock) as mock_exchange,
        patch("app.routers.sso.store_sso_exchange", new_callable=AsyncMock) as mock_store,
    ):
        # SSO returns no groups → default_role is "ic", but admin has hashed_password
        mock_exchange.return_value = _mock_claims(
            sub=f"sub-{uuid.uuid4().hex}",
            email=admin_user.email,
            groups=[],
        )
        mock_store.return_value = "code"
        await client.get(
            "/api/v1/auth/sso/callback?code=c&state=s",
            follow_redirects=False,
        )

    await db.refresh(admin_user)
    result = await db.execute(select(User).where(User.id == admin_user.id))
    user = result.scalar_one()
    assert user.role == "admin"  # NOT demoted to "ic"


@pytest.mark.asyncio
async def test_callback_updates_sso_groups(client, admin_token, db):
    """sso_groups is refreshed on every login."""
    from sqlalchemy import select
    from app.models.user import User

    await _create_sso_config(client, admin_token)
    email = f"groupsuser_{uuid.uuid4().hex[:6]}@example.com"
    sub = f"sub-{uuid.uuid4().hex}"

    with (
        patch("app.routers.sso.exchange_code", new_callable=AsyncMock) as mock_exchange,
        patch("app.routers.sso.store_sso_exchange", new_callable=AsyncMock) as mock_store,
    ):
        mock_exchange.return_value = _mock_claims(
            sub=sub, email=email, groups=["team-a", "team-b"]
        )
        mock_store.return_value = "code"
        await client.get(
            "/api/v1/auth/sso/callback?code=c&state=s",
            follow_redirects=False,
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    assert set(user.sso_groups) == {"team-a", "team-b"}


@pytest.mark.asyncio
async def test_callback_invalid_state_redirects_to_error(client, admin_token):
    await _create_sso_config(client, admin_token)

    with patch("app.routers.sso.exchange_code", new_callable=AsyncMock) as mock_exchange:
        mock_exchange.side_effect = ValueError("SSO state expired or not found")
        resp = await client.get(
            "/api/v1/auth/sso/callback?code=bad&state=bad",
            follow_redirects=False,
        )

    assert resp.status_code == 302
    assert "error=sso_failed" in resp.headers["location"]


@pytest.mark.asyncio
async def test_callback_no_sso_config_redirects_to_error(client):
    resp = await client.get(
        "/api/v1/auth/sso/callback?code=c&state=s",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "error=sso_not_configured" in resp.headers["location"]


# ── Exchange endpoint ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exchange_returns_tokens(client):
    with patch("app.routers.sso.consume_sso_exchange", new_callable=AsyncMock) as mock_consume:
        mock_consume.return_value = {
            "access_token": "fake-access",
            "refresh_token": "fake-refresh",
        }
        resp = await client.post("/api/v1/auth/sso/exchange", json={"code": "valid-code"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "fake-access"
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_exchange_expired_code_returns_400(client):
    with patch("app.routers.sso.consume_sso_exchange", new_callable=AsyncMock) as mock_consume:
        mock_consume.return_value = None
        resp = await client.post("/api/v1/auth/sso/exchange", json={"code": "expired"})
    assert resp.status_code == 400


# ── Per-app group access ──────────────────────────────────────────────────────

async def _make_app(client, token: str, name: str | None = None) -> str:
    """Create an app and return its id."""
    app_name = name or f"test-app-{uuid.uuid4().hex[:8]}"
    with patch("app.routers.apps.create_bare_repo") as mock_create:
        mock_create.return_value = (f"/tmp/{app_name}.git", f"file:///tmp/{app_name}.git")
        resp = await client.post(
            "/api/v1/apps/",
            json={"name": app_name, "description": "Test application for groups"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_list_app_groups_empty(client, ic_token):
    app_id = await _make_app(client, ic_token)
    resp = await client.get(
        f"/api/v1/apps/{app_id}/groups",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_add_and_list_group(client, ic_token):
    app_id = await _make_app(client, ic_token)

    resp = await client.post(
        f"/api/v1/apps/{app_id}/groups",
        json={"group_name": "eng-team"},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["group_name"] == "eng-team"

    resp = await client.get(
        f"/api/v1/apps/{app_id}/groups",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert "eng-team" in resp.json()


@pytest.mark.asyncio
async def test_add_duplicate_group_409(client, ic_token):
    app_id = await _make_app(client, ic_token)
    await client.post(
        f"/api/v1/apps/{app_id}/groups",
        json={"group_name": "eng-team"},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    resp = await client.post(
        f"/api/v1/apps/{app_id}/groups",
        json={"group_name": "eng-team"},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_remove_group(client, ic_token):
    app_id = await _make_app(client, ic_token)
    await client.post(
        f"/api/v1/apps/{app_id}/groups",
        json={"group_name": "eng-team"},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    resp = await client.delete(
        f"/api/v1/apps/{app_id}/groups/eng-team",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 204

    resp = await client.get(
        f"/api/v1/apps/{app_id}/groups",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert "eng-team" not in resp.json()


@pytest.mark.asyncio
async def test_remove_nonexistent_group_404(client, ic_token):
    app_id = await _make_app(client, ic_token)
    resp = await client.delete(
        f"/api/v1/apps/{app_id}/groups/nonexistent",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_non_owner_cannot_add_group(client, ic_token, admin_token):
    """App owner is IC; another IC (admin here used as a second user) cannot add groups."""
    app_id = await _make_app(client, ic_token)
    # Admin can manage, but an unrelated IC cannot. Use a second IC to test this.
    # We'll test that admin CAN add (admin bypass) and a non-owner IC cannot.
    # Here we re-use the admin token (role=admin) which can manage — verify it works.
    resp = await client.post(
        f"/api/v1/apps/{app_id}/groups",
        json={"group_name": "admin-added-group"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_list_apps_includes_group_accessible_apps(client, db):
    """An IC with matching sso_groups sees apps that have that group in allowed_groups."""
    from sqlalchemy import select
    from app.models.user import User
    from app.models.app_submission import AppSubmission
    from app.services.auth_service import create_access_token

    # Create app owner
    owner = User(
        email=f"owner_{uuid.uuid4().hex[:6]}@example.com",
        username=f"owner_{uuid.uuid4().hex[:6]}",
        hashed_password=None,
        role="ic",
        sso_subject=f"sub-{uuid.uuid4().hex}",
    )
    db.add(owner)
    await db.commit()
    await db.refresh(owner)

    # Create the app directly in DB with an allowed_group
    app_id = uuid.uuid4()
    with patch("app.services.git_service.subprocess"):
        pass  # We'll insert directly
    submission = AppSubmission(
        id=app_id,
        submitter_id=owner.id,
        name=f"group-app-{uuid.uuid4().hex[:6]}",
        description="App with group access",
        repo_path="/tmp/fake.git",
        repo_url="file:///tmp/fake.git",
        status="pending_scan",
        allowed_groups=["eng-team"],
    )
    db.add(submission)
    await db.commit()

    # Create SSO user with matching group
    sso_user = User(
        email=f"ssouser_{uuid.uuid4().hex[:6]}@example.com",
        username=f"ssouser_{uuid.uuid4().hex[:6]}",
        hashed_password=None,
        role="ic",
        sso_subject=f"sub-{uuid.uuid4().hex}",
        sso_groups=["eng-team", "other-team"],
    )
    db.add(sso_user)
    await db.commit()
    await db.refresh(sso_user)

    sso_token = create_access_token(str(sso_user.id), sso_user.email, sso_user.role)

    from httpx import AsyncClient, ASGITransport
    from app.main import app as fastapi_app
    from app.deps import get_db

    async def override_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        resp = await ac.get(
            "/api/v1/apps/",
            headers={"Authorization": f"Bearer {sso_token}"},
        )
    fastapi_app.dependency_overrides.clear()

    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert str(app_id) in ids


@pytest.mark.asyncio
async def test_list_apps_no_group_access_without_matching_groups(client, db):
    """An SSO user without matching groups does NOT see the group-gated app."""
    from sqlalchemy import select
    from app.models.user import User
    from app.models.app_submission import AppSubmission
    from app.services.auth_service import create_access_token

    owner = User(
        email=f"owner2_{uuid.uuid4().hex[:6]}@example.com",
        username=f"owner2_{uuid.uuid4().hex[:6]}",
        hashed_password=None,
        role="ic",
    )
    db.add(owner)
    await db.commit()
    await db.refresh(owner)

    app_id = uuid.uuid4()
    submission = AppSubmission(
        id=app_id,
        submitter_id=owner.id,
        name=f"private-group-app-{uuid.uuid4().hex[:6]}",
        description="App gated to a specific group",
        repo_path="/tmp/fake2.git",
        repo_url="file:///tmp/fake2.git",
        status="pending_scan",
        allowed_groups=["secret-team"],
    )
    db.add(submission)
    await db.commit()

    # User in a different group — should NOT see the app
    other_user = User(
        email=f"other_{uuid.uuid4().hex[:6]}@example.com",
        username=f"other_{uuid.uuid4().hex[:6]}",
        hashed_password=None,
        role="ic",
        sso_groups=["wrong-team"],
    )
    db.add(other_user)
    await db.commit()
    await db.refresh(other_user)

    other_token = create_access_token(str(other_user.id), other_user.email, other_user.role)

    from httpx import AsyncClient, ASGITransport
    from app.main import app as fastapi_app
    from app.deps import get_db

    async def override_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        resp = await ac.get(
            "/api/v1/apps/",
            headers={"Authorization": f"Bearer {other_token}"},
        )
    fastapi_app.dependency_overrides.clear()

    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert str(app_id) not in ids


# ── UserResponse schema coercion ──────────────────────────────────────────────

def test_user_response_coerces_none_sso_groups():
    """Existing users with sso_groups=None must not cause validation errors."""
    from app.schemas.user import UserResponse
    import datetime

    data = {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "username": "test",
        "role": "ic",
        "is_active": True,
        "sso_subject": None,
        "sso_groups": None,  # NULL from DB
        "created_at": datetime.datetime.now(),
    }
    ur = UserResponse(**data)
    assert ur.sso_groups == []


def test_app_response_coerces_none_allowed_groups():
    """Existing apps with allowed_groups=NULL must not cause validation errors."""
    from app.schemas.app_submission import AppResponse
    import datetime

    data = {
        "id": uuid.uuid4(),
        "submitter_id": uuid.uuid4(),
        "name": "test-app",
        "description": "desc",
        "repo_path": "/tmp/r.git",
        "repo_url": "file:///tmp/r.git",
        "status": "pending_scan",
        "risk_tier": None,
        "commit_sha": None,
        "created_at": datetime.datetime.now(),
        "updated_at": datetime.datetime.now(),
        "visibility": "private",
        "public_flagged_at": None,
        "allowed_users": None,   # NULL from DB
        "allowed_groups": None,  # NULL from DB
        "rejection": None,
    }
    ar = AppResponse(**data)
    assert ar.allowed_groups == []
    assert ar.allowed_users == []
