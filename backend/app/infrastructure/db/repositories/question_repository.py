import json
import uuid
from typing import Any, Dict, List

from backend.app.infrastructure.db.connection import transaction


class QuestionRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def create_versioned_question(self, user_id: str, bank_id: str, payload: Dict[str, Any]) -> dict:
        question_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            member = conn.execute(
                "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
                (bank_id, user_id),
            ).fetchone()
            if not member or member[0] not in ("ADMIN", "EDITOR"):
                raise PermissionError("user cannot edit this question bank")
            conn.execute("INSERT INTO questions(id, created_by) VALUES (?, ?)", (question_id, user_id))
            conn.execute(
                """INSERT INTO question_versions(
                    id, question_id, version_number, type, stem, options_json, answer,
                    explanation, difficulty, tags_json, created_by
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    version_id,
                    question_id,
                    payload.get("type", "SINGLE"),
                    payload["stem"],
                    json.dumps(payload.get("options", []), ensure_ascii=False),
                    payload.get("answer", ""),
                    payload.get("explanation", ""),
                    int(payload["difficulty"]) if payload.get("difficulty") is not None else 0,
                    json.dumps(payload.get("tags", []), ensure_ascii=False),
                    user_id,
                ),
            )
            conn.execute("INSERT INTO bank_question_items(bank_id, question_id) VALUES (?, ?)", (bank_id, question_id))
        return self.get_for_user(question_id, user_id)

    def batch_create_or_update_questions(
        self,
        user_id: str,
        bank_id: str,
        operations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Atomically insert new questions or create next versions within a single database transaction (EXAM-MASTER pattern)."""
        created_ids = []
        with transaction(self.db_path) as conn:
            member = conn.execute(
                "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
                (bank_id, user_id),
            ).fetchone()
            if not member or member[0] not in ("ADMIN", "EDITOR"):
                raise PermissionError("user cannot edit this question bank")

            for op_info in operations:
                op = op_info.get("op", "create")
                payload = op_info["payload"]
                if op == "merge":
                    target_qid = op_info["question_id"]
                    current_max = conn.execute(
                        "SELECT COALESCE(MAX(version_number), 0) FROM question_versions WHERE question_id = ?",
                        (target_qid,),
                    ).fetchone()[0]
                    v_id = str(uuid.uuid4())
                    conn.execute(
                        """INSERT INTO question_versions(
                            id, question_id, version_number, type, stem, options_json, answer,
                            explanation, difficulty, tags_json, created_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            v_id,
                            target_qid,
                            current_max + 1,
                            payload.get("type", "SINGLE"),
                            payload["stem"],
                            json.dumps(payload.get("options", []), ensure_ascii=False),
                            payload.get("answer", ""),
                            payload.get("explanation", ""),
                            int(payload["difficulty"]) if payload.get("difficulty") is not None else 0,
                            json.dumps(payload.get("tags", []), ensure_ascii=False),
                            user_id,
                        ),
                    )
                    created_ids.append(target_qid)
                else:
                    new_qid = str(uuid.uuid4())
                    new_vid = str(uuid.uuid4())
                    conn.execute("INSERT INTO questions(id, created_by) VALUES (?, ?)", (new_qid, user_id))
                    conn.execute(
                        """INSERT INTO question_versions(
                            id, question_id, version_number, type, stem, options_json, answer,
                            explanation, difficulty, tags_json, created_by
                        ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            new_vid,
                            new_qid,
                            payload.get("type", "SINGLE"),
                            payload["stem"],
                            json.dumps(payload.get("options", []), ensure_ascii=False),
                            payload.get("answer", ""),
                            payload.get("explanation", ""),
                            int(payload["difficulty"]) if payload.get("difficulty") is not None else 0,
                            json.dumps(payload.get("tags", []), ensure_ascii=False),
                            user_id,
                        ),
                    )
                    conn.execute("INSERT INTO bank_question_items(bank_id, question_id) VALUES (?, ?)", (bank_id, new_qid))
                    created_ids.append(new_qid)

        results = []
        for qid in created_ids:
            q = self.get_for_user(qid, user_id)
            if q:
                results.append(q)
        return results

    def get_for_user(self, question_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                """SELECT q.id, qv.id AS version_id, qv.version_number, qv.type,
                          qv.stem, qv.options_json, qv.answer, qv.explanation,
                          qv.difficulty, qv.tags_json, i.bank_id
                   FROM questions q
                   JOIN question_versions qv ON qv.question_id = q.id
                   JOIN bank_question_items i ON i.question_id = q.id
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   WHERE q.id = ? AND qv.version_number = (
                     SELECT MAX(version_number) FROM question_versions WHERE question_id = q.id
                   )""",
                (user_id, question_id),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["options"] = json.loads(result.pop("options_json"))
            result["tags"] = json.loads(result.pop("tags_json"))
            return result

    def get_version_for_user(self, question_id: str, version_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                """SELECT q.id, qv.id AS version_id, qv.version_number, qv.type,
                          qv.stem, qv.options_json, qv.answer, qv.explanation,
                          qv.difficulty, qv.tags_json, i.bank_id
                   FROM questions q JOIN question_versions qv ON qv.question_id = q.id
                   JOIN bank_question_items i ON i.question_id = q.id
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   WHERE q.id = ? AND qv.id = ?""",
                (user_id, question_id, version_id),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["options"] = json.loads(result.pop("options_json"))
            result["tags"] = json.loads(result.pop("tags_json"))
            return result

    def list_for_snapshot(self, snapshot: list[dict], user_id: str) -> list[dict]:
        result = []
        for ref in snapshot:
            question = self.get_version_for_user(ref["question_id"], ref["version_id"], user_id)
            if question:
                result.append(question)
        return result

    def list_for_bank(self, bank_id: str, user_id: str) -> List[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT q.id, qv.id AS version_id, qv.version_number, qv.type,
                          qv.stem, qv.options_json, qv.answer, qv.explanation,
                          qv.difficulty, qv.tags_json, i.bank_id
                   FROM bank_question_items i
                   JOIN questions q ON q.id = i.question_id
                   JOIN question_versions qv ON qv.question_id = q.id
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   LEFT JOIN kill_records k ON k.question_id = q.id AND k.user_id = ?
                   WHERE i.bank_id = ? AND qv.version_number = (
                     SELECT MAX(version_number) FROM question_versions WHERE question_id = q.id
                   ) AND k.question_id IS NULL ORDER BY q.created_at ASC""",
                (user_id, user_id, bank_id),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["options"] = json.loads(item.pop("options_json"))
                item["tags"] = json.loads(item.pop("tags_json"))
                result.append(item)
            return result

    def list_for_elimination(self, bank_id: str, user_id: str) -> List[dict]:
        """Return only questions explicitly killed by this user in an accessible bank."""
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT q.id, qv.id AS version_id, qv.version_number, qv.type,
                          qv.stem, qv.options_json, qv.answer, qv.explanation,
                          qv.difficulty, qv.tags_json, i.bank_id
                   FROM bank_question_items i
                   JOIN questions q ON q.id = i.question_id
                   JOIN question_versions qv ON qv.question_id = q.id
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   JOIN kill_records k ON k.question_id = q.id AND k.user_id = ?
                   WHERE i.bank_id = ? AND qv.version_number = (
                     SELECT MAX(version_number) FROM question_versions WHERE question_id = q.id
                   ) ORDER BY q.created_at ASC""",
                (user_id, user_id, bank_id),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["options"] = json.loads(item.pop("options_json"))
                item["tags"] = json.loads(item.pop("tags_json"))
                result.append(item)
            return result

    def create_next_version(self, user_id: str, question_id: str, payload: Dict[str, Any]) -> dict:
        with transaction(self.db_path) as conn:
            access = conn.execute(
                """SELECT i.bank_id FROM bank_question_items i
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   WHERE i.question_id = ? LIMIT 1""",
                (user_id, question_id),
            ).fetchone()
            if not access:
                raise PermissionError("user cannot edit this question")
            current = conn.execute("SELECT COALESCE(MAX(version_number), 0) FROM question_versions WHERE question_id = ?", (question_id,)).fetchone()[0]
            next_ver = current + 1
            version_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO question_versions(
                    id, question_id, version_number, type, stem, options_json, answer,
                    explanation, difficulty, tags_json, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    version_id, question_id, next_ver, payload.get("type", "SINGLE"), payload["stem"],
                    json.dumps(payload.get("options", []), ensure_ascii=False), payload.get("answer", ""),
                    payload.get("explanation", ""), int(payload["difficulty"]) if payload.get("difficulty") is not None else 0,
                    json.dumps(payload.get("tags", []), ensure_ascii=False), user_id,
                ),
            )
            base_ver = payload.get("base_version_number")
            if base_ver is not None and int(base_ver) < current:
                conflict_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO question_conflicts(id, question_id, user_id, base_version_number, server_version_number, client_version_number, is_resolved)
                       VALUES (?, ?, ?, ?, ?, ?, 0)""",
                    (conflict_id, question_id, user_id, int(base_ver), current, next_ver),
                )
        return self.get_for_user(question_id, user_id)

    def get_active_conflict(self, question_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                """SELECT id, question_id, user_id, base_version_number, server_version_number, client_version_number, is_resolved, created_at
                   FROM question_conflicts
                   WHERE question_id = ? AND is_resolved = 0
                   ORDER BY created_at DESC LIMIT 1""",
                (question_id,),
            ).fetchone()
            return dict(row) if row else None

    def resolve_conflict(self, user_id: str, question_id: str, adopt_version_number: int) -> dict:
        with transaction(self.db_path) as conn:
            access = conn.execute(
                """SELECT i.bank_id FROM bank_question_items i
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   WHERE i.question_id = ? LIMIT 1""",
                (user_id, question_id),
            ).fetchone()
            if not access:
                raise PermissionError("user cannot edit this question")
            target = conn.execute(
                """SELECT type, stem, options_json, answer, explanation, difficulty, tags_json
                   FROM question_versions WHERE question_id = ? AND version_number = ?""",
                (question_id, adopt_version_number),
            ).fetchone()
            if not target:
                raise LookupError("target version not found")
            current = conn.execute("SELECT COALESCE(MAX(version_number), 0) FROM question_versions WHERE question_id = ?", (question_id,)).fetchone()[0]
            new_version_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO question_versions(
                    id, question_id, version_number, type, stem, options_json, answer,
                    explanation, difficulty, tags_json, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_version_id, question_id, current + 1, target[0], target[1],
                    target[2], target[3], target[4], target[5], target[6], user_id,
                ),
            )
            conn.execute(
                """UPDATE question_conflicts
                   SET is_resolved = 1, resolved_version_number = ?, resolved_at = CURRENT_TIMESTAMP
                   WHERE question_id = ? AND is_resolved = 0""",
                (current + 1, question_id),
            )
        return self.get_for_user(question_id, user_id)

    def copy_to_bank(self, user_id: str, source_question_id: str, target_bank_id: str) -> dict:
        """Copy the current content into a new question identity for a bank."""
        new_question_id = str(uuid.uuid4())
        new_version_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            target = conn.execute(
                "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
                (target_bank_id, user_id),
            ).fetchone()
            source = conn.execute(
                """SELECT qv.type, qv.stem, qv.options_json, qv.answer, qv.explanation,
                          qv.difficulty, qv.tags_json
                   FROM question_versions qv
                   JOIN bank_question_items i ON i.question_id = qv.question_id
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   WHERE qv.question_id = ?
                     AND qv.version_number = (SELECT MAX(version_number) FROM question_versions WHERE question_id = ?)""",
                (user_id, source_question_id, source_question_id),
            ).fetchone()
            if not target or target[0] not in ("ADMIN", "EDITOR"):
                raise PermissionError("user cannot edit this question bank")
            if not source:
                raise LookupError("source question not found")
            conn.execute("INSERT INTO questions(id, created_by) VALUES (?, ?)", (new_question_id, user_id))
            conn.execute(
                """INSERT INTO question_versions(
                    id, question_id, version_number, type, stem, options_json, answer,
                    explanation, difficulty, tags_json, created_by
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_version_id, new_question_id, source[0], source[1], source[2], source[3], source[4], source[5], source[6], user_id),
            )
            conn.execute("INSERT INTO bank_question_items(bank_id, question_id) VALUES (?, ?)", (target_bank_id, new_question_id))
        return self.get_for_user(new_question_id, user_id)

    def list_versions(self, question_id: str, user_id: str) -> List[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT qv.id, qv.question_id, qv.version_number, qv.type, qv.stem,
                          qv.options_json, qv.answer, qv.explanation, qv.difficulty,
                          qv.tags_json, qv.created_by, qv.created_at
                   FROM question_versions qv
                   JOIN bank_question_items i ON i.question_id = qv.question_id
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   WHERE qv.question_id = ? ORDER BY qv.version_number ASC""",
                (user_id, question_id),
            ).fetchall()
            values = []
            for row in rows:
                value = dict(row)
                value["options"] = json.loads(value.pop("options_json"))
                value["tags"] = json.loads(value.pop("tags_json"))
                values.append(value)
            return values
