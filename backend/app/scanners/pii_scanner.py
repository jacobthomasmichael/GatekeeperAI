import re
import time
from pathlib import Path

from app.scanners.base import ScannerBase, ScanContext, ScanResult

_PATTERNS = {
    "SSN":         re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    "CREDIT_CARD": re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'),
    "EMAIL":       re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'),
    "PHONE_US":    re.compile(r'\b(?:\+1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b'),
    "DB_CONN_STR": re.compile(
        r'(?:postgresql|mysql|mongodb|redis|mssql)(?:\+\w+)?://[^:]+:[^@]+@[^\s"\']+',
        re.IGNORECASE,
    ),
}

_HIGH_SEVERITY = {"SSN", "CREDIT_CARD", "DB_CONN_STR"}
_SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".env", ".yml", ".yaml", ".json", ".toml", ".cfg", ".ini"}


class PiiScanner(ScannerBase):
    name = "pii"

    def run(self, repo_path: str, context: ScanContext) -> ScanResult:
        start = time.monotonic()
        root = Path(repo_path)

        detected: dict[str, list[str]] = {}

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.parts):
                continue
            if path.suffix not in _SOURCE_EXTENSIONS and path.suffix:
                continue
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue

            for category, pattern in _PATTERNS.items():
                if pattern.search(text):
                    detected.setdefault(category, []).append(str(path.relative_to(root)))

        categories_found = list(detected.keys())
        context.pii_categories = categories_found

        force_red = any(c in _HIGH_SEVERITY for c in categories_found)

        if not categories_found:
            severity, score = "none", 0
        elif force_red:
            severity, score = "high", 40
        else:
            severity, score = "low", 20

        return ScanResult(
            scanner_name=self.name,
            status="flagged" if categories_found else "passed",
            severity=severity,
            findings={"categories": categories_found, "files": detected},
            raw_output=str(detected),
            duration_ms=int((time.monotonic() - start) * 1000),
            risk_score_contribution=score,
            force_red=force_red,
        )
