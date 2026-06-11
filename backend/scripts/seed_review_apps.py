"""
Seed Red and Yellow apps awaiting approval, plus a couple of rejected apps
with review notes visible to the IC submitter.

Run from backend/ with:
    python scripts/seed_review_apps.py
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://gatekeeper:gatekeeper_dev@localhost:5433/gatekeeperai"

IC_USER_ID = uuid.UUID("1129c4fe-371f-41f5-b35e-3ff41a632ead")
APPROVER_ID = uuid.UUID("141e1d82-f0ac-4aee-a908-031eff3598b2")

now = datetime.now(timezone.utc)


# ── Realistic scan findings ────────────────────────────────────────────────────

RED_SECRETS_FINDINGS = {
    "hits": [
        {"file": "src/config.py", "line": 14, "match": "AWS_SECRET_ACCESS_KEY=AKIA...", "rule": "aws-access-token"},
        {"file": ".env.prod", "line": 3, "match": "OPENAI_API_KEY=sk-...", "rule": "openai-api-key"},
    ],
    "count": 2,
}

RED_DEPENDENCY_FINDINGS = {
    "vulnerabilities": [
        {"package": "pillow", "version": "9.0.0", "cve": "CVE-2023-44271", "severity": "critical",
         "description": "Uncontrolled resource consumption via crafted TIFF/PCX files"},
        {"package": "cryptography", "version": "38.0.1", "cve": "CVE-2023-49083", "severity": "high",
         "description": "NULL pointer dereference in PKCS12 parsing"},
        {"package": "requests", "version": "2.27.0", "cve": "CVE-2023-32681", "severity": "medium",
         "description": "Unintended leak of Proxy-Authorization header"},
    ],
    "count": 3,
}

RED_EGRESS_FINDINGS = {
    "blocked_calls": [
        {"host": "169.254.169.254", "path": "/latest/meta-data/", "reason": "EC2 metadata endpoint — credential theft risk"},
        {"host": "10.0.0.0", "path": "/internal-api", "reason": "RFC-1918 private range not in allowlist"},
    ],
    "count": 2,
}

YELLOW_DEPENDENCY_FINDINGS = {
    "vulnerabilities": [
        {"package": "flask", "version": "2.2.3", "cve": "CVE-2023-30861", "severity": "high",
         "description": "Possible disclosure of permanent session cookie due to missing Vary header"},
    ],
    "count": 1,
}

YELLOW_PII_FINDINGS = {
    "matches": [
        {"file": "data/sample.csv", "line": 7, "type": "email", "sample": "j***@example.com"},
        {"file": "data/sample.csv", "line": 12, "type": "ssn", "sample": "***-**-4321"},
    ],
    "count": 2,
}

YELLOW_EGRESS_FINDINGS = {
    "unreviewed_hosts": [
        {"host": "api.stripe.com", "reason": "Payment processor — requires data handling review"},
        {"host": "analytics.segment.com", "reason": "Third-party analytics — PII egress concern"},
    ],
    "count": 2,
}

GREEN_FINDINGS: dict = {"count": 0, "issues": []}


# ── App definitions ────────────────────────────────────────────────────────────

APPS = [
    # ── RED apps (risk_score >= 75) ──────────────────────────────────────────
    {
        "name": "ml-inference-api",
        "description": "FastAPI service wrapping a fine-tuned LLaMA model for internal document Q&A",
        "detected_type": "python-web",
        "risk_tier": "red",
        "risk_score": 92,
        "commit_sha": "a3f1e2c4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0",
        "status": "awaiting_approval",
        "scan_results": [
            {"scanner_name": "secrets", "status": "flagged", "severity": "critical", "findings": RED_SECRETS_FINDINGS, "duration_ms": 810},
            {"scanner_name": "dependency", "status": "flagged", "severity": "critical", "findings": RED_DEPENDENCY_FINDINGS, "duration_ms": 3420},
            {"scanner_name": "egress", "status": "flagged", "severity": "high", "findings": RED_EGRESS_FINDINGS, "duration_ms": 560},
            {"scanner_name": "pii", "status": "passed", "severity": "none", "findings": GREEN_FINDINGS, "duration_ms": 290},
        ],
        "approval": {"decision": None, "comment": None},
    },
    {
        "name": "data-pipeline-runner",
        "description": "Celery-based ETL pipeline that ingests customer records from S3 and loads into Redshift",
        "detected_type": "python",
        "risk_tier": "red",
        "risk_score": 88,
        "commit_sha": "b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0",
        "status": "awaiting_approval",
        "scan_results": [
            {"scanner_name": "secrets", "status": "flagged", "severity": "high", "findings": {
                "hits": [{"file": "config/redshift.py", "line": 8, "match": "password='hardcoded_pass'", "rule": "hardcoded-password"}],
                "count": 1,
            }, "duration_ms": 720},
            {"scanner_name": "dependency", "status": "flagged", "severity": "high", "findings": RED_DEPENDENCY_FINDINGS, "duration_ms": 2910},
            {"scanner_name": "egress", "status": "passed", "severity": "none", "findings": GREEN_FINDINGS, "duration_ms": 420},
            {"scanner_name": "pii", "status": "flagged", "severity": "critical", "findings": {
                "matches": [
                    {"file": "etl/transform.py", "line": 34, "type": "credit_card", "sample": "4*** **** **** 1234"},
                    {"file": "etl/transform.py", "line": 67, "type": "ssn", "sample": "***-**-5678"},
                    {"file": "etl/transform.py", "line": 89, "type": "email", "sample": "c***@corp.com"},
                ],
                "count": 3,
            }, "duration_ms": 1150},
        ],
        "approval": {"decision": None, "comment": None},
    },
    {
        "name": "admin-portal-v2",
        "description": "Internal admin dashboard with user management, billing controls, and audit log viewer",
        "detected_type": "nodejs-next",
        "risk_tier": "red",
        "risk_score": 81,
        "commit_sha": "c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3",
        "status": "awaiting_approval",
        "scan_results": [
            {"scanner_name": "secrets", "status": "passed", "severity": "none", "findings": GREEN_FINDINGS, "duration_ms": 650},
            {"scanner_name": "dependency", "status": "flagged", "severity": "critical", "findings": {
                "vulnerabilities": [
                    {"package": "express", "version": "4.17.1", "cve": "CVE-2022-24999", "severity": "high",
                     "description": "Prototype pollution via qs library"},
                    {"package": "lodash", "version": "4.17.20", "cve": "CVE-2021-23337", "severity": "high",
                     "description": "Command injection via template function"},
                    {"package": "jsonwebtoken", "version": "8.5.1", "cve": "CVE-2022-23529", "severity": "critical",
                     "description": "Remote code execution via crafted JWK"},
                ],
                "count": 3,
            }, "duration_ms": 4100},
            {"scanner_name": "egress", "status": "flagged", "severity": "high", "findings": {
                "unreviewed_hosts": [
                    {"host": "stripe.com", "reason": "Payment data egress requires PCI-DSS sign-off"},
                ],
                "count": 1,
            }, "duration_ms": 380},
            {"scanner_name": "pii", "status": "flagged", "severity": "high", "findings": {
                "matches": [{"file": "pages/api/users.ts", "line": 42, "type": "email", "sample": "a***@corp.com"}],
                "count": 1,
            }, "duration_ms": 670},
        ],
        "approval": {"decision": None, "comment": None},
    },
    # ── YELLOW apps (risk_score 40-74) ───────────────────────────────────────
    {
        "name": "slack-digest-bot",
        "description": "Python bot that reads Slack channel history and posts daily summaries via webhook",
        "detected_type": "python",
        "risk_tier": "yellow",
        "risk_score": 58,
        "commit_sha": "d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6",
        "status": "awaiting_approval",
        "scan_results": [
            {"scanner_name": "secrets", "status": "passed", "severity": "none", "findings": GREEN_FINDINGS, "duration_ms": 430},
            {"scanner_name": "dependency", "status": "flagged", "severity": "medium", "findings": YELLOW_DEPENDENCY_FINDINGS, "duration_ms": 1870},
            {"scanner_name": "egress", "status": "flagged", "severity": "medium", "findings": {
                "unreviewed_hosts": [
                    {"host": "slack.com", "reason": "Workspace messaging platform — verify token scope"},
                    {"host": "hooks.slack.com", "reason": "Webhook egress — ensure rate limits are respected"},
                ],
                "count": 2,
            }, "duration_ms": 310},
            {"scanner_name": "pii", "status": "passed", "severity": "none", "findings": GREEN_FINDINGS, "duration_ms": 220},
        ],
        "approval": {"decision": None, "comment": None},
    },
    {
        "name": "report-exporter",
        "description": "Streamlit app that queries the analytics DB and exports PDF/CSV reports for managers",
        "detected_type": "python-streamlit",
        "risk_tier": "yellow",
        "risk_score": 63,
        "commit_sha": "e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9",
        "status": "awaiting_approval",
        "scan_results": [
            {"scanner_name": "secrets", "status": "passed", "severity": "none", "findings": GREEN_FINDINGS, "duration_ms": 510},
            {"scanner_name": "dependency", "status": "flagged", "severity": "high", "findings": {
                "vulnerabilities": [
                    {"package": "reportlab", "version": "3.6.12", "cve": "CVE-2023-33733", "severity": "high",
                     "description": "RCE via malicious color attribute in paragraphs"},
                ],
                "count": 1,
            }, "duration_ms": 2200},
            {"scanner_name": "egress", "status": "passed", "severity": "none", "findings": GREEN_FINDINGS, "duration_ms": 290},
            {"scanner_name": "pii", "status": "flagged", "severity": "medium", "findings": YELLOW_PII_FINDINGS, "duration_ms": 880},
        ],
        "approval": {"decision": None, "comment": None},
    },
    {
        "name": "customer-feedback-ui",
        "description": "React app for collecting NPS scores and open-ended feedback from enterprise customers",
        "detected_type": "nodejs",
        "risk_tier": "yellow",
        "risk_score": 51,
        "commit_sha": "f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2",
        "status": "awaiting_approval",
        "scan_results": [
            {"scanner_name": "secrets", "status": "passed", "severity": "none", "findings": GREEN_FINDINGS, "duration_ms": 390},
            {"scanner_name": "dependency", "status": "flagged", "severity": "medium", "findings": {
                "vulnerabilities": [
                    {"package": "axios", "version": "0.21.1", "cve": "CVE-2021-3749", "severity": "medium",
                     "description": "Inefficient Regular Expression Complexity (ReDoS)"},
                ],
                "count": 1,
            }, "duration_ms": 1540},
            {"scanner_name": "egress", "status": "flagged", "severity": "medium", "findings": YELLOW_EGRESS_FINDINGS, "duration_ms": 340},
            {"scanner_name": "pii", "status": "flagged", "severity": "low", "findings": {
                "matches": [{"file": "src/forms/ContactForm.tsx", "line": 28, "type": "email", "sample": "placeholder only"}],
                "count": 1,
            }, "duration_ms": 450},
        ],
        "approval": {"decision": None, "comment": None},
    },
    # ── REJECTED apps (show review notes to IC) ──────────────────────────────
    {
        "name": "invoice-processor",
        "description": "Reads PDF invoices from an S3 bucket, extracts line items with OCR, and posts to QuickBooks API",
        "detected_type": "python",
        "risk_tier": "red",
        "risk_score": 85,
        "commit_sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
        "status": "rejected",
        "scan_results": [
            {"scanner_name": "secrets", "status": "flagged", "severity": "critical", "findings": {
                "hits": [
                    {"file": "src/s3_client.py", "line": 6, "match": "AWS_SECRET_ACCESS_KEY='AKIA...'", "rule": "aws-access-token"},
                ],
                "count": 1,
            }, "duration_ms": 680},
            {"scanner_name": "dependency", "status": "flagged", "severity": "high", "findings": {
                "vulnerabilities": [
                    {"package": "pypdf2", "version": "2.10.0", "cve": "CVE-2023-36807", "severity": "high",
                     "description": "Infinite loop via crafted PDF object stream"},
                ],
                "count": 1,
            }, "duration_ms": 2100},
            {"scanner_name": "egress", "status": "passed", "severity": "none", "findings": GREEN_FINDINGS, "duration_ms": 410},
            {"scanner_name": "pii", "status": "flagged", "severity": "high", "findings": {
                "matches": [
                    {"file": "data/sample_invoice.pdf", "line": 0, "type": "credit_card", "sample": "redacted"},
                    {"file": "data/sample_invoice.pdf", "line": 0, "type": "tax_id", "sample": "redacted"},
                ],
                "count": 2,
            }, "duration_ms": 920},
        ],
        "approval": {
            "decision": "rejected",
            "comment": (
                "Blocked on two issues that must be resolved before re-submission:\n\n"
                "1. Hard-coded AWS credentials in src/s3_client.py line 6. "
                "Move these to environment variables and rotate the key immediately — it may already be compromised.\n\n"
                "2. Sample invoice files containing real PII (credit card numbers, tax IDs) are checked in to the repo. "
                "Remove data/sample_invoice.pdf, add *.pdf to .gitignore, and use synthetic test data only.\n\n"
                "Once resolved, open a new submission."
            ),
        },
    },
    {
        "name": "chatgpt-proxy",
        "description": "Thin FastAPI wrapper that forwards prompts to OpenAI and logs responses for auditing",
        "detected_type": "python-web",
        "risk_tier": "yellow",
        "risk_score": 67,
        "commit_sha": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1",
        "status": "rejected",
        "scan_results": [
            {"scanner_name": "secrets", "status": "flagged", "severity": "high", "findings": {
                "hits": [{"file": ".env.example", "line": 2, "match": "OPENAI_API_KEY=sk-real-key-here", "rule": "openai-api-key"}],
                "count": 1,
            }, "duration_ms": 590},
            {"scanner_name": "dependency", "status": "passed", "severity": "none", "findings": GREEN_FINDINGS, "duration_ms": 1430},
            {"scanner_name": "egress", "status": "flagged", "severity": "medium", "findings": {
                "unreviewed_hosts": [
                    {"host": "api.openai.com", "reason": "LLM API — all user prompts egress to OpenAI, DPA required"},
                ],
                "count": 1,
            }, "duration_ms": 350},
            {"scanner_name": "pii", "status": "passed", "severity": "none", "findings": GREEN_FINDINGS, "duration_ms": 270},
        ],
        "approval": {
            "decision": "rejected",
            "comment": (
                "Two items to address:\n\n"
                "1. .env.example contains what appears to be a real OpenAI API key (sk-real-key-here). "
                "Replace with a placeholder (e.g. sk-YOUR_KEY_HERE) and rotate the exposed key.\n\n"
                "2. A Data Processing Agreement (DPA) with OpenAI is required before user prompts "
                "can egress to api.openai.com. Please attach the signed DPA reference number "
                "in the app description and confirm with your legal team before re-submitting."
            ),
        },
    },
]


async def seed() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        created = 0
        for app_def in APPS:
            app_id = uuid.uuid4()
            short = app_id.hex[:8]

            # ── AppSubmission ─────────────────────────────────────────────────
            await session.execute(text("""
                INSERT INTO app_submissions
                    (id, submitter_id, name, description, repo_path, repo_url,
                     detected_type, status, risk_tier, commit_sha, created_at, updated_at)
                VALUES
                    (:id, :submitter_id, :name, :description, :repo_path, :repo_url,
                     :detected_type, :status, :risk_tier, :commit_sha, now(), now())
                ON CONFLICT DO NOTHING
            """), {
                "id": str(app_id),
                "submitter_id": str(IC_USER_ID),
                "name": app_def["name"],
                "description": app_def["description"],
                "repo_path": f"/tmp/seed-{short}",
                "repo_url": f"git://localhost/repos/seed-{short}.git",
                "detected_type": app_def["detected_type"],
                "status": app_def["status"],
                "risk_tier": app_def["risk_tier"],
                "commit_sha": app_def["commit_sha"],
            })
            await session.flush()

            # ── Scan ──────────────────────────────────────────────────────────
            scan_id = uuid.uuid4()
            scan_started = now - timedelta(hours=2)
            scan_completed = scan_started + timedelta(minutes=3)
            await session.execute(text("""
                INSERT INTO scans
                    (id, submission_id, commit_sha, status, risk_tier, risk_score,
                     started_at, completed_at, created_at)
                VALUES
                    (:id, :submission_id, :commit_sha, 'complete', :risk_tier, :risk_score,
                     :started_at, :completed_at, :created_at)
                ON CONFLICT DO NOTHING
            """), {
                "id": str(scan_id),
                "submission_id": str(app_id),
                "commit_sha": app_def["commit_sha"],
                "risk_tier": app_def["risk_tier"],
                "risk_score": app_def["risk_score"],
                "started_at": scan_started,
                "completed_at": scan_completed,
                "created_at": scan_started,
            })
            await session.flush()

            # ── ScanResults ───────────────────────────────────────────────────
            for sr in app_def["scan_results"]:
                await session.execute(text("""
                    INSERT INTO scan_results
                        (id, scan_id, scanner_name, status, severity, findings, duration_ms, created_at)
                    VALUES
                        (:id, :scan_id, :scanner_name, :status, :severity, CAST(:findings AS jsonb), :duration_ms, now())
                    ON CONFLICT DO NOTHING
                """), {
                    "id": str(uuid.uuid4()),
                    "scan_id": str(scan_id),
                    "scanner_name": sr["scanner_name"],
                    "status": sr["status"],
                    "severity": sr["severity"],
                    "findings": __import__("json").dumps(sr["findings"]),
                    "duration_ms": sr["duration_ms"],
                })
            await session.flush()

            # ── Approval ──────────────────────────────────────────────────────
            approval_def = app_def["approval"]
            approval_id = uuid.uuid4()
            sla_deadline = now + timedelta(hours=24)

            if approval_def["decision"] is None:
                # pending
                await session.execute(text("""
                    INSERT INTO approvals
                        (id, scan_id, approver_id, decision, comment, sla_deadline, decided_at, created_at)
                    VALUES
                        (:id, :scan_id, NULL, NULL, NULL, :sla_deadline, NULL, :created_at)
                    ON CONFLICT DO NOTHING
                """), {
                    "id": str(approval_id),
                    "scan_id": str(scan_id),
                    "sla_deadline": sla_deadline,
                    "created_at": scan_completed,
                })
            else:
                decided_at = now - timedelta(hours=1)
                await session.execute(text("""
                    INSERT INTO approvals
                        (id, scan_id, approver_id, decision, comment, sla_deadline, decided_at, created_at)
                    VALUES
                        (:id, :scan_id, :approver_id, :decision, :comment, :sla_deadline, :decided_at, :created_at)
                    ON CONFLICT DO NOTHING
                """), {
                    "id": str(approval_id),
                    "scan_id": str(scan_id),
                    "approver_id": str(APPROVER_ID),
                    "decision": approval_def["decision"],
                    "comment": approval_def["comment"],
                    "sla_deadline": sla_deadline,
                    "decided_at": decided_at,
                    "created_at": scan_completed,
                })

            await session.flush()
            created += 1
            print(f"  ✓ {app_def['name']} ({app_def['risk_tier'].upper()}, {app_def['status']})")

        await session.commit()
        print(f"\nSeeded {created} apps.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
