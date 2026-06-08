from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScanContext:
    scan_id: str
    submission_id: str
    app_name: str
    app_description: str
    commit_sha: str
    detected_type: Optional[str] = None
    # Populated by earlier scanners, read by later ones
    egress_urls: list[str] = field(default_factory=list)
    pii_categories: list[str] = field(default_factory=list)


@dataclass
class ScanResult:
    scanner_name: str
    status: str              # passed | flagged | error
    severity: str            # none | low | medium | high | critical
    findings: dict
    raw_output: str
    duration_ms: int
    risk_score_contribution: int
    force_red: bool = False  # hard-override: forces Red tier regardless of total score


class ScannerBase(ABC):
    name: str

    @abstractmethod
    def run(self, repo_path: str, context: ScanContext) -> ScanResult:
        """Run the scanner against a working-tree directory."""
        ...
