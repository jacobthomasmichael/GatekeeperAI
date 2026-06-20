"""
Tests for per-app RBAC access control:
  - /apps/{id}/users  GET / POST / DELETE
  - /auth/verify/{app} per-app gate
  - list_apps IC visibility (own + shared)
  - get_deployment_for_app IC access
"""
import uuid
import pytest
from unittest.mock import patch

from app.models.app_submission import AppSubmission
from app.models.deployment import Deployment
from app.models.scan import Scan
from app.services.auth_service import hash_password
from app.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _make_app(client, token, name="rbac-test-app"):
    with patch("app.routers.apps.create_bare_repo") as m:
        m.return_value = (f"/tmp/{name}.git", f"file:///tmp/{name}.git")
        resp = await client.post(
            "/api/v1/apps/",
            json={"name": name, "description": "RBAC test application"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _make_approver(db, suffix=None):
    suffix = suffix or uuid.uuid4().hex[:8]
    user = User(
        email=f"approver_{suffix}@example.com",
        username=f"approver_{suffix}",
        hashed_password=hash_password("testpass123"),
        role="approver",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_ic(db, suffix=None):
    suffix = suffix or uuid.uuid4().hex[:8]
    user = User(
        email=f"ic2_{suffix}@example.com",
        username=f"ic2_{suffix}",
        hashed_password=hash_password("testpass123"),
        role="ic",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _login(client, email):
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ── /apps/{id}/users GET ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_app_users_owner_sees_empty(client, ic_token):
    app = await _make_app(client, ic_token, "list-users-app")
    resp = await client.get(f"/api/v1/apps/{app['id']}/users", headers={"Authorization": f"Bearer {ic_token}"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_app_users_non_owner_ic_forbidden(client, ic_token, db):
    app = await _make_app(client, ic_token, "list-users-other-app")
    other = await _make_ic(db)
    other_token = await _login(client, other.email)
    resp = await client.get(f"/api/v1/apps/{app['id']}/users", headers={"Authorization": f"Bearer {other_token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_app_users_admin_can_see(client, ic_token, admin_token):
    app = await _make_app(client, ic_token, "list-users-admin-app")
    resp = await client.get(f"/api/v1/apps/{app['id']}/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200


# ── /apps/{id}/users POST ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_user_by_email(client, ic_token, db):
    app = await _make_app(client, ic_token, "add-user-app")
    grantee = await _make_ic(db)
    resp = await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": grantee.email},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == grantee.email
    assert data["id"] == str(grantee.id)


@pytest.mark.asyncio
async def test_add_user_unknown_email_404(client, ic_token):
    app = await _make_app(client, ic_token, "add-unknown-app")
    resp = await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": "nobody@nowhere.invalid"},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_user_non_owner_forbidden(client, ic_token, db):
    app = await _make_app(client, ic_token, "add-nonowner-app")
    other = await _make_ic(db)
    other_token = await _login(client, other.email)
    third = await _make_ic(db)
    resp = await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": third.email},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_add_user_duplicate_returns_409(client, ic_token, db):
    app = await _make_app(client, ic_token, "add-dup-app")
    grantee = await _make_ic(db)
    resp1 = await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": grantee.email},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": grantee.email},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp2.status_code == 409

    # Still only one entry in list
    list_resp = await client.get(f"/api/v1/apps/{app['id']}/users", headers={"Authorization": f"Bearer {ic_token}"})
    assert len(list_resp.json()) == 1


# ── /apps/{id}/users/{user_id} DELETE ────────────────────────────────────────

@pytest.mark.asyncio
async def test_remove_user(client, ic_token, db):
    app = await _make_app(client, ic_token, "remove-user-app")
    grantee = await _make_ic(db)
    await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": grantee.email},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    resp = await client.delete(
        f"/api/v1/apps/{app['id']}/users/{grantee.id}",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 204

    list_resp = await client.get(f"/api/v1/apps/{app['id']}/users", headers={"Authorization": f"Bearer {ic_token}"})
    assert list_resp.json() == []


@pytest.mark.asyncio
async def test_remove_user_non_owner_forbidden(client, ic_token, db):
    app = await _make_app(client, ic_token, "remove-nonowner-app")
    grantee = await _make_ic(db)
    await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": grantee.email},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    other = await _make_ic(db)
    other_token = await _login(client, other.email)
    resp = await client.delete(
        f"/api/v1/apps/{app['id']}/users/{grantee.id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


# ── list_apps IC visibility ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_shared_app_appears_in_grantee_list(client, ic_token, db):
    app = await _make_app(client, ic_token, "shared-visible-app")
    grantee = await _make_ic(db)
    grantee_token = await _login(client, grantee.email)

    # Before grant — grantee cannot see it
    resp = await client.get("/api/v1/apps/", headers={"Authorization": f"Bearer {grantee_token}"})
    ids_before = [a["id"] for a in resp.json()]
    assert app["id"] not in ids_before

    # Grant access
    await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": grantee.email},
        headers={"Authorization": f"Bearer {ic_token}"},
    )

    # After grant — grantee sees it
    resp = await client.get("/api/v1/apps/", headers={"Authorization": f"Bearer {grantee_token}"})
    ids_after = [a["id"] for a in resp.json()]
    assert app["id"] in ids_after


@pytest.mark.asyncio
async def test_revoked_app_disappears_from_grantee_list(client, ic_token, db):
    app = await _make_app(client, ic_token, "revoke-visible-app")
    grantee = await _make_ic(db)
    grantee_token = await _login(client, grantee.email)

    await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": grantee.email},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    await client.delete(
        f"/api/v1/apps/{app['id']}/users/{grantee.id}",
        headers={"Authorization": f"Bearer {ic_token}"},
    )

    resp = await client.get("/api/v1/apps/", headers={"Authorization": f"Bearer {grantee_token}"})
    ids = [a["id"] for a in resp.json()]
    assert app["id"] not in ids


# ── /auth/verify/{app} ────────────────────────────────────────────────────────

async def _seed_deployed_app(db, owner, safe_name="test-deployed"):
    """Insert a minimal deployed AppSubmission with stable_container_name set."""
    submission = AppSubmission(
        submitter_id=owner.id,
        name=safe_name,
        description="seeded for verify tests",
        repo_path=f"/tmp/{safe_name}.git",
        repo_url=f"file:///tmp/{safe_name}.git",
        status="deployed",
        stable_container_name=f"gka-{safe_name}-abcd1234",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return submission


@pytest.mark.asyncio
async def test_verify_owner_allowed(client, ic_user, ic_token, db):
    sub = await _seed_deployed_app(db, ic_user, "verify-owner-app")
    resp = await client.get(
        f"/api/v1/auth/verify/{sub.name}",
        headers={"Authorization": f"Bearer {ic_token}"},
        cookies={"gka_session": ic_token},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_verify_non_owner_ic_blocked(client, ic_user, db):
    sub = await _seed_deployed_app(db, ic_user, "verify-blocked-app")
    other = await _make_ic(db)
    other_token = await _login(client, other.email)
    resp = await client.get(
        f"/api/v1/auth/verify/{sub.name}",
        cookies={"gka_session": other_token},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_verify_granted_user_allowed(client, ic_user, ic_token, db):
    sub = await _seed_deployed_app(db, ic_user, "verify-granted-app")
    grantee = await _make_ic(db)
    grantee_token = await _login(client, grantee.email)

    # Grant access directly via the API
    await client.post(
        f"/api/v1/apps/{sub.id}/users",
        json={"email": grantee.email},
        headers={"Authorization": f"Bearer {ic_token}"},
    )

    resp = await client.get(
        f"/api/v1/auth/verify/{sub.name}",
        cookies={"gka_session": grantee_token},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_verify_admin_always_allowed(client, admin_token, ic_user, db):
    sub = await _seed_deployed_app(db, ic_user, "verify-admin-app")
    resp = await client.get(
        f"/api/v1/auth/verify/{sub.name}",
        cookies={"gka_session": admin_token},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_verify_unauthenticated_401(client, ic_user, db):
    sub = await _seed_deployed_app(db, ic_user, "verify-unauth-app")
    resp = await client.get(f"/api/v1/auth/verify/{sub.name}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_unknown_app_fail_open(client, ic_token):
    resp = await client.get(
        "/api/v1/auth/verify/nonexistent-app-xyz",
        cookies={"gka_session": ic_token},
    )
    assert resp.status_code == 200


# ── /deployments/app/{id} IC access ──────────────────────────────────────────

async def _seed_deployment(db, submission):
    scan = Scan(
        submission_id=submission.id,
        commit_sha="abc1234abc1234abc1234abc1234abc1234abc12",
        status="completed",
        risk_tier="green",
        risk_score=0,
    )
    db.add(scan)
    await db.flush()

    dep = Deployment(
        submission_id=submission.id,
        scan_id=scan.id,
        status="deployed",
        internal_port=8600,
        external_port=8600,
        public_url=f"http://localhost:3000/apps/{submission.name}/",
    )
    db.add(dep)
    await db.commit()
    await db.refresh(dep)
    return dep


@pytest.mark.asyncio
async def test_deployment_owner_can_fetch(client, ic_user, ic_token, db):
    sub = await _seed_deployed_app(db, ic_user, "dep-owner-app")
    await _seed_deployment(db, sub)
    resp = await client.get(
        f"/api/v1/deployments/app/{sub.id}",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_deployment_non_owner_ic_blocked(client, ic_user, db):
    sub = await _seed_deployed_app(db, ic_user, "dep-blocked-app")
    await _seed_deployment(db, sub)
    other = await _make_ic(db)
    other_token = await _login(client, other.email)
    resp = await client.get(
        f"/api/v1/deployments/app/{sub.id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_deployment_granted_user_can_fetch(client, ic_user, ic_token, db):
    sub = await _seed_deployed_app(db, ic_user, "dep-granted-app")
    await _seed_deployment(db, sub)
    grantee = await _make_ic(db)
    grantee_token = await _login(client, grantee.email)

    await client.post(
        f"/api/v1/apps/{sub.id}/users",
        json={"email": grantee.email},
        headers={"Authorization": f"Bearer {ic_token}"},
    )

    resp = await client.get(
        f"/api/v1/deployments/app/{sub.id}",
        headers={"Authorization": f"Bearer {grantee_token}"},
    )
    assert resp.status_code == 200


# ── Approver role bypasses per-app checks ────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_approver_always_allowed(client, ic_user, db):
    sub = await _seed_deployed_app(db, ic_user, "verify-approver-app")
    approver = await _make_approver(db)
    approver_token = await _login(client, approver.email)
    resp = await client.get(
        f"/api/v1/auth/verify/{sub.name}",
        cookies={"gka_session": approver_token},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_approver_can_list_users(client, ic_token, db):
    app = await _make_app(client, ic_token, "approver-list-app")
    approver = await _make_approver(db)
    approver_token = await _login(client, approver.email)
    resp = await client.get(
        f"/api/v1/apps/{app['id']}/users",
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_approver_cannot_manage_users(client, ic_token, db):
    """Approvers can view but not add/remove users — only owner and admin can."""
    app = await _make_app(client, ic_token, "approver-manage-app")
    approver = await _make_approver(db)
    approver_token = await _login(client, approver.email)
    other = await _make_ic(db)
    resp = await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": other.email},
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    assert resp.status_code == 403


# ── get_app access respects allowlist ────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_app_blocked_for_non_granted_ic(client, ic_token, db):
    app = await _make_app(client, ic_token, "get-app-blocked")
    other = await _make_ic(db)
    other_token = await _login(client, other.email)
    resp = await client.get(
        f"/api/v1/apps/{app['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_app_allowed_for_granted_ic(client, ic_token, db):
    app = await _make_app(client, ic_token, "get-app-granted")
    grantee = await _make_ic(db)
    grantee_token = await _login(client, grantee.email)

    await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": grantee.email},
        headers={"Authorization": f"Bearer {ic_token}"},
    )

    resp = await client.get(
        f"/api/v1/apps/{app['id']}",
        headers={"Authorization": f"Bearer {grantee_token}"},
    )
    assert resp.status_code == 200


# ── Owner cannot remove themselves ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_owner_remove_self_returns_404(client, ic_token, ic_user):
    """Owner is not in allowed_users (access is via submitter_id), so removing
    themselves returns 404 — not a dangerous operation either way."""
    app = await _make_app(client, ic_token, "owner-self-remove-app")
    resp = await client.delete(
        f"/api/v1/apps/{app['id']}/users/{ic_user.id}",
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    assert resp.status_code == 404


# ── Admin can manage any app's users ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_can_add_user_to_any_app(client, ic_token, admin_token, db):
    app = await _make_app(client, ic_token, "admin-add-user-app")
    other = await _make_ic(db)
    resp = await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": other.email},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_admin_can_remove_user_from_any_app(client, ic_token, admin_token, db):
    app = await _make_app(client, ic_token, "admin-remove-user-app")
    grantee = await _make_ic(db)
    await client.post(
        f"/api/v1/apps/{app['id']}/users",
        json={"email": grantee.email},
        headers={"Authorization": f"Bearer {ic_token}"},
    )
    resp = await client.delete(
        f"/api/v1/apps/{app['id']}/users/{grantee.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204
