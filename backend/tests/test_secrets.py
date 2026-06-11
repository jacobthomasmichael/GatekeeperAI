import uuid
import pytest
import pytest_asyncio

from app.models.app_submission import AppSubmission


def _unique_path():
    return f"/tmp/secrets-test-{uuid.uuid4().hex}.git"


@pytest_asyncio.fixture
async def app_submission(db, ic_user):
    """An AppSubmission owned by ic_user."""
    submission = AppSubmission(
        name=f"secrets-app-{uuid.uuid4().hex[:6]}",
        description="App for testing secret management",
        repo_path=_unique_path(),
        repo_url="file:///tmp/secrets-test.git",
        submitter_id=ic_user.id,
        status="pending_scan",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return submission


@pytest_asyncio.fixture
async def other_submission(db, admin_user):
    """An AppSubmission owned by admin_user (different owner)."""
    submission = AppSubmission(
        name=f"other-app-{uuid.uuid4().hex[:6]}",
        description="App owned by a different user",
        repo_path=_unique_path(),
        repo_url="file:///tmp/other.git",
        submitter_id=admin_user.id,
        status="pending_scan",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return submission


# ── List ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_secrets_empty(client, ic_token, app_submission):
    resp = await client.get(
        f"/api/v1/apps/{app_submission.id}/secrets/",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_secrets_requires_auth(client, app_submission):
    resp = await client.get(f"/api/v1/apps/{app_submission.id}/secrets/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_secrets_wrong_owner_denied(client, ic_token, other_submission):
    resp = await client.get(
        f"/api/v1/apps/{other_submission.id}/secrets/",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_secrets_admin_can_access_any(client, admin_token, app_submission):
    resp = await client.get(
        f"/api/v1/apps/{app_submission.id}/secrets/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_secrets_app_not_found(client, ic_token):
    resp = await client.get(
        f"/api/v1/apps/{uuid.uuid4()}/secrets/",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 404


# ── Create ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_secret(client, ic_token, app_submission):
    resp = await client.post(
        f"/api/v1/apps/{app_submission.id}/secrets/",
        json={"key_name": "api_key", "value": "supersecret"},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["key_name"] == "API_KEY"  # uppercased by validator


@pytest.mark.asyncio
async def test_create_secret_appears_in_list(client, ic_token, app_submission):
    await client.post(
        f"/api/v1/apps/{app_submission.id}/secrets/",
        json={"key_name": "DB_PASS", "value": "secret123"},
        headers={"Authorization": f"Bearer {ic_token}"},
    )

    resp = await client.get(
        f"/api/v1/apps/{app_submission.id}/secrets/",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 200
    assert "DB_PASS" in [s["key_name"] for s in resp.json()]


@pytest.mark.asyncio
async def test_create_secret_upserts_existing(client, ic_token, app_submission):
    for value in ("first_value", "second_value"):
        resp = await client.post(
            f"/api/v1/apps/{app_submission.id}/secrets/",
            json={"key_name": "MY_KEY", "value": value},
            headers={"Authorization": f"Bearer {ic_token}"},
        )
        assert resp.status_code == 201

    resp = await client.get(
        f"/api/v1/apps/{app_submission.id}/secrets/",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert [s["key_name"] for s in resp.json()].count("MY_KEY") == 1


@pytest.mark.asyncio
async def test_create_secret_invalid_key_name(client, ic_token, app_submission):
    resp = await client.post(
        f"/api/v1/apps/{app_submission.id}/secrets/",
        json={"key_name": "invalid key!", "value": "val"},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_secret_wrong_owner_denied(client, ic_token, other_submission):
    resp = await client.post(
        f"/api/v1/apps/{other_submission.id}/secrets/",
        json={"key_name": "KEY", "value": "val"},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 403


# ── Delete ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_secret(client, ic_token, app_submission):
    await client.post(
        f"/api/v1/apps/{app_submission.id}/secrets/",
        json={"key_name": "TO_DELETE", "value": "bye"},
        headers={"Authorization": f"Bearer {ic_token}"},
    )

    resp = await client.delete(
        f"/api/v1/apps/{app_submission.id}/secrets/TO_DELETE",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 204

    resp = await client.get(
        f"/api/v1/apps/{app_submission.id}/secrets/",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert "TO_DELETE" not in [s["key_name"] for s in resp.json()]


@pytest.mark.asyncio
async def test_delete_nonexistent_secret(client, ic_token, app_submission):
    resp = await client.delete(
        f"/api/v1/apps/{app_submission.id}/secrets/DOES_NOT_EXIST",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_secret_wrong_owner_denied(client, ic_token, other_submission):
    resp = await client.delete(
        f"/api/v1/apps/{other_submission.id}/secrets/SOME_KEY",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 403
