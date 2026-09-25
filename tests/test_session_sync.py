"""Tests for Scorer and SessionService (Scoring, Session Sync, and Draft Merging)."""
import os
import shutil
import tempfile
import unittest

from backend.database import init_db
from backend.models import MistakeCause, QuestionType, SessionMode
from backend.repositories import (
    BankRepository,
    MistakeRepository,
    QuestionRepository,
    SessionRepository,
)
from backend.services.mistake_service import MistakeService
from backend.services.scoring import Scorer
from backend.services.session_service import SessionService


class TestScorer(unittest.TestCase):
    """Unit tests for Scorer evaluating different question types."""

    def test_single_choice_scoring(self):
        """Single choice scoring exact match, whitespace, case, and mismatch."""
        # Exact match
        is_cor, ratio = Scorer.evaluate("SINGLE", "A", "A")
        self.assertTrue(is_cor)
        self.assertEqual(ratio, 1.0)

        # Case-insensitive and whitespace stripped
        is_cor, ratio = Scorer.evaluate("SINGLE", "  b ", "B")
        self.assertTrue(is_cor)
        self.assertEqual(ratio, 1.0)

        # Mismatch
        is_cor, ratio = Scorer.evaluate("SINGLE", "B", "A")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

        # Empty or None
        is_cor, ratio = Scorer.evaluate("SINGLE", "", "A")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

        is_cor, ratio = Scorer.evaluate("SINGLE", None, "A")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

        # QuestionType enum support
        is_cor, ratio = Scorer.evaluate(QuestionType.SINGLE, "C", "C")
        self.assertTrue(is_cor)
        self.assertEqual(ratio, 1.0)

    def test_judge_normalization_scoring(self):
        """Judge question answers normalization: T/True/1/正确/对 and F/False/0/错误/错."""
        # True representations
        true_variants = ["T", "TRUE", "true", "1", "正确", "对"]
        for variant in true_variants:
            is_cor, ratio = Scorer.evaluate("JUDGE", variant, "T")
            self.assertTrue(is_cor, f"Failed for variant {variant} against 'T'")
            self.assertEqual(ratio, 1.0)

            # Both sides using localized Chinese
            is_cor, ratio = Scorer.evaluate("JUDGE", variant, "正确")
            self.assertTrue(is_cor, f"Failed for variant {variant} against '正确'")
            self.assertEqual(ratio, 1.0)

        # False representations
        false_variants = ["F", "FALSE", "false", "0", "错误", "错"]
        for variant in false_variants:
            is_cor, ratio = Scorer.evaluate("JUDGE", variant, "F")
            self.assertTrue(is_cor, f"Failed for variant {variant} against 'F'")
            self.assertEqual(ratio, 1.0)

            is_cor, ratio = Scorer.evaluate("JUDGE", variant, "错误")
            self.assertTrue(is_cor, f"Failed for variant {variant} against '错误'")
            self.assertEqual(ratio, 1.0)

        # Mismatch cases
        is_cor, ratio = Scorer.evaluate("JUDGE", "对", "错")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

        is_cor, ratio = Scorer.evaluate("JUDGE", "1", "0")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

        is_cor, ratio = Scorer.evaluate("JUDGE", "T", "F")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

        # Invalid/empty
        is_cor, ratio = Scorer.evaluate("JUDGE", "", "T")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

        is_cor, ratio = Scorer.evaluate("JUDGE", None, "T")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

    def test_multi_choice_fractional_scoring(self):
        """Multi-choice scoring: full score for exact match, 0.5 for omissions, 0.0 for wrong options."""
        # Standard answer ABCD: exact match
        is_cor, ratio = Scorer.evaluate("MULTI", "ABCD", "ABCD")
        self.assertTrue(is_cor)
        self.assertEqual(ratio, 1.0)

        # Permuted order match
        is_cor, ratio = Scorer.evaluate("MULTI", "DCBA", "ABCD")
        self.assertTrue(is_cor)
        self.assertEqual(ratio, 1.0)

        # Separator formatting: comma and spaces
        is_cor, ratio = Scorer.evaluate("MULTI", "A, B, C, D", "ABCD")
        self.assertTrue(is_cor)
        self.assertEqual(ratio, 1.0)

        # Partial credit: omitted choices without any wrong option (e.g. AB gives 0.5)
        is_cor, ratio = Scorer.evaluate("MULTI", "AB", "ABCD")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.5)

        is_cor, ratio = Scorer.evaluate("MULTI", "A", "ABCD")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.5)

        is_cor, ratio = Scorer.evaluate("MULTI", "ABC", "ABCD")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.5)

        # Wrong choice included: ABCE gives 0.0
        is_cor, ratio = Scorer.evaluate("MULTI", "ABCE", "ABCD")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

        # Only wrong choice
        is_cor, ratio = Scorer.evaluate("MULTI", "E", "ABCD")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

        # Empty or None
        is_cor, ratio = Scorer.evaluate("MULTI", "", "ABCD")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

        is_cor, ratio = Scorer.evaluate("MULTI", None, "ABCD")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

    def test_essay_scoring(self):
        """Essay question evaluation returns (False, 0.0) by default."""
        is_cor, ratio = Scorer.evaluate("ESSAY", "这是一段简答题作答内容", "参考答案")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)


class TestSessionService(unittest.TestCase):
    """Integration and unit tests for SessionService lifecycle, sync, and answer evaluation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_session_sync.db")
        init_db(self.db_path)

        self.bank_repo = BankRepository(self.db_path)
        self.question_repo = QuestionRepository(self.db_path)
        self.session_repo = SessionRepository(self.db_path)
        self.mistake_repo = MistakeRepository(self.db_path)
        self.mistake_service = MistakeService(self.mistake_repo)

        # Seed bank
        self.bank_id = self.bank_repo.create_bank("测试题库", "用于测试会话与判分")

        # Seed questions
        self.q1_id = self.question_repo.create_question(
            bank_id=self.bank_id,
            q_type="SINGLE",
            stem="1+1=?",
            options=[{"key": "A", "val": "2"}, {"key": "B", "val": "3"}],
            answer="A",
            explanation="基础算术",
        )
        self.q2_id = self.question_repo.create_question(
            bank_id=self.bank_id,
            q_type="MULTI",
            stem="以下哪些是偶数？",
            options=[
                {"key": "A", "val": "2"},
                {"key": "B", "val": "4"},
                {"key": "C", "val": "6"},
                {"key": "D", "val": "8"},
            ],
            answer="ABCD",
            explanation="全都是偶数",
        )
        self.q3_id = self.question_repo.create_question(
            bank_id=self.bank_id,
            q_type="JUDGE",
            stem="地球是圆的吗？",
            options=[],
            answer="T",
            explanation="地球是球体",
        )

        self.service = SessionService(
            session_repo=self.session_repo,
            question_repo=self.question_repo,
            mistake_service=self.mistake_service,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_start_session_lifecycle(self):
        """Test starting a new session and retrieving initial state."""
        session = self.service.start_session(
            bank_id=self.bank_id,
            mode="PRACTICE",
            total_questions=3,
            time_limit=1800,
        )
        self.assertIn("id", session)
        self.assertEqual(session["bank_id"], self.bank_id)
        self.assertEqual(session["mode"], "PRACTICE")
        self.assertEqual(session["total_questions"], 3)
        self.assertEqual(session["time_limit"], 1800)
        self.assertFalse(session["is_completed"])

    def test_submit_answer_scoring_and_practice_mistake_recording(self):
        """Test answer submission, instant scoring, and practice-mode mistake recording."""
        session = self.service.start_session(self.bank_id, "PRACTICE", total_questions=3)
        session_id = session["id"]

        # 1. Answer Single question correctly
        res1 = self.service.submit_answer(
            session_id=session_id,
            question_id=self.q1_id,
            user_answer="A",
            time_spent_delta=10,
        )
        self.assertTrue(res1["is_correct"])
        self.assertEqual(res1["score_ratio"], 1.0)
        self.assertEqual(res1["correct_answer"], "A")
        self.assertEqual(res1["explanation"], "基础算术")

        # In practice mode, first correct answer does NOT register as uncleared mistake
        mistake = self.mistake_repo.get_mistake(self.q1_id)
        self.assertTrue(mistake is None or mistake.get("is_cleared") == 1)

        # 2. Answer Multi question with partial credit (AB out of ABCD)
        res2 = self.service.submit_answer(
            session_id=session_id,
            question_id=self.q2_id,
            user_answer="AB",
            time_spent_delta=15,
        )
        self.assertFalse(res2["is_correct"])
        self.assertEqual(res2["score_ratio"], 0.5)

        # 3. Answer Judge question incorrectly with cause
        res3 = self.service.submit_answer(
            session_id=session_id,
            question_id=self.q3_id,
            user_answer="F",
            time_spent_delta=5,
            mistake_cause=MistakeCause.OPTION_TRAP.value,
        )
        self.assertFalse(res3["is_correct"])
        self.assertEqual(res3["score_ratio"], 0.0)

        # In practice mode, wrong answer should register in MistakeRepository
        mistake3 = self.mistake_repo.get_mistake(self.q3_id)
        self.assertIsNotNone(mistake3)
        self.assertEqual(mistake3["mistake_count"], 1)
        self.assertEqual(mistake3["is_cleared"], 0)
        self.assertEqual(mistake3["mistake_cause"], "OPTION_TRAP")

    def test_submit_answer_exam_mode_no_mistake_service(self):
        """In EXAM mode, mistake service is not invoked during submissions."""
        session = self.service.start_session(self.bank_id, "EXAM", total_questions=3)
        session_id = session["id"]

        res = self.service.submit_answer(
            session_id=session_id,
            question_id=self.q3_id,
            user_answer="F",
            time_spent_delta=10,
        )
        self.assertFalse(res["is_correct"])

        # EXAM mode does not record mistakes into active practice review
        mistake = self.mistake_repo.get_mistake(self.q3_id)
        self.assertIsNone(mistake)

    def test_submit_answer_elimination_and_fsrs_modes_invoke_mistake_service(self):
        """In ELIMINATION and FSRS modes, mistake service is invoked during submissions."""
        # ELIMINATION mode
        sess_elim = self.service.start_session(self.bank_id, "ELIMINATION", total_questions=3)
        res_elim = self.service.submit_answer(
            session_id=sess_elim["id"],
            question_id=self.q1_id,
            user_answer="B",
            mistake_cause="READING_MISS",
        )
        self.assertFalse(res_elim["is_correct"])
        mistake_elim = self.mistake_repo.get_mistake(self.q1_id)
        self.assertIsNotNone(mistake_elim)
        self.assertEqual(mistake_elim["mistake_cause"], "READING_MISS")

        # FSRS mode
        sess_fsrs = self.service.start_session(self.bank_id, "FSRS", total_questions=3)
        res_fsrs = self.service.submit_answer(
            session_id=sess_fsrs["id"],
            question_id=self.q3_id,
            user_answer="F",
            mistake_cause="CONCEPT_GAP",
        )
        self.assertFalse(res_fsrs["is_correct"])
        mistake_fsrs = self.mistake_repo.get_mistake(self.q3_id)
        self.assertIsNotNone(mistake_fsrs)
        self.assertEqual(mistake_fsrs["mistake_cause"], "CONCEPT_GAP")

    def test_submit_answer_returns_cleared_status_on_consecutive_correct(self):
        """submit_answer returns is_cleared=True when answering correctly 2 consecutive times in practice/elimination."""
        sess = self.service.start_session(self.bank_id, "PRACTICE", total_questions=3)
        session_id = sess["id"]

        # First answer wrong -> recorded as mistake
        r1 = self.service.submit_answer(session_id, self.q1_id, "B")
        self.assertFalse(r1["is_correct"])
        self.assertFalse(r1["is_cleared"])
        self.assertEqual(r1["consecutive_correct"], 0)

        # Second answer right -> consecutive 1, not yet cleared
        r2 = self.service.submit_answer(session_id, self.q1_id, "A")
        self.assertTrue(r2["is_correct"])
        self.assertFalse(r2["is_cleared"])
        self.assertEqual(r2["consecutive_correct"], 1)

        # Third answer right -> consecutive 2, eliminated! is_cleared=True
        r3 = self.service.submit_answer(session_id, self.q1_id, "A")
        self.assertTrue(r3["is_correct"])
        self.assertTrue(r3["is_cleared"])
        self.assertEqual(r3["consecutive_correct"], 2)

    def test_draft_synchronization(self):
        """Test merging client localStorage incremental drafts into database."""
        session = self.service.start_session(self.bank_id, "PRACTICE", total_questions=3)
        session_id = session["id"]

        # First draft sync
        synced1 = self.service.sync_draft(
            session_id=session_id,
            current_index=1,
            answers={self.q1_id: "A"},
            flags=[self.q2_id],
            time_spent=25,
        )
        self.assertEqual(synced1["current_index"], 1)
        self.assertEqual(synced1["time_spent"], 25)

        # Second incremental sync merges answers and updates progress
        synced2 = self.service.sync_draft(
            session_id=session_id,
            current_index=2,
            answers={self.q2_id: "ABCD"},
            flags=[self.q2_id, self.q3_id],
            time_spent=50,
        )
        self.assertEqual(synced2["current_index"], 2)
        self.assertEqual(synced2["time_spent"], 50)

        # Check in repository that answers were merged
        stored_session = self.session_repo.get_session(session_id)
        import json
        stored_answers = json.loads(stored_session["answers_json"])
        self.assertIn(self.q1_id, stored_answers)
        self.assertIn(self.q2_id, stored_answers)
        stored_flags = json.loads(stored_session["flags_json"])
        self.assertEqual(stored_flags, [self.q2_id, self.q3_id])

    def test_toggle_flag(self):
        """Test toggling flag adds or removes question_id from session."""
        session = self.service.start_session(self.bank_id, "PRACTICE", total_questions=3)
        session_id = session["id"]

        # Toggle flag on q1 -> added
        flags1 = self.service.toggle_flag(session_id, self.q1_id)
        self.assertIn(self.q1_id, flags1)

        # Toggle flag on q2 -> added
        flags2 = self.service.toggle_flag(session_id, self.q2_id)
        self.assertIn(self.q1_id, flags2)
        self.assertIn(self.q2_id, flags2)

        # Toggle flag on q1 -> removed
        flags3 = self.service.toggle_flag(session_id, self.q1_id)
        self.assertNotIn(self.q1_id, flags3)
        self.assertIn(self.q2_id, flags3)

    def test_complete_session_calculation(self):
        """Test completing session calculates correct count, total score, and accuracy."""
        session = self.service.start_session(self.bank_id, "EXAM", total_questions=3)
        session_id = session["id"]

        # q1: correct (1.0)
        self.service.submit_answer(session_id, self.q1_id, "A", time_spent_delta=20)
        # q2: partial credit (0.5)
        self.service.submit_answer(session_id, self.q2_id, "AB", time_spent_delta=30)
        # q3: wrong (0.0)
        self.service.submit_answer(session_id, self.q3_id, "F", time_spent_delta=10)

        summary = self.service.complete_session(session_id)

        self.assertTrue(summary["is_completed"])
        self.assertEqual(summary["total_questions"], 3)
        self.assertEqual(summary["answered_count"], 3)
        # q1 and q2 are considered correct (is_correct=True), q3 is wrong
        self.assertEqual(summary["correct_count"], 1)
        # Total score: 1.0 + 0.5 + 0.0 = 1.5
        self.assertEqual(summary["score"], 1.5)
        # Accuracy: 2 / 3 * 100 = 66.67%
        self.assertAlmostEqual(summary["accuracy"], 33.33, places=2)

        # Assert enhanced report contract fields
        self.assertEqual(summary["answered_questions"], 3)
        self.assertEqual(summary["total_score"], 3.0)
        self.assertEqual(summary["passing_score"], 1.8)
        self.assertFalse(summary["passed"])  # 1.5 < 1.8
        self.assertIn("breakdown", summary)
        self.assertIn("SINGLE", summary["breakdown"])
        self.assertIn("MULTI", summary["breakdown"])
        self.assertIn("tags_breakdown", summary)
        self.assertIsInstance(summary["tags_breakdown"], dict)

        # Verify DB is marked completed
        db_session = self.session_repo.get_session(session_id)
        self.assertEqual(db_session["is_completed"], 1)
        self.assertEqual(db_session["score"], 1.5)

    def test_shuffle_options_and_questions(self):
        """Test random question ordering and option shuffling with automatic answer remapping."""
        # Test unit method shuffle_question_options
        raw_q = {
            "id": "test_q",
            "type": "SINGLE",
            "options": [
                {"key": "A", "content": "选项一"},
                {"key": "B", "content": "选项二(正解)"},
                {"key": "C", "content": "选项三"},
                {"key": "D", "content": "选项四"},
            ],
            "answer": "B",
        }
        shuffled = SessionService.shuffle_question_options(raw_q)
        # Find which option in shuffled has '选项二(正解)'
        matched = next(o for o in shuffled["options"] if o["content"] == "选项二(正解)")
        # The new answer MUST match this option's key
        self.assertEqual(shuffled["answer"], matched["key"])

        # Test session start with shuffle_options=True
        session = self.service.start_session(
            self.bank_id,
            "PRACTICE",
            total_questions=3,
            shuffle_options=True,
            shuffle_questions=True,
        )
        self.assertTrue(len(session["questions"]) > 0)
        session_id = session["id"]

        for q in session["questions"]:
            q_id = q["id"]
            correct_ans = q["answer"]
            # Submit the remapped answer
            res = self.service.submit_answer(session_id, q_id, correct_ans)
            self.assertTrue(res["is_correct"], f"Expected correct for remapped answer {correct_ans}")


if __name__ == "__main__":
    unittest.main()
