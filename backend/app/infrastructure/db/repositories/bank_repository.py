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

    def list_members(self, bank_id: str, user_id: str) -> list[dict]:
        with transaction(self.db_path) as conn:
            if not conn.execute("SELECT 1 FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone():
                raise PermissionError("access denied")
            rows = conn.execute(
                """SELECT m.bank_id, m.user_id, u.username, m.role
                   FROM question_bank_members m
                   JOIN users u ON u.id = m.user_id
                   WHERE m.bank_id = ? ORDER BY m.role ASC""",
                (bank_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def remove_member(self, bank_id: str, owner_id: str, target_user_id: str) -> bool:
        with transaction(self.db_path) as conn:
            owner = conn.execute("SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, owner_id)).fetchone()
            if not owner or owner[0] != "ADMIN":
                raise PermissionError("only bank admin can remove members")
            if owner_id == target_user_id:
                raise ValueError("cannot remove owner/self")
            res = conn.execute("DELETE FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, target_user_id))
            return res.rowcount > 0

    def create_chapter(self, bank_id: str, user_id: str, name: str, parent_id: str | None = None) -> dict:
        chapter_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            member = conn.execute("SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone()
            if not member or member[0] not in ("ADMIN", "EDITOR"):
                raise PermissionError("user cannot edit this bank")
            if parent_id:
                p_row = conn.execute("SELECT 1 FROM chapters WHERE id = ? AND bank_id = ?", (parent_id, bank_id)).fetchone()
                if not p_row:
                    raise ValueError("parent chapter not found in this bank")
            conn.execute("INSERT INTO chapters(id, bank_id, parent_id, name, sort_order) VALUES (?, ?, ?, ?, (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM chapters WHERE bank_id = ?))", (chapter_id, bank_id, parent_id, name, bank_id))
            return dict(conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone())

    def update_chapter(self, bank_id: str, user_id: str, chapter_id: str, name: str, parent_id: str | None = None) -> dict:
        with transaction(self.db_path) as conn:
            member = conn.execute("SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone()
            if not member or member[0] not in ("ADMIN", "EDITOR"):
                raise PermissionError("user cannot edit this bank")
            ch_row = conn.execute("SELECT * FROM chapters WHERE id = ? AND bank_id = ?", (chapter_id, bank_id)).fetchone()
            if not ch_row:
                raise LookupError("chapter not found in this bank")
            if parent_id:
                if parent_id == chapter_id:
                    raise ValueError("chapter cannot be its own parent")
                p_row = conn.execute("SELECT parent_id FROM chapters WHERE id = ? AND bank_id = ?", (parent_id, bank_id)).fetchone()
                if not p_row:
                    raise ValueError("parent chapter not found in this bank")
                curr = parent_id
                visited = {chapter_id}
                while curr:
                    if curr in visited:
                        raise ValueError("circular chapter hierarchy detected")
                    visited.add(curr)
                    next_p = conn.execute("SELECT parent_id FROM chapters WHERE id = ?", (curr,)).fetchone()
                    curr = next_p[0] if next_p else None
            conn.execute("UPDATE chapters SET name = ?, parent_id = ? WHERE id = ? AND bank_id = ?", (name, parent_id, chapter_id, bank_id))
            return dict(conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone())

    def delete_chapter(self, bank_id: str, user_id: str, chapter_id: str) -> bool:
        with transaction(self.db_path) as conn:
            member = conn.execute("SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone()
            if not member or member[0] not in ("ADMIN", "EDITOR"):
                raise PermissionError("user cannot edit this bank")
            parent_id = conn.execute("SELECT parent_id FROM chapters WHERE id = ? AND bank_id = ?", (chapter_id, bank_id)).fetchone()
            p_val = parent_id[0] if parent_id else None
            conn.execute("UPDATE chapters SET parent_id = ? WHERE parent_id = ? AND bank_id = ?", (p_val, chapter_id, bank_id))
            cur = conn.execute("DELETE FROM chapters WHERE id = ? AND bank_id = ?", (chapter_id, bank_id))
            return cur.rowcount > 0

    def list_chapters(self, bank_id: str, user_id: str) -> list[dict]:
        with transaction(self.db_path) as conn:
            if not conn.execute("SELECT 1 FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone():
                return []
            return [dict(row) for row in conn.execute("SELECT * FROM chapters WHERE bank_id = ? ORDER BY sort_order", (bank_id,)).fetchall()]

    def create_tag(self, bank_id: str, user_id: str, name: str) -> dict:
        tag_name = name.strip()
        with transaction(self.db_path) as conn:
            member = conn.execute("SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone()
            if not member or member[0] not in ("ADMIN", "EDITOR"):
                raise PermissionError("user cannot edit this bank")
            existing = conn.execute("SELECT * FROM knowledge_tags WHERE bank_id = ? AND name = ?", (bank_id, tag_name)).fetchone()
            if existing:
                return dict(existing)
            tag_id = str(uuid.uuid4())
            conn.execute("INSERT INTO knowledge_tags(id, bank_id, name) VALUES (?, ?, ?)", (tag_id, bank_id, tag_name))
            return dict(conn.execute("SELECT * FROM knowledge_tags WHERE id = ?", (tag_id,)).fetchone())

    def update_tag(self, bank_id: str, user_id: str, tag_id: str, name: str) -> dict:
        tag_name = name.strip()
        with transaction(self.db_path) as conn:
            member = conn.execute("SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone()
            if not member or member[0] not in ("ADMIN", "EDITOR"):
                raise PermissionError("user cannot edit this bank")
            cur = conn.execute("UPDATE knowledge_tags SET name = ? WHERE id = ? AND bank_id = ?", (tag_name, tag_id, bank_id))
            if cur.rowcount == 0:
                raise LookupError("tag not found")
            return dict(conn.execute("SELECT * FROM knowledge_tags WHERE id = ?", (tag_id,)).fetchone())

    def delete_tag(self, bank_id: str, user_id: str, tag_id: str) -> bool:
        with transaction(self.db_path) as conn:
            member = conn.execute("SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone()
            if not member or member[0] not in ("ADMIN", "EDITOR"):
                raise PermissionError("user cannot edit this bank")
            cur = conn.execute("DELETE FROM knowledge_tags WHERE id = ? AND bank_id = ?", (tag_id, bank_id))
            return cur.rowcount > 0

    def list_tags(self, bank_id: str, user_id: str) -> list[dict]:
        with transaction(self.db_path) as conn:
            if not conn.execute("SELECT 1 FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone():
                return []
            return [dict(row) for row in conn.execute("SELECT * FROM knowledge_tags WHERE bank_id = ? ORDER BY name", (bank_id,)).fetchall()]
