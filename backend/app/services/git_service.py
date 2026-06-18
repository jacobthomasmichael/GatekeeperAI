import os
import shutil
import subprocess
from pathlib import Path

from app.config import settings

_HOOK_TEMPLATE = """\
#!/bin/bash
# GatekeeperAI post-receive hook — do not edit manually
PLATFORM_API="{callback_url}"
APP_ID="{app_id}"
HOOK_SECRET="{hook_secret}"

while read old_sha new_sha refname; do
    if [ "$refname" = "refs/heads/main" ]; then
        curl -sf -X POST \\
            "$PLATFORM_API/api/v1/scans/trigger/$APP_ID" \\
            -H "Content-Type: application/json" \\
            -H "X-Hook-Secret: $HOOK_SECRET" \\
            -d "{{\\\"commit_sha\\\": \\\"$new_sha\\\"}}" || true
        echo "GatekeeperAI: scan queued for commit $new_sha"
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
    hook_path.write_text(_HOOK_TEMPLATE.format(
        callback_url=settings.HOOK_CALLBACK_URL,
        app_id=app_id,
        hook_secret=settings.HOOK_SECRET,
    ))
    hook_path.chmod(0o755)

    repo_url = f"file://{repo_dir}"
    return str(repo_dir), repo_url


def push_zip_to_repo(repo_path: str, zip_bytes: bytes) -> str:
    """Extract zip_bytes into a new commit on the bare repo's main branch.

    Uses git-fetch (not git-push) so the post-receive hook does not fire —
    the caller is responsible for queuing the scan.  Returns the commit SHA.
    """
    import io
    import zipfile
    import tempfile

    _MAX_ZIP = 50 * 1024 * 1024        # 50 MB compressed
    _MAX_EXTRACT = 200 * 1024 * 1024   # 200 MB uncompressed

    if len(zip_bytes) > _MAX_ZIP:
        raise ValueError("ZIP file exceeds 50 MB")

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        work.mkdir()

        # Throwaway working repo
        subprocess.run(["git", "init", str(work)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(work), "symbolic-ref", "HEAD", "refs/heads/main"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(work), "config", "user.email", "upload@gatekeeperai"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(work), "config", "user.name", "GatekeeperAI"], check=True, capture_output=True)

        # Extract with security checks
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            if sum(i.file_size for i in zf.infolist()) > _MAX_EXTRACT:
                raise ValueError("ZIP content exceeds 200 MB limit")
            entries = zf.infolist()
            for info in entries:
                if info.filename.startswith("/") or ".." in info.filename:
                    raise ValueError(f"Unsafe path in ZIP: {info.filename!r}")
            has_files = any(not info.is_dir() for info in entries)
            if not has_files:
                raise ValueError("ZIP contains no files")
            zf.extractall(str(work))

        # Commit — if content is identical to the last upload, skip and return
        # the existing HEAD SHA rather than failing with "nothing to commit".
        subprocess.run(["git", "-C", str(work), "add", "-A"], check=True, capture_output=True)
        result = subprocess.run(
            ["git", "-C", str(work), "commit", "-m", "Upload via GatekeeperAI web interface"],
            capture_output=True,
        )
        if result.returncode != 0:
            # "nothing to commit" — content is unchanged; return the current HEAD
            existing = subprocess.run(
                ["git", "--git-dir", repo_path, "rev-parse", "refs/heads/main"],
                capture_output=True, text=True,
            )
            if existing.returncode == 0:
                return existing.stdout.strip()
            raise ValueError("ZIP content produced no changes and no prior version exists")

        sha = subprocess.run(
            ["git", "-C", str(work), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()

        # Fetch objects into bare repo — does NOT fire post-receive.
        # Force (+) to allow non-fast-forward updates (each upload is an orphan commit).
        subprocess.run(
            ["git", "--git-dir", repo_path, "fetch", str(work), "+main:refs/heads/main"],
            check=True, capture_output=True,
        )

        return sha


def delete_bare_repo(repo_path: str) -> None:
    path = Path(repo_path)
    if path.exists():
        shutil.rmtree(path)
