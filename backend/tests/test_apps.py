import pytest
from unittest.mock import patch


@pytest.mark.asyncio
async def test_create_app(client, ic_token):
    with patch("app.routers.apps.create_bare_repo") as mock_create:
        mock_create.return_value = ("/tmp/fake-repo.git", "file:///tmp/fake-repo.git")
        resp = await client.post(
            "/api/v1/apps/",
            json={"name": "test-app", "description": "A test application"},
            headers={"Authorization": f"Bearer {ic_token}"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-app"
    assert data["status"] == "pending_scan"


@pytest.mark.asyncio
async def test_list_apps_ic_sees_own(client, ic_token, admin_token):
    with patch("app.routers.apps.create_bare_repo") as mock_create:
        mock_create.return_value = ("/tmp/r2.git", "file:///tmp/r2.git")
        await client.post(
            "/api/v1/apps/",
            json={"name": "ic-only-app", "description": "IC app"},
            headers={"Authorization": f"Bearer {ic_token}"},
        )

    # IC sees only their own apps
    resp = await client.get("/api/v1/apps/", headers={"Authorization": f"Bearer {ic_token}"})
    assert resp.status_code == 200
    names = [a["name"] for a in resp.json()]
    assert all(n in ("test-app", "ic-only-app") for n in names)

    # Admin sees all
    resp = await client.get("/api/v1/apps/", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_duplicate_app_name_rejected(client, ic_token):
    with patch("app.routers.apps.create_bare_repo") as mock_create:
        mock_create.return_value = ("/tmp/dup.git", "file:///tmp/dup.git")
        await client.post(
            "/api/v1/apps/",
            json={"name": "unique-app", "description": "first submission description"},
            headers={"Authorization": f"Bearer {ic_token}"},
        )
        resp = await client.post(
            "/api/v1/apps/",
            json={"name": "unique-app", "description": "second submission description"},
            headers={"Authorization": f"Bearer {ic_token}"},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_app_requires_auth(client):
    resp = await client.get("/api/v1/apps/")
    assert resp.status_code == 401
