import uuid
from typing import Optional

from backend.app.infrastructure.db.connection import transaction


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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

    @staticmethod
    def _as_user(row) -> dict:
        # SQLite stores these as 0/1; the API and the client both compare them
        # to true/false, so the boundary is the right place to make that real.
        data = dict(row)
        for flag in ("is_active", "must_change_password", "is_admin"):
            if flag in data:
                data[flag] = bool(data[flag])
        return data

    def get_by_username(self, username: str) -> Optional[dict]:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, is_active, created_at, "
                "COALESCE(must_change_password, 0) AS must_change_password, "
                "COALESCE(is_admin, 0) AS is_admin FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            return self._as_user(row) if row else None

    def get_by_id(self, user_id: str) -> Optional[dict]:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, is_active, created_at, "
                "COALESCE(must_change_password, 0) AS must_change_password, "
                "COALESCE(is_admin, 0) AS is_admin FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return self._as_user(row) if row else None

    def update_password(self, user_id: str, password_hash: str, must_change_password: int = 0) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, must_change_password = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (password_hash, must_change_password, user_id),
            )

    # ------------------------------------------------------------- admin views

    def count(self) -> int:
        with transaction(self.db_path) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def count_admins(self) -> int:
        with transaction(self.db_path) as conn:
            return int(
                conn.execute("SELECT COUNT(*) FROM users WHERE COALESCE(is_admin, 0) = 1").fetchone()[0]
            )

    def list_all(self) -> list[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT u.id, u.username,
                          COALESCE(u.is_admin, 0) AS is_admin,
                          COALESCE(u.is_active, 1) AS is_active,
                          COALESCE(u.must_change_password, 0) AS must_change_password,
                          u.created_at,
                          (SELECT COUNT(*) FROM question_bank_members m WHERE m.user_id = u.id) AS bank_count
                   FROM users u
                   ORDER BY u.created_at ASC, u.username ASC"""
            ).fetchall()
            return [dict(row) for row in rows]

    def search(self, prefix: str, exclude_user_id: str | None = None, limit: int = 10) -> list[dict]:
        clean = str(prefix or "").strip().lower()
        if not clean:
            return []
        pattern = f"{_escape_like(clean)}%"
        safe_limit = max(1, min(int(limit or 10), 10))
        sql = (
            "SELECT id, username FROM users WHERE lower(username) LIKE ? ESCAPE '\\'"
        )
        params: list = [pattern]
        if exclude_user_id:
            sql += " AND id <> ?"
            params.append(exclude_user_id)
        sql += " ORDER BY username ASC LIMIT ?"
        params.append(safe_limit)
        with transaction(self.db_path) as conn:
            return [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]

    def set_admin(self, user_id: str, is_admin: bool) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET is_admin = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (1 if is_admin else 0, user_id),
            )

    def set_active(self, user_id: str, is_active: bool) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                "UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (1 if is_active else 0, user_id),
            )

    def bootstrap_admin(self, preferred_username: str | None = None) -> Optional[str]:
        """Promote exactly one admin when none exists. Idempotent.

        Prefers EASYEXAM_ADMIN_USERNAME's target when that account exists, then
        falls back to the earliest-created account.
        """
        with transaction(self.db_path) as conn:
            if conn.execute("SELECT 1 FROM users WHERE COALESCE(is_admin, 0) = 1 LIMIT 1").fetchone():
                return None
            target = None
            preferred = str(preferred_username or "").strip().lower()
            if preferred:
                target = conn.execute("SELECT id FROM users WHERE username = ?", (preferred,)).fetchone()
            if not target:
                target = conn.execute(
                    "SELECT id FROM users ORDER BY created_at ASC, username ASC LIMIT 1"
                ).fetchone()
            if not target:
                return None
            conn.execute(
                "UPDATE users SET is_admin = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (target[0],),
            )
            return str(target[0])


class UserSessionRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def create(self, user_id: str, token_hash_value: str, expires: str, user_agent: str | None = None) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                "INSERT INTO user_sessions(id, user_id, token_hash, expires_at, user_agent, last_seen_at) "
                "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (str(uuid.uuid4()), user_id, token_hash_value, expires, user_agent),
            )

    def get_user_id_by_token(self, token_hash_value: str) -> Optional[str]:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT user_id FROM user_sessions WHERE token_hash = ? AND expires_at > CURRENT_TIMESTAMP",
                (token_hash_value,),
            ).fetchone()
            return str(row[0]) if row else None

    def touch(self, token_hash_value: str) -> None:
        with transaction(self.db_path) as conn:
            conn.execute(
                "UPDATE user_sessions SET last_seen_at = CURRENT_TIMESTAMP WHERE token_hash = ?",
                (token_hash_value,),
            )

    def list_for_user(self, user_id: str, current_token_hash: str | None = None) -> list[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT id, user_agent, created_at, last_seen_at, token_hash
                   FROM user_sessions
                   WHERE user_id = ? AND expires_at > CURRENT_TIMESTAMP
                   ORDER BY created_at DESC, id DESC""",
                (user_id,),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "user_agent": row["user_agent"],
                    "created_at": row["created_at"],
                    "last_seen_at": row["last_seen_at"],
                    "current": bool(current_token_hash) and row["token_hash"] == current_token_hash,
                }
                for row in rows
            ]

    def delete_for_user(self, user_id: str, keep_token_hash: str | None = None) -> int:
        with transaction(self.db_path) as conn:
            if keep_token_hash:
                cur = conn.execute(
                    "DELETE FROM user_sessions WHERE user_id = ? AND token_hash <> ?",
                    (user_id, keep_token_hash),
                )
            else:
                cur = conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
            return int(cur.rowcount or 0)

    def delete(self, token_hash_value: str) -> None:
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash_value,))
