import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user
from app.models.app_submission import AppSubmission
from app.models.user import User
from app.schemas.secret import SecretCreate, SecretKeyResponse
from app.services import secrets_service

router = APIRouter(prefix="/apps/{submission_id}/secrets", tags=["secrets"])


async def _get_submission_or_404(submission_id: uuid.UUID, db: AsyncSession) -> AppSubmission:
    submission = await db.get(AppSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="App not found")
    return submission


def _check_ownership(submission: AppSubmission, user: User) -> None:
    if user.role == "admin":
        return
    if submission.submitter_id != user.id:
        raise HTTPException(status_code=403, detail="Not your app")


@router.get("/", response_model=list[SecretKeyResponse])
async def list_secrets(
    submission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    submission = await _get_submission_or_404(submission_id, db)
    _check_ownership(submission, current_user)
    keys = await secrets_service.list_secret_keys(str(submission_id), db)
    return [{"key_name": k, "submission_id": submission_id} for k in keys]


@router.post("/", response_model=SecretKeyResponse, status_code=201)
async def create_secret(
    submission_id: uuid.UUID,
    payload: SecretCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    submission = await _get_submission_or_404(submission_id, db)
    _check_ownership(submission, current_user)
    await secrets_service.set_secret(
        submission_id=str(submission_id),
        key_name=payload.key_name,
        value=payload.value,
        created_by=str(current_user.id),
        db=db,
    )
    await db.commit()
    return {"key_name": payload.key_name, "submission_id": submission_id}


@router.delete("/{key_name}", status_code=204)
async def delete_secret(
    submission_id: uuid.UUID,
    key_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    submission = await _get_submission_or_404(submission_id, db)
    _check_ownership(submission, current_user)
    deleted = await secrets_service.delete_secret(str(submission_id), key_name.upper(), db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Secret not found")
    await db.commit()
