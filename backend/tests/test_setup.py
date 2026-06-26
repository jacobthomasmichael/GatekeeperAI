import pytest
import pytest_asyncio
from unittest.mock import patch
from sqlalchemy import delete, select
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.app_submission import AppSubmission
from app.models.scan import Scan, ScanResult
from app.models.approval import Approval
from app.models.deployment import Deployment
from app.models.secret_store import SecretStore


VALID_PAYLOAD = {
    "company_name": "Acme Corp",
    "server_url": "https://gatekeeper.acme.com",
    "admin_email": "admin@acme.com",
    "admin_username": "acmeadmin",
    "admin_password": "securepass123",
}


@pytest_asyncio.fixture(autouse=True)
async def wipe_admins(db):
    """Remove all admin users and their owned data before each setup test."""
    result = await db.execute(select(User.id).where(User.role == "admin"))
    admin_ids = [row[0] for row in result.all()]

    if admin_ids:
        sub_result = await db.execute(
            select(AppSubmission.id).where(AppSubmission.submitter_id.in_(admin_ids))
        )
        sub_ids = [row[0] for row in sub_result.all()]

        if sub_ids:
            scan_result = await db.execute(
                select(Scan.id).where(Scan.submission_id.in_(sub_ids))
            )
            scan_ids = [row[0] for row in scan_result.all()]

            if scan_ids:
                await db.execute(delete(ScanResult).where(ScanResult.scan_id.in_(scan_ids)))
                await db.execute(delete(Approval).where(Approval.scan_id.in_(scan_ids)))
                await db.execute(delete(Deployment).where(Deployment.scan_id.in_(scan_ids)))
                await db.execute(delete(Scan).where(Scan.id.in_(scan_ids)))

            await db.execute(delete(SecretStore).where(SecretStore.submission_id.in_(sub_ids)))
            await db.execute(delete(Deployment).where(Deployment.submission_id.in_(sub_ids)))
            await db.execute(delete(AppSubmission).where(AppSubmission.submitter_id.in_(admin_ids)))

    await db.execute(delete(AuditLog).where(AuditLog.actor_id.in_(admin_ids)))
    await db.execute(delete(User).where(User.role == "admin"))
    await db.commit()
    yield


# ── Status ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_status_incomplete_before_setup(client):
    resp = await client.get("/api/v1/setup/status")
    assert resp.status_code == 200
    assert resp.json() == {"complete": False}


@pytest.mark.asyncio
async def test_status_complete_after_setup(client):
    with patch("app.routers.setup._patch_env_file"):
        await client.post("/api/v1/setup/complete", json=VALID_PAYLOAD)

    resp = await client.get("/api/v1/setup/status")
    assert resp.status_code == 200
    assert resp.json() == {"complete": True}


# ── Complete ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_setup_complete_creates_admin(client, db):
    with patch("app.routers.setup._patch_env_file"):
        resp = await client.post("/api/v1/setup/complete", json=VALID_PAYLOAD)

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    from sqlalchemy import select
    result = await db.execute(select(User).where(User.email == "admin@acme.com"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.role == "admin"
    assert user.is_active is True


@pytest.mark.asyncio
async def test_setup_complete_patches_env_file(client):
    with patch("app.routers.setup._patch_env_file") as mock_patch:
        await client.post("/api/v1/setup/complete", json=VALID_PAYLOAD)

    mock_patch.assert_called_once()
    updates = mock_patch.call_args[0][0]
    assert updates["APP_BASE_URL"] == "https://gatekeeper.acme.com"


@pytest.mark.asyncio
async def test_setup_complete_409_if_already_done(client):
    with patch("app.routers.setup._patch_env_file"):
        await client.post("/api/v1/setup/complete", json=VALID_PAYLOAD)
        resp = await client.post("/api/v1/setup/complete", json={
            **VALID_PAYLOAD,
            "admin_email": "other@acme.com",
            "admin_username": "otheradmin",
        })

    assert resp.status_code == 409


# ── Validation ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_setup_company_name_too_short(client):
    resp = await client.post("/api/v1/setup/complete", json={**VALID_PAYLOAD, "company_name": "X"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_setup_invalid_server_url(client):
    resp = await client.post("/api/v1/setup/complete", json={**VALID_PAYLOAD, "server_url": "not-a-url"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_setup_admin_username_too_short(client):
    resp = await client.post("/api/v1/setup/complete", json={**VALID_PAYLOAD, "admin_username": "ab"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_setup_admin_password_too_short(client):
    resp = await client.post("/api/v1/setup/complete", json={**VALID_PAYLOAD, "admin_password": "short"})
    assert resp.status_code == 422
