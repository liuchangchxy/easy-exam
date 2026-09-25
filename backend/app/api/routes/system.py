import os
from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "app": "easy-exam",
        "version": "v1",
        "instance_token": os.environ.get("INSTANCE_TOKEN", ""),
    }

