"""Core database repositories for banks, questions, sessions, and mistakes."""
import json
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional
import sqlite3

from backend.database import get_connection


class BaseRepository:
    """Base repository handling SQLite connections and transactions."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = get_connection(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


class BankRepository(BaseRepository):
    """Repository for managing question banks."""

    def create_bank(
        self,
        name: str,
        description: str = "",
        category: str = "默认分类",
    ) -> str:
        bank_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO banks (id, name, description, category, question_count)
                VALUES (?, ?, ?, ?, 0);
                """,
                (bank_id, name, description, category),
            )
        return bank_id

    def get_bank(self, bank_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            cursor = conn.execute("SELECT * FROM banks WHERE id = ?;", (bank_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_banks(self) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cursor = conn.execute("SELECT * FROM banks ORDER BY created_at DESC;")
            return [dict(row) for row in cursor.fetchall()]

    def update_question_count(self, bank_id: str) -> int:
        with self._conn() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM questions WHERE bank_id = ?;", (bank_id,)
            )
            count = cursor.fetchone()[0]
            conn.execute(
                """
                UPDATE banks
                SET question_count = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (count, bank_id),
            )
            return count

    def delete_bank(self, bank_id: str) -> bool:
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM banks WHERE id = ?;", (bank_id,))
            return cursor.rowcount > 0


class QuestionRepository(BaseRepository):
    """Repository for managing questions within banks."""

    def create_question(
        self,
        bank_id: str,
        q_type: Any,
        stem: str,
        options: List[Dict[str, Any]],
        answer: str,
        explanation: str = "",
        difficulty: int = 3,
        tags: Optional[List[str]] = None,
    ) -> str:
        q_id = str(uuid.uuid4())
        type_str = q_type.value if hasattr(q_type, "value") else str(q_type)
        options_json = json.dumps(options, ensure_ascii=False)
        tags_json = json.dumps(tags or [], ensure_ascii=False)

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO questions (
                    id, bank_id, type, stem, options_json, answer,
                    explanation, difficulty, tags_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    q_id,
                    bank_id,
                    type_str,
                    stem,
                    options_json,
                    answer,
                    explanation,
                    difficulty,
                    tags_json,
                ),
            )
            # Synchronize bank question count
            conn.execute(
                """
                UPDATE banks
                SET question_count = (SELECT COUNT(*) FROM questions WHERE bank_id = ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (bank_id, bank_id),
            )
        return q_id

    def _deserialize_question(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        if "options_json" in d:
            try:
                d["options"] = json.loads(d["options_json"])
            except Exception:
                d["options"] = []
        else:
            d["options"] = []

        if "tags_json" in d:
            try:
                d["tags"] = json.loads(d["tags_json"])
            except Exception:
                d["tags"] = []
        else:
            d["tags"] = []
        return d

    def get_question(self, q_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            cursor = conn.execute("SELECT * FROM questions WHERE id = ?;", (q_id,))
            row = cursor.fetchone()
            return self._deserialize_question(row) if row else None

    def list_questions_by_bank(self, bank_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM questions WHERE bank_id = ? ORDER BY created_at ASC;",
                (bank_id,),
            )
            return [self._deserialize_question(row) for row in cursor.fetchall()]

    get_by_bank = list_questions_by_bank

    def delete_question(self, q_id: str) -> bool:
        with self._conn() as conn:
            cursor = conn.execute(
                "SELECT bank_id FROM questions WHERE id = ?;", (q_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False
            bank_id = row[0]
            conn.execute("DELETE FROM questions WHERE id = ?;", (q_id,))
            conn.execute(
                """
                UPDATE banks
                SET question_count = (SELECT COUNT(*) FROM questions WHERE bank_id = ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (bank_id, bank_id),
            )
            return True


class SessionRepository(BaseRepository):
    """Repository for managing practice and exam sessions."""

    def create_session(
        self,
        bank_id: str,
        mode: Any,
        total_questions: int,
        time_limit: int = 0,
    ) -> str:
        session_id = str(uuid.uuid4())
        mode_str = mode.value if hasattr(mode, "value") else str(mode)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    id, bank_id, mode, total_questions, current_index,
                    answers_json, flags_json, time_spent, time_limit,
                    is_completed, score
                )
                VALUES (?, ?, ?, ?, 0, '{}', '[]', 0, ?, 0, 0.0);
                """,
                (session_id, bank_id, mode_str, total_questions, time_limit),
            )
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE id = ?;", (session_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_session_progress(
        self,
        session_id: str,
        current_index: int,
        answers_json: str,
        flags_json: str,
        time_spent: int,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET current_index = ?,
                    answers_json = ?,
                    flags_json = ?,
                    time_spent = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (current_index, answers_json, flags_json, time_spent, session_id),
            )

    def complete_session(self, session_id: str, score: float = 0.0) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET is_completed = 1,
                    score = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (score, session_id),
            )


class MistakeRepository(BaseRepository):
    """Repository for managing mistake records and FSRS progression."""

    def upsert_mistake(
        self,
        question_id: str,
        bank_id: str,
        is_correct: bool,
        mistake_cause: Optional[Any] = None,
    ) -> Dict[str, Any]:
        cause_str = (
            mistake_cause.value
            if hasattr(mistake_cause, "value")
            else (str(mistake_cause) if mistake_cause is not None else None)
        )

        with self._conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM mistake_records WHERE question_id = ?;",
                (question_id,),
            )
            existing = cursor.fetchone()

            if existing:
                rec = dict(existing)
                mistake_count = rec["mistake_count"]
                consecutive_correct = rec["consecutive_correct"]
                is_cleared = rec["is_cleared"]
                current_cause = rec["mistake_cause"]

                if is_correct:
                    consecutive_correct += 1
                    if consecutive_correct >= 2:
                        is_cleared = 1
                else:
                    mistake_count += 1
                    consecutive_correct = 0
                    is_cleared = 0
                    if cause_str is not None:
                        current_cause = cause_str

                conn.execute(
                    """
                    UPDATE mistake_records
                    SET mistake_count = ?,
                        consecutive_correct = ?,
                        is_cleared = ?,
                        mistake_cause = ?,
                        last_review_at = CURRENT_TIMESTAMP
                    WHERE question_id = ?;
                    """,
                    (
                        mistake_count,
                        consecutive_correct,
                        is_cleared,
                        current_cause,
                        question_id,
                    ),
                )
            else:
                rec_id = str(uuid.uuid4())
                if is_correct:
                    mistake_count = 0
                    consecutive_correct = 1
                    is_cleared = 0
                else:
                    mistake_count = 1
                    consecutive_correct = 0
                    is_cleared = 0

                conn.execute(
                    """
                    INSERT INTO mistake_records (
                        id, question_id, bank_id, mistake_count,
                        consecutive_correct, is_cleared, mistake_cause,
                        last_review_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                    """,
                    (
                        rec_id,
                        question_id,
                        bank_id,
                        mistake_count,
                        consecutive_correct,
                        is_cleared,
                        cause_str,
                    ),
                )

            cursor = conn.execute(
                "SELECT * FROM mistake_records WHERE question_id = ?;",
                (question_id,),
            )
            return dict(cursor.fetchone())

    def get_mistake(self, question_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM mistake_records WHERE question_id = ?;",
                (question_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_mistakes(
        self,
        bank_id: Optional[str] = None,
        only_uncleared: bool = True,
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM mistake_records WHERE 1=1"
        params: List[Any] = []
        if bank_id is not None:
            sql += " AND bank_id = ?"
            params.append(bank_id)
        if only_uncleared:
            sql += " AND is_cleared = 0"
        sql += " ORDER BY last_review_at DESC, created_at DESC;"

        with self._conn() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def update_fsrs(
        self,
        question_id: str,
        fsrs_state: int,
        fsrs_stability: float,
        fsrs_difficulty: float,
        fsrs_due: str,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE mistake_records
                SET fsrs_state = ?,
                    fsrs_stability = ?,
                    fsrs_difficulty = ?,
                    fsrs_due = ?,
                    last_review_at = CURRENT_TIMESTAMP
                WHERE question_id = ?;
                """,
                (
                    fsrs_state,
                    fsrs_stability,
                    fsrs_difficulty,
                    fsrs_due,
                    question_id,
                ),
            )
