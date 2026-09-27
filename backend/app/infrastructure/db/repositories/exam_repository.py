import json
import uuid

from backend.app.infrastructure.db.connection import transaction


class ExamRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def create_profile(self, user_id: str, name: str, description: str = "") -> dict:
        profile_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            conn.execute("INSERT INTO exam_profiles(id, user_id, name, description) VALUES (?, ?, ?, ?)", (profile_id, user_id, name, description))
        return self.get_profile(profile_id, user_id)

    def get_profile(self, profile_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute("SELECT * FROM exam_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)).fetchone()
            return dict(row) if row else None

    def list_profiles(self, user_id: str) -> list[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM exam_profiles WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
            results = []
            for r in rows:
                p = dict(r)
                bp = self.latest_blueprint(user_id, p["id"])
                p["latest_blueprint"] = bp
                results.append(p)
            return results

    def save_blueprint(self, user_id: str, profile_id: str, blueprint: dict) -> dict:
        with transaction(self.db_path) as conn:
            profile = conn.execute("SELECT id FROM exam_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)).fetchone()
            if not profile:
                raise LookupError("exam profile not found")
            version = conn.execute("SELECT COALESCE(MAX(version_number), 0) + 1 FROM exam_blueprints WHERE profile_id = ?", (profile_id,)).fetchone()[0]
            blueprint_id = str(uuid.uuid4())
            conn.execute("INSERT INTO exam_blueprints(id, profile_id, version_number, blueprint_json, created_by) VALUES (?, ?, ?, ?, ?)", (blueprint_id, profile_id, version, json.dumps(blueprint, ensure_ascii=False), user_id))
            return {"id": blueprint_id, "profile_id": profile_id, "version_number": version, "blueprint": blueprint}

    def latest_blueprint(self, user_id: str, profile_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                """SELECT b.id, b.profile_id, b.version_number, b.blueprint_json
                   FROM exam_blueprints b JOIN exam_profiles p ON p.id = b.profile_id
                   WHERE b.profile_id = ? AND p.user_id = ?
                   ORDER BY b.version_number DESC LIMIT 1""",
                (profile_id, user_id),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["blueprint"] = json.loads(result.pop("blueprint_json"))
            return result

    def get_blueprint(self, user_id: str, blueprint_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                """SELECT b.id, b.profile_id, b.version_number, b.blueprint_json
                   FROM exam_blueprints b JOIN exam_profiles p ON p.id = b.profile_id
                   WHERE b.id = ? AND p.user_id = ?""",
                (blueprint_id, user_id),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["blueprint"] = json.loads(result.pop("blueprint_json"))
            return result
