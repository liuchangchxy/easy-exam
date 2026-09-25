import uuid
from typing import Optional

from backend.app.infrastructure.db.connection import transaction


class UserRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def create(self, username: str, password_hash: str) -> dict:
        user_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            conn.execute(
                "INSERT INTO users(id, username, password_hash) VALUES (?, ?, ?)",
                (user_id, username, password_hash),
            )
        return self.get_by_id(user_id)

    def get_by_username(self, username: str) -> Optional[dict]:
        with transaction(self.db_path) as conn:
            row = conn.execute("SELECT id, username, password_hash, is_active, created_at, COALESCE(must_change_password, 0) AS must_change_password FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row else None

    def get_by_id(self, user_id: str) -> Optional[dict]:
        with transaction(self.db_path) as conn:
            row = conn.execute("SELECT id, username, password_hash, is_active, created_at, COALESCE(must_change_password, 0) AS must_change_password FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def update_password(self, user_id: str, password_hash: str, must_change_password: int = 0) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, must_change_password = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (password_hash, must_change_password, user_id),
            )


class UserSessionRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def create(self, user_id: str, token_hash_value: str, expires: str) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                "INSERT INTO user_sessions(id, user_id, token_hash, expires_at) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, token_hash_value, expires),
            )

    def get_user_id_by_token(self, token_hash_value: str) -> Optional[str]:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT user_id FROM user_sessions WHERE token_hash = ? AND expires_at > CURRENT_TIMESTAMP",
                (token_hash_value,),
            ).fetchone()
            return str(row[0]) if row else None

    def delete(self, token_hash_value: str) -> None:
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash_value,))
