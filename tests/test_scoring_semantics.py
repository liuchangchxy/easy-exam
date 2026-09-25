import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.domain.learning.scoring import score_answer
from backend.app.main import create_app
from backend.services.scoring import Scorer


class TestScoringSemantics(unittest.TestCase):
    def test_partial_multi_score_is_not_correct_and_is_partial_mastery(self):
        result = Scorer.result("MULTI", "A", "AB")
        self.assertEqual(
            result,
            {
                "is_correct": False,
                "score_ratio": 0.5,
                "mastery_status": "PARTIAL",
            },
        )

    def test_exact_multi_score_is_correct_mastery(self):
        result = Scorer.result("MULTI", "BA", "AB")
        self.assertTrue(result["is_correct"])
        self.assertEqual(result["score_ratio"], 1.0)
        self.assertEqual(result["mastery_status"], "CORRECT")

    def test_empty_answer_is_unanswered(self):
        result = Scorer.result("SINGLE", "", "A")
        self.assertFalse(result["is_correct"])
        self.assertEqual(result["score_ratio"], 0.0)
        self.assertEqual(result["mastery_status"], "UNANSWERED")

    def test_essay_answer_is_saved_without_objective_scoring(self):
        result = score_answer("ESSAY", "我的主观作答", "参考答案")
        self.assertEqual(result["score_ratio"], 0.0)
        self.assertEqual(result["correctness"], "UNANSWERED")
        self.assertEqual(result["mastery_status"], "UNSEEN")
        self.assertFalse(result["is_objective"])

    def test_subjective_questions_do_not_dilute_objective_accuracy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "scoring_test.db")
            client = TestClient(create_app(db_path))

            # Register & login
            client.post("/api/v1/auth/register", json={"username": "scorer_user", "password": "REDACTED_TEST_PASSWORD"})
            token = client.post("/api/v1/auth/login", json={"username": "scorer_user", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Create bank
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "混合题库"}).json()

            # Create 1 objective question and 1 essay question
            q_obj = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "客观单选", "type": "SINGLE", "answer": "A"}).json()
            q_sub = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "主观论述", "type": "ESSAY", "answer": "论述参考要点"}).json()

            # Start session
            session = client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()

            # Submit answers: objective is correct, subjective is answered with text
            client.post(f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers, json={"question_id": q_obj["id"], "user_answer": "A"})
            client.post(f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers, json={"question_id": q_sub["id"], "user_answer": "我的论述思考"})

            # Complete session
            report = client.post(f"/api/v1/practice/sessions/{session['id']}/complete", headers=headers).json()

            # Total questions is 2, but objective question is 1 and correct is 1 -> objective accuracy must be 100.0, NOT 50.0!
            self.assertEqual(report["total_questions"], 2)
            self.assertEqual(report["correct_count"], 1)
            self.assertEqual(report["objective_total"], 1)
            self.assertEqual(report["accuracy"], 100.0)
