import asyncio
import subprocess
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user
from app.models.app_submission import AppSubmission
from app.models.approval import Approval
from app.models.scan import Scan
from app.models.user import User
from app.config import settings
from app.schemas.app_submission import (
    AppCreate, AppResponse, AppUserGrant, AppUserResponse,
    RejectionFeedback, VisibilityUpdate,
)
from app.schemas.sso import AppGroupGrant
from app.services.git_service import create_bare_repo, delete_bare_repo, push_zip_to_repo

router = APIRouter(prefix="/apps", tags=["apps"])

_limiter = Limiter(key_func=get_remote_address)


def _can_access(app: AppSubmission, user: User) -> bool:
    """True if user can read/access this app (not necessarily manage it)."""
    if user.role in ("admin", "approver"):
        return True
    if app.submitter_id == user.id:
        return True
    return bool(app.allowed_users and user.id in app.allowed_users)


def _can_manage(app: AppSubmission, user: User) -> bool:
    """True if user can modify this app (owner or admin only)."""
    if user.role == "admin":
        return True
    return app.submitter_id == user.id


async def _with_rejection(app: AppSubmission, db: AsyncSession) -> dict:
    """Build AppResponse dict, populating rejection feedback if the most recent scan was rejected.

    Checks both outright rejected apps and deployed apps whose most recent UPDATE was rejected
    (status stays 'deployed' after an update rejection, but we still surface the feedback).
    """
    data = {c.name: getattr(app, c.name) for c in app.__table__.columns}
    data["rejection"] = None
    # Normalise None → [] so the schema validator is happy
    if data.get("allowed_users") is None:
        data["allowed_users"] = []
    if data.get("allowed_groups") is None:
        data["allowed_groups"] = []

    if app.status in ("rejected", "deployed"):
        scan_result = await db.execute(
            select(Scan)
            .where(Scan.submission_id == app.id)
            .order_by(Scan.created_at.desc())
            .limit(1)
        )
        scan = scan_result.scalar_one_or_none()
        if scan:
            approval_result = await db.execute(
                select(Approval)
                .where(Approval.scan_id == scan.id, Approval.decision == "rejected")
                .limit(1)
            )
            approval = approval_result.scalar_one_or_none()
            if approval:
                data["rejection"] = RejectionFeedback(
                    decision=approval.decision,
                    comment=approval.comment or "",
                    decided_at=approval.decided_at,
                )
    return data


@router.post("/", response_model=AppResponse, status_code=status.HTTP_201_CREATED)
@_limiter.limit("20/minute")
async def create_app(
    request: Request,
    payload: AppCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    existing = await db.execute(
        select(AppSubmission).where(
            AppSubmission.name == payload.name,
            AppSubmission.submitter_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You already have an app with that name")

    app_id = uuid.uuid4()
    repo_path, repo_url = create_bare_repo(payload.name, str(app_id))

    submission = AppSubmission(
        id=app_id,
        submitter_id=current_user.id,
        name=payload.name,
        description=payload.description,
        repo_path=repo_path,
        repo_url=repo_url,
        status="pending_scan",
    )
    db.add(submission)
    await db.flush()
    await db.refresh(submission)
    return await _with_rejection(submission, db)


@router.get("/", response_model=list[AppResponse])
async def list_apps(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    if current_user.role in ("admin", "approver"):
        result = await db.execute(select(AppSubmission).order_by(AppSubmission.created_at.desc()))
    else:
        # ICs see their own apps AND apps they've been granted access to (user or group)
        conditions = [
            AppSubmission.submitter_id == current_user.id,
            AppSubmission.allowed_users.contains([current_user.id]),
        ]
        if current_user.sso_groups:
            conditions.append(AppSubmission.allowed_groups.overlap(current_user.sso_groups))
        from sqlalchemy import or_
        result = await db.execute(
            select(AppSubmission)
            .where(or_(*conditions))
            .order_by(AppSubmission.created_at.desc())
        )
    apps = list(result.scalars().all())
    return [await _with_rejection(app, db) for app in apps]


@router.get("/{app_id}", response_model=AppResponse)
async def get_app(
    app_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_access(app, current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    return await _with_rejection(app, db)


@router.get("/{app_id}/clone-url")
async def get_clone_url(
    app_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_access(app, current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    from pathlib import Path
    repo_name = Path(app.repo_path).name
    ssh_url = f"ssh://git@{settings.GIT_SSH_HOST}:{settings.GIT_SSH_PORT}/git-repos/{repo_name}"
    return {"clone_url": app.repo_url, "ssh_clone_url": ssh_url, "repo_path": app.repo_path}


@router.post("/{app_id}/upload", status_code=status.HTTP_202_ACCEPTED)
@_limiter.limit("10/minute")
async def upload_zip(
    request: Request,
    app_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Accept a ZIP archive, commit it to the app's repo, and queue a scan."""
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    # Only the owner can upload new code
    if not _can_manage(app, current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip archive")

    zip_bytes = await file.read()

    try:
        commit_sha = await asyncio.to_thread(push_zip_to_repo, app.repo_path, zip_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except subprocess.CalledProcessError as exc:
        import logging
        logging.getLogger(__name__).error("ZIP processing git error: %s\nstderr: %s", exc, exc.stderr)
        raise HTTPException(status_code=500, detail="Failed to process ZIP — ensure the archive contains valid files")

    # detect if this is an update to an already-deployed app
    is_update = app.status == "deployed"
    previous_scan_id = None
    if is_update:
        prev_result = await db.execute(
            select(Scan)
            .join(Approval, Approval.scan_id == Scan.id)
            .where(Scan.submission_id == app_id, Approval.decision == "approved")
            .order_by(Approval.decided_at.desc())
            .limit(1)
        )
        prev_scan = prev_result.scalar_one_or_none()
        previous_scan_id = prev_scan.id if prev_scan else None

    scan = Scan(
        submission_id=app_id,
        commit_sha=commit_sha,
        status="queued",
        scan_type="update" if is_update else "initial",
        previous_scan_id=previous_scan_id,
    )
    db.add(scan)
    app.commit_sha = commit_sha
    app.status = "scanning"
    await db.flush()
    await db.refresh(scan)

    from app.scanners.pipeline import run_scan_pipeline
    task = run_scan_pipeline.delay(str(scan.id))
    scan.celery_task_id = task.id
    await db.commit()

    return {"scan_id": str(scan.id), "commit_sha": commit_sha}


@router.patch("/{app_id}/visibility", response_model=AppResponse)
async def update_visibility(
    app_id: uuid.UUID,
    payload: VisibilityUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_manage(app, current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    app.visibility = payload.visibility
    if payload.visibility == "public":
        from datetime import datetime, timezone
        app.public_flagged_at = datetime.now(timezone.utc)
    else:
        app.public_flagged_at = None
    await db.flush()

    # If the app is deployed, update the proxy config / ingress immediately
    if app.status == "deployed":
        import re
        import logging
        from app.config import settings
        safe_name = re.sub(r"[^a-z0-9_-]", "-", app.name.lower())
        try:
            if settings.DEPLOY_BACKEND == "kubernetes":
                from sqlalchemy import select as sa_select
                from app.models.deployment import Deployment
                dep_result = await db.execute(
                    sa_select(Deployment)
                    .where(Deployment.submission_id == app.id)
                    .order_by(Deployment.created_at.desc())
                )
                dep = dep_result.scalars().first()
                if dep and dep.internal_port and dep.public_url:
                    from app.services.k8s_ingress_service import write_app_ingress
                    write_app_ingress(safe_name, dep.internal_port, dep.public_url, app.visibility)
            elif app.stable_external_port and app.stable_container_name:
                from app.services import nginx_service
                nginx_service.write_app_config(safe_name, app.stable_external_port, app.visibility)
        except Exception as e:
            logging.getLogger(__name__).warning("proxy config update failed: %s", e)

    await db.commit()
    # updated_at has onupdate=func.now(), which SQLAlchemy expires on commit
    # regardless of the session's expire_on_commit=False — refresh explicitly
    # so _with_rejection's synchronous getattr loop below doesn't trigger an
    # unawaited lazy-load (crashes with sqlalchemy.exc.MissingGreenlet).
    await db.refresh(app)
    return await _with_rejection(app, db)


@router.get("/{app_id}/users", response_model=list[AppUserResponse])
async def list_app_users(
    app_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_access(app, current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    user_ids = list(app.allowed_users or [])
    if not user_ids:
        return []
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    return list(users_result.scalars().all())


@router.post("/{app_id}/users", response_model=AppUserResponse, status_code=status.HTTP_201_CREATED)
async def add_app_user(
    app_id: uuid.UUID,
    payload: AppUserGrant,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_manage(app, current_user):
        raise HTTPException(status_code=403, detail="Only the app owner or an admin can manage access")

    user_result = await db.execute(select(User).where(User.email == payload.email))
    target = user_result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="No user found with that email address")
    if target.id == app.submitter_id:
        raise HTTPException(status_code=409, detail="That user is already the app owner")

    existing = list(app.allowed_users or [])
    if target.id in existing:
        raise HTTPException(status_code=409, detail="That user already has access")

    app.allowed_users = existing + [target.id]
    await db.commit()
    return target


@router.delete("/{app_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_app_user(
    app_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_manage(app, current_user):
        raise HTTPException(status_code=403, detail="Only the app owner or an admin can manage access")

    existing = list(app.allowed_users or [])
    if user_id not in existing:
        raise HTTPException(status_code=404, detail="User does not have access to this app")

    app.allowed_users = [u for u in existing if u != user_id]
    await db.commit()


@router.get("/{app_id}/groups")
async def list_app_groups(
    app_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_access(app, current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    return list(app.allowed_groups or [])


@router.post("/{app_id}/groups", status_code=status.HTTP_201_CREATED)
async def add_app_group(
    app_id: uuid.UUID,
    payload: AppGroupGrant,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_manage(app, current_user):
        raise HTTPException(status_code=403, detail="Only the app owner or an admin can manage access")

    group = payload.group_name.strip()
    if not group:
        raise HTTPException(status_code=400, detail="group_name cannot be empty")

    existing = list(app.allowed_groups or [])
    if group in existing:
        raise HTTPException(status_code=409, detail="That group already has access")

    app.allowed_groups = existing + [group]
    await db.commit()
    return {"group_name": group}


@router.delete("/{app_id}/groups/{group_name:path}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_app_group(
    app_id: uuid.UUID,
    group_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_manage(app, current_user):
        raise HTTPException(status_code=403, detail="Only the app owner or an admin can manage access")

    existing = list(app.allowed_groups or [])
    if group_name not in existing:
        raise HTTPException(status_code=404, detail="Group does not have access to this app")

    app.allowed_groups = [g for g in existing if g != group_name]
    await db.commit()


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app(
    app_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not _can_manage(app, current_user):
        raise HTTPException(status_code=403, detail="Access denied")

    delete_bare_repo(app.repo_path)
    await db.delete(app)
