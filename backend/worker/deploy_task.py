import asyncio
import io
import logging
import re
import subprocess
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

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
                    tar.extractall(work_dir, filter="data")
            except subprocess.CalledProcessError as e:
                await _fail(db, deployment, submission, f"git archive failed: {e.stderr.decode()}")
                return

            # Write Dockerfile only if the repo didn't include one
            dockerfile_path = Path(work_dir, "Dockerfile")
            if not dockerfile_path.exists():
                dockerfile_content = dockerfile_service.generate_dockerfile(submission.detected_type)
                dockerfile_path.write_text(dockerfile_content)

            # Determine internal port — prefer EXPOSE from the Dockerfile
            internal_port = _parse_expose(dockerfile_path) or _port_for_type(submission.detected_type)

            # Build image (old container stays live during this step)
            safe_name = re.sub(r"[^a-z0-9_-]", "-", submission.name.lower())
            image_tag = f"gatekeeperai/{safe_name}:{scan.commit_sha[:8] if scan.commit_sha else 'latest'}"

            try:
                container_service.build_image(work_dir, image_tag)
            except Exception as e:
                await _fail(db, deployment, submission, f"docker build failed: {e}")
                return

            # Load secrets as env vars
            from app.services.secrets_service import decrypt_all
            secrets = await decrypt_all(str(submission.id), db)

            # Backfill stable port/name for apps deployed before this feature shipped
            if scan.scan_type == "update" and submission.stable_external_port is None and deployment.external_port:
                submission.stable_external_port = deployment.external_port
                submission.stable_container_name = deployment.container_name

            is_update = scan.scan_type == "update" and submission.stable_external_port is not None

            if is_update:
                external_port = submission.stable_external_port
                container_name = submission.stable_container_name
                old_container_id = deployment.container_id
            else:
                # First deployment: pick a port and persist it as stable
                try:
                    external_port = container_service.pick_external_port()
                except RuntimeError as e:
                    await _fail(db, deployment, submission, str(e))
                    return
                container_name = f"gka-{safe_name}-{str(submission.id)[:8]}"
                submission.stable_external_port = external_port
                submission.stable_container_name = container_name
                old_container_id = None

            # Start new container FIRST — old container stays live until this succeeds
            # Clear unique DB fields before starting so Docker name/ID don't conflict
            deployment.container_id = None
            deployment.container_name = None
            await db.flush()

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
                # New container failed to start — old container is still running, restore DB
                deployment.container_id = old_container_id
                deployment.container_name = container_name if not is_update else deployment.container_name
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
            deployment.scan_id = scan.id
            deployment.env_vars_injected = {k: "***" for k in secrets}

            submission.status = "deployed"

            # Commit before stopping the old container. If the commit fails we
            # stop the new container (old is still running) to avoid a leak.
            try:
                await db.commit()
            except Exception as exc:
                logger.error(
                    "DB commit failed after container start, stopping new container to avoid leak: %s", exc
                )
                try:
                    container_service.stop_container(container.id)
                except Exception:
                    pass
                raise

            # DB committed — now safely tear down the old container
            if old_container_id:
                container_service.stop_container(old_container_id)


async def _fail(db, deployment: Deployment, submission: AppSubmission, reason: str) -> None:
    logger.error("Deploy failed: %s", reason)
    deployment.status = "failed"
    # Updates revert to deployed (old version still live); initial deploys revert to approved for retry
    from app.models.scan import Scan as _Scan
    from sqlalchemy import select as _select
    scan_row = (await db.execute(_select(_Scan).where(_Scan.id == deployment.scan_id))).scalar_one_or_none()
    if scan_row and scan_row.scan_type == "update":
        submission.status = "deployed"
    else:
        submission.status = "approved"
    await db.commit()


def _parse_expose(dockerfile_path: Path) -> int | None:
    """Return the first EXPOSE port from a Dockerfile, or None if not found."""
    try:
        for line in dockerfile_path.read_text().splitlines():
            line = line.strip()
            if line.upper().startswith("EXPOSE"):
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1].split("/")[0])
    except Exception:
        pass
    return None


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
