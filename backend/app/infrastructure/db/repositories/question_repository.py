from datetime import datetime, timezone
import json
import uuid
from typing import Any, Dict, List

from backend.app.infrastructure.db.connection import transaction


class VersionConflictError(Exception):
    def __init__(self, message: str, base_version_number: int, current_version_number: int):
        super().__init__(message)
        self.message = message
        self.base_version_number = base_version_number
        self.current_version_number = current_version_number

    def to_dict(self) -> dict:
        return {
            "error": "version_conflict",
            "message": self.message,
            "base_version_number": self.base_version_number,
            "current_version_number": self.current_version_number,
        }


class QuestionRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def create_versioned_question(self, user_id: str, bank_id: str, payload: Dict[str, Any], conn=None) -> dict:
        if conn is not None:
            return self._create_versioned_question_on_conn(conn, user_id, bank_id, payload)
        with transaction(self.db_path) as c:
            return self._create_versioned_question_on_conn(c, user_id, bank_id, payload)

    def _create_versioned_question_on_conn(self, conn, user_id: str, bank_id: str, payload: Dict[str, Any]) -> dict:
        from backend.app.domain.content.validators import validate_question_invariants
        norm_type, norm_ans, norm_opts = validate_question_invariants(
            payload.get("type", "SINGLE"),
            payload.get("stem", ""),
            payload.get("options", []),
            payload.get("answer", ""),
        )
        payload = {**payload, "type": norm_type, "answer": norm_ans, "options": norm_opts}
        question_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        member = conn.execute(
            "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
            (bank_id, user_id),
        ).fetchone()
        if not member or member[0] not in ("ADMIN", "EDITOR"):
            raise PermissionError("user cannot edit this question bank")
        if payload.get("chapter_id"):
            chap = conn.execute("SELECT 1 FROM chapters WHERE id = ? AND bank_id = ?", (payload["chapter_id"], bank_id)).fetchone()
            if not chap:
                raise ValueError(f"Chapter '{payload['chapter_id']}' does not belong to bank '{bank_id}'")
        conn.execute("INSERT INTO questions(id, created_by) VALUES (?, ?)", (question_id, user_id))
        conn.execute(
            """INSERT INTO question_versions(
                id, question_id, version_number, type, stem, options_json, answer,
                explanation, difficulty, tags_json, created_by, chapter_id
            ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                payload.get("chapter_id"),
            ),
        )
        # EE-007: Entity-based knowledge tags mapping
        for tag_name in (payload.get("tags") or []):
            t_row = conn.execute("SELECT id FROM knowledge_tags WHERE bank_id = ? AND name = ?", (bank_id, tag_name)).fetchone()
            if not t_row:
                tag_id = str(uuid.uuid4())
                conn.execute("INSERT INTO knowledge_tags(id, bank_id, name) VALUES (?, ?, ?)", (tag_id, bank_id, tag_name))
            else:
                tag_id = t_row[0]
            conn.execute("INSERT OR IGNORE INTO question_tag_items(question_version_id, tag_id) VALUES (?, ?)", (version_id, tag_id))
        conn.execute("INSERT INTO bank_question_items(bank_id, question_id) VALUES (?, ?)", (bank_id, question_id))
        return self.get_for_user(question_id, user_id, conn=conn)

    def batch_create_or_update_questions(
        self,
        user_id: str,
        bank_id: str,
        operations: List[Dict[str, Any]],
        conn=None,
    ) -> List[Dict[str, Any]]:
        """Atomically insert new questions or create next versions within a single database transaction (EXAM-MASTER pattern)."""
        created_ids = []
        if conn is not None:
            return self._batch_create_or_update_on_conn(conn, user_id, bank_id, operations, created_ids)
        with transaction(self.db_path) as c:
            return self._batch_create_or_update_on_conn(c, user_id, bank_id, operations, created_ids)

    def _batch_create_or_update_on_conn(
        self,
        conn,
        user_id: str,
        bank_id: str,
        operations: List[Dict[str, Any]],
        created_ids: list,
    ):
        member = conn.execute(
            "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
            (bank_id, user_id),
        ).fetchone()
        if not member or member[0] not in ("ADMIN", "EDITOR"):
            raise PermissionError("user cannot edit this question bank")

        active_exam_qids = self._get_active_exam_question_ids(conn)
        for op_info in operations:
            op = op_info.get("op", "create")
            payload = op_info["payload"]
            from backend.app.domain.content.validators import validate_question_invariants
            norm_type, norm_ans, norm_opts = validate_question_invariants(
                payload.get("type", "SINGLE"),
                payload.get("stem", ""),
                payload.get("options", []),
                payload.get("answer", ""),
            )
            payload = {**payload, "type": norm_type, "answer": norm_ans, "options": norm_opts}
            if op == "merge":
                target_qid = op_info["question_id"]
                if target_qid in active_exam_qids:
                    raise PermissionError("cannot edit question while exam is active")
                current_max = conn.execute(
                    "SELECT COALESCE(MAX(version_number), 0) FROM question_versions WHERE question_id = ?",
                    (target_qid,),
                ).fetchone()[0]
                v_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO question_versions(
                        id, question_id, version_number, type, stem, options_json, answer,
                        explanation, difficulty, tags_json, created_by, chapter_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                        payload.get("chapter_id"),
                    ),
                )
                for tag_name in (payload.get("tags") or []):
                    t_row = conn.execute("SELECT id FROM knowledge_tags WHERE bank_id = ? AND name = ?", (bank_id, tag_name)).fetchone()
                    if not t_row:
                        t_id = str(uuid.uuid4())
                        conn.execute("INSERT INTO knowledge_tags(id, bank_id, name) VALUES (?, ?, ?)", (t_id, bank_id, tag_name))
                    else:
                        t_id = t_row[0]
                    conn.execute("INSERT OR IGNORE INTO question_tag_items(question_version_id, tag_id) VALUES (?, ?)", (v_id, t_id))
                created_ids.append(target_qid)
            else:
                new_qid = str(uuid.uuid4())
                new_vid = str(uuid.uuid4())
                conn.execute("INSERT INTO questions(id, created_by) VALUES (?, ?)", (new_qid, user_id))
                conn.execute(
                    """INSERT INTO question_versions(
                        id, question_id, version_number, type, stem, options_json, answer,
                        explanation, difficulty, tags_json, created_by, chapter_id
                    ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                        payload.get("chapter_id"),
                    ),
                )
                for tag_name in (payload.get("tags") or []):
                    t_row = conn.execute("SELECT id FROM knowledge_tags WHERE bank_id = ? AND name = ?", (bank_id, tag_name)).fetchone()
                    if not t_row:
                        t_id = str(uuid.uuid4())
                        conn.execute("INSERT INTO knowledge_tags(id, bank_id, name) VALUES (?, ?, ?)", (t_id, bank_id, tag_name))
                    else:
                        t_id = t_row[0]
                    conn.execute("INSERT OR IGNORE INTO question_tag_items(question_version_id, tag_id) VALUES (?, ?)", (new_vid, t_id))
                conn.execute("INSERT INTO bank_question_items(bank_id, question_id) VALUES (?, ?)", (bank_id, new_qid))
                created_ids.append(new_qid)

        results = []
        for qid in created_ids:
            q = self.get_for_user(qid, user_id, conn=conn)
            if q:
                results.append(q)
        return results

    # ------------------------------------------------------------------
    # Content batch operations (EE-030): all-or-nothing metadata moves.
    # ------------------------------------------------------------------
    BATCH_OPERATIONS = {"chapter", "add_tags", "remove_tags", "move", "copy", "archive", "restore"}
    BATCH_LIMIT = 500

    def _require_bank_editor(self, conn, bank_id: str, user_id: str, message: str) -> str:
        row = conn.execute(
            "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
            (bank_id, user_id),
        ).fetchone()
        if not row or row[0] not in ("ADMIN", "EDITOR"):
            raise PermissionError(message)
        return row[0]

    def _sync_version_tags(self, conn, bank_id: str, version_id: str, tags: List[str]) -> None:
        """Make question_tag_items exactly match the given tag names for one version."""
        conn.execute("DELETE FROM question_tag_items WHERE question_version_id = ?", (version_id,))
        for tag_name in tags or []:
            name = str(tag_name or "").strip()
            if not name:
                continue
            row = conn.execute(
                "SELECT id FROM knowledge_tags WHERE bank_id = ? AND name = ?",
                (bank_id, name),
            ).fetchone()
            if row:
                tag_id = row[0]
            else:
                tag_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO knowledge_tags(id, bank_id, name) VALUES (?, ?, ?)",
                    (tag_id, bank_id, name),
                )
            conn.execute(
                "INSERT OR IGNORE INTO question_tag_items(question_version_id, tag_id) VALUES (?, ?)",
                (version_id, tag_id),
            )

    def _map_chapter_to_bank(self, conn, source_chapter_id: str | None, target_bank_id: str) -> str | None:
        if not source_chapter_id:
            return None
        source = conn.execute("SELECT name FROM chapters WHERE id = ?", (source_chapter_id,)).fetchone()
        if not source:
            return None
        existing = conn.execute(
            "SELECT id FROM chapters WHERE bank_id = ? AND name = ?",
            (target_bank_id, source[0]),
        ).fetchone()
        if existing:
            return existing[0]
        chapter_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO chapters(id, bank_id, name) VALUES (?, ?, ?)",
            (chapter_id, target_bank_id, source[0]),
        )
        return chapter_id

    def _copy_latest_on_conn(self, conn, user_id: str, target_bank_id: str, source: dict) -> str:
        new_question_id = str(uuid.uuid4())
        new_version_id = str(uuid.uuid4())
        chapter_id = self._map_chapter_to_bank(conn, source.get("chapter_id"), target_bank_id)
        tags = json.loads(source.get("tags_json") or "[]")
        conn.execute("INSERT INTO questions(id, created_by) VALUES (?, ?)", (new_question_id, user_id))
        conn.execute(
            """INSERT INTO question_versions(
                id, question_id, version_number, type, stem, options_json, answer,
                explanation, difficulty, tags_json, created_by, chapter_id
            ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_version_id,
                new_question_id,
                source.get("type", "SINGLE"),
                source.get("stem", ""),
                source.get("options_json") or "[]",
                source.get("answer", ""),
                source.get("explanation", ""),
                int(source.get("difficulty") or 0),
                source.get("tags_json") or "[]",
                user_id,
                chapter_id,
            ),
        )
        self._sync_version_tags(conn, target_bank_id, new_version_id, tags)
        conn.execute(
            "INSERT INTO bank_question_items(bank_id, question_id) VALUES (?, ?)",
            (target_bank_id, new_question_id),
        )
        return new_question_id

    def batch_mutate_questions(
        self,
        user_id: str,
        bank_id: str,
        question_ids: List[str],
        operation: str,
        chapter_id: str | None = None,
        tags: List[str] | None = None,
        target_bank_id: str | None = None,
    ) -> dict:
        """Apply one metadata/move/copy/archive operation to a set of bank questions.

        The whole batch is validated before the first write and executes inside a
        single transaction, so a rejected or invalid item leaves no partial state.
        """
        ids: List[str] = []
        seen = set()
        for raw in question_ids or []:
            qid = str(raw or "").strip()
            if qid and qid not in seen:
                ids.append(qid)
                seen.add(qid)
        if not ids:
            raise ValueError("question_ids cannot be empty")
        if len(ids) > self.BATCH_LIMIT:
            raise ValueError(f"batch size cannot exceed {self.BATCH_LIMIT}")

        op = str(operation or "").strip().lower()
        if op not in self.BATCH_OPERATIONS:
            raise ValueError("unsupported batch operation")

        clean_tags: List[str] = []
        for raw in tags or []:
            name = str(raw or "").strip()
            if name and name not in clean_tags:
                clean_tags.append(name)
        if op in {"add_tags", "remove_tags"} and not clean_tags:
            raise ValueError("tags cannot be empty for this operation")

        target_bank_id = (target_bank_id or "").strip() or None
        if op in {"move", "copy"}:
            if not target_bank_id:
                raise ValueError("target_bank_id is required for move/copy")
            if target_bank_id == bank_id:
                raise ValueError("target bank must differ from the source bank")

        with transaction(self.db_path) as conn:
            self._require_bank_editor(conn, bank_id, user_id, "user cannot edit this question bank")
            if op in {"move", "copy"}:
                self._require_bank_editor(conn, target_bank_id, user_id, "user cannot edit the target question bank")
                target_bank = conn.execute(
                    "SELECT 1 FROM question_banks WHERE id = ? AND is_deleted = 0",
                    (target_bank_id,),
                ).fetchone()
                if not target_bank:
                    raise LookupError("target bank not found")

            if op == "chapter" and chapter_id:
                chapter = conn.execute(
                    "SELECT 1 FROM chapters WHERE id = ? AND bank_id = ?",
                    (chapter_id, bank_id),
                ).fetchone()
                if not chapter:
                    raise ValueError("chapter does not belong to this bank")

            rows: List[dict] = []
            for qid in ids:
                row = conn.execute(
                    """SELECT q.id, q.is_deleted, qv.id AS version_id, qv.version_number,
                              qv.type, qv.stem, qv.options_json, qv.answer, qv.explanation,
                              qv.difficulty, qv.tags_json, qv.chapter_id
                       FROM questions q
                       JOIN bank_question_items i ON i.question_id = q.id AND i.bank_id = ?
                       JOIN question_versions qv ON qv.question_id = q.id
                         AND qv.version_number = (
                           SELECT MAX(version_number) FROM question_versions WHERE question_id = q.id
                         )
                       WHERE q.id = ?""",
                    (bank_id, qid),
                ).fetchone()
                if not row:
                    raise LookupError(f"question '{qid}' not found in this bank")
                rows.append(dict(row))

            active_exam_qids = self._get_active_exam_question_ids(conn)
            locked = [row["id"] for row in rows if row["id"] in active_exam_qids]
            if locked:
                raise PermissionError("cannot edit question while exam is active")

            archived = [row["id"] for row in rows if row["is_deleted"]]
            if archived and op not in {"archive", "restore"}:
                raise ValueError("archived questions must be restored before this operation")

            if op == "chapter":
                for row in rows:
                    conn.execute(
                        "UPDATE question_versions SET chapter_id = ? WHERE id = ?",
                        (chapter_id or None, row["version_id"]),
                    )
                    conn.execute(
                        "UPDATE questions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (row["id"],),
                    )
            elif op in {"add_tags", "remove_tags"}:
                for row in rows:
                    current = json.loads(row.get("tags_json") or "[]")
                    if op == "add_tags":
                        next_tags = current + [name for name in clean_tags if name not in current]
                    else:
                        remove_set = set(clean_tags)
                        next_tags = [name for name in current if name not in remove_set]
                    if next_tags == current:
                        continue
                    conn.execute(
                        "UPDATE question_versions SET tags_json = ? WHERE id = ?",
                        (json.dumps(next_tags, ensure_ascii=False), row["version_id"]),
                    )
                    self._sync_version_tags(conn, bank_id, row["version_id"], next_tags)
                    conn.execute(
                        "UPDATE questions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (row["id"],),
                    )
            elif op == "move":
                for row in rows:
                    mapped_chapter = self._map_chapter_to_bank(conn, row.get("chapter_id"), target_bank_id)
                    conn.execute(
                        "UPDATE question_versions SET chapter_id = ? WHERE id = ?",
                        (mapped_chapter, row["version_id"]),
                    )
                    conn.execute(
                        "DELETE FROM bank_question_items WHERE bank_id = ? AND question_id = ?",
                        (bank_id, row["id"]),
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO bank_question_items(bank_id, question_id) VALUES (?, ?)",
                        (target_bank_id, row["id"]),
                    )
                    current = json.loads(row.get("tags_json") or "[]")
                    self._sync_version_tags(conn, target_bank_id, row["version_id"], current)
                    conn.execute(
                        "UPDATE questions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (row["id"],),
                    )
            elif op == "copy":
                for row in rows:
                    self._copy_latest_on_conn(conn, user_id, target_bank_id, row)
            else:  # archive / restore
                flag = 1 if op == "archive" else 0
                archived_at_sql = "CURRENT_TIMESTAMP" if op == "archive" else "NULL"
                for row in rows:
                    conn.execute(
                        f"UPDATE questions SET is_deleted = ?, archived_at = {archived_at_sql}, "
                        "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (flag, row["id"]),
                    )

            audit_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO audit_logs(id, user_id, action, entity_type, entity_id, details_json)
                   VALUES (?, ?, 'BANK_QUESTIONS_BATCH', 'BANK', ?, ?)""",
                (
                    audit_id,
                    user_id,
                    bank_id,
                    json.dumps(
                        {
                            "operation": op,
                            "question_ids": ids,
                            "chapter_id": chapter_id,
                            "tags": clean_tags,
                            "target_bank_id": target_bank_id,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

            return {
                "bank_id": bank_id,
                "operation": op,
                "affected": len(rows),
                "question_ids": [row["id"] for row in rows],
                "target_bank_id": target_bank_id if op in {"move", "copy"} else None,
            }

    def _get_active_exam_question_ids(self, c, user_id: str | None = None) -> set:
        from datetime import datetime, timezone
        now_dt = datetime.now(timezone.utc)

        def _is_active(row):
            q_json, time_limit, created_at_str = row
            if time_limit and int(time_limit) > 0 and created_at_str:
                try:
                    c_dt = datetime.fromisoformat(str(created_at_str).replace("Z", "+00:00"))
                    if c_dt.tzinfo is None:
                        c_dt = c_dt.replace(tzinfo=timezone.utc)
                    # 允许 60 秒缓冲区，超出则视为超时失效会话，不再锁定题库题目
                    if (now_dt - c_dt).total_seconds() > int(time_limit) * 60 + 60:
                        return False
                except Exception:
                    pass
            return True

        if user_id:
            rows = c.execute(
                "SELECT questions_json, time_limit, created_at FROM practice_sessions WHERE user_id = ? AND mode = 'EXAM' AND is_completed = 0",
                (user_id,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT questions_json, time_limit, created_at FROM practice_sessions WHERE mode = 'EXAM' AND is_completed = 0",
            ).fetchall()
        exam_qids = set()
        for r in rows:
            if r[0] and _is_active(r):
                try:
                    for item in json.loads(r[0]):
                        qid = item.get("question_id")
                        if qid:
                            exam_qids.add(qid)
                except Exception:
                    pass
        return exam_qids

    def get_for_user(self, question_id: str, user_id: str, conn=None) -> dict | None:
        def _query(c):
            row = c.execute(
                """SELECT q.id, q.is_deleted, q.archived_at, qv.id AS version_id, qv.version_number, qv.type,
                          qv.stem, qv.options_json, qv.answer, qv.explanation,
                          qv.difficulty, qv.tags_json, qv.chapter_id, i.bank_id
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
            result["archived"] = bool(result.pop("is_deleted"))
            result["options"] = json.loads(result.pop("options_json"))
            result["tags"] = json.loads(result.pop("tags_json"))
            if result["id"] in self._get_active_exam_question_ids(c, user_id):
                result["answer"] = ""
                result["explanation"] = ""
            result["locked_by_active_exam"] = result["id"] in self._get_active_exam_question_ids(c)
            return result

        if conn is not None:
            return _query(conn)
        with transaction(self.db_path) as c:
            return _query(c)

    def get_version_for_user(self, question_id: str, version_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                """SELECT q.id, qv.id AS version_id, qv.version_number, qv.type,
                          qv.stem, qv.options_json, qv.answer, qv.explanation,
                          qv.difficulty, qv.tags_json, qv.chapter_id, i.bank_id
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

    def get_version_for_session(self, question_id: str, version_id: str, user_id: str, session_id: str) -> dict | None:
        """Resolve a question version that this user's own session snapshot pinned.

        A question may be moved to another bank (or archived) while a member is
        still mid-session. The snapshot taken at session start is the contract
        that keeps that in-progress practice working: it is proof of prior
        access to this exact version. We therefore resolve the version without
        requiring current bank membership, but only when the user owns a
        session whose snapshot actually contains that question + version.
        """
        with transaction(self.db_path) as conn:
            session = conn.execute(
                "SELECT questions_json FROM practice_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
            if not session:
                return None
            try:
                snapshot = json.loads(session[0] or "[]")
            except (TypeError, ValueError):
                return None
            if not any(
                item.get("question_id") == question_id and item.get("version_id") == version_id
                for item in snapshot
                if isinstance(item, dict)
            ):
                return None
            row = conn.execute(
                """SELECT q.id, qv.id AS version_id, qv.version_number, qv.type,
                          qv.stem, qv.options_json, qv.answer, qv.explanation,
                          qv.difficulty, qv.tags_json, qv.chapter_id,
                          (SELECT i.bank_id FROM bank_question_items i
                           WHERE i.question_id = q.id LIMIT 1) AS bank_id
                   FROM questions q JOIN question_versions qv ON qv.question_id = q.id
                   WHERE q.id = ? AND qv.id = ?""",
                (question_id, version_id),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["options"] = json.loads(result.pop("options_json"))
            result["tags"] = json.loads(result.pop("tags_json"))
            return result

    def list_for_snapshot(self, snapshot: list[dict], user_id: str, session_id: str | None = None) -> list[dict]:
        result = []
        with transaction(self.db_path) as conn:
            active_exam_qids = self._get_active_exam_question_ids(conn, user_id)
        for ref in snapshot:
            question = None
            if session_id is not None:
                question = self.get_version_for_session(ref["question_id"], ref["version_id"], user_id, session_id)
            if question is None:
                question = self.get_version_for_user(ref["question_id"], ref["version_id"], user_id)
            if question:
                # Keep historical stats attributed to the bank the question was
                # reached through when the session started, even if it has since
                # been moved to another bank.
                if ref.get("bank_id"):
                    question["bank_id"] = ref["bank_id"]
                if question["id"] in active_exam_qids:
                    question["answer"] = ""
                    question["explanation"] = ""
                result.append(question)
        return result

    def list_for_bank(self, bank_id: str, user_id: str) -> List[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT q.id, qv.id AS version_id, qv.version_number, qv.type,
                          qv.stem, qv.options_json, qv.answer, qv.explanation,
                          qv.difficulty, qv.tags_json, qv.chapter_id, i.bank_id
                   FROM bank_question_items i
                   JOIN questions q ON q.id = i.question_id
                   JOIN question_versions qv ON qv.question_id = q.id
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   LEFT JOIN kill_records k ON k.question_id = q.id AND k.user_id = ?
                   WHERE i.bank_id = ? AND q.is_deleted = 0 AND qv.version_number = (
                     SELECT MAX(version_number) FROM question_versions WHERE question_id = q.id
                   ) AND k.question_id IS NULL ORDER BY q.created_at ASC, q.rowid ASC""",
                (user_id, user_id, bank_id),
            ).fetchall()
            result = []
            active_qids = self._get_active_exam_question_ids(conn, user_id)
            for row in rows:
                item = dict(row)
                item["options"] = json.loads(item.pop("options_json"))
                item["tags"] = json.loads(item.pop("tags_json"))
                if item["id"] in active_qids:
                    item["answer"] = ""
                    item["explanation"] = ""
                result.append(item)
            return result

    def list_content_for_bank(self, bank_id: str, user_id: str, include_archived: bool = False) -> List[dict]:
        """Return all questions belonging to the bank for content management without personal study/kill filtering."""
        archive_clause = "" if include_archived else "AND q.is_deleted = 0"
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                f"""SELECT q.id, q.is_deleted, q.archived_at, qv.id AS version_id, qv.version_number, qv.type,
                          qv.stem, qv.options_json, qv.answer, qv.explanation,
                          qv.difficulty, qv.tags_json, qv.chapter_id, i.bank_id
                   FROM bank_question_items i
                   JOIN questions q ON q.id = i.question_id
                   JOIN question_versions qv ON qv.question_id = q.id
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   WHERE i.bank_id = ? {archive_clause} AND qv.version_number = (
                     SELECT MAX(version_number) FROM question_versions WHERE question_id = q.id
                   ) ORDER BY q.created_at ASC, q.rowid ASC""",
                (user_id, bank_id),
            ).fetchall()
            result = []
            active_qids = self._get_active_exam_question_ids(conn, user_id)
            global_active_qids = self._get_active_exam_question_ids(conn)
            # Tag entities are authoritative for current naming; tags_json on the
            # version stays an immutable historical snapshot (P2-2).
            tag_links: dict[str, list[str]] = {}
            has_links = conn.execute(
                """SELECT 1 FROM question_tag_items qti
                   JOIN question_versions qv ON qv.id = qti.question_version_id
                   JOIN bank_question_items i ON i.question_id = qv.question_id
                   WHERE i.bank_id = ? LIMIT 1""",
                (bank_id,),
            ).fetchone() is not None
            if has_links:
                for link in conn.execute(
                    """SELECT qti.question_version_id AS version_id, t.name AS name
                       FROM question_tag_items qti
                       JOIN question_versions qv ON qv.id = qti.question_version_id
                       JOIN bank_question_items i ON i.question_id = qv.question_id AND i.bank_id = ?
                       JOIN knowledge_tags t ON t.id = qti.tag_id
                       ORDER BY t.name""",
                    (bank_id,),
                ).fetchall():
                    tag_links.setdefault(link["version_id"], []).append(link["name"])
            for row in rows:
                item = dict(row)
                item["options"] = json.loads(item.pop("options_json"))
                snapshot_tags = json.loads(item.pop("tags_json") or "[]")
                item["tags"] = tag_links.get(item["version_id"], []) if has_links else snapshot_tags
                item["archived"] = bool(item.pop("is_deleted"))
                if item["id"] in active_qids:
                    item["answer"] = ""
                    item["explanation"] = ""
                item["locked_by_active_exam"] = item["id"] in global_active_qids
                result.append(item)
            return result

    def list_for_elimination(self, bank_id: str, user_id: str) -> List[dict]:
        """Return only questions explicitly killed by this user in an accessible bank."""
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT q.id, qv.id AS version_id, qv.version_number, qv.type,
                          qv.stem, qv.options_json, qv.answer, qv.explanation,
                          qv.difficulty, qv.tags_json, qv.chapter_id, i.bank_id
                   FROM bank_question_items i
                   JOIN questions q ON q.id = i.question_id
                   JOIN question_versions qv ON qv.question_id = q.id
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   JOIN kill_records k ON k.question_id = q.id AND k.user_id = ?
                   WHERE i.bank_id = ? AND q.is_deleted = 0 AND qv.version_number = (
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
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ? AND m.role IN ('ADMIN', 'EDITOR')
                   WHERE i.question_id = ? LIMIT 1""",
                (user_id, question_id),
            ).fetchone()
            if not access:
                raise PermissionError("user cannot edit this question")
            archived = conn.execute("SELECT is_deleted FROM questions WHERE id = ?", (question_id,)).fetchone()
            if archived and archived[0]:
                raise ValueError("archived question must be restored before editing")
            if question_id in self._get_active_exam_question_ids(conn):
                raise PermissionError("cannot edit question while exam is active")
            from backend.app.domain.content.validators import validate_question_invariants
            norm_type, norm_ans, norm_opts = validate_question_invariants(
                payload.get("type", "SINGLE"), payload.get("stem", ""), payload.get("options", []), payload.get("answer", "")
            )
            payload["type"] = norm_type
            payload["answer"] = norm_ans
            payload["options"] = norm_opts
            current = conn.execute("SELECT COALESCE(MAX(version_number), 0) FROM question_versions WHERE question_id = ?", (question_id,)).fetchone()[0]
            base_ver = payload.get("base_version_number")
            if base_ver is not None and int(base_ver) < current:
                should_reject = payload.get("reject_stale", False) or not payload.get("allow_stale_branch", True)
                if should_reject:
                    conflict_id = str(uuid.uuid4())
                    conn.execute(
                        """INSERT INTO question_conflicts(id, question_id, user_id, base_version_number, server_version_number, client_version_number, is_resolved)
                           VALUES (?, ?, ?, ?, ?, ?, 0)""",
                        (conflict_id, question_id, user_id, int(base_ver), current, current),
                    )
                    conn.commit()
                    raise VersionConflictError(
                        message="Question has been modified by another user. Reload the latest version before editing.",
                        base_version_number=int(base_ver),
                        current_version_number=current,
                    )
            next_ver = current + 1
            version_id = str(uuid.uuid4())
            prev_chap = conn.execute("SELECT chapter_id FROM question_versions WHERE question_id = ? AND version_number = ?", (question_id, current)).fetchone()
            bank_id = access[0]
            if "chapter_id" in payload:
                chap_id = payload.get("chapter_id") or None
                if chap_id:
                    chap = conn.execute("SELECT 1 FROM chapters WHERE id = ? AND bank_id = ?", (chap_id, bank_id)).fetchone()
                    if not chap:
                        raise ValueError(f"Chapter '{chap_id}' does not belong to bank '{bank_id}'")
            else:
                chap_id = prev_chap[0] if prev_chap else None
            conn.execute(
                """INSERT INTO question_versions(
                    id, question_id, version_number, type, stem, options_json, answer,
                    explanation, difficulty, tags_json, created_by, chapter_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    version_id, question_id, next_ver, payload.get("type", "SINGLE"), payload["stem"],
                    json.dumps(payload.get("options", []), ensure_ascii=False), payload.get("answer", ""),
                    payload.get("explanation", ""), int(payload["difficulty"]) if payload.get("difficulty") is not None else 0,
                    json.dumps(payload.get("tags", []), ensure_ascii=False), user_id,
                    chap_id,
                ),
            )
            # EE-007: Entity-based knowledge tags mapping
            bank_id = access[0]
            for tag_name in (payload.get("tags") or []):
                t_row = conn.execute("SELECT id FROM knowledge_tags WHERE bank_id = ? AND name = ?", (bank_id, tag_name)).fetchone()
                if not t_row:
                    tag_id = str(uuid.uuid4())
                    conn.execute("INSERT INTO knowledge_tags(id, bank_id, name) VALUES (?, ?, ?)", (tag_id, bank_id, tag_name))
                else:
                    tag_id = t_row[0]
                conn.execute("INSERT OR IGNORE INTO question_tag_items(question_version_id, tag_id) VALUES (?, ?)", (version_id, tag_id))
            base_ver = payload.get("base_version_number")
            if base_ver is not None and int(base_ver) < current:
                conflict_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO question_conflicts(id, question_id, user_id, base_version_number, server_version_number, client_version_number, is_resolved)
                       VALUES (?, ?, ?, ?, ?, ?, 0)""",
                    (conflict_id, question_id, user_id, int(base_ver), current, next_ver),
                )
            if payload.get("regrade_history"):
                self._execute_regrade_on_conn(
                    conn,
                    user_id=user_id,
                    question_id=question_id,
                    bank_id=bank_id,
                    q_type=payload.get("type", "SINGLE"),
                    q_answer=payload.get("answer", ""),
                    q_explanation=payload.get("explanation", ""),
                    apply_fsrs=payload.get("apply_fsrs", True),
                )
        return self.get_for_user(question_id, user_id)

    def regrade_question_history(self, user_id: str, question_id: str, apply_fsrs: bool = True) -> dict:
        with transaction(self.db_path) as conn:
            access = conn.execute(
                """SELECT i.bank_id FROM bank_question_items i
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ? AND m.role IN ('ADMIN', 'EDITOR')
                   WHERE i.question_id = ? LIMIT 1""",
                (user_id, question_id),
            ).fetchone()
            if not access:
                raise PermissionError("user cannot edit or regrade this question")

            q_row = conn.execute(
                """SELECT q.id, qv.type, qv.answer, qv.explanation, qv.version_number
                   FROM questions q
                   JOIN question_versions qv ON qv.question_id = q.id
                   WHERE q.id = ?
                   ORDER BY qv.version_number DESC LIMIT 1""",
                (question_id,),
            ).fetchone()
            if not q_row:
                raise LookupError("question not found")

            return self._execute_regrade_on_conn(
                conn,
                user_id=user_id,
                question_id=question_id,
                bank_id=access[0],
                q_type=q_row["type"],
                q_answer=q_row["answer"],
                q_explanation=q_row["explanation"],
                apply_fsrs=apply_fsrs,
            )

    @staticmethod
    def _session_records_mistakes_on_conn(conn, session_row) -> bool:
        """Whether this session participates in personal mistake/learning state."""
        try:
            cfg = json.loads(session_row["config_json"] or "{}")
        except (TypeError, ValueError):
            cfg = {}
        if "record_mistakes" in cfg:
            return bool(cfg["record_mistakes"])
        if session_row["mode"] == "EXAM" and session_row["blueprint_id"]:
            bp_row = conn.execute(
                "SELECT blueprint_json FROM exam_blueprints WHERE id = ?",
                (session_row["blueprint_id"],),
            ).fetchone()
            if bp_row:
                try:
                    bp_dict = json.loads(bp_row[0] or "{}")
                except (TypeError, ValueError):
                    bp_dict = {}
                if "record_mistakes" in bp_dict:
                    return bool(bp_dict["record_mistakes"])
        return True

    def _execute_regrade_on_conn(
        self,
        conn,
        user_id: str,
        question_id: str,
        bank_id: str,
        q_type: str,
        q_answer: str,
        q_explanation: str,
        apply_fsrs: bool = True,
    ) -> dict:
        from backend.app.domain.learning.scoring import score_answer
        from backend.app.infrastructure.learning.fsrs_adapter import FSRS5 as FSRS
        fsrs = FSRS()

        attempts = conn.execute(
            """SELECT id, user_id, session_id, user_answer_json, score_ratio, correctness, mastery_status,
                      fsrs_rating, mistake_cause, card_snapshot_json, created_at
               FROM answer_attempts
               WHERE question_id = ?
               ORDER BY created_at ASC""",
            (question_id,),
        ).fetchall()

        regraded_count = 0
        affected_sessions = set()
        affected_users = set()
        # Sessions that opted out of mistake recording must not start producing
        # mistake records merely because their history is being re-graded.
        session_records_mistakes: dict[str, bool] = {}

        for att in attempts:
            att_id = att["id"]
            uid = att["user_id"]
            sess_id = att["session_id"]
            affected_users.add(uid)
            affected_sessions.add(sess_id)

            try:
                user_ans = json.loads(att["user_answer_json"])
            except Exception:
                user_ans = att["user_answer_json"]

            scored = score_answer(q_type, user_ans, q_answer)
            new_score = scored["score_ratio"]
            new_corr = scored["correctness"]
            new_mastery = scored["mastery_status"]

            conn.execute(
                """UPDATE answer_attempts
                   SET score_ratio = ?, correctness = ?, mastery_status = ?
                   WHERE id = ?""",
                (new_score, new_corr, new_mastery, att_id),
            )
            regraded_count += 1

            sess_row = conn.execute(
                "SELECT id, answers_json, mode, config_json, blueprint_id FROM practice_sessions WHERE id = ?",
                (sess_id,),
            ).fetchone()
            if sess_row and sess_id not in session_records_mistakes:
                session_records_mistakes[sess_id] = self._session_records_mistakes_on_conn(conn, sess_row)
            if sess_row and sess_row["answers_json"]:
                try:
                    ans_dict = json.loads(sess_row["answers_json"])
                    if question_id in ans_dict:
                        ans_dict[question_id]["is_correct"] = (new_corr == "CORRECT")
                        ans_dict[question_id]["score_ratio"] = new_score
                        ans_dict[question_id]["correctness"] = new_corr
                        ans_dict[question_id]["mastery_status"] = new_mastery
                        ans_dict[question_id]["correct_answer"] = q_answer
                        ans_dict[question_id]["explanation"] = q_explanation
                        conn.execute("UPDATE practice_sessions SET answers_json = ? WHERE id = ?", (json.dumps(ans_dict, ensure_ascii=False), sess_id))
                except Exception:
                    pass

        for uid in affected_users:
            user_attempts = conn.execute(
                """SELECT session_id, correctness, mastery_status, created_at, fsrs_rating, card_snapshot_json
                   FROM answer_attempts
                   WHERE user_id = ? AND question_id = ?
                   ORDER BY created_at ASC""",
                (uid, question_id),
            ).fetchall()
            if not user_attempts:
                continue

            # Only attempts from sessions that actually recorded mistakes take
            # part in mistake/mastery/FSRS reconstruction. An exam session with
            # record_mistakes=False never wrote personal learning state, so a
            # regrade must not invent one.
            relevant = [
                uatt for uatt in user_attempts
                if session_records_mistakes.get(uatt["session_id"], True)
            ]
            if not relevant:
                continue

            mistakes = 0
            consecutive = 0
            for uatt in relevant:
                corr = uatt["correctness"]
                if corr == "CORRECT":
                    consecutive += 1
                elif corr in {"INCORRECT", "PARTIAL"}:
                    consecutive = 0
                    mistakes += 1
            cleared = int(consecutive >= 2)
            last_mastery = relevant[-1]["mastery_status"]

            conn.execute(
                """INSERT INTO learning_records(user_id, question_id, mistake_count, consecutive_correct, mastery_status, is_cleared, last_attempt_at)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(user_id, question_id) DO UPDATE SET
                     mistake_count=excluded.mistake_count,
                     consecutive_correct=excluded.consecutive_correct,
                     mastery_status=excluded.mastery_status,
                     is_cleared=excluded.is_cleared""",
                (uid, question_id, mistakes, consecutive, last_mastery, cleared),
            )

            if mistakes > 0:
                conn.execute(
                    """INSERT INTO mistake_records(
                         user_id, question_id, bank_id, mistake_count, consecutive_correct, is_cleared, last_review_at
                       ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(user_id, question_id) DO UPDATE SET
                         bank_id=excluded.bank_id,
                         mistake_count=excluded.mistake_count,
                         consecutive_correct=excluded.consecutive_correct,
                         is_cleared=excluded.is_cleared,
                         updated_at=CURRENT_TIMESTAMP""",
                    (uid, question_id, bank_id, mistakes, consecutive, int(cleared or mistakes == 0)),
                )
            else:
                conn.execute(
                    """UPDATE mistake_records SET mistake_count = 0, consecutive_correct = ?, is_cleared = 1, updated_at = CURRENT_TIMESTAMP
                       WHERE user_id = ? AND question_id = ?""",
                    (consecutive, uid, question_id),
                )

            if apply_fsrs:
                # Regrading must never fabricate an FSRS rating. An attempt that
                # was never rated (or has no truthful pre-attempt snapshot) has
                # no baseline to replay from, so the existing card is left
                # untouched instead of being reset or double-scheduled.
                first_att = relevant[0]
                can_replay = (
                    bool(first_att["card_snapshot_json"])
                    and all(uatt["fsrs_rating"] is not None for uatt in relevant)
                )
                if can_replay:
                    card_state = 0
                    card_stability = 0.0
                    card_diff = 5.0
                    last_rev = None
                    last_due = datetime.now(timezone.utc)

                    try:
                        snap = json.loads(first_att["card_snapshot_json"])
                        card_state = snap.get("state", 0)
                        card_stability = float(snap.get("stability", 0.0))
                        card_diff = float(snap.get("difficulty", 5.0))
                        if snap.get("last_review_at"):
                            last_rev = datetime.fromisoformat(snap["last_review_at"])
                    except Exception:
                        pass

                    for uatt in relevant:
                        rating = uatt["fsrs_rating"]
                        att_time = datetime.fromisoformat(uatt["created_at"]) if uatt["created_at"] else datetime.now(timezone.utc)
                        if att_time.tzinfo is None:
                            att_time = att_time.replace(tzinfo=timezone.utc)

                        elapsed = 0.0
                        if last_rev:
                            if last_rev.tzinfo is None:
                                last_rev = last_rev.replace(tzinfo=timezone.utc)
                            elapsed = max(0.0, (att_time - last_rev).total_seconds() / 86400)

                        res = fsrs.schedule(rating=rating, stability=card_stability, difficulty=card_diff, elapsed_days=elapsed, now=att_time)
                        card_state = res.state
                        card_stability = res.stability
                        card_diff = res.difficulty
                        last_rev = att_time
                        last_due = res.due

                    conn.execute(
                        """INSERT INTO fsrs_cards(user_id, question_id, state, stability, difficulty, due_at, last_review_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(user_id, question_id) DO UPDATE SET
                             state=excluded.state, stability=excluded.stability,
                             difficulty=excluded.difficulty, due_at=excluded.due_at,
                             last_review_at=excluded.last_review_at""",
                        (uid, question_id, card_state, card_stability, card_diff, last_due.isoformat(), last_rev.isoformat()),
                    )

        audit_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO audit_logs(id, user_id, action, entity_type, entity_id, details_json)
               VALUES (?, ?, 'QUESTION_REGRADED', 'QUESTION', ?, ?)""",
            (audit_id, user_id, question_id, json.dumps({
                "regraded_attempts": regraded_count,
                "affected_sessions": len(affected_sessions),
                "affected_users": len(affected_users),
                "new_answer": q_answer,
                "apply_fsrs": apply_fsrs,
            }, ensure_ascii=False)),
        )

        return {
            "question_id": question_id,
            "regraded_attempts": regraded_count,
            "affected_sessions": len(affected_sessions),
            "affected_users": len(affected_users),
        }

    def get_active_conflict(self, question_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            access = conn.execute(
                """SELECT i.bank_id FROM bank_question_items i
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   WHERE i.question_id = ? LIMIT 1""",
                (user_id, question_id),
            ).fetchone()
            if not access:
                raise PermissionError("user has no access to this question bank")
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
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ? AND m.role IN ('ADMIN', 'EDITOR')
                   WHERE i.question_id = ? LIMIT 1""",
                (user_id, question_id),
            ).fetchone()
            if not access:
                raise PermissionError("user cannot edit this question")
            archived = conn.execute("SELECT is_deleted FROM questions WHERE id = ?", (question_id,)).fetchone()
            if archived and archived[0]:
                raise ValueError("archived question must be restored before editing")
            if question_id in self._get_active_exam_question_ids(conn):
                raise PermissionError("cannot edit question while exam is active")
            target = conn.execute(
                """SELECT type, stem, options_json, answer, explanation, difficulty, tags_json, chapter_id
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
                    explanation, difficulty, tags_json, created_by, chapter_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_version_id, question_id, current + 1, target[0], target[1],
                    target[2], target[3], target[4], target[5], target[6], user_id,
                    target[7],
                ),
            )
            # Re-associate knowledge tags
            bank_id = access[0]
            tags = json.loads(target[6] or "[]")
            for tag_name in tags:
                t_row = conn.execute("SELECT id FROM knowledge_tags WHERE bank_id = ? AND name = ?", (bank_id, tag_name)).fetchone()
                if not t_row:
                    t_id = str(uuid.uuid4())
                    conn.execute("INSERT INTO knowledge_tags(id, bank_id, name) VALUES (?, ?, ?)", (t_id, bank_id, tag_name))
                else:
                    t_id = t_row[0]
                conn.execute("INSERT OR IGNORE INTO question_tag_items(question_version_id, tag_id) VALUES (?, ?)", (new_version_id, t_id))

            conn.execute(
                """UPDATE question_conflicts
                   SET is_resolved = 1, resolved_version_number = ?, resolved_at = CURRENT_TIMESTAMP
                   WHERE question_id = ? AND is_resolved = 0""",
                (current + 1, question_id),
            )
        return self.get_for_user(question_id, user_id)

    def copy_to_bank(self, user_id: str, source_question_id: str, target_bank_id: str) -> dict:
        """Copy the current content into a new question identity for a bank, preserving chapter and tags."""
        new_question_id = str(uuid.uuid4())
        new_version_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            target = conn.execute(
                "SELECT role FROM question_bank_members WHERE bank_id = ? AND user_id = ?",
                (target_bank_id, user_id),
            ).fetchone()
            source = conn.execute(
                """SELECT qv.type, qv.stem, qv.options_json, qv.answer, qv.explanation,
                          qv.difficulty, qv.tags_json, qv.chapter_id
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

            # Check if source chapter exists and match/recreate in target bank if possible
            target_chapter_id = None
            if source[7]:
                src_ch = conn.execute("SELECT name FROM chapters WHERE id = ?", (source[7],)).fetchone()
                if src_ch:
                    tgt_ch = conn.execute("SELECT id FROM chapters WHERE bank_id = ? AND name = ?", (target_bank_id, src_ch[0])).fetchone()
                    if tgt_ch:
                        target_chapter_id = tgt_ch[0]
                    else:
                        target_chapter_id = str(uuid.uuid4())
                        conn.execute("INSERT INTO chapters(id, bank_id, name) VALUES (?, ?, ?)", (target_chapter_id, target_bank_id, src_ch[0]))

            conn.execute("INSERT INTO questions(id, created_by) VALUES (?, ?)", (new_question_id, user_id))
            conn.execute(
                """INSERT INTO question_versions(
                    id, question_id, version_number, type, stem, options_json, answer,
                    explanation, difficulty, tags_json, created_by, chapter_id
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_version_id, new_question_id, source[0], source[1], source[2], source[3], source[4], source[5], source[6], user_id, target_chapter_id),
            )
            # Copy knowledge tags to target bank
            tags = json.loads(source[6] or "[]")
            for tag_name in tags:
                t_row = conn.execute("SELECT id FROM knowledge_tags WHERE bank_id = ? AND name = ?", (target_bank_id, tag_name)).fetchone()
                if not t_row:
                    t_id = str(uuid.uuid4())
                    conn.execute("INSERT INTO knowledge_tags(id, bank_id, name) VALUES (?, ?, ?)", (t_id, target_bank_id, tag_name))
                else:
                    t_id = t_row[0]
                conn.execute("INSERT OR IGNORE INTO question_tag_items(question_version_id, tag_id) VALUES (?, ?)", (new_version_id, t_id))

            conn.execute("INSERT INTO bank_question_items(bank_id, question_id) VALUES (?, ?)", (target_bank_id, new_question_id))
        return self.get_for_user(new_question_id, user_id)

    def list_versions(self, question_id: str, user_id: str) -> List[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT qv.id, qv.question_id, qv.version_number, qv.type, qv.stem,
                          qv.options_json, qv.answer, qv.explanation, qv.difficulty,
                          qv.tags_json, qv.chapter_id, qv.created_by, qv.created_at
                   FROM question_versions qv
                   JOIN bank_question_items i ON i.question_id = qv.question_id
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   WHERE qv.question_id = ? ORDER BY qv.version_number ASC""",
                (user_id, question_id),
            ).fetchall()
            active_qids = self._get_active_exam_question_ids(conn, user_id)
            is_active_exam = question_id in active_qids
            values = []
            for row in rows:
                value = dict(row)
                value["options"] = json.loads(value.pop("options_json"))
                value["tags"] = json.loads(value.pop("tags_json"))
                if is_active_exam:
                    value["answer"] = ""
                    value["explanation"] = ""
                values.append(value)
            return values

    def delete_version(self, user_id: str, question_id: str, version_id: str) -> dict:
        """Delete one non-current history version.

        Current versions, versions referenced by answer attempts, and versions of
        questions locked by an active exam are protected. The whole check and the
        delete run in one transaction.
        """
        with transaction(self.db_path) as conn:
            access = conn.execute(
                """SELECT i.bank_id FROM bank_question_items i
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                     AND m.role IN ('ADMIN', 'EDITOR')
                   WHERE i.question_id = ? LIMIT 1""",
                (user_id, question_id),
            ).fetchone()
            if not access:
                if not conn.execute("SELECT 1 FROM questions WHERE id = ?", (question_id,)).fetchone():
                    raise LookupError("question not found")
                raise PermissionError("user cannot edit this question")

            question_row = conn.execute(
                "SELECT is_deleted FROM questions WHERE id = ?", (question_id,)
            ).fetchone()
            if question_row and question_row[0]:
                raise ValueError("archived question must be restored before editing")

            row = conn.execute(
                "SELECT id, version_number FROM question_versions WHERE id = ? AND question_id = ?",
                (version_id, question_id),
            ).fetchone()
            if not row:
                raise LookupError("version not found")

            latest = conn.execute(
                "SELECT MAX(version_number) FROM question_versions WHERE question_id = ?",
                (question_id,),
            ).fetchone()
            if latest and row["version_number"] == latest[0]:
                raise ValueError("current version cannot be deleted")

            if question_id in self._get_active_exam_question_ids(conn, user_id):
                raise PermissionError("cannot edit question while exam is active")

            if conn.execute(
                "SELECT 1 FROM answer_attempts WHERE question_version_id = ? LIMIT 1",
                (version_id,),
            ).fetchone():
                raise ValueError("version is referenced by answer attempts")

            conn.execute("DELETE FROM question_versions WHERE id = ?", (version_id,))
            conn.execute(
                """INSERT INTO audit_logs(id, user_id, action, entity_type, entity_id, details_json)
                   VALUES (?, ?, 'QUESTION_VERSION_DELETED', 'QUESTION', ?, ?)""",
                (
                    str(uuid.uuid4()),
                    user_id,
                    question_id,
                    json.dumps({"version_id": version_id, "version_number": row["version_number"]}, ensure_ascii=False),
                ),
            )
            return {
                "question_id": question_id,
                "version_id": version_id,
                "version_number": row["version_number"],
                "deleted": True,
            }
