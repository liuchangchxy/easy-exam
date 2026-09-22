#!/usr/bin/env python3
"""Unit tests for FSRS-5 spaced repetition algorithm and 6-level mistake engine."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from backend.database import init_db
from backend.models import MistakeCause
from backend.repositories import (
    BankRepository,
    QuestionRepository,
    MistakeRepository,
)
from backend.services.fsrs import FSRS5, FSRSResult, DEFAULT_W
from backend.services.mistake_service import MistakeService, TAXONOMY_CAUSES


class TestFSRSAlgorithm(unittest.TestCase):
    """Test pure FSRS-5 scheduling formulas, stability, and difficulty calculations."""

    def setUp(self):
        self.fsrs = FSRS5()

    def test_init_stability_and_difficulty(self):
        """Initial stability and difficulty must reflect the 4 rating scales."""
        # 1=Again, 2=Hard, 3=Good, 4=Easy
        s1 = self.fsrs.init_stability(1)
        s2 = self.fsrs.init_stability(2)
        s3 = self.fsrs.init_stability(3)
        s4 = self.fsrs.init_stability(4)
        self.assertLess(s1, s2)
        self.assertLess(s2, s3)
        self.assertLess(s3, s4)

        d1 = self.fsrs.init_difficulty(1)
        d4 = self.fsrs.init_difficulty(4)
        # Rating 1 is hardest -> highest difficulty; Rating 4 is easiest -> lowest difficulty
        self.assertGreater(d1, d4)
        self.assertTrue(1.0 <= d4 <= 10.0)
        self.assertTrue(1.0 <= d1 <= 10.0)

    def test_schedule_new_cards(self):
        """Scheduling a new card (stability=0) initializes FSRS parameters."""
        now = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)

        # Rating 1 (Again) -> scheduled for 1 day
        res_again = self.fsrs.schedule(rating=1, stability=0.0, difficulty=5.0, now=now)
        self.assertIsInstance(res_again, FSRSResult)
        self.assertEqual(res_again.scheduled_days, 1)
        self.assertEqual(res_again.due, now + timedelta(days=1))
        self.assertAlmostEqual(res_again.stability, DEFAULT_W[0], places=2)

        # Rating 3 (Good) -> scheduled for multiple days (stability w2=2.4)
        res_good = self.fsrs.schedule(rating=3, stability=0.0, difficulty=5.0, now=now)
        self.assertGreaterEqual(res_good.scheduled_days, 1)
        self.assertGreater(res_good.stability, res_again.stability)
        self.assertEqual(res_good.due, now + timedelta(days=res_good.scheduled_days))

        # Rating 4 (Easy) -> longest initial interval
        res_easy = self.fsrs.schedule(rating=4, stability=0.0, difficulty=5.0, now=now)
        self.assertGreater(res_easy.scheduled_days, res_good.scheduled_days)
        self.assertGreater(res_easy.stability, res_good.stability)

    def test_schedule_review_cards(self):
        """Reviewing an existing card updates stability, difficulty, and interval."""
        now = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc)

        # Good review after 2 days
        res_review = self.fsrs.schedule(
            rating=3,
            stability=2.4,
            difficulty=5.0,
            elapsed_days=2.0,
            now=now,
        )
        self.assertGreater(res_review.stability, 2.4)
        self.assertGreater(res_review.scheduled_days, 2)
        self.assertEqual(res_review.due, now + timedelta(days=res_review.scheduled_days))

        # Lapse review (Again on existing card) -> scheduled_days reset to 1
        res_lapse = self.fsrs.schedule(
            rating=1,
            stability=5.0,
            difficulty=5.0,
            elapsed_days=5.0,
            now=now,
        )
        self.assertEqual(res_lapse.scheduled_days, 1)
        self.assertEqual(res_lapse.due, now + timedelta(days=1))

    def test_next_interval_retention_sensitivity(self):
        """Lower requested retention allows longer intervals; higher retention shortens intervals."""
        s = 10.0
        interval_90 = self.fsrs.next_interval(s, request_retention=0.9)
        interval_80 = self.fsrs.next_interval(s, request_retention=0.8)
        interval_95 = self.fsrs.next_interval(s, request_retention=0.95)

        self.assertGreater(interval_80, interval_90)
        self.assertLess(interval_95, interval_90)

    def test_formula_helpers(self):
        """Verify helper methods for formula steps."""
        d = self.fsrs.next_difficulty(5.0, rating=3)
        self.assertTrue(1.0 <= d <= 10.0)

        r = self.fsrs.retrievability(elapsed_days=2.0, stability=2.4)
        self.assertTrue(0.0 <= r <= 1.0)

        s_next = self.fsrs.next_stability(d=5.0, s=2.4, r=r, rating=3)
        self.assertGreater(s_next, 0.1)


class TestMistakeEvaluation(unittest.TestCase):
    """Test 2-consecutive-correct elimination rule and state machine."""

    def setUp(self):
        self.service = MistakeService()

    def test_evaluate_answer_consecutive_correct_kill(self):
        """Two consecutive correct answers eliminate the mistake; failure resets counter."""
        record = {"consecutive_correct": 0, "is_cleared": False, "mistake_count": 1}

        # 1. First correct answer
        rec1 = self.service.evaluate_answer(record, is_correct=True)
        self.assertEqual(rec1["consecutive_correct"], 1)
        self.assertFalse(rec1["is_cleared"])

        # 2. Second consecutive correct answer -> is_cleared becomes True
        rec2 = self.service.evaluate_answer(rec1, is_correct=True)
        self.assertEqual(rec2["consecutive_correct"], 2)
        self.assertTrue(rec2["is_cleared"])

        # 3. Subsequent wrong answer -> resets consecutive_correct to 0, reactivates mistake
        rec3 = self.service.evaluate_answer(rec2, is_correct=False, cause="CONCEPT_GAP")
        self.assertEqual(rec3["consecutive_correct"], 0)
        self.assertFalse(rec3["is_cleared"])
        self.assertEqual(rec3["mistake_cause"], "CONCEPT_GAP")
        self.assertEqual(rec3["mistake_count"], 2)

    def test_evaluate_answer_wrong_resets_streak(self):
        """Single correct answer followed by wrong resets consecutive streak to 0."""
        record = {"consecutive_correct": 1, "is_cleared": False, "mistake_count": 1}
        rec = self.service.evaluate_answer(record, is_correct=False, cause="READING_MISS")
        self.assertEqual(rec["consecutive_correct"], 0)
        self.assertFalse(rec["is_cleared"])
        self.assertEqual(rec["mistake_count"], 2)
        self.assertEqual(rec["mistake_cause"], "READING_MISS")


class TestMistakeServiceIntegration(unittest.TestCase):
    """Test MistakeService with database repository, FSRS scheduling, and taxonomy filtering."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_fsrs_engine.db")
        init_db(self.db_path)

        self.bank_repo = BankRepository(self.db_path)
        self.q_repo = QuestionRepository(self.db_path)
        self.mistake_repo = MistakeRepository(self.db_path)
        self.service = MistakeService(mistake_repo=self.mistake_repo)

        self.bank_id = self.bank_repo.create_bank("FSRS测试题库")
        self.q_id = self.q_repo.create_question(
            bank_id=self.bank_id,
            q_type="SINGLE",
            stem="中国近代史开端是哪一年？",
            options=[{"key": "A", "content": "1840"}, {"key": "B", "content": "1919"}],
            answer="A",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_first_time_correct_not_active_mistake(self):
        """Questions answered correctly on first encounter should not be recorded as active mistakes."""
        q2_id = self.q_repo.create_question(
            bank_id=self.bank_id,
            q_type="SINGLE",
            stem="1+1=?",
            options=[{"key": "A", "content": "2"}],
            answer="A",
        )
        res = self.service.record_question_result(
            question_id=q2_id,
            bank_id=self.bank_id,
            is_correct=True,
        )
        self.assertTrue(res["is_cleared"])

        # Must not appear in active uncleared mistakes
        uncleared = self.mistake_repo.get_mistakes(bank_id=self.bank_id, only_uncleared=True)
        self.assertEqual(len(uncleared), 0)

    def test_record_wrong_then_two_correct_elimination_flow(self):
        """Wrong answer creates active mistake with FSRS schedule; two correct answers eliminate it."""
        # 1. Answer wrongly
        rec1 = self.service.record_question_result(
            question_id=self.q_id,
            bank_id=self.bank_id,
            is_correct=False,
            cause=MistakeCause.CONCEPT_GAP,
        )
        self.assertEqual(rec1["mistake_count"], 1)
        self.assertEqual(rec1["consecutive_correct"], 0)
        self.assertFalse(rec1["is_cleared"])
        self.assertEqual(rec1["mistake_cause"], "CONCEPT_GAP")
        self.assertIsNotNone(rec1["fsrs_due"])
        self.assertGreater(rec1["fsrs_stability"], 0.0)

        active = self.mistake_repo.get_mistakes(bank_id=self.bank_id, only_uncleared=True)
        self.assertEqual(len(active), 1)

        # 2. First correct review
        rec2 = self.service.record_question_result(
            question_id=self.q_id,
            bank_id=self.bank_id,
            is_correct=True,
        )
        self.assertEqual(rec2["consecutive_correct"], 1)
        self.assertFalse(rec2["is_cleared"])

        # 3. Second consecutive correct review -> Eliminated!
        rec3 = self.service.record_question_result(
            question_id=self.q_id,
            bank_id=self.bank_id,
            is_correct=True,
        )
        self.assertEqual(rec3["consecutive_correct"], 2)
        self.assertTrue(rec3["is_cleared"])

        # Uncleared list is now empty
        active_after = self.mistake_repo.get_mistakes(bank_id=self.bank_id, only_uncleared=True)
        self.assertEqual(len(active_after), 0)

    def test_get_due_reviews(self):
        """get_due_reviews returns uncleared mistakes where fsrs_due <= as_of."""
        # Record a mistake
        self.service.record_question_result(
            question_id=self.q_id,
            bank_id=self.bank_id,
            is_correct=False,
            cause="READING_MISS",
        )

        now = datetime.now(timezone.utc)
        # As of tomorrow (due date is +1 day or earlier for rating Again)
        future_time = now + timedelta(days=2)
        due_list = self.service.get_due_reviews(bank_id=self.bank_id, as_of=future_time)
        self.assertEqual(len(due_list), 1)
        self.assertEqual(due_list[0]["question_id"], self.q_id)

        # As of 10 days ago -> not due yet
        past_time = now - timedelta(days=10)
        not_due_list = self.service.get_due_reviews(bank_id=self.bank_id, as_of=past_time)
        self.assertEqual(len(not_due_list), 0)

    def test_get_active_mistakes_by_cause_taxonomy(self):
        """Filter active uncleared mistakes by 6-level taxonomy."""
        causes = [
            "READING_MISS",
            "CONCEPT_GAP",
            "METHOD_GAP",
            "OPTION_TRAP",
            "CALCULATION_ERROR",
            "CARELESSNESS",
        ]
        created_q_ids = []
        for i, cause in enumerate(causes):
            qid = self.q_repo.create_question(
                bank_id=self.bank_id,
                q_type="SINGLE",
                stem=f"题目{i+1}",
                options=[{"key": "A", "content": "1"}],
                answer="A",
            )
            created_q_ids.append(qid)
            self.service.record_question_result(
                question_id=qid,
                bank_id=self.bank_id,
                is_correct=False,
                cause=cause,
            )

        # Verify taxonomy constant contains all 6 causes
        for c in causes:
            self.assertIn(c, TAXONOMY_CAUSES)

        # Filter by each cause individually
        for c in causes:
            filtered = self.service.get_active_mistakes_by_cause(bank_id=self.bank_id, cause=c)
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]["mistake_cause"], c)

        # Eliminate one question (2 consecutive correct)
        target_qid = created_q_ids[0]  # READING_MISS
        self.service.record_question_result(target_qid, self.bank_id, is_correct=True)
        self.service.record_question_result(target_qid, self.bank_id, is_correct=True)

        # Now READING_MISS should return 0 active mistakes
        reading_miss_active = self.service.get_active_mistakes_by_cause(
            bank_id=self.bank_id,
            cause="READING_MISS",
        )
        self.assertEqual(len(reading_miss_active), 0)


if __name__ == "__main__":
    unittest.main()
