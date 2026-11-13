from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
import secrets

from backend.app.dependencies import require_admin
from backend.app.infrastructure.db.repositories.instance_settings_repository import ALLOW_REGISTRATION_KEY
from backend.app.infrastructure.security.password import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])

TEMP_PASSWORD_BYTES = 12


class UserPatchPayload(BaseModel):
    is_admin: bool | None = None
    is_active: bool | None = None


class InstanceSettingsPayload(BaseModel):
    allow_registration: bool


def _public_user(row: dict) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "is_admin": bool(row.get("is_admin")),
        "is_active": bool(row.get("is_active", 1)),
        "must_change_password": bool(row.get("must_change_password")),
        "created_at": row.get("created_at"),
        "bank_count": int(row.get("bank_count", 0) or 0),
    }


def _find_user_row(request: Request, user_id: str) -> dict | None:
    for row in request.app.state.services.users.list_all():
        if row["id"] == user_id:
            return row
    return None


@router.get("/users")
def list_users(request: Request, admin=Depends(require_admin)):
    return [_public_user(row) for row in request.app.state.services.users.list_all()]


@router.patch("/users/{user_id}")
def patch_user(
    user_id: str,
    payload: UserPatchPayload,
    request: Request,
    admin=Depends(require_admin),
):
    users = request.app.state.services.users
    target = users.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")

    changes = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    if "is_admin" in changes and changes["is_admin"] is False:
        if user_id == admin["id"]:
            raise HTTPException(status_code=400, detail="cannot demote yourself")
        if target.get("is_admin") and users.count_admins() <= 1:
            raise HTTPException(status_code=400, detail="cannot demote the last admin")
    if "is_active" in changes and changes["is_active"] is False:
        if user_id == admin["id"]:
            raise HTTPException(status_code=400, detail="cannot disable yourself")
        if target.get("is_admin") and users.count_admins() <= 1:
            raise HTTPException(status_code=400, detail="cannot disable the last admin")

    if "is_admin" in changes:
        users.set_admin(user_id, bool(changes["is_admin"]))
    if "is_active" in changes:
        users.set_active(user_id, bool(changes["is_active"]))
        if not changes["is_active"]:
            # A disabled account keeps no way back in: every device is signed out
            # immediately rather than waiting for a token to expire.
            request.app.state.services.user_sessions.delete_for_user(user_id)

    updated = _find_user_row(request, user_id)
    return _public_user(updated or users.get_by_id(user_id))


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: str, request: Request, admin=Depends(require_admin)):
    users = request.app.state.services.users
    target = users.get_by_id(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")

    temporary_password = secrets.token_urlsafe(TEMP_PASSWORD_BYTES)
    users.update_password(user_id, hash_password(temporary_password), must_change_password=1)
    request.app.state.services.user_sessions.delete_for_user(user_id)
    updated = _find_user_row(request, user_id)
    return {
        "temporary_password": temporary_password,
        "user": _public_user(updated or users.get_by_id(user_id)),
    }


@router.get("/settings")
def get_settings(request: Request, admin=Depends(require_admin)):
    return {"allow_registration": request.app.state.services.instance_settings.allow_registration()}


@router.put("/settings")
def update_settings(payload: InstanceSettingsPayload, request: Request, admin=Depends(require_admin)):
    request.app.state.services.instance_settings.set(
        ALLOW_REGISTRATION_KEY, "true" if payload.allow_registration else "false"
    )
    return {"allow_registration": payload.allow_registration}
