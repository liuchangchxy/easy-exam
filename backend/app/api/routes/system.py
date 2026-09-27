import os
from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    git_sha = os.environ.get("EASYEXAM_BUILD_SHA") or os.environ.get("GIT_COMMIT_SHA")
    if not git_sha:
        try:
            import subprocess
            res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=1.0)
            if res.returncode == 0:
                git_sha = res.stdout.strip()
        except Exception:
            pass
    return {
        "status": "ok",
        "app": "easy-exam",
        "version": "v1",
        "commit_sha": git_sha or "unknown",
        "instance_token": os.environ.get("INSTANCE_TOKEN", ""),
    }

