from backend.app.infrastructure.security.password import hash_password, verify_password
from backend.app.infrastructure.security.sessions import expires_at, new_token, token_hash


class AuthService:
    def __init__(self, users, sessions):
        self.users = users
        self.sessions = sessions

    def register(self, username: str, password: str) -> dict:
        normalized = username.strip().lower()
        if not normalized:
            raise ValueError("username is required")
        if self.users.get_by_username(normalized):
            raise ValueError("username already exists")
        return self.users.create(normalized, hash_password(password))

    def login(self, username: str, password: str) -> tuple[dict, str]:
        user = self.users.get_by_username(username.strip().lower())
        if not user or not user.get("is_active") or not verify_password(password, user["password_hash"]):
            raise ValueError("invalid username or password")
        token = new_token()
        self.sessions.create(user["id"], token_hash(token), expires_at())
        user_info = self.users.get_by_id(user["id"])
        user_info.pop("password_hash", None)
        user_info["must_change_password"] = bool(user.get("must_change_password"))
        return user_info, token

    def change_password(self, user_id: str, old_password: str, new_password: str) -> None:
        user = self.users.get_by_id(user_id)
        if not user or not verify_password(old_password, user["password_hash"]):
            raise ValueError("旧密码错误")
        if len(new_password) < 8:
            raise ValueError("新密码长度至少为 8 位")
        self.users.update_password(user_id, hash_password(new_password), must_change_password=0)
