import uuid
from typing import Optional

from backend.app.infrastructure.db.connection import transaction


class AiAnswerRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def create(self, user_id: str, question: dict, content: str, source: str, provider: Optional[str] = None) -> dict:
        answer_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            conn.execute(
                """INSERT INTO explanation_versions(
                    id, user_id, question_id, question_version_id, source, content, provider
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (answer_id, user_id, question["id"], question["version_id"], source, content, provider),
            )
        return self.get_for_user(answer_id, user_id)

    def get_for_user(self, answer_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, question_id, question_version_id, source, content, provider, is_candidate, is_adopted, parent_version_id, created_at FROM explanation_versions WHERE id = ? AND user_id = ?",
                (answer_id, user_id),
            ).fetchone()
            return dict(row) if row else None

    def list_for_question(self, question_id: str, user_id: str) -> list[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, question_id, question_version_id, source, content, provider, is_candidate, is_adopted, parent_version_id, created_at FROM explanation_versions WHERE question_id = ? AND user_id = ? ORDER BY created_at DESC",
                (question_id, user_id),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                evidence = conn.execute(
                    "SELECT id, title, url, summary, retrieved_at FROM explanation_evidence WHERE explanation_id = ? ORDER BY retrieved_at ASC",
                    (item["id"],),
                ).fetchall()
                item["evidence"] = [dict(value) for value in evidence]
                result.append(item)
            return result

    def add_evidence(self, answer_id: str, user_id: str, evidence: list[dict]) -> list[dict]:
        with transaction(self.db_path) as conn:
            owned = conn.execute(
                "SELECT 1 FROM explanation_versions WHERE id = ? AND user_id = ?",
                (answer_id, user_id),
            ).fetchone()
            if not owned:
                raise LookupError("answer not found")
            for item in evidence:
                conn.execute(
                    "INSERT INTO explanation_evidence(id, explanation_id, title, url, summary) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), answer_id, item.get("title") or "未命名来源", item.get("url"), item.get("summary")),
                )
            rows = conn.execute(
                "SELECT id, title, url, summary, retrieved_at FROM explanation_evidence WHERE explanation_id = ? ORDER BY retrieved_at ASC",
                (answer_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def adopt(self, answer_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute("SELECT question_id FROM explanation_versions WHERE id = ? AND user_id = ?", (answer_id, user_id)).fetchone()
            if not row:
                return None
            conn.execute("UPDATE explanation_versions SET is_adopted = 0 WHERE question_id = ? AND user_id = ?", (row[0], user_id))
            conn.execute("UPDATE explanation_versions SET is_adopted = 1, is_candidate = 0 WHERE id = ? AND user_id = ?", (answer_id, user_id))
        return self.get_for_user(answer_id, user_id)
