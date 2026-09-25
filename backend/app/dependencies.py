from fastapi import Depends, Header, HTTPException, Request


def get_services(request: Request):
    return request.app.state.services


def current_user(authorization: str | None = Header(default=None), request: Request = None):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="authentication required")
    token = authorization.split(" ", 1)[1].strip()
    services = request.app.state.services
    user_id = services.user_sessions.get_user_id_by_token(services.token_hash(token))
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    user = services.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    if user.get("must_change_password"):
        path = request.url.path if request else ""
        allowed_paths = {"/api/v1/auth/me", "/api/v1/auth/change-password", "/api/v1/auth/logout"}
        if path not in allowed_paths:
            raise HTTPException(status_code=403, detail="MUST_CHANGE_PASSWORD")
    return user

