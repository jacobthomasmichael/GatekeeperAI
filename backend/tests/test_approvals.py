import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models.approval import Approval
from app.models.app_submission import AppSubmission
from app.models.scan import Scan


async def _create_approval(db, submitter_id, risk_tier="yellow"):
    """Seed a submission + scan + approval row."""
    import uuid as _uuid
    sub_id = _uuid.uuid4()
    scan_id = _uuid.uuid4()

    sub = AppSubmission(
        id=sub_id,
        submitter_id=submitter_id,
        name=f"app-{sub_id.hex[:6]}",
        description="test app",
        repo_path=f"/tmp/fake-{sub_id.hex[:8]}",
        repo_url=f"file:///tmp/fake-{sub_id.hex[:8]}",
        status="awaiting_approval",
        risk_tier=risk_tier,
    )
    db.add(sub)
    await db.flush()  # sub must exist before scan (FK)

    scan = Scan(
        id=scan_id,
        submission_id=sub_id,
        commit_sha="abc123",
        status="complete",
        risk_tier=risk_tier,
        risk_score=45,
    )
    db.add(scan)
    await db.flush()  # scan must exist before approval (FK)

    approval = Approval(
        scan_id=scan_id,
        sla_deadline=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return approval, scan, sub


@pytest.mark.asyncio
async def test_list_approvals_requires_approver(client, ic_token):
    resp = await client.get(
        "/api/v1/approvals/",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_approvals_as_admin(client, admin_token, admin_user, db):
    await _create_approval(db, submitter_id=admin_user.id)
    resp = await client.get(
        "/api/v1/approvals/?pending_only=false",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_decide_approval(client, admin_token, admin_user, db):
    approval, _, _ = await _create_approval(db, submitter_id=admin_user.id)

    with patch("app.services.approval_service.notification_service.notify_submitter_decision"):
        with patch("worker.deploy_task.deploy_approved_app.delay"):
            resp = await client.post(
                f"/api/v1/approvals/{approval.id}/decide",
                json={"decision": "approved", "comment": "Looks good to me!"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
    assert resp.status_code == 200
    assert resp.json()["decision"] == "approved"


@pytest.mark.asyncio
async def test_decide_requires_comment(client, admin_token, admin_user, db):
    approval, _, _ = await _create_approval(db, submitter_id=admin_user.id)
    resp = await client.post(
        f"/api/v1/approvals/{approval.id}/decide",
        json={"decision": "rejected", "comment": "too short"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_double_decide_rejected(client, admin_token, admin_user, db):
    approval, _, _ = await _create_approval(db, submitter_id=admin_user.id)
    with patch("app.services.approval_service.notification_service.notify_submitter_decision"):
        with patch("worker.deploy_task.deploy_approved_app.delay"):
            await client.post(
                f"/api/v1/approvals/{approval.id}/decide",
                json={"decision": "approved", "comment": "First decision here!"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            resp = await client.post(
                f"/api/v1/approvals/{approval.id}/decide",
                json={"decision": "rejected", "comment": "Second decision here!"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_stats_requires_admin(client, admin_token):
    resp = await client.get(
        "/api/v1/approvals/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data and "pending" in data and "overdue" in data
