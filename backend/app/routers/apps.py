import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from app.schemas.app_submission import AppCreate, AppResponse, RejectionFeedback
from app.services.git_service import create_bare_repo, delete_bare_repo

router = APIRouter(prefix="/apps", tags=["apps"])

_limiter = Limiter(key_func=get_remote_address)


async def _with_rejection(app: AppSubmission, db: AsyncSession) -> dict:
    """Build AppResponse dict, populating rejection feedback if the app was rejected."""
    data = {c.name: getattr(app, c.name) for c in app.__table__.columns}
    data["rejection"] = None

    if app.status == "rejected":
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
        result = await db.execute(
            select(AppSubmission)
            .where(AppSubmission.submitter_id == current_user.id)
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
    if current_user.role == "ic" and app.submitter_id != current_user.id:
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
    if current_user.role == "ic" and app.submitter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    from pathlib import Path
    repo_name = Path(app.repo_path).name
    ssh_url = f"ssh://git@{settings.GIT_SSH_HOST}:{settings.GIT_SSH_PORT}/git-repos/{repo_name}"
    return {"clone_url": app.repo_url, "ssh_clone_url": ssh_url, "repo_path": app.repo_path}


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
    if current_user.role == "ic" and app.submitter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    delete_bare_repo(app.repo_path)
    await db.delete(app)
