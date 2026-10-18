import json
import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from backend.app.main import create_app


class BankContentManagementTests(unittest.TestCase):
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

    def test_bank_content_questions_api_and_guards(self):
        # 1. Setup admin and member users
        admin_token, admin_id = self._register_and_login("admin_user")
        member_token, member_id = self._register_and_login("member_user")
        stranger_token, stranger_id = self._register_and_login("stranger_user")

        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        member_headers = {"Authorization": f"Bearer {member_token}"}
        stranger_headers = {"Authorization": f"Bearer {stranger_token}"}

        # 2. Admin creates a bank
        create_bank_resp = self.client.post(
            "/api/v1/banks",
            json={"name": "Content Test Bank", "category": "CS", "description": "Bank for content mgmt test"},
            headers=admin_headers,
        )
        assert create_bank_resp.status_code == 201
        bank_id = create_bank_resp.json()["id"]

        # 3. Add member to bank
        add_member_resp = self.client.post(
            f"/api/v1/banks/{bank_id}/members",
            json={"username": "member_user", "role": "MEMBER"},
            headers=admin_headers,
        )
        assert add_member_resp.status_code == 201

        # 4. Create 2 questions
        q1_resp = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "What is 2+2?",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "3"}, {"key": "B", "content": "4"}],
                "answer": "B",
                "explanation": "2+2=4",
                "difficulty": 1,
                "tags": ["math", "basic"],
            },
            headers=admin_headers,
        )
        assert q1_resp.status_code == 201
        q1_id = q1_resp.json()["id"]

        q2_resp = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Is Python interpreted?",
                "type": "JUDGE",
                "options": [{"key": "T", "content": "True"}, {"key": "F", "content": "False"}],
                "answer": "T",
                "explanation": "Python is an interpreted language",
                "difficulty": 2,
                "tags": ["python"],
            },
            headers=admin_headers,
        )
        assert q2_resp.status_code == 201
        q2_id = q2_resp.json()["id"]

        # 5. Member reads content questions
        member_content_resp = self.client.get(f"/api/v1/banks/{bank_id}/content/questions", headers=member_headers)
        assert member_content_resp.status_code == 200, member_content_resp.text
        content_questions = member_content_resp.json()
        assert len(content_questions) == 2
        stems = {q["stem"] for q in content_questions}
        assert "What is 2+2?" in stems
        assert "Is Python interpreted?" in stems

        # 6. Stranger (non-member) cannot access content questions (404 or 403)
        stranger_resp = self.client.get(f"/api/v1/banks/{bank_id}/content/questions", headers=stranger_headers)
        assert stranger_resp.status_code in (403, 404)

        # 7. Member kills question 1
        kill_resp = self.client.post(f"/api/v1/kills/{q1_id}", headers=member_headers)
        assert kill_resp.status_code == 201

        # In practice list (list_for_bank), question 1 is excluded for this member
        practice_list_resp = self.client.get(f"/api/v1/banks/{bank_id}/questions", headers=member_headers)
        assert practice_list_resp.status_code == 200
        practice_qids = [q["id"] for q in practice_list_resp.json()]
        assert q1_id not in practice_qids
        assert q2_id in practice_qids

        # BUT in content questions list, question 1 MUST STILL BE PRESENT!
        member_content_after_kill = self.client.get(f"/api/v1/banks/{bank_id}/content/questions", headers=member_headers)
        assert member_content_after_kill.status_code == 200
        content_qids_after_kill = [q["id"] for q in member_content_after_kill.json()]
        assert q1_id in content_qids_after_kill
        assert q2_id in content_qids_after_kill

        # 8. Admin updates question 1 generating version 2
        put_resp = self.client.put(
            f"/api/v1/questions/{q1_id}",
            json={
                "stem": "What is 2 + 2 exactly?",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "3"}, {"key": "B", "content": "4"}],
                "answer": "B",
                "explanation": "2+2=4 always",
                "difficulty": 1,
                "tags": ["math", "arithmetic"],
                "base_version_number": 1,
                "regrade_history": False,
            },
            headers=admin_headers,
        )
        assert put_resp.status_code == 200, put_resp.text
        updated_q1 = put_resp.json()
        assert updated_q1["version_number"] == 2
        assert updated_q1["stem"] == "What is 2 + 2 exactly?"

        # Member cannot edit question (returns 403)
        member_put_resp = self.client.put(
            f"/api/v1/questions/{q1_id}",
            json={
                "stem": "Hacked stem by member",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "3"}, {"key": "B", "content": "4"}],
                "answer": "A",
                "base_version_number": 2,
            },
            headers=member_headers,
        )
        assert member_put_resp.status_code == 403

        # 9. Active exam safety:
        # Admin starts an active EXAM containing q2
        exam_start_resp = self.client.post(
            "/api/v1/practice/sessions",
            json={"bank_id": bank_id, "mode": "EXAM", "total_questions": 1, "question_ids": [q2_id]},
            headers=admin_headers,
        )
        assert exam_start_resp.status_code == 201
        exam_session = exam_start_resp.json()
        assert exam_session["is_completed"] == 0

        # When admin queries content/questions, q2 answer and explanation must be masked
        admin_content_during_exam = self.client.get(f"/api/v1/banks/{bank_id}/content/questions", headers=admin_headers)
        assert admin_content_during_exam.status_code == 200
        q2_item = next(q for q in admin_content_during_exam.json() if q["id"] == q2_id)
        assert q2_item["answer"] == ""
        assert q2_item["explanation"] == ""

        # Attempting to edit q2 while active exam is running must be rejected
        exam_q_edit_resp = self.client.put(
            f"/api/v1/questions/{q2_id}",
            json={
                "stem": "Tampered question during exam",
                "type": "JUDGE",
                "options": [{"key": "T", "content": "True"}, {"key": "F", "content": "False"}],
                "answer": "T",
                "base_version_number": 1,
            },
            headers=admin_headers,
        )
        assert exam_q_edit_resp.status_code == 403

    def test_clear_chapter_in_question_update(self):
        admin_token, _ = self._register_and_login("admin_chap_user")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Create bank
        bank_resp = self.client.post(
            "/api/v1/banks",
            json={"name": "Chapter Bank", "category": "Test"},
            headers=admin_headers,
        )
        bank_id = bank_resp.json()["id"]

        # Create chapter 1 and chapter 2
        chap_resp = self.client.post(
            f"/api/v1/banks/{bank_id}/chapters",
            json={"name": "Chapter 1", "order_num": 1},
            headers=admin_headers,
        )
        assert chap_resp.status_code == 201
        chap_id = chap_resp.json()["id"]

        chap2_resp = self.client.post(
            f"/api/v1/banks/{bank_id}/chapters",
            json={"name": "Chapter 2", "order_num": 2},
            headers=admin_headers,
        )
        assert chap2_resp.status_code == 201
        chap2_id = chap2_resp.json()["id"]

        # Create question with chapter 1
        q_resp = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Question in chapter 1",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}],
                "answer": "A",
                "chapter_id": chap_id,
            },
            headers=admin_headers,
        )
        assert q_resp.status_code == 201
        qid = q_resp.json()["id"]
        assert q_resp.json().get("chapter_id") == chap_id

        # 1. Update without chapter_id (PracticeView edit path) -> retains chapter 1
        practice_edit_resp = self.client.put(
            f"/api/v1/questions/{qid}",
            json={
                "stem": "Stem updated from practice view",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}],
                "answer": "A",
                "base_version_number": 1,
            },
            headers=admin_headers,
        )
        assert practice_edit_resp.status_code == 200, practice_edit_resp.text
        assert practice_edit_resp.json().get("chapter_id") == chap_id

        # 2. Update with explicit new chapter ID -> updates to chapter 2
        update_chap2_resp = self.client.put(
            f"/api/v1/questions/{qid}",
            json={
                "stem": "Question moved to chapter 2",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}],
                "answer": "A",
                "chapter_id": chap2_id,
                "base_version_number": 2,
            },
            headers=admin_headers,
        )
        assert update_chap2_resp.status_code == 200, update_chap2_resp.text
        assert update_chap2_resp.json().get("chapter_id") == chap2_id

        # 3. Update question explicitly clearing chapter (chapter_id: None) -> cleared to None
        update_resp = self.client.put(
            f"/api/v1/questions/{qid}",
            json={
                "stem": "Question with cleared chapter",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}],
                "answer": "A",
                "chapter_id": None,
                "base_version_number": 3,
            },
            headers=admin_headers,
        )
        assert update_resp.status_code == 200, update_resp.text
        assert update_resp.json().get("chapter_id") is None

    def test_concurrent_edit_conflict_recording(self):
        admin_token, _ = self._register_and_login("admin_conflict_user")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Create bank and question v1
        bank_resp = self.client.post(
            "/api/v1/banks",
            json={"name": "Conflict Bank", "category": "Test"},
            headers=admin_headers,
        )
        bank_id = bank_resp.json()["id"]

        q_resp = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Initial version 1",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}],
                "answer": "A",
            },
            headers=admin_headers,
        )
        qid = q_resp.json()["id"]

        # Update to version 2
        self.client.put(
            f"/api/v1/questions/{qid}",
            json={
                "stem": "Updated to version 2",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}],
                "answer": "A",
                "base_version_number": 1,
            },
            headers=admin_headers,
        )

        # Now simulate concurrent edit based on outdated v1 (when current is v2)
        # Without allow_stale_branch, server MUST reject with HTTP 409 conflict
        conflict_edit_resp = self.client.put(
            f"/api/v1/questions/{qid}",
            json={
                "stem": "Conflicting edit based on v1",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}],
                "answer": "A",
                "base_version_number": 1,
                "allow_stale_branch": False,
                "reject_stale": True,
            },
            headers=admin_headers,
        )
        assert conflict_edit_resp.status_code == 409
        err_detail = conflict_edit_resp.json()["detail"]
        assert err_detail["error"] == "version_conflict"
        assert err_detail["base_version_number"] == 1
        assert err_detail["current_version_number"] == 2

        # Verify current version on server is STILL version 2 and stem was NOT overwritten
        server_q = self.client.get(f"/api/v1/questions/{qid}", headers=admin_headers)
        assert server_q.status_code == 200
        assert server_q.json()["version_number"] == 2
        assert server_q.json()["stem"] == "Updated to version 2"

        # Verify active conflict record exists in DB
        conflict_check = self.client.get(f"/api/v1/questions/{qid}/conflict", headers=admin_headers)
        assert conflict_check.status_code == 200
        conf_data = conflict_check.json()
        assert conf_data.get("has_conflict") is True
        assert conf_data["conflict"]["base_version_number"] == 1
        assert conf_data["conflict"]["server_version_number"] == 2

        # Verify backward compatibility: when allow_stale_branch=True, creating a branch succeeds with 200
        branch_resp = self.client.put(
            f"/api/v1/questions/{qid}",
            json={
                "stem": "Branch edit based on v1",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}],
                "answer": "A",
                "base_version_number": 1,
                "allow_stale_branch": True,
            },
            headers=admin_headers,
        )
        assert branch_resp.status_code == 200
        assert branch_resp.json()["version_number"] == 3


if __name__ == "__main__":
    unittest.main()
