import json
import uuid
from typing import List

from backend.app.infrastructure.db.connection import transaction

DEFAULT_CATEGORY = "默认分类"


class BankRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _require_admin(conn, bank_id: str, user_id: str) -> str:
        row = conn.execute(
            "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
            (bank_id, user_id),
        ).fetchone()
        if not row or row[0] != "ADMIN":
            raise PermissionError("only bank admin can manage this bank")
        return row[0]

    @staticmethod
    def _require_editor(conn, bank_id: str, user_id: str) -> str:
        row = conn.execute(
            "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
            (bank_id, user_id),
        ).fetchone()
        if not row or row[0] not in ("ADMIN", "EDITOR"):
            raise PermissionError("user cannot edit this bank")
        return row[0]

    @staticmethod
    def _audit(conn, user_id: str, action: str, bank_id: str, details: dict) -> None:
        conn.execute(
            """INSERT INTO audit_logs(id, user_id, action, entity_type, entity_id, details_json)
               VALUES (?, ?, ?, 'BANK', ?, ?)""",
            (str(uuid.uuid4()), user_id, action, bank_id, json.dumps(details, ensure_ascii=False)),
        )

    @staticmethod
    def _has_active_exam(conn, bank_id: str) -> bool:
        return bool(conn.execute(
            "SELECT 1 FROM practice_sessions WHERE bank_id = ? AND mode = 'EXAM' AND is_completed = 0 LIMIT 1",
            (bank_id,),
        ).fetchone())

    @staticmethod
    def _bank_counts_sql() -> str:
        # Count only non-archived questions; expose archived as a separate count.
        return """
            COUNT(q.id) AS question_count,
            COALESCE(SUM(CASE WHEN i.question_id IS NOT NULL AND q.id IS NULL THEN 1 ELSE 0 END), 0)
                AS archived_question_count
        """

    # ------------------------------------------------------------- bank object

    def create(self, user_id: str, name: str, description: str = "", category: str = DEFAULT_CATEGORY) -> dict:
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
            self._audit(conn, user_id, "BANK_CREATED", bank_id, {"name": name, "category": category})
        return self.get_for_user(bank_id, user_id)

    def update(self, bank_id: str, user_id: str, fields: dict) -> dict:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT id FROM question_banks WHERE id = ? AND is_deleted = 0",
                (bank_id,),
            ).fetchone()
            if not row:
                raise LookupError("bank not found")
            self._require_admin(conn, bank_id, user_id)

            assignments = []
            params = []
            cleaned = {}
            for key in ("name", "description", "category"):
                if key not in fields or fields.get(key) is None:
                    continue
                value = str(fields[key])
                if key in ("name", "category"):
                    value = value.strip()
                    if not value:
                        raise ValueError(f"{key} cannot be empty")
                assignments.append(f"{key} = ?")
                params.append(value)
                cleaned[key] = value
            if not assignments:
                return self.get_for_user(bank_id, user_id)

            assignments.append("updated_at = CURRENT_TIMESTAMP")
            conn.execute(
                f"UPDATE question_banks SET {', '.join(assignments)} WHERE id = ?",
                (*params, bank_id),
            )
            self._audit(conn, user_id, "BANK_UPDATED", bank_id, {"fields": cleaned})
        return self.get_for_user(bank_id, user_id)

    def soft_delete(self, bank_id: str, user_id: str) -> dict:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT is_deleted FROM question_banks WHERE id = ?", (bank_id,)
            ).fetchone()
            if not row:
                raise LookupError("bank not found")
            self._require_admin(conn, bank_id, user_id)
            if row[0]:
                return {"bank_id": bank_id, "deleted": True, "already_deleted": True}
            if self._has_active_exam(conn, bank_id):
                raise ValueError("cannot delete a bank while an exam is active")
            conn.execute(
                "UPDATE question_banks SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (bank_id,),
            )
            self._audit(conn, user_id, "BANK_DELETED", bank_id, {"soft_delete": True})
        return {"bank_id": bank_id, "deleted": True, "already_deleted": False}

    def restore(self, bank_id: str, user_id: str) -> dict:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT is_deleted FROM question_banks WHERE id = ?", (bank_id,)
            ).fetchone()
            if not row:
                raise LookupError("bank not found")
            self._require_admin(conn, bank_id, user_id)
            conn.execute(
                "UPDATE question_banks SET is_deleted = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (bank_id,),
            )
            self._audit(conn, user_id, "BANK_RESTORED", bank_id, {})
        return self.get_for_user(bank_id, user_id)

    def batch(self, user_id: str, bank_ids: List[str], operation: str, category: str | None = None) -> dict:
        ids: List[str] = []
        for raw in bank_ids or []:
            bank_id = str(raw or "").strip()
            if bank_id and bank_id not in ids:
                ids.append(bank_id)
        if not ids:
            raise ValueError("bank_ids cannot be empty")
        if len(ids) > 200:
            raise ValueError("batch size cannot exceed 200")

        op = str(operation or "").strip().lower()
        if op not in {"archive", "delete", "restore", "set_category"}:
            raise ValueError("unsupported batch operation")
        if op == "set_category":
            category = str(category or "").strip()
            if not category:
                raise ValueError("category cannot be empty")

        with transaction(self.db_path) as conn:
            rows = []
            for bank_id in ids:
                row = conn.execute(
                    "SELECT is_deleted FROM question_banks WHERE id = ?", (bank_id,)
                ).fetchone()
                if not row:
                    raise LookupError(f"bank '{bank_id}' not found")
                self._require_admin(conn, bank_id, user_id)
                if op in {"archive", "delete"} and not row[0] and self._has_active_exam(conn, bank_id):
                    raise ValueError("cannot delete a bank while an exam is active")
                rows.append((bank_id, row[0]))

            for bank_id, _ in rows:
                if op in {"archive", "delete"}:
                    conn.execute(
                        "UPDATE question_banks SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (bank_id,),
                    )
                elif op == "restore":
                    conn.execute(
                        "UPDATE question_banks SET is_deleted = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (bank_id,),
                    )
                else:
                    conn.execute(
                        "UPDATE question_banks SET category = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (category, bank_id),
                    )

            details = {"operation": op, "bank_ids": ids, "category": category}
            for bank_id, _ in rows:
                self._audit(conn, user_id, "BANK_BATCH", bank_id, details)
        return {"operation": op, "affected": len(ids), "bank_ids": ids, "category": category}

    # -------------------------------------------------------------- categories

    def list_categories(self, user_id: str) -> List[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT b.category AS name, COUNT(*) AS count
                   FROM question_banks b
                   JOIN question_bank_members m ON m.bank_id = b.id AND m.user_id = ?
                   WHERE b.is_deleted = 0
                   GROUP BY b.category ORDER BY b.category""",
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def _category_bank_ids(self, conn, user_id: str, name: str) -> List[str]:
        rows = conn.execute(
            """SELECT b.id FROM question_banks b
               JOIN question_bank_members m ON m.bank_id = b.id AND m.user_id = ? AND m.role = 'ADMIN'
               WHERE b.is_deleted = 0 AND b.category = ?""",
            (user_id, name),
        ).fetchall()
        return [row[0] for row in rows]

    def rename_category(self, user_id: str, old_name: str, new_name: str) -> dict:
        old = str(old_name or "").strip()
        new = str(new_name or "").strip()
        if not old or not new:
            raise ValueError("category names cannot be empty")
        if old == new:
            return {"old_name": old, "new_name": new, "affected": 0}
        with transaction(self.db_path) as conn:
            bank_ids = self._category_bank_ids(conn, user_id, old)
            if not bank_ids:
                raise LookupError("category not found or no permission")
            conn.execute(
                "UPDATE question_banks SET category = ?, updated_at = CURRENT_TIMESTAMP WHERE category = ? AND id IN (%s)"
                % ",".join("?" for _ in bank_ids),
                (new, old, *bank_ids),
            )
            for bank_id in bank_ids:
                self._audit(conn, user_id, "BANK_CATEGORY_RENAMED", bank_id, {"old": old, "new": new})
        return {"old_name": old, "new_name": new, "affected": len(bank_ids)}

    def delete_category(self, user_id: str, name: str) -> dict:
        target = str(name or "").strip()
        if not target:
            raise ValueError("category name cannot be empty")
        if target == DEFAULT_CATEGORY:
            raise ValueError("default category cannot be deleted")
        with transaction(self.db_path) as conn:
            bank_ids = self._category_bank_ids(conn, user_id, target)
            if not bank_ids:
                raise LookupError("category not found or no permission")
            conn.execute(
                "UPDATE question_banks SET category = ?, updated_at = CURRENT_TIMESTAMP WHERE category = ? AND id IN (%s)"
                % ",".join("?" for _ in bank_ids),
                (DEFAULT_CATEGORY, target, *bank_ids),
            )
            for bank_id in bank_ids:
                self._audit(conn, user_id, "BANK_CATEGORY_DELETED", bank_id, {"category": target})
        return {"name": target, "affected": len(bank_ids), "fallback": DEFAULT_CATEGORY}

    # ----------------------------------------------------------------- lookup

    def get_for_user(self, bank_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                f"""SELECT b.id, b.name, b.description, b.category, b.created_by, m.role,
                          {self._bank_counts_sql()}
                   FROM question_banks b
                   JOIN question_bank_members m ON m.bank_id = b.id AND m.user_id = ?
                   LEFT JOIN bank_question_items i ON i.bank_id = b.id
                   LEFT JOIN questions q ON q.id = i.question_id AND q.is_deleted = 0
                   WHERE b.id = ? AND b.is_deleted = 0
                   GROUP BY b.id, m.role""",
                (user_id, bank_id),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["deleted"] = False
            active_exam = self._has_active_exam(conn, bank_id)
            result["has_active_exam"] = active_exam
            result["locked_by_active_exam"] = active_exam
            return result

    def list_for_user(self, user_id: str, deleted: bool = False) -> List[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                f"""SELECT b.id, b.name, b.description, b.category, b.created_by, m.role,
                          b.created_at, b.updated_at, {self._bank_counts_sql()}
                   FROM question_banks b
                   JOIN question_bank_members m ON m.bank_id = b.id AND m.user_id = ?
                   LEFT JOIN bank_question_items i ON i.bank_id = b.id
                   LEFT JOIN questions q ON q.id = i.question_id AND q.is_deleted = 0
                   WHERE b.is_deleted = ?
                   GROUP BY b.id, m.role
                   ORDER BY COALESCE(b.updated_at, b.created_at) DESC""",
                (user_id, 1 if deleted else 0),
            ).fetchall()
            active_banks = {
                r[0]
                for r in conn.execute(
                    "SELECT DISTINCT bank_id FROM practice_sessions WHERE mode = 'EXAM' AND is_completed = 0"
                ).fetchall()
            }
            results = []
            for row in rows:
                d = dict(row)
                d["deleted"] = bool(deleted)
                d["has_active_exam"] = d["id"] in active_banks
                d["locked_by_active_exam"] = d["id"] in active_banks
                results.append(d)
            return results

    def list_audit(self, bank_id: str, user_id: str, limit: int = 50) -> List[dict]:
        with transaction(self.db_path) as conn:
            self._require_admin(conn, bank_id, user_id)
            safe_limit = max(1, min(int(limit or 50), 200))
            rows = conn.execute(
                """SELECT id, user_id, action, details_json, created_at
                   FROM audit_logs
                   WHERE entity_type = 'BANK' AND entity_id = ?
                   ORDER BY created_at DESC, rowid DESC LIMIT ?""",
                (bank_id, safe_limit),
            ).fetchall()
            results = []
            for row in rows:
                item = dict(row)
                try:
                    item["details"] = json.loads(item.pop("details_json") or "{}")
                except Exception:
                    item["details"] = {}
                results.append(item)
            return results

    # ----------------------------------------------------------------- members

    def add_member(self, bank_id: str, owner_id: str, username: str, role: str = "MEMBER") -> dict:
        role = str(role or "").strip().upper()
        if role not in {"MEMBER", "EDITOR"}:
            raise ValueError("role must be MEMBER or EDITOR")
        with transaction(self.db_path) as conn:
            self._require_admin(conn, bank_id, owner_id)
            target = conn.execute("SELECT id FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
            if not target:
                raise LookupError("user not found")
            conn.execute(
                "INSERT INTO question_bank_members(bank_id, user_id, role) VALUES (?, ?, ?) "
                "ON CONFLICT(bank_id, user_id) DO UPDATE SET role = excluded.role",
                (bank_id, target[0], role),
            )
            self._audit(conn, owner_id, "BANK_MEMBER_ADDED", bank_id,
                        {"user_id": target[0], "role": role})
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

    def update_member_role(self, bank_id: str, owner_id: str, target_user_id: str, role: str) -> dict:
        role = str(role or "").strip().upper()
        if role not in {"MEMBER", "EDITOR"}:
            raise ValueError("role must be MEMBER or EDITOR")
        with transaction(self.db_path) as conn:
            self._require_admin(conn, bank_id, owner_id)
            target = conn.execute(
                "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
                (bank_id, target_user_id),
            ).fetchone()
            if not target:
                raise LookupError("member not found")
            if target[0] == "ADMIN":
                raise ValueError("cannot change the owner role; transfer ownership instead")
            conn.execute(
                "UPDATE question_bank_members SET role = ? WHERE bank_id = ? AND user_id = ?",
                (role, bank_id, target_user_id),
            )
            self._audit(conn, owner_id, "BANK_MEMBER_ROLE_CHANGED", bank_id,
                        {"user_id": target_user_id, "role": role})
        return {"bank_id": bank_id, "user_id": target_user_id, "role": role}

    def remove_member(self, bank_id: str, owner_id: str, target_user_id: str) -> bool:
        with transaction(self.db_path) as conn:
            self._require_admin(conn, bank_id, owner_id)
            if owner_id == target_user_id:
                raise ValueError("cannot remove owner/self")
            res = conn.execute("DELETE FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, target_user_id))
            if res.rowcount:
                self._audit(conn, owner_id, "BANK_MEMBER_REMOVED", bank_id, {"user_id": target_user_id})
            return res.rowcount > 0

    def leave_bank(self, bank_id: str, user_id: str) -> bool:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
                (bank_id, user_id),
            ).fetchone()
            if not row:
                raise LookupError("membership not found")
            if row[0] == "ADMIN":
                raise ValueError("owner cannot leave the bank; transfer ownership first")
            conn.execute("DELETE FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id))
            self._audit(conn, user_id, "BANK_MEMBER_LEFT", bank_id, {"user_id": user_id})
            return True

    def transfer_ownership(self, bank_id: str, owner_id: str, username: str) -> dict:
        with transaction(self.db_path) as conn:
            self._require_admin(conn, bank_id, owner_id)
            target = conn.execute(
                "SELECT id, username FROM users WHERE username = ?", (str(username or "").strip().lower(),)
            ).fetchone()
            if not target:
                raise LookupError("user not found")
            target_id, target_name = target[0], target[1]
            if target_id == owner_id:
                raise ValueError("target user is already the owner")
            membership = conn.execute(
                "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
                (bank_id, target_id),
            ).fetchone()
            if not membership:
                raise LookupError("target user must be a bank member first")
            conn.execute(
                "UPDATE question_bank_members SET role = 'EDITOR' WHERE bank_id = ? AND user_id = ?",
                (bank_id, owner_id),
            )
            conn.execute(
                "UPDATE question_bank_members SET role = 'ADMIN' WHERE bank_id = ? AND user_id = ?",
                (bank_id, target_id),
            )
            self._audit(conn, owner_id, "BANK_OWNER_TRANSFERRED", bank_id,
                        {"from": owner_id, "to": target_id, "username": target_name})
            return {"bank_id": bank_id, "owner_id": target_id, "username": target_name}

    # ---------------------------------------------------------------- chapters

    def create_chapter(self, bank_id: str, user_id: str, name: str, parent_id: str | None = None) -> dict:
        clean = str(name or "").strip()
        if not clean:
            raise ValueError("chapter name cannot be empty")
        chapter_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            self._require_editor(conn, bank_id, user_id)
            if parent_id:
                p_row = conn.execute("SELECT 1 FROM chapters WHERE id = ? AND bank_id = ?", (parent_id, bank_id)).fetchone()
                if not p_row:
                    raise ValueError("parent chapter not found in this bank")
            conn.execute(
                "INSERT INTO chapters(id, bank_id, parent_id, name, sort_order) "
                "VALUES (?, ?, ?, ?, (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM chapters WHERE bank_id = ?))",
                (chapter_id, bank_id, parent_id, clean, bank_id),
            )
            self._audit(conn, user_id, "CHAPTER_CREATED", bank_id,
                        {"chapter_id": chapter_id, "name": clean, "parent_id": parent_id})
            return dict(conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone())

    def update_chapter(self, bank_id: str, user_id: str, chapter_id: str, name: str, parent_id: str | None = None) -> dict:
        clean = str(name or "").strip()
        if not clean:
            raise ValueError("chapter name cannot be empty")
        with transaction(self.db_path) as conn:
            self._require_editor(conn, bank_id, user_id)
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
            conn.execute("UPDATE chapters SET name = ?, parent_id = ? WHERE id = ? AND bank_id = ?", (clean, parent_id, chapter_id, bank_id))
            self._audit(conn, user_id, "CHAPTER_UPDATED", bank_id,
                        {"chapter_id": chapter_id, "name": clean, "parent_id": parent_id})
            return dict(conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone())

    def delete_chapter(self, bank_id: str, user_id: str, chapter_id: str) -> bool:
        with transaction(self.db_path) as conn:
            self._require_editor(conn, bank_id, user_id)
            parent_id = conn.execute("SELECT parent_id FROM chapters WHERE id = ? AND bank_id = ?", (chapter_id, bank_id)).fetchone()
            if not parent_id:
                return False
            p_val = parent_id[0]
            conn.execute("UPDATE chapters SET parent_id = ? WHERE parent_id = ? AND bank_id = ?", (p_val, chapter_id, bank_id))
            cur = conn.execute("DELETE FROM chapters WHERE id = ? AND bank_id = ?", (chapter_id, bank_id))
            if cur.rowcount:
                self._audit(conn, user_id, "CHAPTER_DELETED", bank_id,
                            {"chapter_id": chapter_id, "reparented_to": p_val})
            return cur.rowcount > 0

    def reorder_chapters(self, bank_id: str, user_id: str, items: List[dict]) -> List[dict]:
        if not isinstance(items, list) or not items:
            raise ValueError("items cannot be empty")
        with transaction(self.db_path) as conn:
            self._require_editor(conn, bank_id, user_id)
            existing_rows = conn.execute("SELECT * FROM chapters WHERE bank_id = ?", (bank_id,)).fetchall()
            existing = {row["id"]: dict(row) for row in existing_rows}
            if not existing:
                raise ValueError("bank has no chapters")

            normalized = []
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    raise ValueError("invalid chapter item")
                chapter_id = str(item.get("id") or "").strip()
                if chapter_id not in existing:
                    raise ValueError("chapter does not belong to this bank")
                parent_id = item.get("parent_id") or None
                if parent_id is not None and parent_id not in existing:
                    raise ValueError("parent chapter does not belong to this bank")
                raw_sort = item.get("sort_order", index)
                try:
                    sort_order = int(raw_sort)
                except (TypeError, ValueError):
                    raise ValueError("sort_order must be an integer") from None
                normalized.append((chapter_id, parent_id, sort_order))

            graph = {chapter_id: row.get("parent_id") for chapter_id, row in existing.items()}
            for chapter_id, parent_id, _ in normalized:
                graph[chapter_id] = parent_id
            for chapter_id in graph:
                seen = set()
                cursor = chapter_id
                while cursor:
                    if cursor in seen:
                        raise ValueError("circular chapter hierarchy detected")
                    seen.add(cursor)
                    cursor = graph.get(cursor)

            for chapter_id, parent_id, sort_order in normalized:
                conn.execute(
                    "UPDATE chapters SET parent_id = ?, sort_order = ? WHERE id = ? AND bank_id = ?",
                    (parent_id, sort_order, chapter_id, bank_id),
                )
            self._audit(conn, user_id, "CHAPTERS_REORDERED", bank_id,
                        {"items": [{"id": cid, "parent_id": parent, "sort_order": order}
                                   for cid, parent, order in normalized]})
            return [dict(row) for row in conn.execute(
                "SELECT * FROM chapters WHERE bank_id = ? ORDER BY sort_order, name", (bank_id,)
            ).fetchall()]

    def list_chapters(self, bank_id: str, user_id: str) -> list[dict]:
        with transaction(self.db_path) as conn:
            if not conn.execute("SELECT 1 FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone():
                return []
            return [dict(row) for row in conn.execute("SELECT * FROM chapters WHERE bank_id = ? ORDER BY sort_order, name", (bank_id,)).fetchall()]

    # -------------------------------------------------------------------- tags

    def _sync_question_tags(self, conn, bank_id: str, version_id: str, tags: List[str]) -> None:
        conn.execute("DELETE FROM question_tag_items WHERE question_version_id = ?", (version_id,))
        for raw in tags or []:
            name = str(raw or "").strip()
            if not name:
                continue
            row = conn.execute(
                "SELECT id FROM knowledge_tags WHERE bank_id = ? AND name = ?", (bank_id, name)
            ).fetchone()
            if row:
                tag_id = row[0]
            else:
                tag_id = str(uuid.uuid4())
                conn.execute("INSERT INTO knowledge_tags(id, bank_id, name) VALUES (?, ?, ?)", (tag_id, bank_id, name))
            conn.execute(
                "INSERT OR IGNORE INTO question_tag_items(question_version_id, tag_id) VALUES (?, ?)",
                (version_id, tag_id),
            )

    def _repoint_tag_items(self, conn, tag_id: str, target_tag_id: str) -> int:
        """Move tag links from one tag entity to another without touching version snapshots."""
        rows = conn.execute(
            "SELECT question_version_id FROM question_tag_items WHERE tag_id = ?", (tag_id,)
        ).fetchall()
        for row in rows:
            conn.execute(
                "INSERT OR IGNORE INTO question_tag_items(question_version_id, tag_id) VALUES (?, ?)",
                (row[0], target_tag_id),
            )
        conn.execute("DELETE FROM question_tag_items WHERE tag_id = ?", (tag_id,))
        return len(rows)

    def create_tag(self, bank_id: str, user_id: str, name: str) -> dict:
        tag_name = str(name or "").strip()
        if not tag_name:
            raise ValueError("tag name cannot be empty")
        with transaction(self.db_path) as conn:
            self._require_editor(conn, bank_id, user_id)
            existing = conn.execute("SELECT * FROM knowledge_tags WHERE bank_id = ? AND name = ?", (bank_id, tag_name)).fetchone()
            if existing:
                return dict(existing)
            tag_id = str(uuid.uuid4())
            conn.execute("INSERT INTO knowledge_tags(id, bank_id, name) VALUES (?, ?, ?)", (tag_id, bank_id, tag_name))
            self._audit(conn, user_id, "TAG_CREATED", bank_id, {"tag_id": tag_id, "name": tag_name})
            return dict(conn.execute("SELECT * FROM knowledge_tags WHERE id = ?", (tag_id,)).fetchone())

    def update_tag(self, bank_id: str, user_id: str, tag_id: str, name: str) -> dict:
        tag_name = str(name or "").strip()
        if not tag_name:
            raise ValueError("tag name cannot be empty")
        with transaction(self.db_path) as conn:
            self._require_editor(conn, bank_id, user_id)
            tag = conn.execute("SELECT * FROM knowledge_tags WHERE id = ? AND bank_id = ?", (tag_id, bank_id)).fetchone()
            if not tag:
                raise LookupError("tag not found")
            old_name = tag["name"]
            if old_name == tag_name:
                return dict(tag)
            conflict = conn.execute(
                "SELECT * FROM knowledge_tags WHERE bank_id = ? AND name = ? AND id <> ?",
                (bank_id, tag_name, tag_id),
            ).fetchone()
            if conflict:
                moved = self._repoint_tag_items(conn, tag_id, conflict["id"])
                conn.execute("DELETE FROM knowledge_tags WHERE id = ?", (tag_id,))
                self._audit(conn, user_id, "TAG_MERGED", bank_id,
                            {"from": old_name, "into": tag_name, "tag_id": tag_id, "links": moved})
                return dict(conflict)
            conn.execute("UPDATE knowledge_tags SET name = ? WHERE id = ? AND bank_id = ?", (tag_name, tag_id, bank_id))
            self._audit(conn, user_id, "TAG_RENAMED", bank_id, {"from": old_name, "to": tag_name})
            return dict(conn.execute("SELECT * FROM knowledge_tags WHERE id = ?", (tag_id,)).fetchone())

    def delete_tag(self, bank_id: str, user_id: str, tag_id: str) -> bool:
        with transaction(self.db_path) as conn:
            self._require_editor(conn, bank_id, user_id)
            tag = conn.execute("SELECT name FROM knowledge_tags WHERE id = ? AND bank_id = ?", (tag_id, bank_id)).fetchone()
            if not tag:
                return False
            links = conn.execute(
                "SELECT COUNT(*) FROM question_tag_items WHERE tag_id = ?", (tag_id,)
            ).fetchone()[0]
            # Historical version snapshots (tags_json) stay immutable; removing the
            # entity only drops the current tag link.
            conn.execute("DELETE FROM question_tag_items WHERE tag_id = ?", (tag_id,))
            cur = conn.execute("DELETE FROM knowledge_tags WHERE id = ? AND bank_id = ?", (tag_id, bank_id))
            if cur.rowcount:
                self._audit(conn, user_id, "TAG_DELETED", bank_id, {"name": tag[0], "links": links})
            return cur.rowcount > 0


    def list_tags(self, bank_id: str, user_id: str) -> list[dict]:
        with transaction(self.db_path) as conn:
            if not conn.execute("SELECT 1 FROM question_bank_members WHERE bank_id = ? AND user_id = ?", (bank_id, user_id)).fetchone():
                return []
            rows = conn.execute(
                """SELECT t.*, COUNT(DISTINCT qti.question_version_id) AS question_count
                   FROM knowledge_tags t
                   LEFT JOIN question_tag_items qti ON qti.tag_id = t.id
                   WHERE t.bank_id = ? GROUP BY t.id ORDER BY t.name""",
                (bank_id,),
            ).fetchall()
            return [dict(row) for row in rows]
