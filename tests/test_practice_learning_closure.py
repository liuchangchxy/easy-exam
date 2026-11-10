"""PR 90 practice/learning closure regressions.

Covers draft answer persistence and cross-device conflict reporting, multi-bank
Today/Review sessions, report time, and kill-queue isolation.
"""
import tempfile
import unittest

from backend.app.application.auth_service import AuthService
from backend.app.application.bank_service import BankService
from backend.app.application.practice_service import PracticeService
from backend.app.infrastructure.db.connection import migrate
from backend.app.infrastructure.db.repositories.bank_repository import BankRepository
from backend.app.infrastructure.db.repositories.practice_repository import PracticeRepository
from backend.app.infrastructure.db.repositories.question_repository import QuestionRepository
from backend.app.infrastructure.db.repositories.user_repository import UserRepository, UserSessionRepository


class TestPracticeLearningClosure(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_pr90.db"
        migrate(self.db_path)
        self.users = UserRepository(self.db_path)
        self.sessions = UserSessionRepository(self.db_path)
        self.banks = BankRepository(self.db_path)
        self.questions = QuestionRepository(self.db_path)
        self.practices = PracticeRepository(self.db_path)

        self.auth = AuthService(self.users, self.sessions)
        self.bank_service = BankService(self.banks, self.questions)
        self.practice_service = PracticeService(self.practices, self.questions, self.banks)

        user = self.auth.register("closure_user", "Password123")
        self.user_id = user["id"]
        _, self.token = self.auth.login("closure_user", "Password123")
        self.bank = self.bank_service.create_bank(self.user_id, {"name": "Closure Bank"})
        self.bank_id = self.bank["id"]

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _question(self, stem="Closure question", answer="A"):
        return self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": stem,
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}, {"key": "B", "content": "B"}],
            "answer": answer,
        })

    def test_same_device_draft_edit_is_not_reported_as_conflict(self):
        q = self._question()
        sess = self.practice_service.start_session(self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]])

        first = self.practice_service.sync_draft(self.user_id, sess["id"], {
            "current_index": 0,
            "answers": {q["id"]: "A"},
            "base_answers": {},
            "time_spent": 5,
        })
        self.assertEqual(first["answers"][q["id"]], "A")
        self.assertEqual(first["conflicts"], [])

        second = self.practice_service.sync_draft(self.user_id, sess["id"], {
            "current_index": 0,
            "answers": {q["id"]: "B"},
            "base_answers": {q["id"]: "A"},
            "time_spent": 9,
        })
        self.assertEqual(second["answers"][q["id"]], "B")
        self.assertEqual(second["conflicts"], [])

    def test_cross_device_draft_conflict_keeps_server_answer_and_reports_it(self):
        q = self._question()
        sess = self.practice_service.start_session(self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]])

        # Device A observes the empty draft.
        self.practice_service.sync_draft(self.user_id, sess["id"], {
            "answers": {q["id"]: "A"},
            "base_answers": {},
        })
        # Device B edits from the base it observed (A -> B).
        self.practice_service.sync_draft(self.user_id, sess["id"], {
            "answers": {q["id"]: "B"},
            "base_answers": {q["id"]: "A"},
        })
        # Device A still believes the server holds A, so its C must not win silently.
        result = self.practice_service.sync_draft(self.user_id, sess["id"], {
            "answers": {q["id"]: "C"},
            "base_answers": {q["id"]: "A"},
        })

        self.assertEqual(result["answers"][q["id"]], "B", "cross-device conflict must keep the server value")
        self.assertEqual(len(result["conflicts"]), 1)
        conflict = result["conflicts"][0]
        self.assertEqual(conflict["question_id"], q["id"])
        self.assertEqual(conflict["existing_answer"], "B")
        self.assertEqual(conflict["incoming_answer"], "C")

    def test_complete_report_carries_session_time_spent(self):
        q = self._question()
        sess = self.practice_service.start_session(self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]])
        self.practice_service.sync_draft(self.user_id, sess["id"], {
            "current_index": 0,
            "answers": {q["id"]: "A"},
            "time_spent": 42,
        })

        report = self.practice_service.complete_session(self.user_id, sess["id"])
        self.assertEqual(report["time_spent"], 42, "practice report must expose the persisted time spent")

    def test_matching_draft_does_not_erase_scored_attempt(self):
        q = self._question()
        sess = self.practice_service.start_session(self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]])
        self.practice_service.submit_attempt(self.user_id, sess["id"], q["id"], "A")
        before = self.practice_service.get_session(self.user_id, sess["id"])["answers"][q["id"]]
        self.assertIsInstance(before, dict)
        synced = self.practice_service.sync_draft(self.user_id, sess["id"], {
            "answers": {q["id"]: "A"}, "base_answers": {q["id"]: "A"},
        })
        self.assertEqual(synced["answers"][q["id"]], before)

    def test_multi_draft_representation_preserves_scored_attempt(self):
        q = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "Multiple answers", "type": "MULTI",
            "options": [{"key": "A", "content": "A"}, {"key": "B", "content": "B"}], "answer": "AB",
        })
        sess = self.practice_service.start_session(self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"]])
        self.practice_service.submit_attempt(self.user_id, sess["id"], q["id"], "AB")
        before = self.practice_service.get_session(self.user_id, sess["id"])["answers"][q["id"]]
        synced = self.practice_service.sync_draft(self.user_id, sess["id"], {
            "answers": {q["id"]: ["B", "A"]}, "base_answers": {q["id"]: "AB"},
        })
        self.assertEqual(synced["answers"][q["id"]], before)
        self.assertEqual(synced["conflicts"], [])

    def test_concurrent_drafts_preserve_both_answers(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        questions = [self._question("Concurrent one"), self._question("Concurrent two")]
        sess = self.practice_service.start_session(self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q["id"] for q in questions])
        barrier = Barrier(2)
        def save(q):
            barrier.wait()
            return self.practice_service.sync_draft(self.user_id, sess["id"], {"answers": {q["id"]: "A"}, "base_answers": {}})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, questions))
        self.assertTrue(all(not item["conflicts"] for item in results))
        answers = self.practice_service.get_session(self.user_id, sess["id"])["answers"]
        self.assertEqual(answers, {q["id"]: "A" for q in questions})

    def test_multi_bank_fsrs_session_covers_due_questions_from_every_bank(self):
        bank2 = self.bank_service.create_bank(self.user_id, {"name": "Second Bank"})
        q1 = self._question("Bank one due")
        q2 = self.bank_service.create_question(self.user_id, bank2["id"], {
            "stem": "Bank two due",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}, {"key": "B", "content": "B"}],
            "answer": "A",
        })
        self.practices.mark_weak(self.user_id, q1["id"])
        self.practices.mark_weak(self.user_id, q2["id"])

        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="FSRS", bank_ids=[self.bank_id, bank2["id"]],
        )
        self.assertEqual(session["total_questions"], 2)

        questions = self.practice_service.get_session(self.user_id, session["id"])["questions"]
        self.assertEqual({q["id"] for q in questions}, {q1["id"], q2["id"]})

        for item in questions:
            attempt = self.practice_service.submit_attempt(self.user_id, session["id"], item["id"], "A")
            self.assertEqual(attempt["correctness"], "CORRECT")
        report = self.practice_service.complete_session(self.user_id, session["id"])
        self.assertEqual(report["answered_count"], 2)
        self.assertEqual(sorted(report["bank_ids"]), sorted([self.bank_id, bank2["id"]]))

    def test_multi_bank_session_rejects_a_bank_the_user_cannot_access(self):
        other = self.auth.register("other_owner", "Password123")
        foreign_bank = self.bank_service.create_bank(other["id"], {"name": "Foreign"})
        with self.assertRaises(LookupError):
            self.practice_service.start_session(
                self.user_id, self.bank_id, mode="PRACTICE",
                bank_ids=[self.bank_id, foreign_bank["id"]],
            )

    def test_explicit_clear_is_kept_when_the_same_payload_edits_another_question(self):
        q1 = self._question("Cleared question")
        q2 = self._question("Edited question")
        sess = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q1["id"], q2["id"]],
        )
        self.practice_service.sync_draft(self.user_id, sess["id"], {
            "answers": {q1["id"]: "A", q2["id"]: "B"},
            "base_answers": {},
        })

        result = self.practice_service.sync_draft(self.user_id, sess["id"], {
            "answers": {q1["id"]: "", q2["id"]: "C"},
            "base_answers": {q1["id"]: "A", q2["id"]: "B"},
        })

        self.assertEqual(result["answers"][q1["id"]], "", "an explicit clear must not be dropped")
        self.assertEqual(result["answers"][q2["id"]], "C")
        self.assertEqual(result["conflicts"], [])

    def test_explicit_clear_conflicts_when_another_device_changed_the_answer(self):
        q1 = self._question("Cleared question")
        sess = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q1["id"]],
        )
        self.practice_service.sync_draft(self.user_id, sess["id"], {
            "answers": {q1["id"]: "A"},
            "base_answers": {},
        })
        # Another device moved A -> B after this client last observed A.
        self.practice_service.sync_draft(self.user_id, sess["id"], {
            "answers": {q1["id"]: "B"},
            "base_answers": {q1["id"]: "A"},
        })

        result = self.practice_service.sync_draft(self.user_id, sess["id"], {
            "answers": {q1["id"]: ""},
            "base_answers": {q1["id"]: "A"},
        })

        self.assertEqual(result["answers"][q1["id"]], "B")
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertEqual(result["conflicts"][0]["existing_answer"], "B")
        self.assertEqual(result["conflicts"][0]["incoming_answer"], "")

    def test_legacy_mixed_payload_still_preserves_the_existing_answer(self):
        q1 = self._question("Legacy clear")
        q2 = self._question("Legacy edit")
        sess = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[q1["id"], q2["id"]],
        )
        self.practice_service.sync_draft(self.user_id, sess["id"], {
            "answers": {q1["id"]: "A"},
        })

        result = self.practice_service.sync_draft(self.user_id, sess["id"], {
            "answers": {q1["id"]: "", q2["id"]: "B"},
        })

        self.assertEqual(result["answers"][q1["id"]], "A", "legacy mixed payload must not drop a valid answer")
        self.assertEqual(result["answers"][q2["id"]], "B")

    def test_killed_question_leaves_mistake_and_due_queues(self):
        mistaken = self._question("Mistaken question")
        sess = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="PRACTICE", question_ids=[mistaken["id"]],
        )
        self.practice_service.submit_attempt(self.user_id, sess["id"], mistaken["id"], "B")
        self.practice_service.complete_session(self.user_id, sess["id"])

        ids = {row["question_id"] for row in self.practices.list_mistakes(self.user_id)}
        self.assertIn(mistaken["id"], ids)

        due = self._question("Weak due question")
        self.practices.mark_weak(self.user_id, due["id"])
        self.assertIn(due["id"], {row["question_id"] for row in self.practices.list_due_reviews(self.user_id)})

        self.practices.kill(self.user_id, mistaken["id"])
        self.practices.kill(self.user_id, due["id"])

        ids = {row["question_id"] for row in self.practices.list_mistakes(self.user_id)}
        self.assertNotIn(mistaken["id"], ids, "killed questions must leave the mistake review queue")
        self.assertNotIn(due["id"], {row["question_id"] for row in self.practices.list_due_reviews(self.user_id)})

        self.practices.unkill(self.user_id, due["id"])
        self.assertIn(due["id"], {row["question_id"] for row in self.practices.list_due_reviews(self.user_id)})

    def test_wrong_answer_in_elimination_restores_a_killed_question(self):
        q = self._question("Killed question")
        self.practices.kill(self.user_id, q["id"])
        sess = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="ELIMINATION", question_ids=[q["id"]],
        )
        self.practice_service.submit_attempt(self.user_id, sess["id"], q["id"], "B")
        killed = {row["question_id"] for row in self.practices.list_killed(self.user_id)}
        self.assertNotIn(q["id"], killed, "a wrong answer in elimination must revive the question")


if __name__ == "__main__":
    unittest.main()
