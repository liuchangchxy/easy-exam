import uuid
from typing import List

from backend.app.infrastructure.db.connection import transaction


class BankRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def create(self, user_id: str, name: str, description: str = "", category: str = "默认分类") -> dict:
        bank_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            conn.execute(
                "INSERT INTO question_banks(id, name, description, category, created_by) VALUES (?, ?, ?, ?, ?)",
                (bank_id, name, description, category, user_id),
            )
            conn.execute(
                "INSERT INTO question_bank_members(bank_id, user_id, role) VALUES (?, ?, 'ADMIN')",
                (bank_id, user_id),
            )
        return self.get_for_user(bank_id, user_id)

    def get_for_user(self, bank_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                """SELECT b.id, b.name, b.description, b.category, b.created_by, m.role,
                          COUNT(i.question_id) AS question_count
                   FROM question_banks b
                   JOIN question_bank_members m ON m.bank_id = b.id AND m.user_id = ?
                   LEFT JOIN bank_question_items i ON i.bank_id = b.id
                   WHERE b.id = ? AND b.is_deleted = 0
                   GROUP BY b.id, m.role""",
                (user_id, bank_id),
            ).fetchone()
            return dict(row) if row else None

    def list_for_user(self, user_id: str) -> List[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT b.id, b.name, b.description, b.category, b.created_by, m.role,
                          COUNT(i.question_id) AS question_count
                   FROM question_banks b
                   JOIN question_bank_members m ON m.bank_id = b.id AND m.user_id = ?
                   LEFT JOIN bank_question_items i ON i.bank_id = b.id
                   WHERE b.is_deleted = 0
                   GROUP BY b.id, m.role ORDER BY b.created_at DESC""",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def add_member(self, bank_id: str, owner_id: str, username: str, role: str = "MEMBER") -> dict:
        if role not in {"MEMBER", "EDITOR"}:
            raise ValueError("role must be MEMBER or EDITOR")
        with transaction(self.db_path) as conn:
            owner = conn.execute("SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, owner_id)).fetchone()
            target = conn.execute("SELECT id FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
            if not owner or owner[0] != "ADMIN":
                raise PermissionError("only bank admin can add members")
            if not target:
                raise LookupError("user not found")
            conn.execute("INSERT INTO question_bank_members(bank_id, user_id, role) VALUES (?, ?, ?) ON CONFLICT(bank_id, user_id) DO UPDATE SET role = excluded.role", (bank_id, target[0], role))
            return {"bank_id": bank_id, "user_id": target[0], "username": username.strip().lower(), "role": role}

    def create_chapter(self, bank_id: str, user_id: str, name: str, parent_id: str | None = None) -> dict:
        chapter_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            if not conn.execute("SELECT 1 FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone():
                raise PermissionError("user cannot edit this bank")
            conn.execute("INSERT INTO chapters(id, bank_id, parent_id, name, sort_order) VALUES (?, ?, ?, ?, (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM chapters WHERE bank_id = ?))", (chapter_id, bank_id, parent_id, name, bank_id))
            return dict(conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone())

    def list_chapters(self, bank_id: str, user_id: str) -> list[dict]:
        with transaction(self.db_path) as conn:
            if not conn.execute("SELECT 1 FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone():
                return []
            return [dict(row) for row in conn.execute("SELECT * FROM chapters WHERE bank_id = ? ORDER BY sort_order", (bank_id,)).fetchall()]

    def create_tag(self, bank_id: str, user_id: str, name: str) -> dict:
        tag_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            if not conn.execute("SELECT 1 FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone():
                raise PermissionError("user cannot edit this bank")
            conn.execute("INSERT INTO knowledge_tags(id, bank_id, name) VALUES (?, ?, ?)", (tag_id, bank_id, name.strip()))
            return dict(conn.execute("SELECT * FROM knowledge_tags WHERE id = ?", (tag_id,)).fetchone())

    def list_tags(self, bank_id: str, user_id: str) -> list[dict]:
        with transaction(self.db_path) as conn:
            if not conn.execute("SELECT 1 FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone():
                return []
            return [dict(row) for row in conn.execute("SELECT * FROM knowledge_tags WHERE bank_id = ? ORDER BY name", (bank_id,)).fetchall()]
