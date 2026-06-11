import os
import shutil
import subprocess
from pathlib import Path

from app.config import settings

_HOOK_TEMPLATE = """\
#!/bin/bash
# GatekeeperAI post-receive hook — do not edit manually
PLATFORM_API="${{GATEKEEPER_API_URL:-http://localhost:8000}}"
APP_ID="{app_id}"
HOOK_SECRET="{hook_secret}"

while read old_sha new_sha refname; do
    if [ "$refname" = "refs/heads/main" ]; then
        curl -sf -X POST \\
            "${{PLATFORM_API}}/api/v1/scans/trigger/${{APP_ID}}" \\
            -H "Content-Type: application/json" \\
            -H "X-Hook-Secret: ${{HOOK_SECRET}}" \\
            -d "{{\\\"commit_sha\\\": \\\"${{new_sha}}\\\"}}" || true
        echo "GatekeeperAI: scan queued for commit ${{new_sha}}"
    fi
done
"""


def create_bare_repo(app_name: str, app_id: str) -> tuple[str, str]:
    """Initialise a bare git repo and install the post-receive hook.

    Returns (repo_path, repo_url).
    """
    base = Path(settings.GIT_REPOS_BASE_PATH)
    base.mkdir(parents=True, exist_ok=True)

    short_id = str(app_id)[:8]
    repo_dir = base / f"{app_name}-{short_id}.git"

    subprocess.run(
        ["git", "init", "--bare", str(repo_dir)],
        check=True,
        capture_output=True,
    )

    hook_path = repo_dir / "hooks" / "post-receive"
    hook_path.write_text(_HOOK_TEMPLATE.format(app_id=app_id, hook_secret=settings.HOOK_SECRET))
    hook_path.chmod(0o755)

    repo_url = f"file://{repo_dir}"
    return str(repo_dir), repo_url


def delete_bare_repo(repo_path: str) -> None:
    path = Path(repo_path)
    if path.exists():
        shutil.rmtree(path)
