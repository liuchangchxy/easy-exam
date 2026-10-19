import json
import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from backend.app.main import create_app


class Issue57ConsistencyTests(unittest.TestCase):
    def setUp(self):
        self._temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self._temp_db.name
        self._temp_db.close()
        self.app = create_app(db_path=self.db_path)
        self.client = TestClient(self.app)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def _register_and_login(self, username, password="Password123!"):
        resp = self.client.post("/api/v1/auth/register", json={"username": username, "password": password})
        assert resp.status_code == 201, resp.text
        login_resp = self.client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert login_resp.status_code == 200, login_resp.text
        token = login_resp.json()["token"]
        user_id = login_resp.json()["user"]["id"]
        return token, user_id

    def test_multi_choice_requires_at_least_two_answers(self):
        """Defect 1 & Risk 8: MULTI question cannot be saved with only 1 correct answer or duplicate options."""
        token, user_id = self._register_and_login("admin_multi")
        headers = {"Authorization": f"Bearer {token}"}

        bank_resp = self.client.post(
            "/api/v1/banks",
            json={"name": "Multi Bank", "category": "Test"},
            headers=headers,
        )
        assert bank_resp.status_code == 201
        bank_id = bank_resp.json()["id"]

        # 1. MULTI with only 1 answer must be rejected
        res = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Which of the following are prime?",
                "type": "MULTI",
                "options": [{"key": "A", "content": "2"}, {"key": "B", "content": "3"}, {"key": "C", "content": "4"}],
                "answer": "A",
            },
            headers=headers,
        )
        self.assertIn(res.status_code, (400, 422), f"Expected 400/422 for single-answer MULTI, got {res.status_code}: {res.text}")

        # 2. MULTI with duplicate answer keys (e.g. 'A,A') must be rejected
        res_dup_ans = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Which of the following are prime?",
                "type": "MULTI",
                "options": [{"key": "A", "content": "2"}, {"key": "B", "content": "3"}, {"key": "C", "content": "4"}],
                "answer": "A,A",
            },
            headers=headers,
        )
        self.assertIn(res_dup_ans.status_code, (400, 422), f"Expected 400/422 for duplicate answer keys, got {res_dup_ans.status_code}")

        # 3. MULTI with duplicate option keys must be rejected
        res_dup_opt = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Which of the following are prime?",
                "type": "MULTI",
                "options": [{"key": "A", "content": "2"}, {"key": "A", "content": "3"}, {"key": "C", "content": "4"}],
                "answer": "A,C",
            },
            headers=headers,
        )
        self.assertIn(res_dup_opt.status_code, (400, 422), f"Expected 400/422 for duplicate option keys, got {res_dup_opt.status_code}")

        # 4. Valid MULTI with 2 distinct answers must succeed
        res_valid = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Which of the following are prime?",
                "type": "MULTI",
                "options": [{"key": "A", "content": "2"}, {"key": "B", "content": "3"}, {"key": "C", "content": "4"}],
                "answer": "A,B",
            },
            headers=headers,
        )
        self.assertEqual(res_valid.status_code, 201, res_valid.text)
        q_id = res_valid.json()["id"]

        # 5. Updating to single answer on MULTI must also be rejected
        update_res = self.client.put(
            f"/api/v1/questions/{q_id}",
            json={
                "stem": "Which of the following are prime?",
                "type": "MULTI",
                "options": [{"key": "A", "content": "2"}, {"key": "B", "content": "3"}, {"key": "C", "content": "4"}],
                "answer": "B",
                "base_version_number": 1,
            },
            headers=headers,
        )
        self.assertIn(update_res.status_code, (400, 422), f"Expected 400/422 on updating MULTI to single answer, got {update_res.status_code}")

    def test_cross_user_active_exam_protection_on_edit_and_merge(self):
        """Defect 3 & Risk 9: Active exam protection must cover cross-user edits and batch import merge."""
        admin_token, admin_id = self._register_and_login("exam_admin")
        student_token, student_id = self._register_and_login("exam_student")

        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        student_headers = {"Authorization": f"Bearer {student_token}"}

        # Admin creates bank and questions
        bank_resp = self.client.post(
            "/api/v1/banks",
            json={"name": "Exam Protected Bank", "category": "Sec"},
            headers=admin_headers,
        )
        bank_id = bank_resp.json()["id"]

        # Add student as MEMBER
        self.client.post(
            f"/api/v1/banks/{bank_id}/members",
            json={"username": "exam_student", "role": "MEMBER"},
            headers=admin_headers,
        )

        # Create question 1
        q_resp = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Question in exam?",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "Yes"}, {"key": "B", "content": "No"}],
                "answer": "A",
            },
            headers=admin_headers,
        )
        q_id = q_resp.json()["id"]

        # Student starts an EXAM session
        start_exam_resp = self.client.post(
            "/api/v1/exams/sessions",
            json={"bank_id": bank_id, "total_questions": 1, "time_limit": 60},
            headers=student_headers,
        )
        self.assertEqual(start_exam_resp.status_code, 201)
        exam_session_id = start_exam_resp.json()["id"]

        # Cross-user protection: Admin attempts to edit the question while Student is in active exam!
        # MUST return 403 Forbidden!
        edit_resp = self.client.put(
            f"/api/v1/questions/{q_id}",
            json={
                "stem": "Question modified during exam!",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "Yes"}, {"key": "B", "content": "No"}],
                "answer": "B",
                "base_version_number": 1,
            },
            headers=admin_headers,
        )
        self.assertEqual(edit_resp.status_code, 403, f"Admin edit should be blocked by student's active exam, got {edit_resp.status_code}: {edit_resp.text}")

        # Risk 9: Admin attempts batch import with duplicate_strategy='merge' targeting q_id
        # MUST be blocked by active exam protection!
        import_resp = self.client.post(
            f"/api/v1/imports/banks/{bank_id}",
            json={
                "format": "json",
                "content": json.dumps([{
                    "stem": "Question in exam?",
                    "type": "SINGLE",
                    "options": [{"key": "A", "content": "Yes"}, {"key": "B", "content": "No"}],
                    "answer": "A",
                    "explanation": "Attempting merge during exam",
                }]),
                "duplicate_strategy": "merge",
            },
            headers=admin_headers,
        )
        self.assertEqual(import_resp.status_code, 403, f"Batch merge should be blocked by active exam, got {import_resp.status_code}: {import_resp.text}")

        # Student completes exam session
        complete_resp = self.client.post(
            f"/api/v1/exams/sessions/{exam_session_id}/complete",
            headers=student_headers,
        )
        self.assertEqual(complete_resp.status_code, 200)

        # After exam completion, Admin can edit normally
        edit_resp_after = self.client.put(
            f"/api/v1/questions/{q_id}",
            json={
                "stem": "Question modified after exam!",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "Yes"}, {"key": "B", "content": "No"}],
                "answer": "B",
                "base_version_number": 1,
            },
            headers=admin_headers,
        )
        self.assertEqual(edit_resp_after.status_code, 200, edit_resp_after.text)

    def test_importer_rejects_single_answer_multi_choice(self):
        """Defect 1: Importers must reject MULTI question with only 1 correct answer."""
        token, user_id = self._register_and_login("import_user")
        headers = {"Authorization": f"Bearer {token}"}

        bank_resp = self.client.post(
            "/api/v1/banks",
            json={"name": "Import Test Bank", "category": "Test"},
            headers=headers,
        )
        bank_id = bank_resp.json()["id"]

        # Import JSON with MULTI question having single answer "A"
        invalid_json = json.dumps([{
            "stem": "Which of these are vowels?",
            "type": "MULTI",
            "options": [{"key": "A", "content": "A"}, {"key": "B", "content": "B"}, {"key": "C", "content": "C"}],
            "answer": "A",
        }])

        resp = self.client.post(
            f"/api/v1/imports/banks/{bank_id}",
            json={"format": "json", "content": invalid_json},
            headers=headers,
        )
        self.assertIn(resp.status_code, (400, 422), f"Importer must reject MULTI with single answer, got {resp.status_code}: {resp.text}")

    def test_exam_timeout_and_completion_idempotency(self):
        """Risk 7: When exam times out, complete_session must still score answers and return report idempotently."""
        token, user_id = self._register_and_login("timeout_student")
        headers = {"Authorization": f"Bearer {token}"}

        bank_resp = self.client.post(
            "/api/v1/banks",
            json={"name": "Timeout Bank", "category": "Test"},
            headers=headers,
        )
        bank_id = bank_resp.json()["id"]

        q_resp = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "What is capital of France?",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "Paris"}, {"key": "B", "content": "Rome"}],
                "answer": "A",
            },
            headers=headers,
        )
        q_id = q_resp.json()["id"]

        # Start exam with 1 minute limit
        start_resp = self.client.post(
            "/api/v1/exams/sessions",
            json={"bank_id": bank_id, "total_questions": 1, "time_limit": 1},
            headers=headers,
        )
        session_id = start_resp.json()["id"]

        # Student saves draft with answer
        sync_resp = self.client.post(
            f"/api/v1/practice/sessions/{session_id}/sync",
            json={"answers": {q_id: "A"}, "current_index": 0, "time_spent": 10},
            headers=headers,
        )
        self.assertEqual(sync_resp.status_code, 200)

        # Complete exam session directly (even if attempts weren't submitted individually or timer expired)
        comp_resp = self.client.post(
            f"/api/v1/exams/sessions/{session_id}/complete",
            headers=headers,
        )
        self.assertEqual(comp_resp.status_code, 200, comp_resp.text)
        report = comp_resp.json()
        self.assertEqual(report["total_questions"], 1)
        self.assertEqual(report["correct_count"], 1, f"Report should score answers from draft: {report}")
        self.assertEqual(report["score"], 1.0)

        # Calling complete again must be idempotent
        comp_resp_again = self.client.post(
            f"/api/v1/exams/sessions/{session_id}/complete",
            headers=headers,
        )
        self.assertEqual(comp_resp_again.status_code, 200)
        self.assertEqual(comp_resp_again.json()["score"], 1.0)



if __name__ == "__main__":
    unittest.main()
