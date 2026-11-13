from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from backend.app.application.auth_service import RegistrationDisabledError
from backend.app.dependencies import current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)


def _current_token_hash(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        token = header.split(" ", 1)[1].strip()
        return request.app.state.services.token_hash(token)
    return None


@router.post("/register", status_code=201)
def register(payload: Credentials, request: Request):
    try:
        return request.app.state.services.auth.register(payload.username, payload.password)
    except RegistrationDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/login")
def login(payload: Credentials, request: Request):
    try:
        user, token = request.app.state.services.auth.login(
            payload.username, payload.password, user_agent=request.headers.get("User-Agent")
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"token": token, "user": user}


@router.post("/logout", status_code=204)
def logout(request: Request, authorization: str | None = None):
    # Header extraction is intentionally explicit to keep token handling in this route.
    token_header = request.headers.get("Authorization", "")
    if token_header.lower().startswith("bearer "):
        request.app.state.services.user_sessions.delete(request.app.state.services.token_hash(token_header.split(" ", 1)[1].strip()))
    return Response(status_code=204)


@router.get("/me")
def me(user=Depends(current_user)):
    user_data = dict(user)
    user_data.pop("password_hash", None)
    return user_data


class ChangePasswordPayload(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=256)



@router.post("/change-password")
def change_password(payload: ChangePasswordPayload, request: Request, user=Depends(current_user)):
    try:
        request.app.state.services.auth.change_password(
            user["id"],
            payload.old_password,
            payload.new_password,
            current_token_hash=_current_token_hash(request),
        )
        return {"status": "success", "message": "密码修改成功"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions")
def list_sessions(request: Request, user=Depends(current_user)):
    return request.app.state.services.user_sessions.list_for_user(
        user["id"], current_token_hash=_current_token_hash(request)
    )


@router.delete("/sessions")
def revoke_other_sessions(request: Request, user=Depends(current_user)):
    revoked = request.app.state.services.user_sessions.delete_for_user(
        user["id"], keep_token_hash=_current_token_hash(request)
    )
    return {"revoked": revoked}
