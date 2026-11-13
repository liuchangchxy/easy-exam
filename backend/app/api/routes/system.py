import hashlib
import os
from fastapi import APIRouter

router = APIRouter(tags=["system"])


def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16] if token else ""


@router.get("/health")
def health():
    git_sha = os.environ.get("EASYEXAM_BUILD_SHA") or os.environ.get("GIT_COMMIT_SHA")
    if not git_sha:
        try:
            import subprocess
            res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1.0)
            if res.returncode == 0:
                git_sha = res.stdout.strip()
        except Exception:
            pass
    return {
        "status": "ok",
        "app": "easy-exam",
        "version": "v1",
        "commit_sha": git_sha or "unknown",
        # The instance token identifies a deployment to its own tooling; it is
        # not a credential but it is still not something an unauthenticated
        # caller should be handed. A stable fingerprint answers "which instance
        # am I talking to" without publishing the value.
        "instance_fingerprint": _fingerprint(os.environ.get("INSTANCE_TOKEN", "")),
    }

