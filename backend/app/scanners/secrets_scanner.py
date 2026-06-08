import json
import subprocess
import sys
import time
from pathlib import Path

from app.scanners.base import ScannerBase, ScanContext, ScanResult

_DETECT_SECRETS = str(Path(sys.executable).parent / "detect-secrets")

_CRITICAL_TYPES = {
    "AWS Access Key",
    "Private Key",
    "Stripe Access Key",
    "Slack Token",
    "GitHub Token",
    "SendGrid API Key",
    "Twilio API Key",
}


class SecretsScanner(ScannerBase):
    name = "secrets"

    def run(self, repo_path: str, context: ScanContext) -> ScanResult:
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [_DETECT_SECRETS, "scan", "--all-files", repo_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            raw = proc.stdout or "{}"
            data = json.loads(raw)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            return ScanResult(
                scanner_name=self.name,
                status="error",
                severity="none",
                findings={"error": str(e)},
                raw_output=str(e),
                duration_ms=int((time.monotonic() - start) * 1000),
                risk_score_contribution=0,
            )

        items = []
        for file_path, secrets in data.get("results", {}).items():
            for secret in secrets:
                items.append({
                    "type": secret.get("type", "Unknown"),
                    "file": file_path,
                    "line": secret.get("line_number"),
                    "is_verified": secret.get("is_verified", False),
                })

        has_critical = any(item["type"] in _CRITICAL_TYPES for item in items)
        count = len(items)

        if count == 0:
            severity, score, force_red = "none", 0, False
        elif has_critical:
            severity, score, force_red = "critical", 50, True
        else:
            severity = "high"
            score = min(25 * count, 40)
            force_red = False

        return ScanResult(
            scanner_name=self.name,
            status="flagged" if count > 0 else "passed",
            severity=severity,
            findings={"count": count, "items": items},
            raw_output=raw,
            duration_ms=int((time.monotonic() - start) * 1000),
            risk_score_contribution=score,
            force_red=force_red,
        )
