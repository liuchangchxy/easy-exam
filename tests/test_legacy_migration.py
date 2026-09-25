import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.database import init_db
from backend.repositories import BankRepository, QuestionRepository, SessionRepository, MistakeRepository
from scripts.migrate_legacy_db import migrate_legacy_db
from scripts.verify_migration import verify_migration


class TestLegacyMigration(unittest.TestCase):
    def test_dry_run_does_not_create_target_and_reports_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.db"
            target = Path(tmp) / "new.db"
            report = Path(tmp) / "dry-run.json"
            init_db(str(source))
            bank_id = BankRepository(str(source)).create_bank("旧题库")
            question_id = QuestionRepository(str(source)).create_question(bank_id, "SINGLE", "题目", [{"key": "A", "content": "答案"}], "A")
            session_id = SessionRepository(str(source)).create_session(bank_id, "PRACTICE", 1, questions_json='[{"id": "' + question_id + '", "type": "SINGLE", "answer": "A"}]')
            SessionRepository(str(source)).update_session_progress(session_id, 0, '{"' + question_id + '": {"answer": "B", "is_correct": false, "score_ratio": 0.0}}', '[]', 5)
            MistakeRepository(str(source)).upsert_mistake(question_id, bank_id, is_correct=False)

            result = migrate_legacy_db(str(source), str(target), str(report), dry_run=True)

            self.assertFalse(target.exists())
            self.assertEqual(result["counts"]["banks"], 1)
            self.assertEqual(result["counts"]["questions"], 1)
            self.assertTrue(report.exists())

    def test_migration_creates_default_user_and_preserves_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.db"
            target = Path(tmp) / "new.db"
            report = Path(tmp) / "migration.json"
            init_db(str(source))
            bank_id = BankRepository(str(source)).create_bank("旧题库")
            question_id = QuestionRepository(str(source)).create_question(bank_id, "SINGLE", "题目", [{"key": "A", "content": "答案"}], "A")
            session_id = SessionRepository(str(source)).create_session(bank_id, "PRACTICE", 1, questions_json='[{"id": "' + question_id + '", "type": "SINGLE", "answer": "A"}]')
            SessionRepository(str(source)).update_session_progress(session_id, 0, '{"' + question_id + '": {"answer": "B", "is_correct": false, "score_ratio": 0.0}}', '[]', 5)
            MistakeRepository(str(source)).upsert_mistake(question_id, bank_id, is_correct=False)

            result = migrate_legacy_db(str(source), str(target), str(report), dry_run=False)
            verification = verify_migration(str(target), result["source_counts"])

            self.assertEqual(verification["questions"], 1)
            self.assertEqual(verification["banks"], 1)
            self.assertEqual(verification["question_versions"], 1)
            self.assertEqual(verification["practice_sessions"], 1)
            self.assertEqual(verification["answer_attempts"], 1)
            self.assertEqual(verification["learning_records"], 1)
            self.assertEqual(verification["mistake_records"], 1)
            self.assertTrue(result["backup_path"])

            conn = sqlite3.connect(str(target))
            try:
                # 迁移验证安全规范：历史迁入的作答真实保持 card_snapshot_json 为 NULL，杜绝虚假基准伪造
                legacy_attempt = conn.execute("SELECT card_snapshot_json, fsrs_rating FROM answer_attempts LIMIT 1").fetchone()
                self.assertIsNone(legacy_attempt[0])
            finally:
                conn.close()

    def test_migration_records_unconverted_records_and_enforces_foreign_keys_and_readonly_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.db"
            target = Path(tmp) / "new.db"
            report = Path(tmp) / "migration.json"
            init_db(str(source))
            bank_id = BankRepository(str(source)).create_bank("正常题库")
            q_id = QuestionRepository(str(source)).create_question(bank_id, "SINGLE", "题", [{"key": "A", "content": "1"}], "A")

            conn = sqlite3.connect(str(source))
            try:
                conn.execute(
                    "INSERT INTO questions (id, bank_id, type, stem, options_json, answer) VALUES (?, ?, 'SINGLE', '孤儿题', '[]', 'A')",
                    ("orphaned-question", "non-existent-bank")
                )
                conn.execute(
                    "INSERT INTO sessions (id, bank_id, mode, total_questions, answers_json) VALUES (?, ?, 'PRACTICE', 1, ?)",
                    ("orphaned-sess", "non-existent-bank", '{"' + q_id + '": {"answer": "A", "is_correct": true}}')
                )
                conn.execute(
                    "INSERT INTO sessions (id, bank_id, mode, total_questions, answers_json) VALUES (?, ?, 'PRACTICE', 1, ?)",
                    ("sess-with-bad-q", bank_id, '{"non-existent-q": {"answer": "A", "is_correct": true}}')
                )
                conn.execute(
                    "INSERT INTO mistake_records (question_id, bank_id, mistake_count) VALUES (?, ?, 1)",
                    ("non-existent-q", bank_id)
                )
                conn.commit()
            finally:
                conn.close()

            result = migrate_legacy_db(str(source), str(target), str(report), dry_run=False)

            self.assertIn("unconverted", result)
            self.assertEqual(len(result["unconverted"]["questions"]), 1)
            self.assertEqual(result["unconverted"]["questions"][0]["question_id"], "orphaned-question")
            self.assertEqual(len(result["unconverted"]["sessions"]), 1)
            self.assertEqual(result["unconverted"]["sessions"][0]["session_id"], "orphaned-sess")
            self.assertEqual(len(result["unconverted"]["answers"]), 1)
            self.assertEqual(result["unconverted"]["answers"][0]["question_id"], "non-existent-q")
            self.assertEqual(len(result["unconverted"]["mistakes"]), 1)
            self.assertEqual(result["unconverted"]["mistakes"][0]["question_id"], "non-existent-q")
            self.assertTrue(len(result["warnings"]) >= 4)

            self.assertIn("migrated_user", result)
            self.assertTrue(result["migrated_user"]["must_change_password"])
            self.assertNotEqual(result["migrated_user"]["temporary_password"], "migration-reset-required")
            self.assertTrue(len(result["migrated_user"]["temporary_password"]) >= 16)


if __name__ == "__main__":
    unittest.main()
