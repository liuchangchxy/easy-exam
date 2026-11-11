import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


class TestExamClosure(unittest.TestCase):
    """Regression coverage for the PR 90 exam final-closure fixes."""

    def setUp(self):
        self._orig_secret = os.environ.get("EASYEXAM_SECRET_KEY")
        os.environ["EASYEXAM_SECRET_KEY"] = "easyexam-ci-secret-32bytes-passphrase!!"
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = str(Path(self.temp_dir.name) / "easyexam-exam-closure.db")
        self.app = create_app(self.db_path)
        self.client = TestClient(self.app)
        self.client.post("/api/v1/auth/register", json={"username": "exam_closure", "password": "password-123456"})
        token = self.client.post(
            "/api/v1/auth/login",
            json={"username": "exam_closure", "password": "password-123456"},
        ).json()["token"]
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        if self._orig_secret is not None:
            os.environ["EASYEXAM_SECRET_KEY"] = self._orig_secret
        else:
            os.environ.pop("EASYEXAM_SECRET_KEY", None)
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _bank(self, name="模考收口题库"):
        response = self.client.post("/api/v1/banks", headers=self.headers, json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _question(self, bank_id, *, stem, qtype="SINGLE", answer="A", **extra):
        payload = {
            "stem": stem,
            "type": qtype,
            "answer": answer,
            "options": [
                {"key": "A", "content": "选项 A"},
                {"key": "B", "content": "选项 B"},
            ],
        }
        payload.update(extra)
        response = self.client.post(f"/api/v1/banks/{bank_id}/questions", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _profile(self, name="收口试卷"):
        response = self.client.post("/api/v1/exams/profiles", headers=self.headers, json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _save_blueprint(self, profile_id, blueprint):
        response = self.client.post(
            f"/api/v1/exams/profiles/{profile_id}/blueprint",
            headers=self.headers,
            json={"blueprint": blueprint},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_blueprint_round_trip_preserves_custom_names_and_fields(self):
        profile = self._profile()
        blueprint = {
            "negative_mark": 0.5,
            "allow_fallback": False,
            "custom_note": "保留我",
            "sections": [
                {
                    "name": "第一章 · 自定义名称",
                    "type": "SINGLE",
                    "count": 7,
                    "difficulty": 3,
                    "chapter_id": "chap-1",
                    "tags": "高频,易错",
                    "weight": 0.4,
                },
                {
                    "name": "多选冲刺",
                    "type": "MULTI",
                    "count": 2,
                    "difficulty": 4,
                    "chapter_id": "",
                    "tags": "",
                },
            ],
        }
        self._save_blueprint(profile["id"], blueprint)

        loaded = self.client.get(f"/api/v1/exams/profiles/{profile['id']}/blueprint", headers=self.headers)
        self.assertEqual(loaded.status_code, 200, loaded.text)
        stored = loaded.json()["blueprint"]
        self.assertEqual(stored, blueprint)

        listed = self.client.get("/api/v1/exams/profiles", headers=self.headers).json()
        self.assertEqual(listed[0]["latest_blueprint"]["blueprint"], blueprint)

    def test_blueprint_selection_honors_requested_total(self):
        bank = self._bank()
        self._question(bank["id"], stem="判断 1", qtype="JUDGE", answer="T")
        self._question(bank["id"], stem="判断 2", qtype="JUDGE", answer="F")
        self._question(bank["id"], stem="单选 1")
        self._question(bank["id"], stem="单选 2", answer="B")
        self._question(bank["id"], stem="单选 3", answer="A")

        profile = self._profile()
        self._save_blueprint(profile["id"], {
            "sections": [
                {"name": "判断", "type": "JUDGE", "count": 2},
                {"name": "单选", "type": "SINGLE", "count": 3},
            ],
        })

        session = self.client.post("/api/v1/exams/sessions", headers=self.headers, json={
            "bank_id": bank["id"],
            "profile_id": profile["id"],
            "total_questions": 2,
        })
        self.assertEqual(session.status_code, 201, session.text)
        questions = self.client.get(
            f"/api/v1/practice/sessions/{session.json()['id']}/questions",
            headers=self.headers,
        ).json()
        self.assertEqual(len(questions), 2, "The requested paper size must cap blueprint selection")

        full = self.client.post("/api/v1/exams/sessions", headers=self.headers, json={
            "bank_id": bank["id"],
            "profile_id": profile["id"],
            "total_questions": 5,
        })
        full_questions = self.client.get(
            f"/api/v1/practice/sessions/{full.json()['id']}/questions",
            headers=self.headers,
        ).json()
        self.assertEqual(len(full_questions), 5)

    def test_exam_report_lists_blank_questions_with_standard_answers(self):
        bank = self._bank()
        answered = self._question(bank["id"], stem="会做的题", answer="A")
        blank = self._question(bank["id"], stem="空着的题", answer="B", explanation="官方解析")

        session = self.client.post("/api/v1/exams/sessions", headers=self.headers, json={"bank_id": bank["id"]})
        self.assertEqual(session.status_code, 201, session.text)
        session_id = session.json()["id"]
        sync = self.client.post(
            f"/api/v1/practice/sessions/{session_id}/sync",
            headers=self.headers,
            json={"answers": {answered["id"]: "A"}},
        )
        self.assertEqual(sync.status_code, 200, sync.text)
        report = self.client.post(f"/api/v1/practice/sessions/{session_id}/complete", headers=self.headers)
        self.assertEqual(report.status_code, 200, report.text)
        body = report.json()

        self.assertEqual(body["answered_count"], 1)
        self.assertEqual(body["unanswered_count"], 1)
        self.assertEqual(body["correct_count"], 1)
        self.assertEqual(body["answers"][answered["id"]]["correctness"], "CORRECT")
        blank_entry = body["answers"][blank["id"]]
        self.assertEqual(blank_entry["correctness"], "UNANSWERED")
        self.assertIsNone(blank_entry["user_answer"])
        self.assertEqual(blank_entry["correct_answer"], "B")
        self.assertEqual(blank_entry["explanation"], "官方解析")

    def test_blank_multi_answer_is_not_scored_as_an_attempt(self):
        bank = self._bank()
        question = self._question(bank["id"], stem="多选空答", qtype="MULTI", answer="A,B")

        session = self.client.post("/api/v1/exams/sessions", headers=self.headers, json={"bank_id": bank["id"]})
        session_id = session.json()["id"]
        sync = self.client.post(
            f"/api/v1/practice/sessions/{session_id}/sync",
            headers=self.headers,
            json={"answers": {question["id"]: []}},
        )
        self.assertEqual(sync.status_code, 200, sync.text)
        report = self.client.post(f"/api/v1/practice/sessions/{session_id}/complete", headers=self.headers).json()

        self.assertEqual(report["answered_count"], 0)
        self.assertEqual(report["unanswered_count"], 1)
        self.assertEqual(report["incorrect_count"], 0)
        self.assertEqual(report["score"], 0)
        self.assertEqual(report["answers"][question["id"]]["correctness"], "UNANSWERED")

    def test_exam_draft_sync_respects_observed_baseline(self):
        bank = self._bank()
        question = self._question(bank["id"], stem="基线题", answer="A")
        session = self.client.post("/api/v1/exams/sessions", headers=self.headers, json={"bank_id": bank["id"]})
        session_id = session.json()["id"]

        self.client.post(
            f"/api/v1/practice/sessions/{session_id}/sync",
            headers=self.headers,
            json={"answers": {question["id"]: "A"}},
        )
        # The client observed A, so switching to B is an ordinary local edit.
        normal = self.client.post(
            f"/api/v1/practice/sessions/{session_id}/sync",
            headers=self.headers,
            json={"answers": {question["id"]: "B"}, "base_answers": {question["id"]: "A"}},
        ).json()
        self.assertFalse(normal["has_conflict"])
        self.assertEqual(normal["answers"][question["id"]], "B")

        # A stale baseline means another device wrote since this client loaded.
        # The server keeps its value and reports the rejected write.
        stale = self.client.post(
            f"/api/v1/practice/sessions/{session_id}/sync",
            headers=self.headers,
            json={"answers": {question["id"]: "C"}, "base_answers": {question["id"]: "A"}},
        ).json()
        self.assertTrue(stale["has_conflict"])
        self.assertEqual(stale["conflicts"][0]["existing_answer"], "B")
        self.assertEqual(stale["conflicts"][0]["incoming_answer"], "C")
        self.assertEqual(stale["answers"][question["id"]], "B")

    def test_exam_draft_sync_reports_conflicting_answers(self):
        bank = self._bank()
        question = self._question(bank["id"], stem="冲突题", answer="A")
        session = self.client.post("/api/v1/exams/sessions", headers=self.headers, json={"bank_id": bank["id"]})
        session_id = session.json()["id"]

        first = self.client.post(
            f"/api/v1/practice/sessions/{session_id}/sync",
            headers=self.headers,
            json={"answers": {question["id"]: "A"}},
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertFalse(first.json()["has_conflict"])

        second = self.client.post(
            f"/api/v1/practice/sessions/{session_id}/sync",
            headers=self.headers,
            json={"answers": {question["id"]: "B"}},
        )
        self.assertEqual(second.status_code, 200, second.text)
        body = second.json()
        self.assertTrue(body["has_conflict"])
        self.assertEqual(len(body["conflicts"]), 1)
        conflict = body["conflicts"][0]
        self.assertEqual(conflict["question_id"], question["id"])
        self.assertEqual(conflict["existing_answer"], "A")
        self.assertEqual(conflict["incoming_answer"], "B")


if __name__ == "__main__":
    unittest.main()
