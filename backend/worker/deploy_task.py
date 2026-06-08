import asyncio
import io
import re
import subprocess
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings
from app.models.app_submission import AppSubmission
from app.models.approval import Approval
from app.models.deployment import Deployment
from app.models.scan import Scan
from app.services import container_service, dockerfile_service
from worker.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def deploy_approved_app(self, approval_id: str) -> None:
    try:
        asyncio.run(_async_deploy(approval_id))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _async_deploy(approval_id: str) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        await _run_deploy(approval_id, SessionLocal)
    finally:
        await engine.dispose()


async def _run_deploy(approval_id: str, SessionLocal) -> None:
    async with SessionLocal() as db:
        approval = await db.get(Approval, uuid.UUID(approval_id))
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")

        scan = await db.get(Scan, approval.scan_id)
        submission = await db.get(AppSubmission, scan.submission_id)

        # Create or find existing Deployment row
        from sqlalchemy import select
        result = await db.execute(
            select(Deployment).where(Deployment.submission_id == submission.id)
        )
        deployment = result.scalar_one_or_none()
        if not deployment:
            deployment = Deployment(
                submission_id=submission.id,
                scan_id=scan.id,
                status="building",
            )
            db.add(deployment)
            await db.flush()
        else:
            deployment.scan_id = scan.id
            deployment.status = "building"

        await db.commit()

        with tempfile.TemporaryDirectory() as work_dir:
            # Extract repo at approved commit
            try:
                proc = subprocess.run(
                    ["git", "archive", "--format=tar", scan.commit_sha or "HEAD"],
                    cwd=submission.repo_path,
                    capture_output=True,
                    check=True,
                )
                with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tar:
                    tar.extractall(work_dir)
            except subprocess.CalledProcessError as e:
                await _fail(db, deployment, submission, f"git archive failed: {e.stderr.decode()}")
                return

            # Write Dockerfile
            dockerfile_content = dockerfile_service.generate_dockerfile(submission.detected_type)
            Path(work_dir, "Dockerfile").write_text(dockerfile_content)

            # Build image
            safe_name = re.sub(r"[^a-z0-9_-]", "-", submission.name.lower())
            image_tag = f"gatekeeperai/{safe_name}:{scan.commit_sha[:8] if scan.commit_sha else 'latest'}"
            container_name = f"gka-{safe_name}-{str(submission.id)[:8]}"

            try:
                container_service.build_image(work_dir, image_tag)
            except Exception as e:
                await _fail(db, deployment, submission, f"docker build failed: {e}")
                return

            # Load secrets as env vars
            from app.services.secrets_service import decrypt_all
            secrets = await decrypt_all(str(submission.id), db)

            # Pick port
            internal_port = _port_for_type(submission.detected_type)
            try:
                external_port = container_service.pick_external_port()
            except RuntimeError as e:
                await _fail(db, deployment, submission, str(e))
                return

            # Start container
            try:
                container = container_service.start_container(
                    image_tag=image_tag,
                    container_name=container_name,
                    internal_port=internal_port,
                    external_port=external_port,
                    env_vars=secrets,
                    allowed_egress_urls=deployment.allowed_egress_urls or [],
                )
            except Exception as e:
                await _fail(db, deployment, submission, f"docker run failed: {e}")
                return

            public_url = f"{settings.APP_BASE_URL}:{external_port}"

            deployment.container_id = container.id
            deployment.container_name = container_name
            deployment.image_tag = image_tag
            deployment.status = "running"
            deployment.internal_port = internal_port
            deployment.external_port = external_port
            deployment.public_url = public_url
            deployment.env_vars_injected = {k: "***" for k in secrets}

            submission.status = "deployed"
            await db.commit()


async def _fail(db, deployment: Deployment, submission: AppSubmission, reason: str) -> None:
    import logging
    logging.getLogger(__name__).error("Deploy failed: %s", reason)
    deployment.status = "failed"
    submission.status = "approved"  # revert to approved so it can be retried
    await db.commit()


def _port_for_type(detected_type: str | None) -> int:
    mapping = {
        "python-streamlit": 8501,
        "python-gradio": 7860,
        "python-web": 8000,
        "python": 8000,
        "nodejs-next": 3000,
        "nodejs": 3000,
        "static": 80,
    }
    return mapping.get(detected_type or "", 8000)
