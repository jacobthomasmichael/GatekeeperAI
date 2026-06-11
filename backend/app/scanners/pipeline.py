import asyncio
import io
import json
import subprocess
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone

import redis as sync_redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings
from app.models.app_submission import AppSubmission
from app.models.scan import Scan, ScanResult as ScanResultModel
from app.scanners.base import ScanContext
from app.scanners.dependency_scanner import DependencyScanner
from app.scanners.egress_scanner import EgressScanner
from app.scanners.llm_scanner import LLMScanner
from app.scanners.pii_scanner import PiiScanner
from app.scanners.risk_engine import compute_risk_tier
from app.scanners.secrets_scanner import SecretsScanner
from worker.celery_app import celery_app

SCANNERS = [
    SecretsScanner(),
    DependencyScanner(),
    EgressScanner(),
    PiiScanner(),
    LLMScanner(),
]


def _publish(scan_id: str, event: dict) -> None:
    try:
        r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.publish(f"scan:{scan_id}:events", json.dumps(event))
        r.close()
    except Exception:
        pass


def _detect_app_type(repo_path: str) -> str | None:
    from pathlib import Path
    root = Path(repo_path)
    if (root / "requirements.txt").exists():
        txt = (root / "requirements.txt").read_text(errors="ignore").lower()
        if "streamlit" in txt:
            return "python-streamlit"
        if "gradio" in txt:
            return "python-gradio"
        if "fastapi" in txt or "flask" in txt:
            return "python-web"
        return "python"
    if (root / "package.json").exists():
        pkg = (root / "package.json").read_text(errors="ignore").lower()
        if '"next"' in pkg:
            return "nodejs-next"
        return "nodejs"
    if (root / "index.html").exists():
        return "static"
    return None


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_scan_pipeline(self, scan_id: str) -> None:
    try:
        asyncio.run(_async_pipeline(scan_id))
    except Exception as exc:
        _publish(scan_id, {"event": "error", "message": str(exc)})
        raise self.retry(exc=exc)


async def _async_pipeline(scan_id: str) -> None:
    # Create a dedicated engine per task — disposed before the event loop closes,
    # avoiding the asyncpg "event loop is closed" error in Celery workers.
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        await _run_with_session(scan_id, SessionLocal)
    finally:
        await engine.dispose()


async def _run_with_session(scan_id: str, SessionLocal) -> None:
    async with SessionLocal() as db:
        scan = await db.get(Scan, uuid.UUID(scan_id))
        if not scan:
            raise ValueError(f"Scan {scan_id} not found")

        submission = await db.get(AppSubmission, scan.submission_id)
        if not submission:
            raise ValueError(f"Submission {scan.submission_id} not found")

        # Mark scan as running
        scan.status = "running"
        scan.started_at = datetime.now(timezone.utc)
        await db.commit()

        _publish(scan_id, {"event": "started", "scan_id": scan_id})

        # Extract bare repo HEAD to a temp working tree
        with tempfile.TemporaryDirectory() as work_dir:
            try:
                proc = subprocess.run(
                    ["git", "archive", "--format=tar", scan.commit_sha],
                    cwd=submission.repo_path,
                    capture_output=True,
                    check=True,
                )
                with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tar:
                    tar.extractall(work_dir)
            except subprocess.CalledProcessError as e:
                await _fail_scan(db, scan, submission, f"git archive failed: {e.stderr.decode()}")
                return

            detected_type = _detect_app_type(work_dir)
            if detected_type and not submission.detected_type:
                submission.detected_type = detected_type

            context = ScanContext(
                scan_id=scan_id,
                submission_id=str(submission.id),
                app_name=submission.name,
                app_description=submission.description,
                commit_sha=scan.commit_sha,
                detected_type=detected_type,
            )

            scanner_results = []
            for scanner in SCANNERS:
                _publish(scan_id, {"event": "scanner_started", "scanner": scanner.name})

                result = scanner.run(work_dir, context)

                # Persist scan_result row
                db_result = ScanResultModel(
                    scan_id=scan.id,
                    scanner_name=result.scanner_name,
                    status=result.status,
                    severity=result.severity,
                    findings=result.findings,
                    raw_output=result.raw_output[:4000],  # cap stored raw output
                    duration_ms=result.duration_ms,
                )
                db.add(db_result)
                await db.flush()

                scanner_results.append(result)
                _publish(scan_id, {
                    "event": "scanner_complete",
                    "scanner": result.scanner_name,
                    "status": result.status,
                    "severity": result.severity,
                    "duration_ms": result.duration_ms,
                })

            # Compute final risk tier
            risk_tier, risk_score = compute_risk_tier(scanner_results)

            # Update scan
            scan.status = "complete"
            scan.risk_tier = risk_tier
            scan.risk_score = risk_score
            scan.completed_at = datetime.now(timezone.utc)

            # Update submission
            submission.risk_tier = risk_tier
            if risk_tier == "green":
                submission.status = "approved"
            else:
                submission.status = "awaiting_approval"

            # Create approval record for Yellow/Red
            from app.services.approval_service import route_after_scan
            await route_after_scan(scan, submission, db)

            await db.commit()

        _publish(scan_id, {
            "event": "complete",
            "risk_tier": risk_tier,
            "risk_score": risk_score,
            "status": submission.status,
        })


async def _fail_scan(db, scan: Scan, submission: AppSubmission, reason: str) -> None:
    scan.status = "failed"
    scan.completed_at = datetime.now(timezone.utc)
    submission.status = "failed"
    await db.commit()
    _publish(str(scan.id), {"event": "error", "message": reason})
