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

    def list_drafts(self, user_id: str, status: str = "DRAFT") -> List[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM ai_question_drafts WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                (user_id, status),
            ).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["options"] = json.loads(item.pop("options_json") or "[]")
                item["tags"] = json.loads(item.pop("tags_json") or "[]")
                results.append(item)
            return results

    def get_draft(self, user_id: str, draft_id: str) -> Optional[dict]:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM ai_question_drafts WHERE id = ? AND user_id = ?",
                (draft_id, user_id),
            ).fetchone()
            if not row:
                return None
            res = dict(row)
            res["options"] = json.loads(res.pop("options_json") or "[]")
            res["tags"] = json.loads(res.pop("tags_json") or "[]")
            return res

    def update_status(self, user_id: str, draft_id: str, status: str) -> Optional[dict]:
        with transaction(self.db_path) as conn:
            conn.execute(
                "UPDATE ai_question_drafts SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (status, draft_id, user_id),
            )
            return self.get_draft(user_id, draft_id)

    def delete_draft(self, user_id: str, draft_id: str) -> bool:
        with transaction(self.db_path) as conn:
            res = conn.execute(
                "DELETE FROM ai_question_drafts WHERE id = ? AND user_id = ?",
                (draft_id, user_id),
            )
            return res.rowcount > 0
