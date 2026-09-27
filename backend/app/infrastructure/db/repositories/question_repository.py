from datetime import datetime, timezone
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
        return self.get_for_user(question_id, user_id)

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

    def get_for_user(self, question_id: str, user_id: str, conn=None) -> dict | None:
        def _query(c):
            row = c.execute(
                """SELECT q.id, qv.id AS version_id, qv.version_number, qv.type,
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
            result["options"] = json.loads(result.pop("options_json"))
            result["tags"] = json.loads(result.pop("tags_json"))
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
                          qv.difficulty, qv.tags_json, qv.chapter_id, i.bank_id
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
                          qv.difficulty, qv.tags_json, qv.chapter_id, i.bank_id
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
            prev_chap = conn.execute("SELECT chapter_id FROM question_versions WHERE question_id = ? AND version_number = ?", (question_id, current)).fetchone()
            chap_id = payload.get("chapter_id") if "chapter_id" in payload and payload.get("chapter_id") is not None else (prev_chap[0] if prev_chap else None)
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
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
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

            sess_row = conn.execute("SELECT id, answers_json, mode FROM practice_sessions WHERE id = ?", (sess_id,)).fetchone()
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
                """SELECT correctness, mastery_status, created_at, fsrs_rating, card_snapshot_json
                   FROM answer_attempts
                   WHERE user_id = ? AND question_id = ?
                   ORDER BY created_at ASC""",
                (uid, question_id),
            ).fetchall()
            if not user_attempts:
                continue

            mistakes = 0
            consecutive = 0
            for uatt in user_attempts:
                corr = uatt["correctness"]
                if corr == "CORRECT":
                    consecutive += 1
                elif corr in {"INCORRECT", "PARTIAL"}:
                    consecutive = 0
                    mistakes += 1
            cleared = int(consecutive >= 2)
            last_mastery = user_attempts[-1]["mastery_status"]

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
                card_state = 0
                card_stability = 0.0
                card_diff = 5.0
                last_rev = None
                last_due = datetime.now(timezone.utc)

                first_att = user_attempts[0]
                if first_att["card_snapshot_json"]:
                    try:
                        snap = json.loads(first_att["card_snapshot_json"])
                        card_state = snap.get("state", 0)
                        card_stability = float(snap.get("stability", 0.0))
                        card_diff = float(snap.get("difficulty", 5.0))
                        if snap.get("last_review_at"):
                            last_rev = datetime.fromisoformat(snap["last_review_at"])
                    except Exception:
                        pass

                for uatt in user_attempts:
                    rating = uatt["fsrs_rating"]
                    if rating is None:
                        if uatt["correctness"] in {"INCORRECT", "PARTIAL"}:
                            rating = 1
                        else:
                            rating = 3
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
            values = []
            for row in rows:
                value = dict(row)
                value["options"] = json.loads(value.pop("options_json"))
                value["tags"] = json.loads(value.pop("tags_json"))
                values.append(value)
            return values
