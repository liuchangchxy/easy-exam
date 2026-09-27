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

    def get_for_user(self, user_id: str, asset_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM personal_assets WHERE id = ? AND user_id = ?",
                (asset_id, user_id),
            ).fetchone()
            return dict(row) if row else None

    def delete(self, user_id: str, asset_id: str) -> bool:
        with transaction(self.db_path) as conn:
            res = conn.execute(
                "DELETE FROM personal_assets WHERE id = ? AND user_id = ?",
                (asset_id, user_id),
            )
            return res.rowcount > 0

    def list_for_user(self, user_id: str, question_id: str | None = None) -> list[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM personal_assets WHERE user_id = ?"
                + (" AND question_id = ?" if question_id else "")
                + " ORDER BY created_at DESC",
                (user_id, question_id) if question_id else (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def find_relevant(self, user_id: str, question_id: str | None = None, tags: list[str] | None = None) -> list[dict]:
        """Retrieve relevant personal reference materials strictly scoped to user_id."""
        with transaction(self.db_path) as conn:
            params = [user_id]
            clauses = ["user_id = ?"]
            sub_clauses = []
            if question_id:
                sub_clauses.append("question_id = ?")
                params.append(question_id)
            if tags:
                for t in tags:
                    if t and t.strip():
                        sub_clauses.append("content LIKE ?")
                        params.append(f"%{t.strip()}%")
            if sub_clauses:
                clauses.append(f"({' OR '.join(sub_clauses)})")

            query = f"SELECT * FROM personal_assets WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT 5"
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(row) for row in rows]
