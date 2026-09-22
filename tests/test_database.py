#!/usr/bin/env python3
"""Unit tests for SQLite WAL database layer and core repositories."""
import os
import tempfile
import unittest

from backend.database import init_db, get_connection
from backend.models import QuestionType, SessionMode, MistakeCause
from backend.repositories import (
    BankRepository,
    QuestionRepository,
    SessionRepository,
    MistakeRepository,
)


class TestDatabase(unittest.TestCase):
    """Test database initialization and WAL settings."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_exam.db")
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_wal_mode_and_busy_timeout(self):
        """Verify WAL journal mode and busy timeout are configured."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        self.assertEqual(mode.lower(), "wal")

        cursor.execute("PRAGMA busy_timeout;")
        timeout = cursor.fetchone()[0]
        self.assertEqual(timeout, 5000)
        conn.close()

    def test_schema_tables_created(self):
        """Verify all 4 core tables exist in the schema."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected_tables = {"banks", "questions", "sessions", "mistake_records"}
        self.assertTrue(expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}")

    def test_bank_crud(self):
        """Verify BankRepository create, get, and list operations."""
        repo = BankRepository(self.db_path)
        bank_id = repo.create_bank("公考行测", "行测真题库", "公务员")
        self.assertIsInstance(bank_id, str)
        self.assertTrue(len(bank_id) > 0)

        bank = repo.get_bank(bank_id)
        self.assertIsNotNone(bank)
        self.assertEqual(bank["name"], "公考行测")
        self.assertEqual(bank["description"], "行测真题库")
        self.assertEqual(bank["category"], "公务员")
        self.assertEqual(bank["question_count"], 0)

        banks = repo.list_banks()
        self.assertEqual(len(banks), 1)
        self.assertEqual(banks[0]["id"], bank_id)

        # Non-existent bank
        self.assertIsNone(repo.get_bank("non-existent-id"))

    def test_question_crud_and_deserialization(self):
        """Verify QuestionRepository create, get, and list by bank."""
        b_repo = BankRepository(self.db_path)
        bank_id = b_repo.create_bank("测试题库", "描述", "科目")

        q_repo = QuestionRepository(self.db_path)
        options = [
            {"key": "A", "content": "1"},
            {"key": "B", "content": "2"},
        ]
        tags = ["数学", "初级"]

        q_id = q_repo.create_question(
            bank_id=bank_id,
            q_type=QuestionType.SINGLE,
            stem="1+1=?",
            options=options,
            answer="B",
            explanation="基础算术",
            difficulty=1,
            tags=tags,
        )
        self.assertIsInstance(q_id, str)

        q = q_repo.get_question(q_id)
        self.assertIsNotNone(q)
        self.assertEqual(q["id"], q_id)
        self.assertEqual(q["bank_id"], bank_id)
        self.assertEqual(q["type"], "SINGLE")
        self.assertEqual(q["stem"], "1+1=?")
        self.assertEqual(q["answer"], "B")
        self.assertEqual(q["explanation"], "基础算术")
        self.assertEqual(q["difficulty"], 1)

        # JSON fields must be deserialized to native Python structures
        self.assertEqual(q["options"], options)
        self.assertEqual(q["tags"], tags)

        # Bank question count should be updated
        bank = b_repo.get_bank(bank_id)
        self.assertEqual(bank["question_count"], 1)

        # List questions by bank
        q_list = q_repo.list_questions_by_bank(bank_id)
        self.assertEqual(len(q_list), 1)
        self.assertEqual(q_list[0]["id"], q_id)
        self.assertEqual(q_list[0]["options"], options)

        # Non-existent question
        self.assertIsNone(q_repo.get_question("unknown-q"))

    def test_session_lifecycle_and_progress(self):
        """Verify SessionRepository create, get, and progress update."""
        b_repo = BankRepository(self.db_path)
        bank_id = b_repo.create_bank("模考题库")

        s_repo = SessionRepository(self.db_path)
        session_id = s_repo.create_session(
            bank_id=bank_id,
            mode=SessionMode.EXAM,
            total_questions=50,
            time_limit=3600,
        )
        self.assertIsInstance(session_id, str)

        session = s_repo.get_session(session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session["bank_id"], bank_id)
        self.assertEqual(session["mode"], "EXAM")
        self.assertEqual(session["total_questions"], 50)
        self.assertEqual(session["time_limit"], 3600)
        self.assertEqual(session["current_index"], 0)
        self.assertEqual(session["time_spent"], 0)
        self.assertEqual(session["is_completed"], 0)

        # Update progress
        s_repo.update_session_progress(
            session_id=session_id,
            current_index=5,
            answers_json='{"q1": {"answer": "A", "is_correct": true}}',
            flags_json='["q2"]',
            time_spent=120,
        )

        updated = s_repo.get_session(session_id)
        self.assertEqual(updated["current_index"], 5)
        self.assertEqual(updated["answers_json"], '{"q1": {"answer": "A", "is_correct": true}}')
        self.assertEqual(updated["flags_json"], '["q2"]')
        self.assertEqual(updated["time_spent"], 120)

    def test_mistake_records_and_elimination_flow(self):
        """Verify MistakeRepository upsert logic, consecutive correct, and clearing."""
        b_repo = BankRepository(self.db_path)
        bank_id = b_repo.create_bank("错题测试库")
        q_repo = QuestionRepository(self.db_path)
        q_id = q_repo.create_question(
            bank_id=bank_id,
            q_type="SINGLE",
            stem="题目1",
            options=[{"key": "A", "content": "1"}],
            answer="A",
        )

        m_repo = MistakeRepository(self.db_path)

        # 1. 首次答错：新增错题记录，连对0，未消灭
        rec1 = m_repo.upsert_mistake(
            question_id=q_id,
            bank_id=bank_id,
            is_correct=False,
            mistake_cause=MistakeCause.CONCEPT_GAP,
        )
        self.assertEqual(rec1["mistake_count"], 1)
        self.assertEqual(rec1["consecutive_correct"], 0)
        self.assertEqual(rec1["is_cleared"], 0)
        self.assertEqual(rec1["mistake_cause"], "CONCEPT_GAP")

        # 检查 get_mistakes 列表包含该错题
        uncleared = m_repo.get_mistakes(bank_id=bank_id, only_uncleared=True)
        self.assertEqual(len(uncleared), 1)
        self.assertEqual(uncleared[0]["question_id"], q_id)

        # 2. 第一次答对：连对 1，仍未消灭
        rec2 = m_repo.upsert_mistake(
            question_id=q_id,
            bank_id=bank_id,
            is_correct=True,
        )
        self.assertEqual(rec2["mistake_count"], 1)
        self.assertEqual(rec2["consecutive_correct"], 1)
        self.assertEqual(rec2["is_cleared"], 0)

        # 3. 第二次连对：连对 2，达到消灭阈值，自动消灭 (is_cleared=1)
        rec3 = m_repo.upsert_mistake(
            question_id=q_id,
            bank_id=bank_id,
            is_correct=True,
        )
        self.assertEqual(rec3["consecutive_correct"], 2)
        self.assertEqual(rec3["is_cleared"], 1)

        # 此时 only_uncleared=True 应为空，only_uncleared=False 应能查到
        self.assertEqual(len(m_repo.get_mistakes(bank_id=bank_id, only_uncleared=True)), 0)
        all_mistakes = m_repo.get_mistakes(bank_id=bank_id, only_uncleared=False)
        self.assertEqual(len(all_mistakes), 1)
        self.assertEqual(all_mistakes[0]["is_cleared"], 1)

        # 4. 后续一旦再次答错：连对清零，重新激活 (is_cleared=0)，错题次数累加为 2
        rec4 = m_repo.upsert_mistake(
            question_id=q_id,
            bank_id=bank_id,
            is_correct=False,
            mistake_cause=MistakeCause.READING_MISS,
        )
        self.assertEqual(rec4["mistake_count"], 2)
        self.assertEqual(rec4["consecutive_correct"], 0)
        self.assertEqual(rec4["is_cleared"], 0)
        self.assertEqual(rec4["mistake_cause"], "READING_MISS")

        # 再次进入 uncleared 列表
        self.assertEqual(len(m_repo.get_mistakes(bank_id=bank_id, only_uncleared=True)), 1)

    def test_wal_concurrency(self):
        """Verify WAL mode allows concurrent readers and writers without deadlock."""
        b_repo = BankRepository(self.db_path)
        bank_id = b_repo.create_bank("并发题库")

        # Open reader connection
        conn_reader = get_connection(self.db_path)
        cursor_reader = conn_reader.cursor()
        cursor_reader.execute("SELECT COUNT(*) FROM banks;")
        self.assertEqual(cursor_reader.fetchone()[0], 1)

        # Write on another connection
        b_repo.create_bank("并发题库2")

        # Reader can read immediately without lock contention
        cursor_reader.execute("SELECT COUNT(*) FROM banks;")
        self.assertEqual(cursor_reader.fetchone()[0], 2)
        conn_reader.close()


if __name__ == "__main__":
    unittest.main()
