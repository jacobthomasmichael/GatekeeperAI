import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user
from app.models.app_submission import AppSubmission
from app.models.user import User
from app.schemas.app_submission import AppCreate, AppResponse
from app.services.git_service import create_bare_repo, delete_bare_repo

router = APIRouter(prefix="/apps", tags=["apps"])


@router.post("/", response_model=AppResponse, status_code=status.HTTP_201_CREATED)
async def create_app(
    payload: AppCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppSubmission:
    # Check name uniqueness per submitter
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
    return submission


@router.get("/", response_model=list[AppResponse])
async def list_apps(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AppSubmission]:
    if current_user.role in ("admin", "approver"):
        result = await db.execute(select(AppSubmission).order_by(AppSubmission.created_at.desc()))
    else:
        result = await db.execute(
            select(AppSubmission)
            .where(AppSubmission.submitter_id == current_user.id)
            .order_by(AppSubmission.created_at.desc())
        )
    return list(result.scalars().all())


@router.get("/{app_id}", response_model=AppResponse)
async def get_app(
    app_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppSubmission:
    result = await db.execute(select(AppSubmission).where(AppSubmission.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if current_user.role == "ic" and app.submitter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return app


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
    return {"clone_url": app.repo_url, "repo_path": app.repo_path}


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
