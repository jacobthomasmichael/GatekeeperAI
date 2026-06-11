import pytest


# ── Authorization ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_users_requires_admin(client, ic_token):
    resp = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {ic_token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_user_requires_admin(client, ic_token):
    resp = await client.post(
        "/api/v1/admin/users",
        json={"email": "x@example.com", "username": "xuser", "password": "password123", "role": "ic"},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_audit_logs_requires_admin(client, ic_token):
    resp = await client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {ic_token}"})
    assert resp.status_code == 403


# ── User listing ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_users_as_admin(client, admin_token, admin_user, ic_user):
    resp = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()]
    assert admin_user.email in emails
    assert ic_user.email in emails


# ── User creation ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_user_as_admin(client, admin_token):
    resp = await client.post(
        "/api/v1/admin/users",
        json={"email": "new@example.com", "username": "newuser", "password": "password123", "role": "approver"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert data["role"] == "approver"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_user_duplicate_email_rejected(client, admin_token, ic_user):
    resp = await client.post(
        "/api/v1/admin/users",
        json={"email": ic_user.email, "username": "different_name", "password": "password123", "role": "ic"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_user_duplicate_username_rejected(client, admin_token, ic_user):
    resp = await client.post(
        "/api/v1/admin/users",
        json={"email": "different@example.com", "username": ic_user.username, "password": "password123", "role": "ic"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_user_invalid_role_rejected(client, admin_token):
    resp = await client.post(
        "/api/v1/admin/users",
        json={"email": "x2@example.com", "username": "x2user", "password": "password123", "role": "superuser"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


# ── User updates ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_change_user_role(client, admin_token, ic_user):
    resp = await client.patch(
        f"/api/v1/admin/users/{ic_user.id}",
        json={"role": "approver"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "approver"


@pytest.mark.asyncio
async def test_disable_user(client, admin_token, ic_user):
    resp = await client.patch(
        f"/api/v1/admin/users/{ic_user.id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_disabled_user_cannot_login(client, admin_token, ic_user):
    await client.patch(
        f"/api/v1/admin/users/{ic_user.id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.post("/api/v1/auth/login", json={"email": ic_user.email, "password": "testpass123"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_modify_self(client, admin_token, admin_user):
    resp = await client.patch(
        f"/api/v1/admin/users/{admin_user.id}",
        json={"role": "ic"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_nonexistent_user(client, admin_token):
    import uuid
    resp = await client.patch(
        f"/api/v1/admin/users/{uuid.uuid4()}",
        json={"role": "ic"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


# ── Audit logs ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_logs_returns_page(client, admin_token):
    resp = await client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "items" in data
    assert "page" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_audit_logs_pagination(client, admin_token):
    resp = await client.get(
        "/api/v1/admin/audit-logs?page=1&page_size=2",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) <= 2
