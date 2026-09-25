import uuid

from backend.app.infrastructure.db.connection import transaction


class AssetRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def create(self, user_id: str, payload: dict) -> dict:
        asset_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            conn.execute("INSERT INTO personal_assets(id, user_id, question_id, knowledge_tag_id, asset_type, content) VALUES (?, ?, ?, ?, ?, ?)", (asset_id, user_id, payload.get("question_id"), payload.get("knowledge_tag_id"), payload["asset_type"], payload["content"]))
            return dict(conn.execute("SELECT * FROM personal_assets WHERE id = ?", (asset_id,)).fetchone())

    def list_for_user(self, user_id: str, question_id: str | None = None) -> list[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM personal_assets WHERE user_id = ?" + (" AND question_id = ?" if question_id else "") + " ORDER BY created_at DESC", (user_id, question_id) if question_id else (user_id,)).fetchall()
            return [dict(row) for row in rows]
