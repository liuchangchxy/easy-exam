import json
import os
import sqlite3
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

    def test_single_choice_and_judge_invariants(self):
        """Review Finding 2: Server must strictly validate SINGLE, JUDGE, and MULTI invariants."""
        token, _ = self._register_and_login("invariant_tester")
        headers = {"Authorization": f"Bearer {token}"}

        bank_resp = self.client.post(
            "/api/v1/banks",
            json={"name": "Invariants Bank", "category": "Test"},
            headers=headers,
        )
        bank_id = bank_resp.json()["id"]

        # 1. SINGLE with answer outside options ("Z")
        res_single_bad_ans = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Single choice with invalid answer key",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                "answer": "Z",
            },
            headers=headers,
        )
        self.assertEqual(res_single_bad_ans.status_code, 400)
        self.assertIn("单选题答案包含不存在的选项键", res_single_bad_ans.text)

        # 2. SINGLE with < 2 options
        res_single_few_opts = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Single choice with 1 option",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}],
                "answer": "A",
            },
            headers=headers,
        )
        self.assertEqual(res_single_few_opts.status_code, 400)

        # 3. SINGLE with empty answer
        res_single_no_ans = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Single choice with no answer",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                "answer": "",
            },
            headers=headers,
        )
        self.assertEqual(res_single_no_ans.status_code, 400)

        # 4. JUDGE with invalid answer (e.g. "A")
        res_judge_bad_ans = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Judge question with bad answer",
                "type": "JUDGE",
                "options": [{"key": "T", "content": "正确"}, {"key": "F", "content": "错误"}],
                "answer": "A",
            },
            headers=headers,
        )
        self.assertEqual(res_judge_bad_ans.status_code, 400)
        self.assertIn("判断题答案必须为正确", res_judge_bad_ans.text)

        # 5. JUDGE with non-JUDGE options (A, B, C, D) must have options normalized strictly to T/F
        res_judge_ghost_opts = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Judge question converted from single choice",
                "type": "JUDGE",
                "options": [
                    {"key": "A", "content": "Option A"},
                    {"key": "B", "content": "Option B"},
                    {"key": "C", "content": "Option C"},
                    {"key": "D", "content": "Option D"},
                ],
                "answer": "正确",
            },
            headers=headers,
        )
        self.assertEqual(res_judge_ghost_opts.status_code, 201)
        judge_data = res_judge_ghost_opts.json()
        self.assertEqual(judge_data["answer"], "T")
        self.assertEqual(len(judge_data["options"]), 2)
        self.assertEqual([o["key"] for o in judge_data["options"]], ["T", "F"])

        # 6. MULTI with no options must be rejected
        res_multi_no_opts = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Multi question with no options",
                "type": "MULTI",
                "options": [],
                "answer": "A,B",
            },
            headers=headers,
        )
        self.assertEqual(res_multi_no_opts.status_code, 400)

        # 7. Valid SINGLE, MULTI, and JUDGE persist and re-read cleanly
        res_valid_single = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Valid single question",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                "answer": "B",
            },
            headers=headers,
        )
        self.assertEqual(res_valid_single.status_code, 201)
        single_id = res_valid_single.json()["id"]
        get_single = self.client.get(f"/api/v1/questions/{single_id}", headers=headers).json()
        self.assertEqual(get_single["answer"], "B")
        self.assertEqual(get_single["type"], "SINGLE")

    def test_resolve_conflict_and_pdf_confirm_under_active_exam(self):
        """Review Finding 3: resolve_conflict and pdf-confirm must enforce active exam protection."""
        admin_token, admin_id = self._register_and_login("exam_admin_finding3")
        student_token, student_id = self._register_and_login("exam_student_finding3")

        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        student_headers = {"Authorization": f"Bearer {student_token}"}

        # Admin creates bank
        bank_resp = self.client.post(
            "/api/v1/banks",
            json={"name": "Conflict Protect Bank", "category": "Sec"},
            headers=admin_headers,
        )
        bank_id = bank_resp.json()["id"]

        # Add student as MEMBER
        self.client.post(
            f"/api/v1/banks/{bank_id}/members",
            json={"username": "exam_student_finding3", "role": "MEMBER"},
            headers=admin_headers,
        )

        # Admin creates question (v1)
        q_resp = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Initial version of question",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                "answer": "A",
            },
            headers=admin_headers,
        )
        q_id = q_resp.json()["id"]

        # Admin updates question to v2
        up_resp = self.client.put(
            f"/api/v1/questions/{q_id}",
            json={
                "stem": "Second version of question",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                "answer": "B",
                "base_version_number": 1,
            },
            headers=admin_headers,
        )
        self.assertEqual(up_resp.status_code, 200)

        # Student starts an EXAM session with this question
        start_exam_resp = self.client.post(
            "/api/v1/exams/sessions",
            json={"bank_id": bank_id, "total_questions": 1, "time_limit": 60},
            headers=student_headers,
        )
        self.assertEqual(start_exam_resp.status_code, 201)
        exam_session_id = start_exam_resp.json()["id"]

        # Admin attempts resolve-conflict to adopt version 1 while exam is active
        resolve_resp = self.client.post(
            f"/api/v1/questions/{q_id}/resolve-conflict",
            json={"adopt_version_number": 1},
            headers=admin_headers,
        )
        self.assertEqual(resolve_resp.status_code, 403, f"Expected 403 for resolve-conflict during active exam: {resolve_resp.text}")

        # Check version count: must still be 2 (no version 3 inserted, no partial write)
        versions_resp = self.client.get(f"/api/v1/questions/{q_id}/versions", headers=admin_headers)
        self.assertEqual(versions_resp.status_code, 200)
        self.assertEqual(len(versions_resp.json()), 2)

        # Stage a pending PDF import draft to test pdf-confirm
        draft_id = "test-pdf-draft-1"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO pdf_import_drafts(id, user_id, bank_id, filename, candidate_questions_json, status)
                   VALUES (?, ?, ?, 'sample.pdf', '[]', 'PENDING')""",
                (draft_id, admin_id, bank_id),
            )

        # Admin attempts pdf-confirm merge while exam is active
        pdf_conf_resp = self.client.post(
            f"/api/v1/imports/banks/{bank_id}/pdf-confirm",
            json={
                "draft_id": draft_id,
                "questions": [{
                    "stem": "Second version of question",
                    "type": "SINGLE",
                    "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                    "answer": "B",
                }],
                "duplicate_strategy": "merge",
            },
            headers=admin_headers,
        )
        self.assertEqual(pdf_conf_resp.status_code, 403, f"Expected 403 for pdf-confirm merge during active exam: {pdf_conf_resp.text}")

        # Student completes exam session
        complete_resp = self.client.post(
            f"/api/v1/exams/sessions/{exam_session_id}/complete",
            headers=student_headers,
        )
        self.assertEqual(complete_resp.status_code, 200)

        # Now resolve-conflict succeeds
        resolve_after = self.client.post(
            f"/api/v1/questions/{q_id}/resolve-conflict",
            json={"adopt_version_number": 1},
            headers=admin_headers,
        )
        self.assertEqual(resolve_after.status_code, 200)
        self.assertEqual(resolve_after.json()["version_number"], 3)
        self.assertEqual(resolve_after.json()["answer"], "A")

    def test_error_messages_actionable_under_accept_language(self):
        """Review Finding 4: Error responses must carry structured error_code and actionable detail under Accept-Language."""
        admin_token, admin_id = self._register_and_login("error_tester")
        headers_zh = {"Authorization": f"Bearer {admin_token}", "Accept-Language": "zh-CN,zh;q=0.9"}
        headers_en = {"Authorization": f"Bearer {admin_token}", "Accept-Language": "en-US,en;q=0.9"}

        bank_resp = self.client.post(
            "/api/v1/banks",
            json={"name": "Error Msg Bank", "category": "Test"},
            headers=headers_zh,
        )
        bank_id = bank_resp.json()["id"]

        # 1. Illegal MULTI import returns 422 with actionable detail in body
        import_bad_multi = self.client.post(
            f"/api/v1/imports/banks/{bank_id}",
            json={
                "format": "json",
                "content": json.dumps([{
                    "stem": "Multi with only one answer",
                    "type": "MULTI",
                    "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                    "answer": "A",
                }]),
            },
            headers=headers_zh,
        )
        self.assertEqual(import_bad_multi.status_code, 422)
        body = import_bad_multi.json()
        self.assertIn("error_code", body)
        self.assertIn("detail", body)
        self.assertIn("多选题必须至少包含两个不同的正确答案", body["detail"])

        # 2. Active exam 403 returns EXAM_ACTIVE_PROTECTED and clear detail
        student_token, _ = self._register_and_login("student_err")
        student_headers = {"Authorization": f"Bearer {student_token}"}
        self.client.post(f"/api/v1/banks/{bank_id}/members", json={"username": "student_err", "role": "MEMBER"}, headers=headers_zh)

        q_resp = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Question for error check",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                "answer": "A",
            },
            headers=headers_zh,
        )
        q_id = q_resp.json()["id"]

        self.client.post(
            "/api/v1/exams/sessions",
            json={"bank_id": bank_id, "total_questions": 1, "time_limit": 60},
            headers=student_headers,
        )

        # In zh-CN:
        edit_zh = self.client.put(
            f"/api/v1/questions/{q_id}",
            json={
                "stem": "Question edit attempt",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                "answer": "B",
                "base_version_number": 1,
            },
            headers=headers_zh,
        )
        self.assertEqual(edit_zh.status_code, 403)
        self.assertEqual(edit_zh.json().get("error_code"), "EXAM_ACTIVE_PROTECTED")
        self.assertIn("cannot edit question while exam is active", edit_zh.json().get("detail", ""))

        # In en-US:
        edit_en = self.client.put(
            f"/api/v1/questions/{q_id}",
            json={
                "stem": "Question edit attempt",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                "answer": "B",
                "base_version_number": 1,
            },
            headers=headers_en,
        )
        self.assertEqual(edit_en.status_code, 403)
        self.assertEqual(edit_en.json().get("error_code"), "EXAM_ACTIVE_PROTECTED")

    def test_cross_user_bank_lock_status_exposed_in_read_models(self):
        """Review Finding 5: Server exposes cross-user lock status in bank and question read models."""
        admin_token, _ = self._register_and_login("admin_lock_view")
        student_token, _ = self._register_and_login("student_lock_view")

        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        student_headers = {"Authorization": f"Bearer {student_token}"}

        bank_resp = self.client.post(
            "/api/v1/banks",
            json={"name": "Lock View Bank", "category": "Test"},
            headers=admin_headers,
        )
        bank_id = bank_resp.json()["id"]

        self.client.post(f"/api/v1/banks/{bank_id}/members", json={"username": "student_lock_view", "role": "MEMBER"}, headers=admin_headers)

        q_resp = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            json={
                "stem": "Question in lock test",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
                "answer": "A",
            },
            headers=admin_headers,
        )
        q_id = q_resp.json()["id"]

        # Before exam: lock flags must be False
        bank_before = self.client.get(f"/api/v1/banks/{bank_id}", headers=admin_headers).json()
        self.assertFalse(bank_before.get("locked_by_active_exam"))
        self.assertFalse(bank_before.get("has_active_exam"))

        qs_before = self.client.get(f"/api/v1/banks/{bank_id}/content/questions", headers=admin_headers).json()
        self.assertFalse(qs_before[0].get("locked_by_active_exam"))

        # Student starts exam session
        exam_resp = self.client.post(
            "/api/v1/exams/sessions",
            json={"bank_id": bank_id, "total_questions": 1, "time_limit": 60},
            headers=student_headers,
        )
        session_id = exam_resp.json()["id"]

        # During student's active exam: Admin sees locked_by_active_exam == True on bank and questions!
        bank_during = self.client.get(f"/api/v1/banks/{bank_id}", headers=admin_headers).json()
        self.assertTrue(bank_during.get("locked_by_active_exam"))
        self.assertTrue(bank_during.get("has_active_exam"))

        qs_during = self.client.get(f"/api/v1/banks/{bank_id}/content/questions", headers=admin_headers).json()
        self.assertTrue(qs_during[0].get("locked_by_active_exam"))

        # Student completes exam session
        self.client.post(f"/api/v1/exams/sessions/{session_id}/complete", headers=student_headers)

        # After exam completion: lock is released!
        bank_after = self.client.get(f"/api/v1/banks/{bank_id}", headers=admin_headers).json()
        self.assertFalse(bank_after.get("locked_by_active_exam"))
        self.assertFalse(bank_after.get("has_active_exam"))

        qs_after = self.client.get(f"/api/v1/banks/{bank_id}/content/questions", headers=admin_headers).json()
        self.assertFalse(qs_after[0].get("locked_by_active_exam"))


if __name__ == "__main__":
    unittest.main()
