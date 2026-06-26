import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user, require_approver, require_admin
from app.models.app_submission import AppSubmission
from app.models.deployment import Deployment
from app.models.user import User
from app.schemas.deployment import DeploymentResponse
from app.services import container_service

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.get("/", response_model=list[DeploymentResponse])
async def list_deployments(
    _: User = Depends(require_approver),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(
        select(Deployment, AppSubmission.visibility, AppSubmission.public_flagged_at)
        .join(AppSubmission, AppSubmission.id == Deployment.submission_id)
        .order_by(Deployment.created_at.desc())
    )
    rows = result.all()
    out = []
    for d, vis, flagged_at in rows:
        data = {c.name: getattr(d, c.name) for c in d.__table__.columns}
        data["app_visibility"] = vis
        data["app_public_flagged_at"] = flagged_at
        out.append(data)
    return out


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: uuid.UUID,
    _: User = Depends(require_approver),
    db: AsyncSession = Depends(get_db),
) -> Deployment:
    deployment = await db.get(Deployment, deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment


@router.get("/app/{submission_id}", response_model=DeploymentResponse)
async def get_deployment_for_app(
    submission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Deployment:
    if current_user.role == "ic":
        app = await db.get(AppSubmission, submission_id)
        if not app:
            raise HTTPException(status_code=404, detail="No deployment found for this app")
        if app.submitter_id != current_user.id and not (
            app.allowed_users and current_user.id in app.allowed_users
        ):
            raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(
        select(Deployment).where(Deployment.submission_id == submission_id)
    )
    deployment = result.scalar_one_or_none()
    if not deployment:
        raise HTTPException(status_code=404, detail="No deployment found for this app")
    return deployment


@router.post("/{deployment_id}/stop", response_model=DeploymentResponse)
async def stop_deployment(
    deployment_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Deployment:
    deployment = await db.get(Deployment, deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    if deployment.status not in ("running", "starting"):
        raise HTTPException(status_code=409, detail=f"Deployment is {deployment.status}")

    if deployment.container_id:
        container_service.stop_container(deployment.container_id)

    submission = await db.get(AppSubmission, deployment.submission_id)
    if submission:
        import re
        from app.config import settings
        safe_name = re.sub(r"[^a-z0-9_-]", "-", submission.name.lower())
        if settings.DEPLOY_BACKEND == "kubernetes":
            from app.services.k8s_ingress_service import remove_app_ingress
            remove_app_ingress(safe_name)
        else:
            from app.services import nginx_service
            nginx_service.remove_app_config(safe_name)
        submission.status = "stopped"

    deployment.status = "stopped"
    from datetime import datetime, timezone
    deployment.stopped_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(deployment)
    return deployment


@router.post("/{deployment_id}/start", response_model=DeploymentResponse)
async def restart_deployment(
    deployment_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Deployment:
    """Trigger a re-deploy by enqueuing the deploy task again."""
    deployment = await db.get(Deployment, deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    from sqlalchemy import select as sa_select
    from app.models.approval import Approval
    result = await db.execute(
        sa_select(Approval).where(
            Approval.scan_id == deployment.scan_id,
            Approval.decision == "approved",
        )
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=409, detail="No approved approval found for this deployment")

    submission = await db.get(AppSubmission, deployment.submission_id)
    if submission:
        submission.status = "deployed"

    from worker.deploy_task import deploy_approved_app
    deploy_approved_app.delay(str(approval.id))

    deployment.status = "starting"
    await db.commit()
    await db.refresh(deployment)
    return deployment


@router.get("/app/{submission_id}/health")
async def get_app_health(
    submission_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Live container/pod health — accessible to the app owner."""
    if current_user.role == "ic":
        app = await db.get(AppSubmission, submission_id)
        if not app:
            raise HTTPException(status_code=404, detail="App not found")
        if app.submitter_id != current_user.id and not (
            app.allowed_users and current_user.id in app.allowed_users
        ):
            raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(
        select(Deployment).where(Deployment.submission_id == submission_id)
    )
    deployment = result.scalar_one_or_none()

    from app.config import settings
    if settings.DEPLOY_BACKEND == "kubernetes":
        if not deployment or not deployment.k8s_deployment_name:
            return {"status": "no_deployment", "restart_count": 0, "logs": None}
        from app.services.k8s_app_service import get_app_status
        safe_name = deployment.k8s_deployment_name.removeprefix("gk-app-")
        k8s_status = get_app_status(safe_name)
        status_str = "running" if k8s_status["available"] else (
            "stopped" if k8s_status["total_replicas"] == 0 else "starting"
        )
        return {"status": status_str, "restart_count": 0, "logs": None}
    else:
        if not deployment or not deployment.container_id:
            return {"status": "no_container", "restart_count": 0, "logs": None}
        return container_service.get_container_health(deployment.container_id)


@router.get("/{deployment_id}/logs")
async def get_logs(
    deployment_id: uuid.UUID,
    tail: int = 200,
    _: User = Depends(require_approver),
    db: AsyncSession = Depends(get_db),
) -> dict:
    deployment = await db.get(Deployment, deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    from app.config import settings
    if settings.DEPLOY_BACKEND == "kubernetes":
        if deployment.k8s_deployment_name:
            import re as _re
            from app.services.k8s_app_service import get_app_logs
            # Derive safe_name from k8s_deployment_name ("gk-app-{safe_name}")
            safe_name = deployment.k8s_deployment_name.removeprefix("gk-app-")
            try:
                live = get_app_logs(safe_name, tail_lines=tail)
                if live:
                    return {"logs": live}
            except Exception:
                pass
    else:
        if deployment.container_id:
            try:
                live = container_service.get_container_logs(deployment.container_id, tail=tail)
                if live:
                    return {"logs": live}
            except Exception:
                pass
    return {"logs": deployment.logs_cache or ""}


@router.get("/{deployment_id}/status")
async def get_status(
    deployment_id: uuid.UUID,
    _: User = Depends(require_approver),
    db: AsyncSession = Depends(get_db),
) -> dict:
    deployment = await db.get(Deployment, deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    from app.config import settings
    live_status = deployment.status
    if settings.DEPLOY_BACKEND == "kubernetes":
        if deployment.k8s_deployment_name:
            from app.services.k8s_app_service import get_app_status
            safe_name = deployment.k8s_deployment_name.removeprefix("gk-app-")
            k8s_status = get_app_status(safe_name)
            if k8s_status["available"]:
                live_status = "running"
            elif k8s_status["total_replicas"] == 0:
                live_status = "stopped"
            else:
                live_status = "starting"
            if live_status != deployment.status:
                deployment.status = live_status
                await db.commit()
    else:
        if deployment.container_id:
            live_status = container_service.get_container_status(deployment.container_id)
            if live_status != deployment.status and live_status in ("running", "exited", "dead"):
                deployment.status = live_status if live_status == "running" else "stopped"
                await db.commit()

    return {
        "deployment_id": deployment_id,
        "status": live_status,
        "public_url": deployment.public_url,
    }
