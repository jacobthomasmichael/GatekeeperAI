import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_and_login(client):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "newuser_reg@example.com",
        "username": "newuser_reg",
        "password": "password123",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser_reg@example.com"
    assert data["role"] == "ic"

    resp = await client.post("/api/v1/auth/login", json={
        "email": "newuser_reg@example.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    tokens = resp.json()
    assert "access_token" in tokens
    assert tokens["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client, ic_user):
    resp = await client.post("/api/v1/auth/register", json={
        "email": ic_user.email,
        "username": "completely_different",
        "password": "password123",
    })
    assert resp.status_code == 409


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
