import ast
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from app.scanners.base import ScannerBase, ScanContext, ScanResult

_URL_RE = re.compile(r'https?://[^\s"\'<>\])\}]+')
_INTERNAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
_INTERNAL_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                      "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                      "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                      "172.30.", "172.31.", "192.168.")
_KNOWN_SAFE_HOSTS = {
    "api.anthropic.com", "api.openai.com", "api.cohere.ai",
    "api.stripe.com", "api.sendgrid.com", "hooks.slack.com",
    "graph.microsoft.com", "api.github.com",
}
_SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}


def _is_internal(host: str) -> bool:
    host = host.lower().split(":")[0]
    if host in _INTERNAL_HOSTS:
        return True
    return any(host.startswith(p) for p in _INTERNAL_PREFIXES)


def _extract_urls_from_file(path: Path) -> set[str]:
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return set()
    return set(_URL_RE.findall(text))


def _extract_python_ast_strings(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(errors="ignore"))
    except SyntaxError:
        return set()
    urls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for match in _URL_RE.findall(node.value):
                urls.add(match)
    return urls


class EgressScanner(ScannerBase):
    name = "egress"

    def run(self, repo_path: str, context: ScanContext) -> ScanResult:
        start = time.monotonic()
        root = Path(repo_path)

        all_urls: set[str] = set()
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.parts):
                continue  # skip .git, .venv, etc.
            all_urls |= _extract_urls_from_file(path)
            if path.suffix == ".py":
                all_urls |= _extract_python_ast_strings(path)

        external_urls = []
        for url in sorted(all_urls):
            try:
                host = urlparse(url).hostname or ""
            except ValueError:
                continue
            if host and not _is_internal(host):
                external_urls.append(url)

        # Update context for LLM scanner to read
        context.egress_urls = external_urls

        unknown = [u for u in external_urls if urlparse(u).hostname not in _KNOWN_SAFE_HOSTS]

        if not external_urls:
            score = 0
            severity = "none"
        elif not unknown:
            score = 10
            severity = "low"
        else:
            score = 20
            severity = "medium"

        return ScanResult(
            scanner_name=self.name,
            status="flagged" if external_urls else "passed",
            severity=severity,
            findings={
                "external_url_count": len(external_urls),
                "external_urls": external_urls,
                "unknown_urls": unknown,
                "internal_only": len(external_urls) == 0,
            },
            raw_output="\n".join(all_urls),
            duration_ms=int((time.monotonic() - start) * 1000),
            risk_score_contribution=score,
        )
