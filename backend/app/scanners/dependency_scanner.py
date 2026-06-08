import json
import subprocess
import sys
import time
from pathlib import Path

from app.scanners.base import ScannerBase, ScanContext, ScanResult

_PIP_AUDIT = str(Path(sys.executable).parent / "pip-audit")

_SEVERITY_SCORE = {"critical": 40, "high": 20, "medium": 10, "low": 2}
_SEVERITY_CAPS = {"critical": 40, "high": 35, "medium": 20, "low": 5}


def _cvss_to_severity(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    return "low"


class DependencyScanner(ScannerBase):
    name = "dependency"

    def run(self, repo_path: str, context: ScanContext) -> ScanResult:
        start = time.monotonic()
        root = Path(repo_path)

        # Detect project type and audit accordingly
        if (root / "requirements.txt").exists():
            return self._audit_python(root / "requirements.txt", start)
        if (root / "pyproject.toml").exists():
            return self._audit_python(None, start, cwd=str(root))
        if (root / "package-lock.json").exists():
            return self._audit_node(root, start)

        return ScanResult(
            scanner_name=self.name,
            status="passed",
            severity="none",
            findings={"note": "No supported dependency file found"},
            raw_output="",
            duration_ms=int((time.monotonic() - start) * 1000),
            risk_score_contribution=0,
        )

    def _audit_python(self, req_file: Path | None, start: float, cwd: str | None = None) -> ScanResult:
        cmd = [_PIP_AUDIT, "--format", "json"]
        if req_file:
            cmd += ["-r", str(req_file)]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=cwd,
            )
            raw = proc.stdout or "[]"
            # pip-audit outputs a list of vulnerability objects
            data = json.loads(raw) if raw.strip() else []
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            return self._error_result(str(e), start)

        return self._parse_pip_audit(data, raw, start)

    def _audit_node(self, root: Path, start: float) -> ScanResult:
        try:
            proc = subprocess.run(
                ["npm", "audit", "--json"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(root),
            )
            raw = proc.stdout or "{}"
            data = json.loads(raw)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            return self._error_result(str(e), start)

        return self._parse_npm_audit(data, raw, start)

    def _parse_pip_audit(self, data: dict | list, raw: str, start: float) -> ScanResult:
        # pip-audit >= 2.0 returns {"dependencies": [...], "fixes": [...]}
        deps = data.get("dependencies", []) if isinstance(data, dict) else data
        items = []
        worst_severity = "none"
        total_score = 0

        for dep in deps:
            for vuln in dep.get("vulns", []):
                # No CVSS score in this format; default to "high" for any finding
                severity = "high"
                items.append({
                    "package": dep.get("name"),
                    "version": dep.get("version"),
                    "id": vuln.get("id"),
                    "aliases": vuln.get("aliases", []),
                    "severity": severity,
                    "fix_versions": vuln.get("fix_versions", []),
                })
                if _SEVERITY_SCORE.get(severity, 0) > _SEVERITY_SCORE.get(worst_severity, 0):
                    worst_severity = severity
                total_score = min(total_score + _SEVERITY_SCORE.get(severity, 0), _SEVERITY_CAPS.get(severity, 20))

        return ScanResult(
            scanner_name=self.name,
            status="flagged" if items else "passed",
            severity=worst_severity if items else "none",
            findings={"count": len(items), "items": items},
            raw_output=raw,
            duration_ms=int((time.monotonic() - start) * 1000),
            risk_score_contribution=total_score,
            force_red=worst_severity == "critical",
        )

    def _parse_npm_audit(self, data: dict, raw: str, start: float) -> ScanResult:
        items = []
        worst_severity = "none"
        total_score = 0

        for name, vuln in data.get("vulnerabilities", {}).items():
            severity = vuln.get("severity", "low")
            items.append({
                "package": name,
                "severity": severity,
                "via": [v if isinstance(v, str) else v.get("title", "") for v in vuln.get("via", [])],
            })
            if _SEVERITY_SCORE.get(severity, 0) > _SEVERITY_SCORE.get(worst_severity, 0):
                worst_severity = severity
            total_score = min(total_score + _SEVERITY_SCORE.get(severity, 0), _SEVERITY_CAPS.get(severity, 20))

        return ScanResult(
            scanner_name=self.name,
            status="flagged" if items else "passed",
            severity=worst_severity if items else "none",
            findings={"count": len(items), "items": items},
            raw_output=raw,
            duration_ms=int((time.monotonic() - start) * 1000),
            risk_score_contribution=total_score,
            force_red=worst_severity == "critical",
        )

    def _error_result(self, error: str, start: float) -> ScanResult:
        return ScanResult(
            scanner_name=self.name,
            status="error",
            severity="none",
            findings={"error": error},
            raw_output=error,
            duration_ms=int((time.monotonic() - start) * 1000),
            risk_score_contribution=0,
        )
