"""Tests for the Blue/Green App Updates feature."""
import io
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.app_submission import AppSubmission
from app.models.approval import Approval
from app.models.scan import Scan
from app.services.approval_service import route_after_scan, _is_same_or_lower_risk


# ---------------------------------------------------------------------------
# Unit tests — risk comparison helper
# ---------------------------------------------------------------------------

def test_risk_same_tier_is_not_higher():
    assert _is_same_or_lower_risk("green", "green") is True
    assert _is_same_or_lower_risk("yellow", "yellow") is True
    assert _is_same_or_lower_risk("red", "red") is True


def test_risk_lower_tier_qualifies():
    assert _is_same_or_lower_risk("green", "yellow") is True
    assert _is_same_or_lower_risk("green", "red") is True
    assert _is_same_or_lower_risk("yellow", "red") is True


def test_risk_higher_tier_does_not_qualify():
    assert _is_same_or_lower_risk("yellow", "green") is False
    assert _is_same_or_lower_risk("red", "green") is False
    assert _is_same_or_lower_risk("red", "yellow") is False


def test_risk_none_values_do_not_qualify():
    assert _is_same_or_lower_risk(None, "green") is False
    assert _is_same_or_lower_risk("green", None) is False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("app.py", "print('hello')")
    return buf.getvalue()


async def _make_submission(db, user_id: uuid.UUID, name: str) -> AppSubmission:
    sub = AppSubmission(
        submitter_id=user_id,
        name=name,
        description="test description for blue green",
        repo_path=f"/tmp/{name}.git",
        repo_url=f"file:///tmp/{name}.git",
    )
    db.add(sub)
    await db.flush()
    return sub


# ---------------------------------------------------------------------------
# Upload endpoint — scan_type tagging
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initial_upload_sets_scan_type_initial(client, ic_token, ic_user, db):
    """First upload to a new app should produce scan_type='initial'."""
    with patch("app.routers.apps.create_bare_repo") as mock_repo, \
         patch("app.routers.apps.push_zip_to_repo") as mock_push, \
         patch("app.scanners.pipeline.run_scan_pipeline") as mock_pipeline:

        mock_repo.return_value = ("/tmp/bg-init.git", "file:///tmp/bg-init.git")
        mock_push.return_value = "a" * 40
        mock_pipeline.delay = MagicMock(return_value=MagicMock(id="task-1"))

        create_resp = await client.post(
            "/api/v1/apps/",
            json={"name": "bg-init-app", "description": "blue green initial test"},
            headers={"Authorization": f"Bearer {ic_token}"},
        )
        assert create_resp.status_code == 201
        app_id = create_resp.json()["id"]

        upload_resp = await client.post(
            f"/api/v1/apps/{app_id}/upload",
            files={"file": ("app.zip", _make_zip(), "application/zip")},
            headers={"Authorization": f"Bearer {ic_token}"},
        )
        assert upload_resp.status_code == 202
        scan_id = upload_resp.json()["scan_id"]

    scan = await db.get(Scan, uuid.UUID(scan_id))
    assert scan.scan_type == "initial"
    assert scan.previous_scan_id is None


@pytest.mark.asyncio
async def test_upload_to_deployed_app_sets_scan_type_update(client, ic_token, ic_user, db):
    """Upload to an already-deployed app should produce scan_type='update'
    and link previous_scan_id to the last approved scan."""
    with patch("app.routers.apps.create_bare_repo") as mock_repo:
        mock_repo.return_value = ("/tmp/bg-update.git", "file:///tmp/bg-update.git")
        create_resp = await client.post(
            "/api/v1/apps/",
            json={"name": "bg-update-app", "description": "blue green update test"},
            headers={"Authorization": f"Bearer {ic_token}"},
        )
    assert create_resp.status_code == 201
    app_id = uuid.UUID(create_resp.json()["id"])

    # Set app to "deployed" with a previously approved scan
    app = await db.get(AppSubmission, app_id)
    app.status = "deployed"

    prev_scan = Scan(
        submission_id=app_id,
        commit_sha="p" * 40,
        status="complete",
        scan_type="initial",
        risk_tier="yellow",
    )
    db.add(prev_scan)
    await db.flush()

    prev_approval = Approval(
        scan_id=prev_scan.id,
        decision="approved",
        decided_at=datetime.now(timezone.utc),
        sla_deadline=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(prev_approval)
    await db.commit()

    with patch("app.routers.apps.push_zip_to_repo") as mock_push, \
         patch("app.scanners.pipeline.run_scan_pipeline") as mock_pipeline:

        mock_push.return_value = "b" * 40
        mock_pipeline.delay = MagicMock(return_value=MagicMock(id="task-2"))

        upload_resp = await client.post(
            f"/api/v1/apps/{app_id}/upload",
            files={"file": ("app.zip", _make_zip(), "application/zip")},
            headers={"Authorization": f"Bearer {ic_token}"},
        )
        assert upload_resp.status_code == 202
        new_scan_id = upload_resp.json()["scan_id"]

    new_scan = await db.get(Scan, uuid.UUID(new_scan_id))
    assert new_scan.scan_type == "update"
    assert new_scan.previous_scan_id == prev_scan.id


# ---------------------------------------------------------------------------
# Approval service — expedited routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_same_risk_is_expedited(db, ic_user):
    """An update with same risk tier gets is_expedited=True and a 4-hour SLA."""
    sub = await _make_submission(db, ic_user.id, "exp-same-risk")

    prev_scan = Scan(submission_id=sub.id, commit_sha="p" * 40,
                     status="complete", scan_type="initial", risk_tier="yellow")
    db.add(prev_scan)
    await db.flush()

    new_scan = Scan(submission_id=sub.id, commit_sha="n" * 40,
                    status="complete", scan_type="update",
                    risk_tier="yellow", previous_scan_id=prev_scan.id)
    db.add(new_scan)
    await db.flush()

    with patch("app.services.approval_service._approver_emails", new=AsyncMock(return_value=[])), \
         patch("app.services.approval_service.notification_service"):
        approval = await route_after_scan(new_scan, sub, db)

    assert approval is not None
    assert new_scan.is_expedited is True
    sla_hours = (approval.sla_deadline - datetime.now(timezone.utc)).total_seconds() / 3600
    assert sla_hours < 5


@pytest.mark.asyncio
async def test_update_lower_risk_is_expedited(db, ic_user):
    """An update that improves risk (red → yellow) is also expedited."""
    sub = await _make_submission(db, ic_user.id, "exp-lower-risk")

    prev_scan = Scan(submission_id=sub.id, commit_sha="p" * 40,
                     status="complete", scan_type="initial", risk_tier="red")
    db.add(prev_scan)
    await db.flush()

    new_scan = Scan(submission_id=sub.id, commit_sha="n" * 40,
                    status="complete", scan_type="update",
                    risk_tier="yellow", previous_scan_id=prev_scan.id)
    db.add(new_scan)
    await db.flush()

    with patch("app.services.approval_service._approver_emails", new=AsyncMock(return_value=[])), \
         patch("app.services.approval_service.notification_service"):
        approval = await route_after_scan(new_scan, sub, db)

    assert approval is not None
    assert new_scan.is_expedited is True


@pytest.mark.asyncio
async def test_update_higher_risk_is_not_expedited(db, ic_user):
    """An update that worsens risk (yellow → red) goes through full 24hr review."""
    sub = await _make_submission(db, ic_user.id, "exp-higher-risk")

    prev_scan = Scan(submission_id=sub.id, commit_sha="p" * 40,
                     status="complete", scan_type="initial", risk_tier="yellow")
    db.add(prev_scan)
    await db.flush()

    new_scan = Scan(submission_id=sub.id, commit_sha="n" * 40,
                    status="complete", scan_type="update",
                    risk_tier="red", previous_scan_id=prev_scan.id)
    db.add(new_scan)
    await db.flush()

    with patch("app.services.approval_service._approver_emails", new=AsyncMock(return_value=[])), \
         patch("app.services.approval_service.notification_service"):
        approval = await route_after_scan(new_scan, sub, db)

    assert approval is not None
    assert new_scan.is_expedited is False
    sla_hours = (approval.sla_deadline - datetime.now(timezone.utc)).total_seconds() / 3600
    assert sla_hours > 20


@pytest.mark.asyncio
async def test_green_update_goes_to_approval_queue(db, ic_user):
    """A green update still requires approval (unlike initial green which auto-deploys)."""
    sub = await _make_submission(db, ic_user.id, "green-update")

    prev_scan = Scan(submission_id=sub.id, commit_sha="p" * 40,
                     status="complete", scan_type="initial", risk_tier="green")
    db.add(prev_scan)
    await db.flush()

    new_scan = Scan(submission_id=sub.id, commit_sha="n" * 40,
                    status="complete", scan_type="update",
                    risk_tier="green", previous_scan_id=prev_scan.id)
    db.add(new_scan)
    await db.flush()

    with patch("app.services.approval_service._approver_emails", new=AsyncMock(return_value=[])), \
         patch("app.services.approval_service.notification_service"):
        approval = await route_after_scan(new_scan, sub, db)

    assert approval is not None
    assert new_scan.is_expedited is True


@pytest.mark.asyncio
async def test_initial_green_skips_approval_queue(db, ic_user):
    """Initial green scan produces no approval record — auto-deploy path unchanged."""
    sub = await _make_submission(db, ic_user.id, "green-initial")

    scan = Scan(submission_id=sub.id, commit_sha="g" * 40,
                status="complete", scan_type="initial", risk_tier="green")
    db.add(scan)
    await db.flush()

    with patch("app.services.approval_service._approver_emails", new=AsyncMock(return_value=[])), \
         patch("app.services.approval_service.notification_service"):
        approval = await route_after_scan(scan, sub, db)

    assert approval is None
