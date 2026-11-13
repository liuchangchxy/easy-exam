from fastapi import Depends, Header, HTTPException, Request


def get_services(request: Request):
    return request.app.state.services


def current_user(authorization: str | None = Header(default=None), request: Request = None):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="authentication required")
    token = authorization.split(" ", 1)[1].strip()
    services = request.app.state.services
    token_hash_value = services.token_hash(token)
    user_id = services.user_sessions.get_user_id_by_token(token_hash_value)
    if not user_id:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    user = services.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    # Disabling an account must end its access now, not when the 30-day token
    # finally expires. The session row is already gone when an admin disables
    # somebody, but a token minted before that check still lands here.
    if not user.get("is_active"):
        raise HTTPException(status_code=401, detail="account is disabled")
    if user.get("must_change_password"):
        path = request.url.path if request else ""
        allowed_paths = {"/api/v1/auth/me", "/api/v1/auth/change-password", "/api/v1/auth/logout"}
        if path not in allowed_paths:
            raise HTTPException(status_code=403, detail="MUST_CHANGE_PASSWORD")
    services.user_sessions.touch(token_hash_value)
    return user


def require_admin(user=Depends(current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="admin required")
    return user

