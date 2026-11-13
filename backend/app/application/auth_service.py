from backend.app.infrastructure.security.password import hash_password, verify_password
from backend.app.infrastructure.security.sessions import expires_at, new_token, token_hash


class RegistrationDisabledError(ValueError):
    """Raised when instance registration is closed for non-first users."""


class AuthService:
    def __init__(self, users, sessions, settings=None):
        self.users = users
        self.sessions = sessions
        self.settings = settings

    def register(self, username: str, password: str) -> dict:
        normalized = username.strip().lower()
        if not normalized:
            raise ValueError("username is required")
        if self.users.get_by_username(normalized):
            raise ValueError("username already exists")
        is_first_user = self.users.count() == 0
        if not is_first_user and self.settings is not None and not self.settings.allow_registration():
            raise RegistrationDisabledError("registration is disabled")
        created = self.users.create(normalized, hash_password(password))
        if is_first_user:
            # A fresh instance must always have exactly one administrator.
            self.users.set_admin(created["id"], True)
            created = self.users.get_by_id(created["id"])
        created.pop("password_hash", None)
        return created

    def login(self, username: str, password: str, user_agent: str | None = None) -> tuple[dict, str]:
        user = self.users.get_by_username(username.strip().lower())
        if not user or not user.get("is_active") or not verify_password(password, user["password_hash"]):
            raise ValueError("invalid username or password")
        token = new_token()
        self.sessions.create(user["id"], token_hash(token), expires_at(), user_agent=user_agent)
        user_info = self.users.get_by_id(user["id"])
        user_info.pop("password_hash", None)
        user_info["must_change_password"] = bool(user.get("must_change_password"))
        return user_info, token

    def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str,
        current_token_hash: str | None = None,
    ) -> None:
        user = self.users.get_by_id(user_id)
        if not user or not verify_password(old_password, user["password_hash"]):
            raise ValueError("旧密码错误")
        if len(new_password) < 8:
            raise ValueError("新密码长度至少为 8 位")
        self.users.update_password(user_id, hash_password(new_password), must_change_password=0)
        # Revoke every other device; the caller's session stays signed in.
        self.sessions.delete_for_user(user_id, keep_token_hash=current_token_hash)
