import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_endpoint_removed(client):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "anyone@example.com",
        "username": "anyone",
        "password": "password123",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_create_and_login(client, admin_token):
    resp = await client.post(
        "/api/v1/admin/users",
        json={"email": "created@example.com", "username": "created_user", "password": "password123", "role": "ic"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "ic"

    resp = await client.post("/api/v1/auth/login", json={
        "email": "created@example.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_wrong_password_rejected(client, ic_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email": ic_user.email,
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user(client, ic_token, ic_user):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == ic_user.email


@pytest.mark.asyncio
async def test_refresh_token(client, ic_user):
    login = await client.post("/api/v1/auth/login", json={
        "email": ic_user.email,
        "password": "testpass123",
    })
    refresh_token = login.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_invalid_token_rejected(client):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer notarealtoken"},
    )
    assert resp.status_code == 401
