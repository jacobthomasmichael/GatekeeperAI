import json
import time
from pathlib import Path

from app.scanners.base import ScannerBase, ScanContext, ScanResult

_SYSTEM_PROMPT = """You are a security analyst reviewing source code submitted to an enterprise app runtime platform.
Analyse the provided application code and return ONLY a valid JSON object with these fields:
- "description": plain-English summary of what the app does (2-4 sentences, non-technical, for a CISO audience)
- "capabilities": array of strings from this exact set: ["reads_database","writes_database","calls_external_api","handles_pii","handles_payments","runs_code","scrapes_web","sends_email","accesses_filesystem"]
- "intent_match": boolean — does the code's actual behaviour match the submitter's stated description?
- "discrepancy_notes": if intent_match is false, describe what differs; otherwise empty string
- "risk_flags": array of specific security concerns not already caught by automated scanners (empty array if none)

Respond with raw JSON only. No markdown fences, no explanation."""

_KEY_FILES = ["main.py", "app.py", "index.js", "index.ts", "server.js", "server.ts",
              "app.ts", "src/main.py", "src/app.py", "src/index.js", "src/index.ts"]
_MAX_FILE_CHARS = 3000
_MAX_TOTAL_CHARS = 12000


def _collect_code_summary(repo_path: str) -> str:
    root = Path(repo_path)
    sections: list[str] = []
    total = 0

    # Priority: known entrypoint files first
    for name in _KEY_FILES:
        p = root / name
        if p.exists():
            content = p.read_text(errors="ignore")[:_MAX_FILE_CHARS]
            sections.append(f"### {name}\n{content}")
            total += len(content)
            if total >= _MAX_TOTAL_CHARS:
                break

    # Fill remaining budget with other source files
    if total < _MAX_TOTAL_CHARS:
        for p in sorted(root.rglob("*.py")) + sorted(root.rglob("*.js")) + sorted(root.rglob("*.ts")):
            if any(part.startswith(".") or part in ("node_modules", "__pycache__", ".venv") for part in p.parts):
                continue
            if str(p.name) in _KEY_FILES:
                continue
            content = p.read_text(errors="ignore")[:_MAX_FILE_CHARS]
            sections.append(f"### {p.relative_to(root)}\n{content}")
            total += len(content)
            if total >= _MAX_TOTAL_CHARS:
                break

    return "\n\n".join(sections) if sections else "(no source files found)"


class LLMScanner(ScannerBase):
    name = "llm"

    def run(self, repo_path: str, context: ScanContext) -> ScanResult:
        start = time.monotonic()

        try:
            import anthropic
            from app.config import settings

            if settings.ANTHROPIC_API_KEY.startswith("sk-ant-placeholder"):
                return self._placeholder_result(start)

            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            code_summary = _collect_code_summary(repo_path)

            user_content = (
                f"App name: {context.app_name}\n"
                f"Submitter description: {context.app_description}\n"
                f"External URLs detected: {', '.join(context.egress_urls) or 'none'}\n"
                f"PII categories detected: {', '.join(context.pii_categories) or 'none'}\n\n"
                f"Source code:\n{code_summary}"
            )

            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=[{
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": code_summary,
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": (
                                f"App name: {context.app_name}\n"
                                f"Submitter description: {context.app_description}\n"
                                f"External URLs detected: {', '.join(context.egress_urls) or 'none'}\n"
                                f"PII categories detected: {', '.join(context.pii_categories) or 'none'}"
                            ),
                        },
                    ],
                }],
            )

            raw = response.content[0].text
            parsed = json.loads(raw)

        except ImportError:
            return self._error_result("anthropic package not installed", start)
        except json.JSONDecodeError as e:
            return self._error_result(f"LLM returned non-JSON: {e}", start)
        except Exception as e:
            return self._error_result(str(e), start)

        score = 0
        if not parsed.get("intent_match", True):
            score += 25
        score += min(len(parsed.get("risk_flags", [])) * 10, 20)
        high_risk_caps = {"handles_payments", "runs_code", "handles_pii"}
        for cap in parsed.get("capabilities", []):
            if cap in high_risk_caps:
                score += 10

        return ScanResult(
            scanner_name=self.name,
            status="flagged" if score > 0 else "passed",
            severity="medium" if score >= 25 else ("low" if score > 0 else "none"),
            findings=parsed,
            raw_output=raw if "raw" in dir() else "",
            duration_ms=int((time.monotonic() - start) * 1000),
            risk_score_contribution=score,
        )

    def _placeholder_result(self, start: float) -> ScanResult:
        return ScanResult(
            scanner_name=self.name,
            status="passed",
            severity="none",
            findings={
                "description": "LLM analysis skipped — set ANTHROPIC_API_KEY in .env to enable.",
                "capabilities": [],
                "intent_match": True,
                "discrepancy_notes": "",
                "risk_flags": [],
            },
            raw_output="",
            duration_ms=int((time.monotonic() - start) * 1000),
            risk_score_contribution=0,
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
