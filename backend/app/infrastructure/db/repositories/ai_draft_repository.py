import json
import uuid
from typing import Any, Dict, List, Optional

from backend.app.infrastructure.db.connection import transaction


class AiDraftRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def create_draft(
        self,
        user_id: str,
        original_question_id: Optional[str],
        target_bank_id: str,
        payload: Dict[str, Any],
    ) -> dict:
        draft_id = str(uuid.uuid4())
        options_json = json.dumps(payload.get("options") or [], ensure_ascii=False)
        tags_json = json.dumps(payload.get("tags") or [], ensure_ascii=False)
        with transaction(self.db_path) as conn:
            conn.execute(
                """INSERT INTO ai_question_drafts(
                    id, user_id, original_question_id, target_bank_id,
                    stem, type, options_json, answer, explanation,
                    difficulty, tags_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT')""",
                (
                    draft_id,
                    user_id,
                    original_question_id,
                    target_bank_id,
                    payload.get("stem", ""),
                    payload.get("type", "SINGLE"),
                    options_json,
                    payload.get("answer", ""),
                    payload.get("explanation", ""),
                    payload.get("difficulty", 3),
                    tags_json,
                ),
            )
            row = conn.execute("SELECT * FROM ai_question_drafts WHERE id = ?", (draft_id,)).fetchone()
            res = dict(row)
            res["options"] = json.loads(res.pop("options_json") or "[]")
            res["tags"] = json.loads(res.pop("tags_json") or "[]")
            return res

    _SELECT_WITH_BANK = """
        SELECT d.*, b.name AS target_bank_name, m.role AS target_bank_role
        FROM ai_question_drafts d
        LEFT JOIN question_banks b ON b.id = d.target_bank_id
        LEFT JOIN question_bank_members m ON m.bank_id = d.target_bank_id AND m.user_id = d.user_id
    """

    @staticmethod
    def _serialize_draft(row) -> dict:
        item = dict(row)
        item["options"] = json.loads(item.pop("options_json") or "[]")
        item["tags"] = json.loads(item.pop("tags_json") or "[]")
        item["can_manage"] = item.get("target_bank_role") in ("ADMIN", "EDITOR")
        return item

    def list_drafts(self, user_id: str, status: str = "DRAFT", bank_id: Optional[str] = None) -> List[dict]:
        query = self._SELECT_WITH_BANK + " WHERE d.user_id = ? AND d.status = ?"
        params: list[Any] = [user_id, status]
        if bank_id:
            query += " AND d.target_bank_id = ?"
            params.append(bank_id)
        query += " ORDER BY d.created_at DESC"
        with transaction(self.db_path) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [self._serialize_draft(row) for row in rows]

    def get_draft(self, user_id: str, draft_id: str, conn=None) -> Optional[dict]:
        def _query(c):
            row = c.execute(
                self._SELECT_WITH_BANK + " WHERE d.id = ? AND d.user_id = ?",
                (draft_id, user_id),
            ).fetchone()
            return self._serialize_draft(row) if row else None

        if conn is not None:
            return _query(conn)
        with transaction(self.db_path) as conn:
            return _query(conn)

    def get_bank_role(self, user_id: str, bank_id: str, conn=None) -> Optional[str]:
        def _query(c):
            row = c.execute(
                """SELECT m.role
                   FROM question_bank_members m
                   JOIN question_banks b ON b.id = m.bank_id AND b.is_deleted = 0
                   WHERE m.bank_id = ? AND m.user_id = ?""",
                (bank_id, user_id),
            ).fetchone()
            return row[0] if row else None

        if conn is not None:
            return _query(conn)
        with transaction(self.db_path) as conn:
            return _query(conn)

    def update_status(self, user_id: str, draft_id: str, status: str, expected_status: str | None = None, conn=None) -> Optional[dict]:
        def _exec(c):
            if expected_status:
                cur = c.execute(
                    "UPDATE ai_question_drafts SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ? AND status = ?",
                    (status, draft_id, user_id, expected_status),
                )
                if cur.rowcount == 0:
                    return None
            else:
                c.execute(
                    "UPDATE ai_question_drafts SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                    (status, draft_id, user_id),
                )
            row = c.execute(
                "SELECT * FROM ai_question_drafts WHERE id = ? AND user_id = ?",
                (draft_id, user_id),
            ).fetchone()
            if not row:
                return None
            res = dict(row)
            res["options"] = json.loads(res.pop("options_json") or "[]")
            res["tags"] = json.loads(res.pop("tags_json") or "[]")
            return res

        if conn is not None:
            return _exec(conn)
        with transaction(self.db_path) as conn:
            return _exec(conn)

    def delete_draft(self, user_id: str, draft_id: str) -> bool:
        with transaction(self.db_path) as conn:
            res = conn.execute(
                "DELETE FROM ai_question_drafts WHERE id = ? AND user_id = ?",
                (draft_id, user_id),
            )
            return res.rowcount > 0
