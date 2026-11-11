import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from backend.app.infrastructure.db.connection import transaction
from backend.app.infrastructure.learning.fsrs_adapter import FSRS5


# Fixed namespace so an idempotent retry of the same logical answer can be given
# a deterministic row id. With a client key the id depends only on the key, so
# any retry of that key collapses even if the payload changed. Without a key the
# id also carries the attempt ordinal: two retries that are consecutive in time
# collapse, but a user legitimately changing A→B→A must still get a fresh row
# instead of colliding with the historical A attempt.
_ATTEMPT_NAMESPACE = uuid.UUID("5b0f3c2a-9d1e-4c7b-8a21-6f4e2d9c1b77")
_SUBJECTIVE_TYPES = {"ESSAY", "SHORT_ANSWER", "SUBJECTIVE"}


def _canonical_answer(question_type: str, value: Any) -> tuple:
    """Return a scoring-equivalent representation used for replay detection.

    Two payloads that score identically must be treated as the same answer, so a
    retry is not turned into a second attempt just because the client serialized
    the value differently (e.g. a MULTI list in another order).
    """
    type_name = str(question_type or "SINGLE").upper()
    if type_name == "MULTI":
        if value is None:
            return (type_name, ())
        tokens = set()
        items = value if isinstance(value, (list, tuple, set)) else [value]
        for item in items:
            if item is None:
                continue
            tokens.update(char for char in str(item).strip().upper() if char.isalnum())
        return (type_name, tuple(sorted(tokens)))
    if type_name == "JUDGE":
        text = str(value or "").strip().upper()
        if text in {"TRUE", "1", "正确", "对", "YES", "Y", "T"}:
            return (type_name, "T")
        if text in {"FALSE", "0", "错误", "错", "NO", "N", "F"}:
            return (type_name, "F")
        return (type_name, text)
    if isinstance(value, (list, tuple, set)):
        return (type_name, tuple(sorted(str(item).strip() for item in value)))
    if isinstance(value, dict):
        return (type_name, json.dumps(value, sort_keys=True, ensure_ascii=False))
    text = "" if value is None else str(value)
    if type_name in _SUBJECTIVE_TYPES:
        return (type_name, text.strip())
    return (type_name, text.strip().upper())


def _attempt_id_for(
    user_id: str,
    session_id: str,
    question_id: str,
    canonical_answer: tuple,
    client_attempt_id: str | None,
    attempt_seq: int = 0,
) -> str:
    if client_attempt_id:
        seed = f"client|{user_id}|{session_id}|{question_id}|{client_attempt_id}"
    else:
        seed = f"answer|{user_id}|{session_id}|{question_id}|{canonical_answer!r}|{attempt_seq}"
    return str(uuid.uuid5(_ATTEMPT_NAMESPACE, seed))


def _loads_json(value, fallback=None):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback if fallback is not None else value



class PracticeRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.fsrs = FSRS5()

    def create_session(
        self,
        user_id: str,
        bank_id: str,
        mode: str,
        total_questions: int,
        time_limit: int = 0,
        exam_profile_id: str | None = None,
        blueprint_id: str | None = None,
        question_refs: list[dict] | None = None,
        config: dict | None = None,
    ) -> dict:
        session_id = str(uuid.uuid4())
        with transaction(self.db_path) as conn:
            conn.execute(
                """INSERT INTO practice_sessions(
                    id, user_id, bank_id, mode, total_questions, time_limit,
                    exam_profile_id, blueprint_id, questions_json, config_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, user_id, bank_id, mode, total_questions, time_limit,
                 exam_profile_id, blueprint_id, json.dumps(question_refs or [], ensure_ascii=False),
                 json.dumps(config or {}, ensure_ascii=False)),
            )
        return self.get_session(session_id, user_id)

    def get_session(self, session_id: str, user_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute("SELECT * FROM practice_sessions WHERE id = ? AND user_id = ?", (session_id, user_id)).fetchone()
            return dict(row) if row else None

    def list_active_sessions(self, user_id: str, mode: str | None = None) -> list[dict]:
        with transaction(self.db_path) as conn:
            query = "SELECT * FROM practice_sessions WHERE user_id = ? AND is_completed = 0"
            params = [user_id]
            if mode:
                query += " AND mode = ?"
                params.append(mode)
            query += " ORDER BY updated_at DESC"
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def abandon_session(self, session_id: str, user_id: str) -> bool:
        with transaction(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE practice_sessions SET is_completed = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ? AND is_completed = 0",
                (session_id, user_id),
            )
            return cur.rowcount > 0

    def abandon_all_sessions(self, user_id: str) -> int:
        with transaction(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE practice_sessions SET is_completed = 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND is_completed = 0",
                (user_id,),
            )
            return cur.rowcount

    _ATTEMPT_COLUMNS = """id, user_answer_json, correctness, mastery_status, score_ratio,
                          fsrs_rating, mistake_cause, card_snapshot_json, created_at"""

    def _attempt_rows(self, conn, session_id: str, question_id: str) -> list:
        return conn.execute(
            f"""SELECT {self._ATTEMPT_COLUMNS}
                FROM answer_attempts
                WHERE session_id = ? AND question_id = ?
                ORDER BY created_at DESC, rowid DESC""",
            (session_id, question_id),
        ).fetchall()

    def _find_replay_attempt(
        self,
        conn,
        question_type: str,
        canonical_answer: tuple,
        client_attempt_id: str | None,
        attempt_id: str,
        latest,
    ):
        """Return the attempt this submission replays, if any.

        A keyed submission replays exactly the row carrying the same key (it may
        be older than the latest answer, which is a genuinely stale offline
        replay). An unkeyed legacy submission only replays the *latest* attempt
        when its answer is scoring-equivalent: that is the "response lost, client
        retried" case. Matching any older answer would turn a legitimate A→B→A
        answer change into a phantom replay and permanently deduplicate by
        answer, so the historical rows are deliberately not scanned.
        """
        if client_attempt_id:
            return conn.execute(
                f"SELECT {self._ATTEMPT_COLUMNS} FROM answer_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
        if latest is None:
            return None
        stored = _loads_json(latest["user_answer_json"], latest["user_answer_json"])
        if _canonical_answer(question_type, stored) == canonical_answer:
            return latest
        return None

    def _settle_duplicate_attempt(
        self,
        conn,
        user_id: str,
        session: dict,
        question: dict,
        existing,
        latest,
        fsrs_rating: int | None,
        mistake_cause: str | None,
        result: dict,
    ) -> dict:
        """Return the existing attempt for a replay instead of inserting again.

        A replay that matches the *latest* attempt may still carry a new FSRS
        rating/mistake cause (the two-step practice flow), so those attributes
        are updated on that attempt. A replay that matches an older attempt is
        stale (e.g. an offline queue drained after a newer manual answer); it
        must not mutate history or roll the card back.
        """
        is_latest = latest is not None and latest["id"] == existing["id"]
        current_rating = existing["fsrs_rating"]
        current_cause = existing["mistake_cause"]
        if is_latest:
            if fsrs_rating is not None and fsrs_rating != existing["fsrs_rating"]:
                conn.execute("UPDATE answer_attempts SET fsrs_rating = ? WHERE id = ?", (fsrs_rating, existing["id"]))
                current_rating = fsrs_rating
                if result.get("is_objective", True):
                    existing_dict = dict(existing)
                    snapshot = json.loads(existing_dict["card_snapshot_json"]) if existing_dict.get("card_snapshot_json") else None
                    if snapshot is None:
                        card_row = conn.execute(
                            "SELECT state, stability, difficulty, due_at, last_review_at FROM fsrs_cards WHERE user_id = ? AND question_id = ?",
                            (user_id, question["id"]),
                        ).fetchone()
                        # 存量/无快照记录安全策略：
                        # 检查该存量作答是否已在历史上完成过 FSRS 调度
                        already_scheduled = (
                            existing_dict.get("fsrs_rating") is not None
                            or (
                                card_row is not None
                                and card_row["last_review_at"] is not None
                                and existing_dict.get("created_at") is not None
                                and str(card_row["last_review_at"]).strip() == str(existing_dict["created_at"]).strip()
                            )
                        )
                        if not already_scheduled:
                            # 未调度过的存量作答（如迁移的未评级作答）：当前卡片（或初始新卡）确为该次作答的初始基准
                            if card_row:
                                snapshot = dict(card_row)
                            else:
                                snapshot = {"state": 0, "stability": 0.0, "difficulty": 5.0, "due_at": None, "last_review_at": None}
                            conn.execute(
                                "UPDATE answer_attempts SET card_snapshot_json = ? WHERE id = ?",
                                (json.dumps(snapshot, ensure_ascii=False), existing["id"]),
                            )
                        # 若 already_scheduled 为 True：
                        # 该作答此前已在卡片上触发过调度，且无作答前快照。
                        # 严禁在已被该作答更新过的卡片上二次叠加调度，亦严禁用默认值重置卡片。
                        # 保持 snapshot 为 None，冻结保护卡片现有状态，仅记录用户评级反馈。

                    if snapshot is not None:
                        stability = float(snapshot["stability"]) if snapshot.get("stability") is not None else 0.0
                        difficulty = float(snapshot["difficulty"]) if snapshot.get("difficulty") is not None else 5.0
                        if existing_dict.get("created_at"):
                            attempt_time = datetime.fromisoformat(existing_dict["created_at"])
                            if attempt_time.tzinfo is None:
                                attempt_time = attempt_time.replace(tzinfo=timezone.utc)
                        else:
                            attempt_time = datetime.now(timezone.utc)
                        elapsed_days = 0.0
                        if snapshot.get("last_review_at"):
                            last_review = datetime.fromisoformat(snapshot["last_review_at"])
                            if last_review.tzinfo is None:
                                last_review = last_review.replace(tzinfo=timezone.utc)
                            elapsed_days = max(0.0, (attempt_time - last_review).total_seconds() / 86400)
                        fsrs_result = self.fsrs.schedule(
                            rating=fsrs_rating,
                            stability=stability,
                            difficulty=difficulty,
                            elapsed_days=elapsed_days,
                            now=attempt_time,
                        )
                        conn.execute(
                            """INSERT INTO fsrs_cards(user_id, question_id, state, stability, difficulty, due_at, last_review_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?)
                               ON CONFLICT(user_id, question_id) DO UPDATE SET
                                 state=excluded.state, stability=excluded.stability,
                                 difficulty=excluded.difficulty, due_at=excluded.due_at,
                                 last_review_at=excluded.last_review_at""",
                            (user_id, question["id"], fsrs_result.state, fsrs_result.stability,
                             fsrs_result.difficulty, fsrs_result.due.isoformat(), attempt_time.isoformat()),
                        )
            if mistake_cause is not None:
                conn.execute("UPDATE answer_attempts SET mistake_cause = ? WHERE id = ?", (mistake_cause, existing["id"]))
                conn.execute("UPDATE mistake_records SET mistake_cause = ? WHERE user_id = ? AND question_id = ?", (mistake_cause, user_id, question["id"]))
                current_cause = mistake_cause

        latest_row = latest or existing
        return {
            "id": latest_row["id"],
            "session_id": session["id"],
            "question_id": question["id"],
            "user_answer": _loads_json(latest_row["user_answer_json"], latest_row["user_answer_json"]),
            "correctness": latest_row["correctness"],
            "mastery_status": latest_row["mastery_status"],
            "score_ratio": latest_row["score_ratio"],
            "is_objective": result.get("is_objective", True),
            "is_correct": latest_row["correctness"] == "CORRECT",
            "fsrs_rating": current_rating if is_latest else latest_row["fsrs_rating"],
            "mistake_cause": current_cause if is_latest else latest_row["mistake_cause"],
            "duplicate": True,
            "idempotent_replay": True,
            "replayed_attempt_id": existing["id"],
        }

    def save_attempt(
        self,
        user_id: str,
        session: dict,
        question: dict,
        user_answer: Any,
        result: dict,
        fsrs_rating: int | None = None,
        mistake_cause: str | None = None,
        client_attempt_id: str | None = None,
    ) -> dict:
        canonical_answer = _canonical_answer(question.get("type"), user_answer)
        client_key = str(client_attempt_id).strip() if client_attempt_id else None
        with transaction(self.db_path) as conn:
            # Serialize writers before the duplicate check so two simultaneous
            # retries cannot both observe "no attempt yet" and double-insert.
            conn.execute("BEGIN IMMEDIATE")
            current_session = conn.execute(
                "SELECT user_id, is_completed FROM practice_sessions WHERE id = ?",
                (session["id"],),
            ).fetchone()
            if not current_session or current_session["user_id"] != user_id:
                raise LookupError("practice session not found")
            if current_session["is_completed"]:
                raise ValueError("session already completed")

            rows = self._attempt_rows(conn, session["id"], question["id"])
            latest = rows[0] if rows else None
            attempt_id = _attempt_id_for(
                user_id, session["id"], question["id"], canonical_answer, client_key,
                attempt_seq=len(rows),
            )
            existing = self._find_replay_attempt(
                conn, question.get("type"), canonical_answer, client_key, attempt_id, latest,
            )
            if existing is not None:
                return self._settle_duplicate_attempt(
                    conn, user_id, session, question, existing, latest, fsrs_rating, mistake_cause, result,
                )

            now = datetime.now(timezone.utc)
            before_card = conn.execute(
                "SELECT state, stability, difficulty, due_at, last_review_at FROM fsrs_cards WHERE user_id = ? AND question_id = ?",
                (user_id, question["id"]),
            ).fetchone()
            card_snapshot = dict(before_card) if before_card else {"state": 0, "stability": 0.0, "difficulty": 5.0, "due_at": None, "last_review_at": None}
            card_snapshot_json = json.dumps(card_snapshot, ensure_ascii=False)

            try:
                conn.execute(
                    """INSERT INTO answer_attempts(
                        id, user_id, session_id, bank_id, question_id, question_version_id,
                        user_answer_json, score_ratio, correctness, mastery_status, fsrs_rating, mistake_cause, card_snapshot_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        attempt_id, user_id, session["id"], question["bank_id"], question["id"], question["version_id"],
                        json.dumps(user_answer, ensure_ascii=False), result["score_ratio"], result["correctness"], result["mastery_status"], fsrs_rating, mistake_cause, card_snapshot_json, now.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError:
                # Another writer inserted the same deterministic attempt id
                # between our check and insert. Treat it as the same replay;
                # if the row is not ours, the original error is real.
                rows = self._attempt_rows(conn, session["id"], question["id"])
                latest = rows[0] if rows else None
                existing = conn.execute(
                    f"SELECT {self._ATTEMPT_COLUMNS} FROM answer_attempts WHERE id = ?",
                    (attempt_id,),
                ).fetchone()
                if existing is None:
                    raise
                return self._settle_duplicate_attempt(
                    conn, user_id, session, question, existing, latest, fsrs_rating, mistake_cause, result,
                )
            current_sess_row = conn.execute("SELECT answers_json FROM practice_sessions WHERE id = ?", (session["id"],)).fetchone()
            answers = json.loads((current_sess_row[0] if current_sess_row else session.get("answers_json")) or "{}")
            answers[question["id"]] = {
                "answer": user_answer,
                "user_answer": user_answer,
                "is_correct": result["correctness"] == "CORRECT",
                "score_ratio": result["score_ratio"],
                "correctness": result["correctness"],
                "mastery_status": result["mastery_status"],
                "correct_answer": question["answer"],
                "explanation": question["explanation"],
            }
            conn.execute("UPDATE practice_sessions SET answers_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (json.dumps(answers, ensure_ascii=False), session["id"]))
            previous = conn.execute("SELECT * FROM learning_records WHERE user_id = ? AND question_id = ?", (user_id, question["id"])).fetchone()
            if previous:
                mistakes = int(previous["mistake_count"])
                consecutive = int(previous["consecutive_correct"])
            else:
                mistakes = 0
                consecutive = 0
            is_exam = session.get("mode") == "EXAM"
            is_elimination = session.get("mode") == "ELIMINATION"
            # EE-002: Respect record_mistakes configuration for every session mode
            # (the field is stored in config_json; exam blueprints may also carry it).
            record_mistakes = True
            cfg = json.loads(session.get("config_json") or "{}")
            if "record_mistakes" in cfg:
                record_mistakes = bool(cfg["record_mistakes"])
            elif is_exam and session.get("blueprint_id"):
                bp_row = conn.execute("SELECT blueprint_json FROM exam_blueprints WHERE id = ?", (session["blueprint_id"],)).fetchone()
                if bp_row:
                    bp_dict = json.loads(bp_row[0] or "{}")
                    if "record_mistakes" in bp_dict:
                        record_mistakes = bool(bp_dict["record_mistakes"])

            if result["correctness"] == "CORRECT":
                consecutive += 1
                cleared = int(consecutive >= 2)
            elif result["correctness"] in {"INCORRECT", "PARTIAL"}:
                consecutive = 0
                if record_mistakes:
                    mistakes += 1
                cleared = 0
                # SPEC §4.3: only a wrong answer inside the elimination queue may
                # revive a killed question. Answers submitted from another session
                # (including stale/offline ones started before the kill) must never
                # silently take a question out of the kill queue.
                if record_mistakes and is_elimination:
                    conn.execute("DELETE FROM kill_records WHERE user_id = ? AND question_id = ?", (user_id, question["id"]))
            else:
                cleared = int(previous["is_cleared"]) if previous else 0
            mistake_cleared = int(cleared or mistakes == 0)

            if not is_exam or record_mistakes:
                conn.execute(
                    """INSERT INTO learning_records(user_id, question_id, mistake_count, consecutive_correct, mastery_status, is_cleared, last_attempt_at)
                       VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(user_id, question_id) DO UPDATE SET
                         mistake_count=excluded.mistake_count,
                         consecutive_correct=excluded.consecutive_correct,
                         mastery_status=excluded.mastery_status,
                         is_cleared=excluded.is_cleared,
                         last_attempt_at=excluded.last_attempt_at""",
                    (user_id, question["id"], mistakes, consecutive, result["mastery_status"], cleared),
                )

            if mistakes > 0 and record_mistakes:
                conn.execute(
                """INSERT INTO mistake_records(
                    user_id, question_id, bank_id, mistake_count,
                    consecutive_correct, is_cleared, last_review_at, mistake_cause
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(user_id, question_id) DO UPDATE SET
                    bank_id=excluded.bank_id,
                    mistake_count=excluded.mistake_count,
                    consecutive_correct=excluded.consecutive_correct,
                    is_cleared=excluded.is_cleared,
                    last_review_at=excluded.last_review_at,
                    mistake_cause=COALESCE(excluded.mistake_cause, mistake_records.mistake_cause),
                    updated_at=CURRENT_TIMESTAMP""",
                    (user_id, question["id"], question["bank_id"], mistakes, consecutive, mistake_cleared, mistake_cause),
                )
            if not is_exam:
                if fsrs_rating is None:
                    if result["correctness"] in {"INCORRECT", "PARTIAL"}:
                        fsrs_rating = 1
                    elif result["correctness"] == "CORRECT" and previous and int(previous["mistake_count"]) > 0:
                        fsrs_rating = 3
            if not is_exam and result.get("is_objective", True) and fsrs_rating is not None:
                current_card = before_card
                elapsed_days = 0.0
                stability = float(current_card["stability"]) if current_card else 0.0
                difficulty = float(current_card["difficulty"]) if current_card else 5.0
                if current_card and current_card["last_review_at"]:
                    last_review = datetime.fromisoformat(current_card["last_review_at"])
                    if last_review.tzinfo is None:
                        last_review = last_review.replace(tzinfo=timezone.utc)
                    elapsed_days = max(0.0, (now - last_review).total_seconds() / 86400)
                fsrs_result = self.fsrs.schedule(
                    rating=fsrs_rating,
                    stability=stability,
                    difficulty=difficulty,
                    elapsed_days=elapsed_days,
                    now=now,
                )
                conn.execute(
                    """INSERT INTO fsrs_cards(user_id, question_id, state, stability, difficulty, due_at, last_review_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(user_id, question_id) DO UPDATE SET
                         state=excluded.state, stability=excluded.stability,
                         difficulty=excluded.difficulty, due_at=excluded.due_at,
                         last_review_at=excluded.last_review_at""",
                    (user_id, question["id"], fsrs_result.state, fsrs_result.stability,
                     fsrs_result.difficulty, fsrs_result.due.isoformat(), now.isoformat()),
                )
            conn.execute(
                "INSERT INTO learning_events(id, user_id, event_type, aggregate_type, aggregate_id, payload_json) VALUES (?, ?, 'ANSWER_ATTEMPTED', 'question', ?, ?)",
                (str(uuid.uuid4()), user_id, question["id"], json.dumps(result, ensure_ascii=False)),
            )
        return {
            "id": attempt_id,
            "session_id": session["id"],
            "question_id": question["id"],
            "user_answer": user_answer,
            **result,
            "is_correct": result["correctness"] == "CORRECT",
            "fsrs_rating": fsrs_rating,
            "mistake_cause": mistake_cause,
            "duplicate": False,
            "idempotent_replay": False,
        }

    def update_draft(self, user_id: str, session_id: str, current_index=None, answers=None, flags=None, time_spent=None, base_answers=None) -> dict | None:
        def _is_empty(val):
            if val is None:
                return True
            if isinstance(val, (list, tuple, set, dict)) and len(val) == 0:
                return True
            if isinstance(val, str) and not val.strip():
                return True
            return False

        def _raw(val):
            if isinstance(val, dict):
                return val.get("user_answer", val.get("answer"))
            return val

        conflicts = []
        with transaction(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM practice_sessions WHERE id = ? AND user_id = ?", (session_id, user_id)).fetchone()
            if not row:
                return None
            if row["is_completed"]:
                raise ValueError("session already completed")
            current = dict(row)
            session_questions = json.loads(current.get("questions_json") or "[]")
            allowed_qids = {item["question_id"] for item in session_questions} if session_questions else set()
            version_ids = {item["question_id"]: item.get("version_id") for item in session_questions}

            merged_answers = json.loads(current.get("answers_json") or "{}")
            if answers is not None:
                has_non_empty_incoming = any(not _is_empty(_raw(v)) for v in answers.values())
                for q_id, incoming_val in answers.items():
                    if allowed_qids and q_id not in allowed_qids:
                        continue
                    existing_val = merged_answers.get(q_id)
                    existing_raw = _raw(existing_val)
                    incoming_raw = _raw(incoming_val)
                    version = conn.execute("SELECT type FROM question_versions WHERE id = ?", (version_ids.get(q_id),)).fetchone()
                    question_type = version["type"] if version else "SINGLE"
                    def equivalent(left, right):
                        return _canonical_answer(question_type, left) == _canonical_answer(question_type, right)
                    # Replaying an unchanged draft must not strip scored-attempt metadata.
                    if isinstance(existing_val, dict) and not isinstance(incoming_val, dict) and equivalent(existing_raw, incoming_raw):
                        continue
                    if _is_empty(incoming_raw):
                        if _is_empty(existing_raw):
                            merged_answers[q_id] = ""
                            continue
                        if base_answers is not None:
                            # With an observed base, an empty value is an explicit clear by
                            # this client and must apply even when the same payload also
                            # edits another question. Only a diverged base is a conflict.
                            if not equivalent(existing_raw, _raw(base_answers.get(q_id))):
                                conflicts.append({
                                    "question_id": q_id,
                                    "existing_answer": existing_raw,
                                    "incoming_answer": incoming_raw,
                                })
                                continue
                            merged_answers[q_id] = ""
                            continue
                        # P2-3 legacy client (no base snapshot): if all incoming answers in
                        # this sync request are empty (e.g. {q: ""}), treat it as an explicit
                        # clear; a mixed payload ({q1: "", q2: "B"}) is ambiguous, so keep
                        # the existing valid answer rather than dropping it.
                        if not has_non_empty_incoming:
                            merged_answers[q_id] = ""
                        continue
                    if not _is_empty(existing_raw) and not equivalent(existing_raw, incoming_raw):
                        # Optimistic concurrency for cross-device drafts: the client sends the
                        # server values it last observed. A difference means another device has
                        # written since then, so keep the server value and report the conflict
                        # instead of silently overwriting the other device's answer.
                        if base_answers is not None:
                            if not equivalent(existing_raw, _raw(base_answers.get(q_id))):
                                conflicts.append({
                                    "question_id": q_id,
                                    "existing_answer": existing_raw,
                                    "incoming_answer": incoming_raw,
                                })
                                continue
                        else:
                            # Legacy client with no base snapshot: keep the historical
                            # behaviour of accepting the write, but still report it.
                            conflicts.append({
                                "question_id": q_id,
                                "existing_answer": existing_raw,
                                "incoming_answer": incoming_raw,
                            })
                    merged_answers[q_id] = incoming_val

            if flags is not None:
                valid_flags = [f for f in flags if not allowed_qids or f in allowed_qids]
                merged_flags = list(dict.fromkeys(valid_flags))
            else:
                merged_flags = json.loads(current.get("flags_json") or "[]")

            if current_index is not None:
                max_idx = max(0, len(session_questions) - 1) if session_questions else 0
                final_index = max(0, min(int(current_index), max_idx))
            else:
                final_index = current["current_index"]

            safe_time = max(0, int(time_spent or 0)) if time_spent is not None else None
            merged_time = max(int(current.get("time_spent") or 0), safe_time) if safe_time is not None else current["time_spent"]

            conn.execute(
                "UPDATE practice_sessions SET current_index = ?, answers_json = ?, flags_json = ?, time_spent = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (final_index, json.dumps(merged_answers, ensure_ascii=False), json.dumps(merged_flags, ensure_ascii=False), merged_time, session_id),
            )
        session = self.get_session(session_id, user_id)
        if session:
            session["has_conflict"] = bool(conflicts)
            session["conflicts"] = conflicts
        return session

    def toggle_flag(self, user_id: str, session_id: str, question_id: str) -> list[str] | None:
        with transaction(self.db_path) as conn:
            row = conn.execute("SELECT flags_json, is_completed, questions_json FROM practice_sessions WHERE id = ? AND user_id = ?", (session_id, user_id)).fetchone()
            if not row:
                return None
            if row["is_completed"]:
                raise ValueError("session already completed")
            session_questions = json.loads(row["questions_json"] or "[]")
            allowed_qids = {item["question_id"] for item in session_questions} if session_questions else set()
            if allowed_qids and question_id not in allowed_qids:
                raise LookupError("question not in this session")

            flags = json.loads(row[0] or "[]")
            if question_id in flags:
                flags.remove(question_id)
            else:
                flags.append(question_id)
            conn.execute("UPDATE practice_sessions SET flags_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (json.dumps(flags), session_id))
            return flags

    def complete(self, user_id: str, session_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            conn.execute("UPDATE practice_sessions SET is_completed = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?", (session_id, user_id))
        return self.get_session(session_id, user_id)

    def list_attempts(self, user_id: str, session_id: str) -> list[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT a.id, a.session_id, a.question_id, a.question_version_id,
                          a.user_answer_json, a.score_ratio, a.correctness,
                          a.mastery_status, a.time_spent, a.created_at,
                          qv.type, qv.stem, qv.answer AS correct_answer,
                          qv.explanation, qv.tags_json
                   FROM answer_attempts a
                   JOIN question_versions qv ON qv.id = a.question_version_id
                   WHERE a.user_id = ? AND a.session_id = ?
                   ORDER BY a.created_at ASC, a.id ASC""",
                (user_id, session_id),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["user_answer"] = json.loads(item.pop("user_answer_json"))
                item["tags"] = json.loads(item.pop("tags_json") or "[]")
                result.append(item)
            return result

    def list_mistakes(self, user_id: str, bank_id: str | None = None) -> list[dict]:
        with transaction(self.db_path) as conn:
            exam_rows = conn.execute(
                "SELECT questions_json FROM practice_sessions WHERE user_id = ? AND mode = 'EXAM' AND is_completed = 0",
                (user_id,),
            ).fetchall()
            active_exam_qids = set()
            for er in exam_rows:
                if er[0]:
                    try:
                        for item in json.loads(er[0]):
                            qid = item.get("question_id")
                            if qid:
                                active_exam_qids.add(qid)
                    except Exception:
                        pass

            sql = """SELECT m.user_id, m.question_id, m.mistake_count, m.consecutive_correct,
                             l.mastery_status, m.is_cleared, l.last_attempt_at, m.mistake_cause,
                             i.bank_id, qv.stem, qv.type, qv.answer, f.due_at,
                             CASE WHEN f.due_at IS NOT NULL
                                       AND datetime(replace(f.due_at, 'T', ' ')) <= CURRENT_TIMESTAMP
                                  THEN 1 ELSE 0 END AS is_due
                      FROM mistake_records m
                      JOIN learning_records l ON l.user_id = m.user_id AND l.question_id = m.question_id
                      JOIN questions q ON q.id = m.question_id AND q.is_deleted = 0
                      JOIN bank_question_items i ON i.question_id = m.question_id
                      JOIN question_bank_members qbm ON qbm.bank_id = i.bank_id AND qbm.user_id = m.user_id
                      JOIN question_versions qv ON qv.question_id = l.question_id
                      LEFT JOIN fsrs_cards f ON f.user_id = m.user_id AND f.question_id = m.question_id
                      LEFT JOIN kill_records k ON k.user_id = m.user_id AND k.question_id = m.question_id
                      WHERE m.user_id = ? AND m.is_cleared = 0 AND k.question_id IS NULL
                        AND qv.version_number = (SELECT MAX(version_number) FROM question_versions WHERE question_id = l.question_id)"""
            params = [user_id]
            if bank_id:
                sql += " AND i.bank_id = ?"
                params.append(bank_id)
            sql += " ORDER BY l.last_attempt_at DESC"
            rows = conn.execute(sql, params).fetchall()
            results = []
            for row in rows:
                item = dict(row)
                if item["question_id"] in active_exam_qids:
                    item["answer"] = ""
                results.append(item)
            return results

    def update_mistake_cause(self, user_id: str, question_id: str, mistake_cause: str) -> dict:
        with transaction(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE mistake_records SET mistake_cause = ? WHERE user_id = ? AND question_id = ?",
                (mistake_cause, user_id, question_id),
            )
            if cursor.rowcount == 0:
                raise LookupError("mistake record not found")
            conn.execute(
                """UPDATE answer_attempts SET mistake_cause = ?
                   WHERE id = (SELECT id FROM answer_attempts WHERE user_id = ? AND question_id = ? ORDER BY created_at DESC LIMIT 1)""",
                (mistake_cause, user_id, question_id),
            )
            return {"question_id": question_id, "mistake_cause": mistake_cause}

    def mark_weak(self, user_id: str, question_id: str) -> dict | None:
        with transaction(self.db_path) as conn:
            row = conn.execute(
                """SELECT i.bank_id FROM bank_question_items i
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   WHERE i.question_id = ? LIMIT 1""",
                (user_id, question_id),
            ).fetchone()
            if not row:
                return None
            conn.execute("INSERT OR IGNORE INTO weak_question_flags(user_id, question_id) VALUES (?, ?)", (user_id, question_id))
            conn.execute(
                """INSERT OR IGNORE INTO fsrs_cards(user_id, question_id, state, stability, difficulty, due_at)
                   VALUES (?, ?, 0, 0, 5, CURRENT_TIMESTAMP)""",
                (user_id, question_id),
            )
        return {"user_id": user_id, "question_id": question_id, "bank_id": row["bank_id"], "is_weak_flagged": True}

    def unmark_weak(self, user_id: str, question_id: str) -> bool:
        with transaction(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM weak_question_flags WHERE user_id = ? AND question_id = ?", (user_id, question_id))
            if cursor.rowcount:
                conn.execute(
                    """DELETE FROM fsrs_cards WHERE user_id = ? AND question_id = ?
                       AND last_review_at IS NULL
                       AND NOT EXISTS (SELECT 1 FROM mistake_records WHERE user_id = ? AND question_id = ? AND is_cleared = 0)""",
                    (user_id, question_id, user_id, question_id),
                )
            return bool(cursor.rowcount)

    def list_due_reviews(self, user_id: str, bank_id: str | None = None) -> list[dict]:
        sql = """SELECT f.user_id, f.question_id, i.bank_id, qv.stem, qv.type,
                         COALESCE(m.mistake_count, 0) AS mistake_count,
                         COALESCE(m.is_cleared, 0) AS is_cleared,
                         m.mistake_cause, f.due_at,
                         CASE WHEN w.question_id IS NULL THEN 0 ELSE 1 END AS is_weak_flagged
                  FROM fsrs_cards f
                  JOIN questions q ON q.id = f.question_id AND q.is_deleted = 0
                  JOIN bank_question_items i ON i.question_id = f.question_id
                  JOIN question_bank_members bm ON bm.bank_id = i.bank_id AND bm.user_id = f.user_id
                  JOIN question_versions qv ON qv.question_id = f.question_id
                  LEFT JOIN mistake_records m ON m.user_id = f.user_id AND m.question_id = f.question_id
                  LEFT JOIN weak_question_flags w ON w.user_id = f.user_id AND w.question_id = f.question_id
                  LEFT JOIN kill_records k ON k.user_id = f.user_id AND k.question_id = f.question_id
                  WHERE f.user_id = ? AND k.question_id IS NULL
                    AND datetime(replace(f.due_at, 'T', ' ')) <= CURRENT_TIMESTAMP
                    AND (w.question_id IS NOT NULL OR (m.question_id IS NOT NULL AND m.is_cleared = 0))
                    AND qv.version_number = (SELECT MAX(version_number) FROM question_versions WHERE question_id = f.question_id)"""
        params = [user_id]
        if bank_id:
            sql += " AND i.bank_id = ?"
            params.append(bank_id)
        sql += " ORDER BY f.due_at ASC"
        with transaction(self.db_path) as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def summary(self, user_id: str) -> dict:
        with transaction(self.db_path) as conn:
            totals = conn.execute(
                """SELECT COUNT(*) AS attempts,
                          COALESCE(SUM(a.score_ratio), 0) AS score,
                          SUM(CASE WHEN a.correctness = 'CORRECT' THEN 1 ELSE 0 END) AS correct
                   FROM answer_attempts a
                   JOIN questions q ON q.id = a.question_id AND q.is_deleted = 0
                   JOIN question_bank_members m ON m.bank_id = a.bank_id AND m.user_id = a.user_id
                   JOIN question_versions qv ON qv.id = a.question_version_id
                   WHERE a.user_id = ? AND UPPER(qv.type) NOT IN ('ESSAY', 'SHORT_ANSWER', 'SUBJECTIVE')""",
                (user_id,),
            ).fetchone()
            questions = conn.execute(
                """SELECT COUNT(*) FROM learning_records lr
                   JOIN questions q ON q.id = lr.question_id AND q.is_deleted = 0
                   WHERE lr.user_id = ?""",
                (user_id,),
            ).fetchone()[0]
            weak = conn.execute(
                """SELECT COUNT(*) FROM learning_records lr
                   JOIN questions q ON q.id = lr.question_id AND q.is_deleted = 0
                   WHERE lr.user_id = ? AND lr.mastery_status IN ('WEAK', 'PARTIAL') AND lr.is_cleared = 0
                     AND NOT EXISTS (
                       SELECT 1 FROM kill_records k
                       WHERE k.user_id = lr.user_id AND k.question_id = lr.question_id
                     )""",
                (user_id,),
            ).fetchone()[0]
            return {
                "attempts": int(totals["attempts"] or 0),
                "score": round(float(totals["score"] or 0), 2),
                "correct": int(totals["correct"] or 0),
                "tracked_questions": int(questions),
                "weak_questions": int(weak),
            }

    def trends(self, user_id: str, bank_id: str | None = None, window_days: int = 14) -> dict:
        window_days = max(1, min(int(window_days), 365))
        with transaction(self.db_path) as conn:
            bank_filter = " AND i.bank_id = ?" if bank_id else ""
            attempt_bank_filter = " AND a.bank_id = ?" if bank_id else ""
            bank_params = [bank_id] if bank_id else []
            total = conn.execute(
                """SELECT COUNT(*) FROM bank_question_items i
                   JOIN questions q ON q.id = i.question_id AND q.is_deleted = 0
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   WHERE 1=1""" + bank_filter,
                [user_id, *bank_params],
            ).fetchone()[0]
            params = [user_id, *bank_params]
            recent = conn.execute(
                """SELECT COUNT(*) AS attempts,
                          COUNT(DISTINCT a.question_id) AS attempted_questions,
                          COALESCE(SUM(a.score_ratio), 0) AS score,
                          COALESCE(SUM(a.time_spent), 0) AS time_spent,
                          COALESCE(SUM(CASE WHEN a.correctness = 'CORRECT' THEN 1 ELSE 0 END), 0) AS correct
                   FROM answer_attempts a
                   JOIN questions q ON q.id = a.question_id AND q.is_deleted = 0
                   JOIN question_bank_members m ON m.bank_id = a.bank_id AND m.user_id = a.user_id
                   JOIN question_versions qv ON qv.id = a.question_version_id
                   WHERE a.user_id = ? AND UPPER(qv.type) NOT IN ('ESSAY', 'SHORT_ANSWER', 'SUBJECTIVE')""" + attempt_bank_filter + " AND a.created_at >= datetime('now', ?)" ,
                [*params, f"-{window_days} days"],
            ).fetchone()
            baseline = conn.execute(
                """SELECT COUNT(*) AS attempts,
                          COUNT(DISTINCT a.question_id) AS attempted_questions,
                          COALESCE(SUM(a.score_ratio), 0) AS score,
                          COALESCE(SUM(a.time_spent), 0) AS time_spent,
                          COALESCE(SUM(CASE WHEN a.correctness = 'CORRECT' THEN 1 ELSE 0 END), 0) AS correct
                   FROM answer_attempts a
                   JOIN questions q ON q.id = a.question_id AND q.is_deleted = 0
                   JOIN question_bank_members m ON m.bank_id = a.bank_id AND m.user_id = a.user_id
                   JOIN question_versions qv ON qv.id = a.question_version_id
                   WHERE a.user_id = ? AND UPPER(qv.type) NOT IN ('ESSAY', 'SHORT_ANSWER', 'SUBJECTIVE')""" + attempt_bank_filter + " AND a.created_at < datetime('now', ?)" ,
                [*params, f"-{window_days} days"],
            ).fetchone()
            due_filter = " AND i.bank_id = ?" if bank_id else ""
            due = conn.execute(
                """SELECT COUNT(*) FROM fsrs_cards f
                   JOIN questions q ON q.id = f.question_id AND q.is_deleted = 0
                   JOIN bank_question_items i ON i.question_id = f.question_id
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = f.user_id
                   LEFT JOIN kill_records k ON k.user_id = f.user_id AND k.question_id = f.question_id
                   LEFT JOIN mistake_records mr ON mr.user_id = f.user_id AND mr.question_id = f.question_id
                   LEFT JOIN weak_question_flags w ON w.user_id = f.user_id AND w.question_id = f.question_id
                   WHERE f.user_id = ? AND k.question_id IS NULL
                     AND datetime(replace(f.due_at, 'T', ' ')) <= CURRENT_TIMESTAMP
                     AND (w.question_id IS NOT NULL OR (mr.question_id IS NOT NULL AND mr.is_cleared = 0))""" + due_filter,
                [user_id, *bank_params],
            ).fetchone()[0]

        def metrics(row: dict) -> dict:
            attempts = int(row["attempts"] or 0)
            time_spent = int(row.get("time_spent") or 0)
            return {
                "attempts": attempts,
                "attempted_questions": int(row.get("attempted_questions") or 0),
                "correct_rate": round(int(row["correct"] or 0) / attempts * 100, 2) if attempts else 0.0,
                "score": round(float(row["score"] or 0), 2),
                "time_spent": time_spent,
                "avg_time_per_question": round(time_spent / attempts, 1) if attempts else 0.0,
            }

        recent_metrics = metrics(dict(recent))
        baseline_metrics = metrics(dict(baseline))
        attempted = int(recent["attempted_questions"] or 0)

        with transaction(self.db_path) as conn:
            lifetime = conn.execute(
                """SELECT COUNT(DISTINCT a.question_id) FROM answer_attempts a
                   JOIN questions q ON q.id = a.question_id AND q.is_deleted = 0
                   JOIN question_bank_members m ON m.bank_id = a.bank_id AND m.user_id = a.user_id
                   WHERE a.user_id = ?""" + attempt_bank_filter,
                [user_id, *bank_params],
            ).fetchone()[0]

            weak_bank_filter = " AND m.bank_id = ?" if bank_id else ""
            weak_rows = conn.execute(
                """SELECT qv.tags_json, qv.type, m.mistake_count
                   FROM mistake_records m
                   JOIN questions q ON q.id = m.question_id AND q.is_deleted = 0
                   JOIN question_bank_members mb ON mb.bank_id = m.bank_id AND mb.user_id = m.user_id
                   JOIN question_versions qv ON qv.question_id = m.question_id
                   LEFT JOIN kill_records k ON k.user_id = m.user_id AND k.question_id = m.question_id
                   WHERE m.user_id = ? AND m.is_cleared = 0 AND k.question_id IS NULL
                     AND qv.version_number = (SELECT MAX(version_number) FROM question_versions WHERE question_id = m.question_id)""" + weak_bank_filter,
                [user_id, *bank_params],
            ).fetchall()

            tag_mistakes = {}
            for row in weak_rows:
                tags = json.loads(row["tags_json"] or "[]")
                for tag in tags:
                    tag_mistakes[tag] = tag_mistakes.get(tag, 0) + int(row["mistake_count"] or 1)
                qtype = row["type"]
                if qtype:
                    tag_mistakes[qtype] = tag_mistakes.get(qtype, 0) + int(row["mistake_count"] or 1)
            sorted_weak = sorted(tag_mistakes.items(), key=lambda x: x[1], reverse=True)[:5]
            weak_points = [{"name": k, "mistakes": v} for k, v in sorted_weak]

            reviews_done = conn.execute(
                """SELECT COUNT(*) FROM answer_attempts a
                   JOIN questions q ON q.id = a.question_id AND q.is_deleted = 0
                   JOIN practice_sessions s ON s.id = a.session_id
                   WHERE a.user_id = ? AND a.created_at >= datetime('now', ?)
                   AND a.fsrs_rating IS NOT NULL AND s.mode = 'FSRS'""" + attempt_bank_filter,
                [user_id, f"-{window_days} days", *bank_params],
            ).fetchone()[0]
            total_review_needed = int(reviews_done) + int(due)
            review_completion_rate = round(int(reviews_done) / max(1, total_review_needed) * 100, 1) if total_review_needed > 0 else 100.0

        return {
            "window_days": window_days,
            "total_questions": int(total),
            "attempted_questions": int(lifetime),
            "coverage_percent": round(int(lifetime) / int(total) * 100, 2) if total else 0.0,
            "recent": recent_metrics,
            "baseline": baseline_metrics,
            "due_reviews": int(due),
            "recent_attempted_questions": attempted,
            "weak_points": weak_points,
            "review_completion_rate": review_completion_rate,
            "reviews_completed": int(reviews_done),
        }

    def recommendation_candidates(self, user_id: str, bank_id: str | None = None, question_type: str | None = None) -> list[dict]:
        """Return private learning state joined with current question content.

        The repository only gathers facts.  Ranking and explanation wording
        live in the learning domain so the API remains deterministic offline.
        """
        sql = """SELECT ? AS user_id, q.id AS question_id, i.bank_id,
                         COALESCE(l.mistake_count, 0) AS mistake_count,
                         COALESCE(l.consecutive_correct, 0) AS consecutive_correct,
                         COALESCE(l.mastery_status, 'UNSEEN') AS mastery_status,
                         COALESCE(l.is_cleared, 0) AS is_cleared, l.last_attempt_at,
                         qv.stem, qv.type, qv.tags_json, qv.difficulty, qv.chapter_id,
                         f.due_at, CASE WHEN w.question_id IS NULL THEN 0 ELSE 1 END AS is_weak_flagged,
                         CASE WHEN f.due_at IS NOT NULL
                                   AND datetime(replace(f.due_at, 'T', ' ')) <= CURRENT_TIMESTAMP
                              THEN 1 ELSE 0 END AS is_due
                  FROM bank_question_items i
                  JOIN questions q ON q.id = i.question_id AND q.is_deleted = 0
                  JOIN question_bank_members m
                    ON m.bank_id = i.bank_id AND m.user_id = ?
                  JOIN question_versions qv ON qv.question_id = q.id
                  LEFT JOIN learning_records l
                    ON l.user_id = ? AND l.question_id = q.id
                  LEFT JOIN fsrs_cards f
                    ON f.user_id = ? AND f.question_id = q.id
                  LEFT JOIN weak_question_flags w
                    ON w.user_id = ? AND w.question_id = q.id
                  LEFT JOIN kill_records k
                    ON k.user_id = ? AND k.question_id = q.id
                  WHERE k.question_id IS NULL
                    AND qv.version_number = (
                      SELECT MAX(version_number)
                      FROM question_versions WHERE question_id = q.id
                    )"""
        params: list = [user_id, user_id, user_id, user_id, user_id, user_id]
        if bank_id:
            sql += " AND i.bank_id = ?"
            params.append(bank_id)
        if question_type:
            sql += " AND qv.type = ?"
            params.append(question_type.upper())
        sql += " ORDER BY l.last_attempt_at DESC"
        with transaction(self.db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["tags"] = json.loads(item.pop("tags_json") or "[]")
                item["difficulty"] = int(item.get("difficulty") or 0)
                item["chapter_id"] = item.get("chapter_id")
                item["is_cleared"] = bool(item["is_cleared"])
                item["is_due"] = bool(item["is_due"])
                item["is_weak_flagged"] = bool(item["is_weak_flagged"])
                result.append(item)
            return result

    def kill(self, user_id: str, question_id: str) -> None:
        with transaction(self.db_path) as conn:
            access = conn.execute(
                """SELECT i.bank_id FROM bank_question_items i
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   WHERE i.question_id = ? LIMIT 1""",
                (user_id, question_id),
            ).fetchone()
            if not access:
                raise PermissionError("user cannot access this question bank")
            conn.execute("INSERT OR REPLACE INTO kill_records(user_id, question_id) VALUES (?, ?)", (user_id, question_id))

    def unkill(self, user_id: str, question_id: str) -> None:
        with transaction(self.db_path) as conn:
            conn.execute("DELETE FROM kill_records WHERE user_id = ? AND question_id = ?", (user_id, question_id))

    def list_killed(self, user_id: str) -> list[dict]:
        with transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT k.user_id, k.question_id, k.killed_at, qv.stem, qv.type,
                          i.bank_id
                   FROM kill_records k
                   JOIN questions q ON q.id = k.question_id AND q.is_deleted = 0
                   JOIN bank_question_items i ON i.question_id = k.question_id
                   JOIN question_bank_members m ON m.bank_id = i.bank_id AND m.user_id = ?
                   JOIN question_versions qv ON qv.question_id = k.question_id
                   WHERE k.user_id = ? AND qv.version_number = (SELECT MAX(version_number) FROM question_versions WHERE question_id = k.question_id)
                   ORDER BY k.killed_at DESC""", (user_id, user_id)).fetchall()
            return [dict(row) for row in rows]

    def append_events(self, user_id: str, events: list[dict]) -> int:
        accepted = 0
        with transaction(self.db_path) as conn:
            for event in events:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO learning_events(id, user_id, event_type, aggregate_type, aggregate_id, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (event["id"], user_id, event["event_type"], event["aggregate_type"], event["aggregate_id"], json.dumps(event.get("payload", {}), ensure_ascii=False)),
                )
                accepted += cursor.rowcount
        return accepted

    def list_events(self, user_id: str, after: str | None = None) -> list[dict]:
        with transaction(self.db_path) as conn:
            if after:
                # 检查 after 是否是事件的 id
                target_row = conn.execute("SELECT rowid, created_at FROM learning_events WHERE user_id = ? AND id = ?", (user_id, after)).fetchone()
                if target_row:
                    rows = conn.execute(
                        "SELECT id, event_type, aggregate_type, aggregate_id, payload_json, created_at FROM learning_events WHERE user_id = ? AND rowid > ? ORDER BY rowid ASC",
                        (user_id, target_row[0])
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, event_type, aggregate_type, aggregate_id, payload_json, created_at FROM learning_events WHERE user_id = ? AND (created_at > ? OR rowid > (SELECT COALESCE(MAX(rowid), 0) FROM learning_events WHERE user_id = ? AND created_at <= ?)) ORDER BY rowid ASC",
                        (user_id, after, user_id, after)
                    ).fetchall()
            else:
                rows = conn.execute("SELECT id, event_type, aggregate_type, aggregate_id, payload_json, created_at FROM learning_events WHERE user_id = ? ORDER BY rowid ASC", (user_id,)).fetchall()
            result = []
            for row in rows:
                value = dict(row)
                value["payload"] = json.loads(value.pop("payload_json"))
                result.append(value)
            return result
