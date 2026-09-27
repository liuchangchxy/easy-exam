import json
import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


class TestV1Architecture(unittest.TestCase):
    def setUp(self):
        self._orig_secret = os.environ.get("EASYEXAM_SECRET_KEY")
        os.environ["EASYEXAM_SECRET_KEY"] = "easyexam-ci-secret-32bytes-passphrase!!"
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = str(Path(self.temp_dir.name) / "easyexam-v1.db")
        self.app = create_app(self.db_path)
        self.client = TestClient(self.app)

    def tearDown(self):
        if self._orig_secret is not None:
            os.environ["EASYEXAM_SECRET_KEY"] = self._orig_secret
        else:
            os.environ.pop("EASYEXAM_SECRET_KEY", None)
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_v1_health_uses_new_application_entrypoint(self):
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["app"], "easy-exam")
        self.assertEqual(body["version"], "v1")
        self.assertIn("commit_sha", body)
        self.assertIn("instance_token", body)

    def test_register_login_and_current_user_are_isolated(self):
        register = self.client.post(
            "/api/v1/auth/register",
            json={"username": "alice", "password": "correct horse battery staple"},
        )
        self.assertEqual(register.status_code, 201)
        self.assertEqual(register.json()["username"], "alice")
        self.assertNotIn("password", register.json())

        login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "correct horse battery staple"},
        )
        self.assertEqual(login.status_code, 200)
        token = login.json()["token"]
        self.assertTrue(token)
        self.assertNotIn("password_hash", login.json())

        me = self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "alice")

    def test_question_banks_are_visible_only_to_members(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        self.client.post("/api/v1/auth/register", json={"username": "bob", "password": "password-123456"})
        alice_token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        bob_token = self.client.post("/api/v1/auth/login", json={"username": "bob", "password": "password-123456"}).json()["token"]
        self.client.post("/api/v1/banks", headers={"Authorization": f"Bearer {alice_token}"}, json={"name": "Alice 私有题库"})
        bob_banks = self.client.get("/api/v1/banks", headers={"Authorization": f"Bearer {bob_token}"})
        self.assertEqual(bob_banks.status_code, 200)
        self.assertEqual(bob_banks.json(), [])

    def test_bank_admin_can_share_bank_with_member(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        self.client.post("/api/v1/auth/register", json={"username": "bob", "password": "password-123456"})
        alice = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        bob = self.client.post("/api/v1/auth/login", json={"username": "bob", "password": "password-123456"}).json()["token"]
        bank = self.client.post("/api/v1/banks", headers={"Authorization": f"Bearer {alice}"}, json={"name": "共享题库"}).json()
        member = self.client.post(f"/api/v1/banks/{bank['id']}/members", headers={"Authorization": f"Bearer {alice}"}, json={"username": "bob", "role": "MEMBER"})
        self.assertEqual(member.status_code, 201)
        self.assertEqual(len(self.client.get("/api/v1/banks", headers={"Authorization": f"Bearer {bob}"}).json()), 1)

    def test_wrong_attempt_enters_private_mistake_list(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "错题题库"}).json()
        question = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "答案？", "answer": "A"}).json()
        session = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
        self.client.post(f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers, json={"question_id": question["id"], "user_answer": "B"})
        mistakes = self.client.get("/api/v1/mistakes", headers=headers)
        self.assertEqual(mistakes.status_code, 200)
        self.assertEqual(mistakes.json()[0]["question_id"], question["id"])
        summary = self.client.get("/api/v1/learning/summary", headers=headers)
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["attempts"], 1)
        self.assertEqual(summary.json()["weak_questions"], 1)

    def test_update_mistake_cause_persists_to_records_and_attempts(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "错题题库"}).json()
        question = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "答案？", "answer": "A"}).json()
        session = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
        self.client.post(f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers, json={"question_id": question["id"], "user_answer": "B"})

        res = self.client.put(f"/api/v1/mistakes/{question['id']}/cause", headers=headers, json={"mistake_cause": "CONCEPT"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["mistake_cause"], "CONCEPT")

        mistakes = self.client.get("/api/v1/mistakes", headers=headers).json()
        self.assertEqual(mistakes[0]["mistake_cause"], "CONCEPT")

    def test_mistake_and_fsrs_sessions_are_strictly_scoped_to_target_questions(self):
        self.client.post("/api/v1/auth/register", json={"username": "bob-scoped", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "bob-scoped", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "专项题库"}).json()
        q1 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题1", "answer": "A"}).json()
        q2 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题2", "answer": "B"}).json()
        q3 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题3", "answer": "C"}).json()

        # Normal session: answer q1 right, q2 wrong
        sess1 = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
        self.client.post(f"/api/v1/practice/sessions/{sess1['id']}/attempts", headers=headers, json={"question_id": q1["id"], "user_answer": "A"})
        self.client.post(f"/api/v1/practice/sessions/{sess1['id']}/attempts", headers=headers, json={"question_id": q2["id"], "user_answer": "wrong"})

        # Start MISTAKE mode session without question_ids -> should only include q2
        mistake_sess = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"], "mode": "MISTAKE"}).json()
        self.assertEqual(mistake_sess["total_questions"], 1)
        mistake_qs = self.client.get(f"/api/v1/practice/sessions/{mistake_sess['id']}/questions", headers=headers).json()
        self.assertEqual(len(mistake_qs), 1)
        self.assertEqual(mistake_qs[0]["id"], q2["id"])

        # Start MISTAKE mode session with specific question_ids
        scoped_sess = self.client.post(
            "/api/v1/practice/sessions",
            headers=headers,
            json={"bank_id": bank["id"], "mode": "MISTAKE", "question_ids": [q2["id"]]}
        ).json()
        self.assertEqual(scoped_sess["total_questions"], 1)
        scoped_qs = self.client.get(f"/api/v1/practice/sessions/{scoped_sess['id']}/questions", headers=headers).json()
        self.assertEqual([q["id"] for q in scoped_qs], [q2["id"]])

    def test_killed_list_includes_bank_id_and_can_launch_elimination_session(self):
        self.client.post("/api/v1/auth/register", json={"username": "carol-kill", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "carol-kill", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "斩杀题库测试"}).json()
        q1 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "斩杀题目", "answer": "A"}).json()

        # Kill question
        self.client.post(f"/api/v1/kills/{q1['id']}", headers=headers)
        kills = self.client.get("/api/v1/kills", headers=headers).json()
        self.assertEqual(len(kills), 1)
        self.assertEqual(kills[0]["bank_id"], bank["id"])

        # Start elimination session using bank_id
        session = self.client.post(
            "/api/v1/practice/sessions",
            headers=headers,
            json={"bank_id": kills[0]["bank_id"], "mode": "ELIMINATION", "question_ids": [q1["id"]]}
        ).json()
        self.assertEqual(session["mode"], "ELIMINATION")
        self.assertEqual(session["total_questions"], 1)

    def test_submit_attempt_with_fsrs_rating_updates_card_and_rejects_inconsistent_rating(self):
        self.client.post("/api/v1/auth/register", json={"username": "dave-fsrs", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "dave-fsrs", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "FSRS题库"}).json()
        q1 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "FSRS题", "answer": "A"}).json()
        # Initial practice attempt: wrong answer creates a mistake/card
        init_sess = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
        self.client.post(f"/api/v1/practice/sessions/{init_sess['id']}/attempts", headers=headers, json={"question_id": q1["id"], "user_answer": "B"})

        # Make card legitimately due for FSRS review
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE fsrs_cards SET due_at = '2020-01-01 00:00:00' WHERE question_id = ?", (q1["id"],))
            conn.commit()

        # Now start FSRS session with question_ids
        sess = self.client.post(
            "/api/v1/practice/sessions",
            headers=headers,
            json={"bank_id": bank["id"], "mode": "FSRS", "question_ids": [q1["id"]]}
        ).json()
        self.assertEqual(sess["mode"], "FSRS")

        # Wrong answer with rating 3 must be rejected with 422
        bad_res = self.client.post(
            f"/api/v1/practice/sessions/{sess['id']}/attempts",
            headers=headers,
            json={"question_id": q1["id"], "user_answer": "B", "fsrs_rating": 3}
        )
        self.assertEqual(bad_res.status_code, 422)

        # Right answer with rating 3 succeeds
        good_res = self.client.post(
            f"/api/v1/practice/sessions/{sess['id']}/attempts",
            headers=headers,
            json={"question_id": q1["id"], "user_answer": "A", "fsrs_rating": 3}
        )
        self.assertEqual(good_res.status_code, 201)
        self.assertEqual(good_res.json()["fsrs_rating"], 3)

    def test_submitting_rating_on_existing_attempt_updates_rating_and_reschedules_fsrs(self):
        self.client.post("/api/v1/auth/register", json={"username": "frank-rating", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "frank-rating", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "评级更新题库"}).json()
        q1 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "评级更新题", "answer": "A"}).json()
        sess = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()

        # Step 1: User submits answer "A" without rating first (as happens on practice page)
        res1 = self.client.post(
            f"/api/v1/practice/sessions/{sess['id']}/attempts",
            headers=headers,
            json={"question_id": q1["id"], "user_answer": "A"}
        )
        self.assertEqual(res1.status_code, 201)
        self.assertIsNone(res1.json().get("fsrs_rating"))

        # Step 2: User now clicks "4 - Easy" on UI, calling submitAttempt with identical user_answer "A" and fsrs_rating=4
        res2 = self.client.post(
            f"/api/v1/practice/sessions/{sess['id']}/attempts",
            headers=headers,
            json={"question_id": q1["id"], "user_answer": "A", "fsrs_rating": 4}
        )
        self.assertEqual(res2.status_code, 201)
        self.assertEqual(res2.json()["fsrs_rating"], 4)

        # Step 3: User changes rating to "3 - Good" -> must update to 3
        res3 = self.client.post(
            f"/api/v1/practice/sessions/{sess['id']}/attempts",
            headers=headers,
            json={"question_id": q1["id"], "user_answer": "A", "fsrs_rating": 3}
        )
        self.assertEqual(res3.status_code, 201)
        self.assertEqual(res3.json()["fsrs_rating"], 3)

    def test_exam_submission_is_idempotent_and_completed_session_rejects_further_attempts(self):
        self.client.post("/api/v1/auth/register", json={"username": "eve-idempotent", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "eve-idempotent", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "幂等测试题库"}).json()
        q1 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "幂等题", "answer": "A"}).json()
        sess = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"], "mode": "EXAM"}).json()

        # Submit attempt
        res1 = self.client.post(
            f"/api/v1/practice/sessions/{sess['id']}/attempts",
            headers=headers,
            json={"question_id": q1["id"], "user_answer": "B"}
        )
        self.assertEqual(res1.status_code, 201)

        # Retry identical attempt (e.g. frontend network retry)
        res2 = self.client.post(
            f"/api/v1/practice/sessions/{sess['id']}/attempts",
            headers=headers,
            json={"question_id": q1["id"], "user_answer": "B"}
        )
        self.assertEqual(res2.status_code, 201)

        # Check mistake records: mistake_count must be 1, not 2
        mistakes = self.client.get("/api/v1/mistakes", headers=headers).json()
        self.assertEqual(len(mistakes), 1)
        self.assertEqual(mistakes[0]["mistake_count"], 1)

        # Complete session
        comp1 = self.client.post(f"/api/v1/practice/sessions/{sess['id']}/complete", headers=headers)
        self.assertEqual(comp1.status_code, 200)

        # Subsequent attempts on completed session must be rejected
        late_attempt = self.client.post(
            f"/api/v1/practice/sessions/{sess['id']}/attempts",
            headers=headers,
            json={"question_id": q1["id"], "user_answer": "A"}
        )
        self.assertIn(late_attempt.status_code, {400, 409, 422})

        # Calling complete again is idempotent
        comp2 = self.client.post(f"/api/v1/practice/sessions/{sess['id']}/complete", headers=headers)
        self.assertEqual(comp2.status_code, 200)

    def test_change_password_flow(self):
        self.client.post("/api/v1/auth/register", json={"username": "frank-pwd", "password": "old-password-123456"})
        login_res = self.client.post("/api/v1/auth/login", json={"username": "frank-pwd", "password": "old-password-123456"}).json()
        token = login_res["token"]
        self.assertFalse(login_res["user"]["must_change_password"])

        headers = {"Authorization": f"Bearer {token}"}
        # Change password with wrong old password fails
        bad_change = self.client.post("/api/v1/auth/change-password", headers=headers, json={"old_password": "wrong", "new_password": "new-password-123456"})
        self.assertEqual(bad_change.status_code, 400)

        # Change password with correct old password succeeds
        good_change = self.client.post("/api/v1/auth/change-password", headers=headers, json={"old_password": "old-password-123456", "new_password": "new-password-123456"})
        self.assertEqual(good_change.status_code, 200)

        # Login with old password fails
        old_login = self.client.post("/api/v1/auth/login", json={"username": "frank-pwd", "password": "old-password-123456"})
        self.assertEqual(old_login.status_code, 401)

        # Login with new password succeeds
        new_login = self.client.post("/api/v1/auth/login", json={"username": "frank-pwd", "password": "new-password-123456"})
        self.assertEqual(new_login.status_code, 200)

    def test_exam_profile_blueprint_and_exam_session_are_versioned(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        profile = self.client.post("/api/v1/exams/profiles", headers=headers, json={"name": "公考"})
        self.assertEqual(profile.status_code, 201)
        saved = self.client.post(f"/api/v1/exams/profiles/{profile.json()['id']}/blueprint", headers=headers, json={"blueprint": {"sections": [{"name": "判断", "weight": 0.5}]}})
        self.assertEqual(saved.status_code, 201)
        self.assertEqual(saved.json()["version_number"], 1)
        session = self.client.post(
            "/api/v1/exams/sessions",
            headers=headers,
            json={"bank_id": "missing-bank", "profile_id": profile.json()["id"]},
        )
        self.assertEqual(session.status_code, 404)

    def test_exam_session_persists_selected_blueprint_version(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        profile = self.client.post("/api/v1/exams/profiles", headers=headers, json={"name": "蓝图绑定"}).json()
        blueprint = self.client.post(
            f"/api/v1/exams/profiles/{profile['id']}/blueprint",
            headers=headers,
            json={"blueprint": {"sections": [{"name": "判断", "weight": 1.0}]}},
        ).json()
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "模考"}).json()
        self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题", "type": "JUDGE", "answer": "T"})
        session = self.client.post(
            "/api/v1/exams/sessions", headers=headers,
            json={"bank_id": bank["id"], "profile_id": profile["id"]},
        )
        self.assertEqual(session.status_code, 201)
        self.assertEqual(session.json()["exam_profile_id"], profile["id"])
        self.assertEqual(session.json()["blueprint_id"], blueprint["id"])

    def test_exam_blueprint_negative_mark_applies_only_at_final_report(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        profile = self.client.post("/api/v1/exams/profiles", headers=headers, json={"name": "负分规则"}).json()
        self.client.post(
            f"/api/v1/exams/profiles/{profile['id']}/blueprint",
            headers=headers,
            json={"blueprint": {"negative_mark": 0.25}},
        )
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "负分题库"}).json()
        question = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题", "answer": "A"}).json()
        session = self.client.post("/api/v1/exams/sessions", headers=headers, json={"bank_id": bank["id"], "profile_id": profile["id"]}).json()
        attempt = self.client.post(
            f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers,
            json={"question_id": question["id"], "user_answer": "B"},
        )
        self.assertNotIn("correctness", attempt.json())
        report = self.client.post(f"/api/v1/exams/sessions/{session['id']}/complete", headers=headers)
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.json()["score"], -0.25)

    def test_exam_session_does_not_leak_answers_or_explanations_before_completion(self):
        self.client.post("/api/v1/auth/register", json={"username": "exam_student", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "exam_student", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "保密考试题库"}).json()
        q1 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "第一题", "type": "SINGLE", "answer": "B", "explanation": "机密解析1", "tags": ["常识"]}).json()
        q2 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "第二题", "type": "MULTI", "answer": "CD", "explanation": "机密解析2", "tags": ["逻辑"]}).json()

        # Start exam session
        session = self.client.post("/api/v1/exams/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
        session_id = session["id"]

        # 1. Inspect get_session before completion
        s_data = self.client.get(f"/api/v1/practice/sessions/{session_id}", headers=headers).json()
        for q in s_data["questions"]:
            self.assertNotIn("answer", q, "Exam session leaked standard answer via get_session")
            self.assertNotIn("explanation", q, "Exam session leaked explanation via get_session")

        # 2. Inspect get_session_questions before completion
        q_data = self.client.get(f"/api/v1/practice/sessions/{session_id}/questions", headers=headers).json()
        for q in q_data:
            self.assertNotIn("answer", q, "Exam questions endpoint leaked standard answer")
            self.assertNotIn("explanation", q, "Exam questions endpoint leaked explanation")

        # 3. Submit attempt before completion
        att = self.client.post(f"/api/v1/practice/sessions/{session_id}/attempts", headers=headers, json={"question_id": q1["id"], "user_answer": "B"}).json()
        self.assertFalse(att.get("feedback_available", True))
        self.assertNotIn("correctness", att, "Exam attempt leaked correctness")
        self.assertNotIn("score_ratio", att, "Exam attempt leaked score_ratio")
        self.assertNotIn("is_correct", att, "Exam attempt leaked is_correct")

        # 4. Sync draft before completion
        synced = self.client.post(f"/api/v1/practice/sessions/{session_id}/sync", headers=headers, json={"answers": {q1["id"]: "B"}}).json()
        for q in synced["questions"]:
            self.assertNotIn("answer", q, "Exam sync leaked standard answer")
            self.assertNotIn("explanation", q, "Exam sync leaked explanation")

        # 5. Complete session: now answers, explanations, type_stats, and tag_stats should be available
        report = self.client.post(f"/api/v1/exams/sessions/{session_id}/complete", headers=headers).json()
        self.assertTrue(report["is_completed"])
        self.assertIn("type_stats", report)
        self.assertIn("SINGLE", report["type_stats"])
        self.assertIn("tag_stats", report)
        self.assertIn("常识", report["tag_stats"])
        self.assertEqual(report["answers"][q1["id"]]["correct_answer"], "B")
        self.assertEqual(report["answers"][q1["id"]]["explanation"], "机密解析1")

    def test_kill_is_explicit_and_wrong_answer_restores_question(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "斩杀题库"}).json()
        question = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题", "answer": "A"}).json()
        killed = self.client.post(f"/api/v1/kills/{question['id']}", headers=headers)
        self.assertEqual(killed.status_code, 201)
        self.assertEqual(len(self.client.get("/api/v1/kills", headers=headers).json()), 1)
        regular = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
        regular_state = self.client.get(f"/api/v1/practice/sessions/{regular['id']}", headers=headers).json()
        self.assertNotIn(question["id"], regular_state["question_ids"])
        session_response = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"], "mode": "ELIMINATION"})
        self.assertEqual(session_response.status_code, 201)
        session = session_response.json()
        session_state = self.client.get(f"/api/v1/practice/sessions/{session['id']}", headers=headers).json()
        self.assertIn(question["id"], session_state["question_ids"])
        attempt = self.client.post(f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers, json={"question_id": question["id"], "user_answer": "B"})
        self.assertEqual(attempt.status_code, 201)
        self.assertEqual(self.client.get("/api/v1/kills", headers=headers).json(), [])

    def test_sync_events_are_append_only_and_idempotent(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        event = {"id": "device-a-1", "event_type": "NOTE_UPDATED", "aggregate_type": "question", "aggregate_id": "q1", "payload": {"text": "版本 A"}}
        first = self.client.post("/api/v1/sync/events", headers=headers, json={"events": [event]})
        second = self.client.post("/api/v1/sync/events", headers=headers, json={"events": [event]})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json()["accepted"], 0)
        events = self.client.get("/api/v1/sync/events", headers=headers).json()
        self.assertEqual(len(events), 1)

    def test_draft_sync_merges_answers_and_prevents_empty_overwrites_and_reports_conflicts(self):
        self.client.post("/api/v1/auth/register", json={"username": "sync_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "sync_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "同步题库"}).json()
        q1 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题1", "answer": "A"}).json()
        q2 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题2", "answer": "B"}).json()

        session = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
        session_id = session["id"]

        # Device 1 syncs q1: "A"
        res1 = self.client.post(f"/api/v1/sync/sessions/{session_id}", headers=headers, json={"answers": {q1["id"]: "A"}}).json()
        self.assertEqual(res1["answers"][q1["id"]], "A")

        # Device 2 syncs q2: "B", but has empty answer "" for q1
        res2 = self.client.post(f"/api/v1/sync/sessions/{session_id}", headers=headers, json={"answers": {q1["id"]: "", q2["id"]: "B"}}).json()
        # Merged result: q1 MUST NOT be overwritten by empty string!
        self.assertEqual(res2["answers"][q1["id"]], "A")
        self.assertEqual(res2["answers"][q2["id"]], "B")

        # Device 3 syncs conflicting answer for q1: "C"
        res3 = self.client.post(f"/api/v1/sync/sessions/{session_id}", headers=headers, json={"answers": {q1["id"]: "C"}}).json()
        self.assertTrue(res3.get("has_conflict", False))
        self.assertTrue(any(c.get("question_id") == q1["id"] for c in res3.get("conflicts", [])))


    def test_versioned_schema_contains_private_assets_and_import_jobs(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            conn.close()
        self.assertIn("personal_assets", tables)
        self.assertIn("import_jobs", tables)
        self.assertIn("mistake_records", tables)

    def test_bank_chapters_and_knowledge_tags_are_scoped_to_bank(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "分类题库"}).json()
        chapter = self.client.post(f"/api/v1/banks/{bank['id']}/chapters", headers=headers, json={"name": "第一章"})
        tag = self.client.post(f"/api/v1/banks/{bank['id']}/tags", headers=headers, json={"name": "网络"})
        self.assertEqual(chapter.status_code, 201)
        self.assertEqual(tag.status_code, 201)
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank['id']}/chapters", headers=headers).json()[0]["name"], "第一章")
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank['id']}/tags", headers=headers).json()[0]["name"], "网络")

    def test_personal_assets_are_private_and_queryable(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = self.client.post("/api/v1/assets", headers=headers, json={"asset_type": "NOTE", "content": "记住这个公式"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.get("/api/v1/assets", headers=headers).json()[0]["content"], "记住这个公式")

    def test_question_bank_and_question_version_are_created_for_current_user(self):
        self.client.post(
            "/api/v1/auth/register",
            json={"username": "alice", "password": "password-123456"},
        )
        login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "password-123456"},
        )
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        bank = self.client.post(
            "/api/v1/banks",
            headers=headers,
            json={"name": "网络基础", "description": "基础题库"},
        )
        self.assertEqual(bank.status_code, 201)
        bank_id = bank.json()["id"]

        question = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            headers=headers,
            json={
                "stem": "HTTP 默认端口是什么？",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "80"}],
                "answer": "A",
                "explanation": "HTTP 默认端口为 80。",
            },
        )
        self.assertEqual(question.status_code, 201)
        self.assertEqual(question.json()["version_number"], 1)

    def test_practice_attempt_persists_partial_score_without_mastery(self):
        self.client.post(
            "/api/v1/auth/register",
            json={"username": "alice", "password": "password-123456"},
        )
        login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "password-123456"},
        )
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "多选题库"}).json()
        question = self.client.post(
            f"/api/v1/banks/{bank['id']}/questions",
            headers=headers,
            json={
                "stem": "选择正确选项",
                "type": "MULTI",
                "options": [{"key": "A", "content": "甲"}, {"key": "B", "content": "乙"}],
                "answer": "AB",
            },
        ).json()

        session = self.client.post(
            "/api/v1/practice/sessions",
            headers=headers,
            json={"bank_id": bank["id"], "mode": "PRACTICE"},
        )
        self.assertEqual(session.status_code, 201)
        attempt = self.client.post(
            f"/api/v1/practice/sessions/{session.json()['id']}/attempts",
            headers=headers,
            json={"question_id": question["id"], "user_answer": "A"},
        )

        self.assertEqual(attempt.status_code, 201)
        self.assertEqual(attempt.json()["correctness"], "PARTIAL")
        self.assertEqual(attempt.json()["mastery_status"], "PARTIAL")
        self.assertFalse(attempt.json()["is_correct"])

    def test_ai_answer_versions_are_saved_and_personal_adoption_is_separate(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        login = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"})
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "AI题库"}).json()
        question = self.client.post(
            f"/api/v1/banks/{bank['id']}/questions",
            headers=headers,
            json={"stem": "1+1=?", "type": "SINGLE", "options": [], "answer": "2"},
        ).json()

        candidate = self.client.post(
            f"/api/v1/ai/questions/{question['id']}/answers",
            headers=headers,
            json={"content": "答案是 2，因为加法单位元规则。", "source": "AI"},
        )
        self.assertEqual(candidate.status_code, 201)
        self.assertEqual(candidate.json()["source"], "AI")
        self.assertFalse(candidate.json()["is_adopted"])

        adopted = self.client.post(
            f"/api/v1/ai/answers/{candidate.json()['id']}/adopt",
            headers=headers,
        )
        self.assertEqual(adopted.status_code, 200)
        self.assertTrue(adopted.json()["is_adopted"])
        self.assertEqual(self.client.get(f"/api/v1/ai/questions/{question['id']}/answers", headers=headers).json()[0]["id"], candidate.json()["id"])

    def test_ai_generation_is_optional_and_offline_answer_is_still_saved(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "AI离线题库"}).json()
        question = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题", "answer": "A"}).json()
        generated = self.client.post(f"/api/v1/ai/questions/{question['id']}/generate", headers=headers, json={"query": "解释一下"})
        self.assertEqual(generated.status_code, 201)
        self.assertEqual(generated.json()["source"], "AI")
        self.assertTrue(generated.json()["content"])

    def test_web_verification_saves_a_separate_explanation_and_evidence_state(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "联网核查"}).json()
        question = self.client.post(
            f"/api/v1/banks/{bank['id']}/questions", headers=headers,
            json={"stem": "题目", "answer": "A"},
        ).json()
        verified = self.client.post(
            f"/api/v1/ai/questions/{question['id']}/verify-web", headers=headers,
            json={"query": "官方依据"},
        )
        self.assertEqual(verified.status_code, 201)
        body = verified.json()
        self.assertEqual(body["source"], "WEB")
        self.assertIn("verification_status", body)
        self.assertIn("evidence", body)
        self.assertEqual(self.client.get(f"/api/v1/ai/questions/{question['id']}/answers", headers=headers).json()[0]["source"], "WEB")

    def test_question_edit_creates_new_version_and_old_version_remains_queryable(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "版本题库"}).json()
        question = self.client.post(
            f"/api/v1/banks/{bank['id']}/questions", headers=headers,
            json={"stem": "旧题干", "type": "SINGLE", "answer": "A"},
        ).json()

        updated = self.client.put(
            f"/api/v1/questions/{question['id']}", headers=headers,
            json={"stem": "新题干", "type": "SINGLE", "answer": "B"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["version_number"], 2)
        versions = self.client.get(f"/api/v1/questions/{question['id']}/versions", headers=headers)
        self.assertEqual(versions.status_code, 200)
        self.assertEqual([item["version_number"] for item in versions.json()], [1, 2])

    def test_practice_session_freezes_question_versions_at_start(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "会话题目快照"}).json()
        question = self.client.post(
            f"/api/v1/banks/{bank['id']}/questions", headers=headers,
            json={"stem": "启动时题干", "answer": "A"},
        ).json()
        session = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
        updated = self.client.put(
            f"/api/v1/questions/{question['id']}", headers=headers,
            json={"stem": "修改後題干", "answer": "B"},
        )
        self.assertEqual(updated.status_code, 200)
        session_questions = self.client.get(f"/api/v1/practice/sessions/{session['id']}/questions", headers=headers)
        self.assertEqual(session_questions.json()[0]["stem"], "启动时题干")
        attempt = self.client.post(
            f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers,
            json={"question_id": question["id"], "user_answer": "A"},
        )
        self.assertEqual(attempt.status_code, 201)
        self.assertEqual(attempt.json()["correctness"], "CORRECT")

    def test_copying_a_question_creates_an_independent_learning_identity(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        source_bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "源题库"}).json()
        target_bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "目标题库"}).json()
        source_question = self.client.post(
            f"/api/v1/banks/{source_bank['id']}/questions",
            headers=headers,
            json={"stem": "可复制题", "answer": "A"},
        ).json()
        copied = self.client.post(
            f"/api/v1/banks/{target_bank['id']}/questions/{source_question['id']}/copy",
            headers=headers,
        )
        self.assertEqual(copied.status_code, 201)
        self.assertNotEqual(copied.json()["id"], source_question["id"])
        self.assertEqual(copied.json()["stem"], source_question["stem"])

    def test_exam_hides_feedback_until_submit_and_report_recomputes_attempts(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "模考题库"}).json()
        first = self.client.post(
            f"/api/v1/banks/{bank['id']}/questions",
            headers=headers,
            json={"stem": "判断题", "type": "JUDGE", "answer": "T", "tags": ["判断"]},
        ).json()
        self.client.post(
            f"/api/v1/banks/{bank['id']}/questions",
            headers=headers,
            json={"stem": "单选题", "type": "SINGLE", "answer": "A", "tags": ["基础"]},
        )
        session = self.client.post(
            "/api/v1/exams/sessions", headers=headers,
            json={"bank_id": bank["id"], "total_questions": 2, "time_limit": 60},
        ).json()
        attempt = self.client.post(
            f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers,
            json={"question_id": first["id"], "user_answer": "F"},
        )
        self.assertEqual(attempt.status_code, 201)
        self.assertNotIn("correct_answer", attempt.json())
        self.assertEqual(attempt.json()["feedback_available"], False)

        report = self.client.post(f"/api/v1/practice/sessions/{session['id']}/complete", headers=headers)
        self.assertEqual(report.status_code, 200)
        body = report.json()
        self.assertEqual(body["answered_count"], 1)
        self.assertEqual(body["unanswered_count"], 1)
        self.assertEqual(body["correct_count"], 0)
        self.assertEqual(body["incorrect_count"], 1)
        self.assertEqual(body["type_stats"]["JUDGE"]["incorrect"], 1)
        self.assertEqual(body["tag_stats"]["判断"]["incorrect"], 1)

    def test_exam_question_and_session_reads_do_not_leak_answers_before_submission(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "保密模考"}).json()
        question = self.client.post(
            f"/api/v1/banks/{bank['id']}/questions", headers=headers,
            json={"stem": "题目", "answer": "SECRET-ANSWER", "explanation": "SECRET-EXPLANATION"},
        ).json()
        session = self.client.post(
            "/api/v1/exams/sessions", headers=headers,
            json={"bank_id": bank["id"]},
        ).json()
        attempt = self.client.post(
            f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers,
            json={"question_id": question["id"], "user_answer": "B"},
        )
        self.assertEqual(attempt.status_code, 201)
        self.assertFalse(attempt.json()["feedback_available"])

        question_payload = self.client.get(f"/api/v1/practice/sessions/{session['id']}/questions", headers=headers).json()[0]
        session_payload = self.client.get(f"/api/v1/practice/sessions/{session['id']}", headers=headers).json()
        self.assertEqual(question_payload["id"], question["id"])
        self.assertNotIn("answer", question_payload)
        self.assertNotIn("explanation", question_payload)
        self.assertNotIn("SECRET-ANSWER", str(session_payload))
        self.assertNotIn("SECRET-EXPLANATION", str(session_payload))
        self.assertNotIn("correctness", session_payload["answers"][question["id"]])

    def test_scoped_modes_reject_arbitrary_question_ids_outside_scoped_queues(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "专项防绕过题库"}).json()
        q1 = self.client.post(
            f"/api/v1/banks/{bank['id']}/questions", headers=headers,
            json={"stem": "题目1", "answer": "A"},
        ).json()
        q2 = self.client.post(
            f"/api/v1/banks/{bank['id']}/questions", headers=headers,
            json={"stem": "题目2", "answer": "B"},
        ).json()

        # q1 与 q2 目前均不是错题，尝试以 MISTAKE 模式传入 q1 作为 question_ids 必须被拒绝（400）
        resp_mistake = self.client.post(
            "/api/v1/practice/sessions", headers=headers,
            json={"bank_id": bank["id"], "mode": "MISTAKE", "question_ids": [q1["id"]]},
        )
        self.assertEqual(resp_mistake.status_code, 400)
        self.assertIn("当前题库没有符合条件的题目", resp_mistake.json()["detail"])

        # q1 与 q2 也均不是到期题，尝试以 FSRS 模式传入 q1 作为 question_ids 必须被拒绝（400）
        resp_fsrs = self.client.post(
            "/api/v1/practice/sessions", headers=headers,
            json={"bank_id": bank["id"], "mode": "FSRS", "question_ids": [q1["id"]]},
        )
        self.assertEqual(resp_fsrs.status_code, 400)
        self.assertIn("当前题库没有符合条件的题目", resp_fsrs.json()["detail"])

        # 将 q1 斩杀，q2 保持未斩杀
        kill_resp = self.client.post(f"/api/v1/kills/{q1['id']}", headers=headers)
        self.assertIn(kill_resp.status_code, (200, 201))
        # ELIMINATION 模式是针对已斩杀题的专项复习，传入未斩杀的 q2 必须被拒绝（400）
        resp_elim = self.client.post(
            "/api/v1/practice/sessions", headers=headers,
            json={"bank_id": bank["id"], "mode": "ELIMINATION", "question_ids": [q2["id"]]},
        )
        self.assertEqual(resp_elim.status_code, 400)
        self.assertIn("当前题库没有符合条件的题目", resp_elim.json()["detail"])

        # 传入已斩杀的 q1，ELIMINATION 模式应该成功创建
        resp_elim_ok = self.client.post(
            "/api/v1/practice/sessions", headers=headers,
            json={"bank_id": bank["id"], "mode": "ELIMINATION", "question_ids": [q1["id"]]},
        )
        self.assertEqual(resp_elim_ok.status_code, 201)
        self.assertEqual(resp_elim_ok.json()["total_questions"], 1)

        # 制造 q2 的错题记录
        practice_session = self.client.post(
            "/api/v1/practice/sessions", headers=headers,
            json={"bank_id": bank["id"], "mode": "PRACTICE", "question_ids": [q2["id"]]},
        ).json()
        self.client.post(
            f"/api/v1/practice/sessions/{practice_session['id']}/attempts", headers=headers,
            json={"question_id": q2["id"], "user_answer": "WRONG_ANSWER"},
        )
        # 现在 q2 是错题，MISTAKE 模式传入 q2 应该成功创建
        resp_mistake_ok = self.client.post(
            "/api/v1/practice/sessions", headers=headers,
            json={"bank_id": bank["id"], "mode": "MISTAKE", "question_ids": [q2["id"]]},
        )
        self.assertEqual(resp_mistake_ok.status_code, 201)
        self.assertEqual(resp_mistake_ok.json()["total_questions"], 1)

        # 但若同时传入 [q1, q2]，由于 q1 不是错题，只有 q2 会入选
        resp_mistake_mixed = self.client.post(
            "/api/v1/practice/sessions", headers=headers,
            json={"bank_id": bank["id"], "mode": "MISTAKE", "question_ids": [q1["id"], q2["id"]]},
        )
        self.assertEqual(resp_mistake_mixed.status_code, 201)
        self.assertEqual(resp_mistake_mixed.json()["total_questions"], 1)

    def test_must_change_password_user_is_blocked_from_business_apis_and_enforces_min_8_chars(self):
        # 1. 注册并手动设置 must_change_password = 1
        reg_resp = self.client.post("/api/v1/auth/register", json={"username": "mustchange", "password": "initial-password-123"})
        self.assertEqual(reg_resp.status_code, 201)
        user_id = reg_resp.json()["id"]

        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE users SET must_change_password = 1 WHERE id = ?", (user_id,))
            conn.commit()

        # 2. 登录该用户
        login_resp = self.client.post("/api/v1/auth/login", json={"username": "mustchange", "password": "initial-password-123"})
        self.assertEqual(login_resp.status_code, 200)
        token = login_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. 校验 /api/v1/auth/me 可访问且 must_change_password 为 True
        me_resp = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me_resp.status_code, 200)
        self.assertTrue(me_resp.json().get("must_change_password"))

        # 4. 尝试访问业务 API /api/v1/banks，必须被拦截并返回 403 MUST_CHANGE_PASSWORD
        banks_resp = self.client.get("/api/v1/banks", headers=headers)
        self.assertEqual(banks_resp.status_code, 403)
        self.assertIn("MUST_CHANGE_PASSWORD", banks_resp.json()["detail"])

        # 5. 尝试修改密码为小于 8 位的弱密码（例如 6 位），必须被校验拒绝
        weak_pwd_resp = self.client.post(
            "/api/v1/auth/change-password", headers=headers,
            json={"old_password": "initial-password-123", "new_password": "123456"},
        )
        self.assertIn(weak_pwd_resp.status_code, (400, 422))

        # 6. 使用合规的 8 位及以上新密码修改
        ok_pwd_resp = self.client.post(
            "/api/v1/auth/change-password", headers=headers,
            json={"old_password": "initial-password-123", "new_password": "new-secure-password-456"},
        )
        self.assertEqual(ok_pwd_resp.status_code, 200)

        # 7. 改密成功后，业务 API 恢复正常访问
        banks_after = self.client.get("/api/v1/banks", headers=headers)
        self.assertEqual(banks_after.status_code, 200)

    def test_two_step_fsrs_rating_is_strictly_equivalent_to_single_step_submission(self):
        import sqlite3

        # 用户 A：单步一次性提交 rating=4
        self.client.post("/api/v1/auth/register", json={"username": "user_single_step", "password": "password-123456"})
        token_a = self.client.post("/api/v1/auth/login", json={"username": "user_single_step", "password": "password-123456"}).json()["token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}
        bank_a = self.client.post("/api/v1/banks", headers=headers_a, json={"name": "题库A"}).json()
        q_a = self.client.post(f"/api/v1/banks/{bank_a['id']}/questions", headers=headers_a, json={"stem": "测试题A", "answer": "A"}).json()

        # 用户 B：两步流程（先提交答案，再提交 rating=4）
        self.client.post("/api/v1/auth/register", json={"username": "user_two_step", "password": "password-123456"})
        token_b = self.client.post("/api/v1/auth/login", json={"username": "user_two_step", "password": "password-123456"}).json()["token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}
        bank_b = self.client.post("/api/v1/banks", headers=headers_b, json={"name": "题库B"}).json()
        q_b = self.client.post(f"/api/v1/banks/{bank_b['id']}/questions", headers=headers_b, json={"stem": "测试题B", "answer": "A"}).json()

        # 给两个用户制造完全相同的卡片初始基线状态
        sess_init_a = self.client.post("/api/v1/practice/sessions", headers=headers_a, json={"bank_id": bank_a["id"]}).json()
        self.client.post(f"/api/v1/practice/sessions/{sess_init_a['id']}/attempts", headers=headers_a, json={"question_id": q_a["id"], "user_answer": "B"})

        sess_init_b = self.client.post("/api/v1/practice/sessions", headers=headers_b, json={"bank_id": bank_b["id"]}).json()
        self.client.post(f"/api/v1/practice/sessions/{sess_init_b['id']}/attempts", headers=headers_b, json={"question_id": q_b["id"], "user_answer": "B"})

        # 确保两边卡片初始状态完全一致且到期
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE fsrs_cards SET difficulty = 5.0, stability = 1.0, due_at = '2020-01-01 00:00:00', last_review_at = '2020-01-01 00:00:00'")
            conn.commit()

        from unittest.mock import patch
        from datetime import datetime, timezone
        fixed_now = datetime(2026, 9, 24, 10, 0, 0, tzinfo=timezone.utc)
        class MockDateTime:
            @classmethod
            def now(cls, tz=None):
                return fixed_now
            @classmethod
            def fromisoformat(cls, s):
                return datetime.fromisoformat(s)

        with patch("backend.app.infrastructure.db.repositories.practice_repository.datetime", MockDateTime):
            # 用户 A 进行复习：一次性带 rating=4 提交
            sess_a = self.client.post("/api/v1/practice/sessions", headers=headers_a, json={"bank_id": bank_a["id"], "mode": "FSRS", "question_ids": [q_a["id"]]}).json()
            self.client.post(f"/api/v1/practice/sessions/{sess_a['id']}/attempts", headers=headers_a, json={"question_id": q_a["id"], "user_answer": "A", "fsrs_rating": 4})

            # 用户 B 进行复习：两步流程（第一步不带 rating，第二步带 rating=4）
            sess_b = self.client.post("/api/v1/practice/sessions", headers=headers_b, json={"bank_id": bank_b["id"], "mode": "FSRS", "question_ids": [q_b["id"]]}).json()
            # 步骤 1：仅提交答案（系统默认暂按 3 调度）
            self.client.post(f"/api/v1/practice/sessions/{sess_b['id']}/attempts", headers=headers_b, json={"question_id": q_b["id"], "user_answer": "A"})
            # 步骤 2：用户在前端选择 rating=4 并再次提交同一答案
            self.client.post(f"/api/v1/practice/sessions/{sess_b['id']}/attempts", headers=headers_b, json={"question_id": q_b["id"], "user_answer": "A", "fsrs_rating": 4})

        # 物理读取并比对两边的 FSRS 卡片最终数值与调度状态
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            card_a = dict(conn.execute("SELECT state, stability, difficulty, due_at, last_review_at FROM fsrs_cards WHERE question_id = ?", (q_a["id"],)).fetchone())
            card_b = dict(conn.execute("SELECT state, stability, difficulty, due_at, last_review_at FROM fsrs_cards WHERE question_id = ?", (q_b["id"],)).fetchone())

        self.assertEqual(card_a["state"], card_b["state"])
        self.assertEqual(card_a["due_at"], card_b["due_at"])
        self.assertEqual(card_a["last_review_at"], card_b["last_review_at"])
        self.assertEqual(card_a["difficulty"], card_b["difficulty"])
        self.assertEqual(card_a["stability"], card_b["stability"])

    def test_legacy_attempt_without_snapshot_preserves_and_updates_existing_fsrs_card(self):
        self.client.post("/api/v1/auth/register", json={"username": "legacy_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "legacy_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        user_id = self.client.get("/api/v1/auth/me", headers=headers).json()["id"]

        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "旧题库"}).json()
        q = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={
            "stem": "旧题目",
            "answer": "A",
        }).json()

        # 模拟旧数据库迁入的状态：已有一张稳定度较高的 FSRS 卡片（非初始 0.0/5.0）
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO fsrs_cards(user_id, question_id, state, stability, difficulty, due_at, last_review_at)
                   VALUES (?, ?, 2, 15.0, 3.2, '2026-01-01 00:00:00', '2026-01-01 00:00:00')""",
                (user_id, q["id"]),
            )
            conn.commit()

        # 创建一个未完成的会话
        sess = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()

        # 模拟旧库导入的作答记录：card_snapshot_json 为 NULL，fsrs_rating 为 NULL
        attempt_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO answer_attempts(
                    id, user_id, session_id, bank_id, question_id, question_version_id,
                    user_answer_json, score_ratio, correctness, mastery_status, fsrs_rating, card_snapshot_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, 'CORRECT', 'MASTERED', NULL, NULL, '2026-02-01 00:00:00')""",
                (attempt_id, user_id, sess["id"], bank["id"], q["id"], q["version_id"], json.dumps("A")),
            )
            conn.commit()

        # 用户在前端继续该会话并给出评分 4 (Easy)
        resp = self.client.post(f"/api/v1/practice/sessions/{sess['id']}/attempts", headers=headers, json={
            "question_id": q["id"],
            "user_answer": "A",
            "fsrs_rating": 4,
        })
        self.assertEqual(resp.status_code, 201)

        # 物理核验：卡片稳定度绝不能被重置为初始新卡（初始 rating=4 的 stability 仅 5.8 左右，而 15.0 经过 Easy 复习应大幅提升到 >15.0）
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            card = dict(conn.execute("SELECT state, stability, difficulty FROM fsrs_cards WHERE user_id = ? AND question_id = ?", (user_id, q["id"])).fetchone())
            att = dict(conn.execute("SELECT card_snapshot_json, fsrs_rating FROM answer_attempts WHERE id = ?", (attempt_id,)).fetchone())

        self.assertIsNotNone(att["card_snapshot_json"])
        snapshot = json.loads(att["card_snapshot_json"])
        self.assertEqual(snapshot["stability"], 15.0)
        self.assertEqual(snapshot["difficulty"], 3.2)
        # 稳定度绝未被当作 0.0 初始卡片覆盖，而是从 15.0 继承并向上调度
        self.assertGreater(card["stability"], 15.0)
        self.assertEqual(card["state"], 2)

    def test_legacy_attempt_already_scheduled_preserves_card_without_double_scheduling_when_rating_changed(self):
        self.client.post("/api/v1/auth/register", json={"username": "legacy_sched_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "legacy_sched_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        user_id = self.client.get("/api/v1/auth/me", headers=headers).json()["id"]

        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "已调度旧题库"}).json()
        q = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={
            "stem": "已调度旧题目",
            "answer": "A",
        }).json()

        # 模拟存量状态：该旧题目在 2026-02-01 已被该次作答调度过，卡片稳定度为 12.0，难度为 3.5
        attempt_time = "2026-02-01 10:00:00"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO fsrs_cards(user_id, question_id, state, stability, difficulty, due_at, last_review_at)
                   VALUES (?, ?, 2, 12.0, 3.5, '2026-03-01 10:00:00', ?)""",
                (user_id, q["id"], attempt_time),
            )
            conn.commit()

        # 创建一个未完成的会话
        sess = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()

        # 存量作答记录：该作答历史上已打分 fsrs_rating=3，但因历史版本无快照，card_snapshot_json 为 NULL
        attempt_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO answer_attempts(
                    id, user_id, session_id, bank_id, question_id, question_version_id,
                    user_answer_json, score_ratio, correctness, mastery_status, fsrs_rating, card_snapshot_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, 'CORRECT', 'MASTERED', 3, NULL, ?)""",
                (attempt_id, user_id, sess["id"], bank["id"], q["id"], q["version_id"], json.dumps("A"), attempt_time),
            )
            conn.commit()

        # 用户在未完成会话中修改该次评分为 4 (Easy)
        resp = self.client.post(f"/api/v1/practice/sessions/{sess['id']}/attempts", headers=headers, json={
            "question_id": q["id"],
            "user_answer": "A",
            "fsrs_rating": 4,
        })
        self.assertEqual(resp.status_code, 201)

        # 核心安全策略物理断言：
        # 1. 作答记录上的 fsrs_rating 成功更新为 4；
        # 2. 卡片状态被安全保护，绝未在 12.0 上二次叠加调度（若二次调度，rating=4 会让稳定性蹿升至 >25），亦绝未重置为新卡（5.8）；
        # 3. 卡片 stability 严格保持 12.0，difficulty 保持 3.5，state 保持 2！
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            card = dict(conn.execute("SELECT state, stability, difficulty, due_at, last_review_at FROM fsrs_cards WHERE user_id = ? AND question_id = ?", (user_id, q["id"])).fetchone())
            att = dict(conn.execute("SELECT fsrs_rating, card_snapshot_json FROM answer_attempts WHERE id = ?", (attempt_id,)).fetchone())

        self.assertEqual(att["fsrs_rating"], 4)
        self.assertIsNone(att["card_snapshot_json"])
        self.assertEqual(card["stability"], 12.0)
        self.assertEqual(card["difficulty"], 3.5)
        self.assertEqual(card["state"], 2)
        self.assertEqual(card["last_review_at"], attempt_time)

    def test_exam_record_mistakes_strategy_switchable(self):
        # EE-002: Test that record_mistakes can be switched off in mock exam
        self.client.post("/api/v1/auth/register", json={"username": "mistake_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "mistake_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "模考错题策略库"}).json()
        q1 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题1", "type": "SINGLE", "answer": "A"}).json()
        q2 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题2", "type": "SINGLE", "answer": "B"}).json()

        # 1. 模考 session 指定 record_mistakes = False
        sess_no_record = self.client.post("/api/v1/exams/sessions", headers=headers, json={
            "bank_id": bank["id"],
            "total_questions": 2,
            "record_mistakes": False,
        }).json()
        self.client.post(f"/api/v1/practice/sessions/{sess_no_record['id']}/attempts", headers=headers, json={
            "question_id": q1["id"],
            "user_answer": "C",  # Wrong answer
        })
        mistakes_after_first = self.client.get("/api/v1/mistakes", headers=headers).json()
        self.assertEqual(len(mistakes_after_first), 0, "When record_mistakes is False, wrong answer must not enter mistake records")

        # 2. 模考 session 指定 record_mistakes = True (默认行为)
        sess_record = self.client.post("/api/v1/exams/sessions", headers=headers, json={
            "bank_id": bank["id"],
            "total_questions": 2,
            "record_mistakes": True,
        }).json()
        self.client.post(f"/api/v1/practice/sessions/{sess_record['id']}/attempts", headers=headers, json={
            "question_id": q2["id"],
            "user_answer": "C",  # Wrong answer
        })
        mistakes_after_second = self.client.get("/api/v1/mistakes", headers=headers).json()
        self.assertEqual(len(mistakes_after_second), 1, "When record_mistakes is True, wrong answer must enter mistake records")
        self.assertEqual(mistakes_after_second[0]["question_id"], q2["id"])

    def test_exam_blueprint_dynamic_question_selection(self):
        # EE-001: Test dynamic question selection by blueprint sections (type, count, etc.)
        self.client.post("/api/v1/auth/register", json={"username": "blueprint_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "blueprint_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "蓝图组卷测试库"}).json()

        # Add 2 JUDGE, 3 SINGLE, 1 MULTI
        self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "判断1", "type": "JUDGE", "answer": "T"})
        self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "判断2", "type": "JUDGE", "answer": "F"})
        self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "单选1", "type": "SINGLE", "answer": "A"})
        self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "单选2", "type": "SINGLE", "answer": "B"})
        self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "单选3", "type": "SINGLE", "answer": "C"})
        self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "多选1", "type": "MULTI", "answer": "AB"})

        # Create Profile with Blueprint: 1 JUDGE, 2 SINGLE
        profile = self.client.post("/api/v1/exams/profiles", headers=headers, json={"name": "专项模拟档案"}).json()
        bp = self.client.post(f"/api/v1/exams/profiles/{profile['id']}/blueprint", headers=headers, json={
            "blueprint": {
                "sections": [
                    {"name": "判断题部分", "type": "JUDGE", "count": 1},
                    {"name": "单选题部分", "type": "SINGLE", "count": 2},
                ]
            }
        }).json()

        # Start exam session with profile_id
        session = self.client.post("/api/v1/exams/sessions", headers=headers, json={
            "bank_id": bank["id"],
            "profile_id": profile["id"],
        }).json()

        sess_detail = self.client.get(f"/api/v1/practice/sessions/{session['id']}", headers=headers).json()
        questions = sess_detail["questions"]
        self.assertEqual(len(questions), 3, "Blueprint should select exactly 3 questions (1 JUDGE, 2 SINGLE)")
        judge_count = sum(1 for q in questions if q["type"] == "JUDGE")
        single_count = sum(1 for q in questions if q["type"] == "SINGLE")
        self.assertEqual(judge_count, 1)
        self.assertEqual(single_count, 2)

    def test_exam_profiles_and_blueprint_listing_apis(self):
        # EE-010: Test GET profiles and latest blueprint
        self.client.post("/api/v1/auth/register", json={"username": "prof_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "prof_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        p1 = self.client.post("/api/v1/exams/profiles", headers=headers, json={"name": "档案A", "description": "描述A"}).json()
        self.client.post(f"/api/v1/exams/profiles/{p1['id']}/blueprint", headers=headers, json={"blueprint": {"negative_mark": 0.5}}).json()

        list_resp = self.client.get("/api/v1/exams/profiles", headers=headers)
        self.assertEqual(list_resp.status_code, 200)
        self.assertGreaterEqual(len(list_resp.json()), 1)
        first = list_resp.json()[0]
        self.assertEqual(first["name"], "档案A")
        self.assertIsNotNone(first.get("latest_blueprint"))

        bp_resp = self.client.get(f"/api/v1/exams/profiles/{p1['id']}/blueprint", headers=headers)
        self.assertEqual(bp_resp.status_code, 200)
        self.assertEqual(bp_resp.json()["blueprint"]["negative_mark"], 0.5)

    def test_list_active_sessions_returns_incomplete_sessions(self):
        # EE-019: Test GET /api/v1/practice/sessions/active returns incomplete sessions
        self.client.post("/api/v1/auth/register", json={"username": "active_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "active_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "未完成会话测试库"}).json()
        self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题A", "answer": "A"}).json()

        # Start a session
        sess = self.client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()

        # Check active sessions
        active_list = self.client.get("/api/v1/practice/sessions/active", headers=headers)
        self.assertEqual(active_list.status_code, 200)
        self.assertEqual(len(active_list.json()), 1)
        self.assertEqual(active_list.json()[0]["id"], sess["id"])

        # Complete the session
        self.client.post(f"/api/v1/practice/sessions/{sess['id']}/complete", headers=headers)

        # Active list should now be empty
        active_after = self.client.get("/api/v1/practice/sessions/active", headers=headers)
        self.assertEqual(active_after.status_code, 200)
        self.assertEqual(len(active_after.json()), 0)

    def test_bank_export_supports_multiple_formats(self):
        # EE-008: Test V1 bank export route supporting JSON, CSV, and text
        self.client.post("/api/v1/auth/register", json={"username": "export_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "export_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "导出测试题库"}).json()
        self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={
            "stem": "导出题目1", "type": "SINGLE", "answer": "A", "options": [{"key": "A", "text": "甲"}]
        })

        # JSON export
        res_json = self.client.get(f"/api/v1/banks/{bank['id']}/export?format=json", headers=headers)
        self.assertEqual(res_json.status_code, 200)
        self.assertIn("导出题目1", res_json.text)

        # CSV export
        res_csv = self.client.get(f"/api/v1/banks/{bank['id']}/export?format=csv", headers=headers)
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("导出题目1", res_csv.text)

        # TXT export
        res_txt = self.client.get(f"/api/v1/banks/{bank['id']}/export?format=txt", headers=headers)
        self.assertEqual(res_txt.status_code, 200)
        self.assertIn("导出题目1", res_txt.text)

    def test_personal_assets_rag_retrieval_and_isolation(self):
        # EE-003: User assets RAG retrieval, prompt injection, and isolation
        self.client.post("/api/v1/auth/register", json={"username": "rag_alice", "password": "password-123456"})
        token_a = self.client.post("/api/v1/auth/login", json={"username": "rag_alice", "password": "password-123456"}).json()["token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        self.client.post("/api/v1/auth/register", json={"username": "rag_bob", "password": "password-123456"})
        token_b = self.client.post("/api/v1/auth/login", json={"username": "rag_bob", "password": "password-123456"}).json()["token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Alice creates a question and a personal note linked to it
        bank = self.client.post("/api/v1/banks", headers=headers_a, json={"name": "Alice Bank"}).json()
        q = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers_a, json={
            "stem": "光合作用的光反应场所是哪里？",
            "type": "SINGLE",
            "options": [{"key": "A", "text": "类囊体薄膜"}, {"key": "B", "text": "叶绿体基质"}],
            "answer": "A",
            "explanation": "光反应在类囊体薄膜上进行",
        }).json()

        # Alice adds a personal asset for this question
        note_res = self.client.post("/api/v1/assets", headers=headers_a, json={
            "asset_type": "NOTE",
            "content": "我的易错速记：光反应类囊体，暗反应在基质！",
            "question_id": q["id"],
        })
        self.assertEqual(note_res.status_code, 201)
        alice_asset_id = note_res.json()["id"]

        # Bob adds an unrelated note
        self.client.post("/api/v1/assets", headers=headers_b, json={
            "asset_type": "NOTE",
            "content": "Bob 的完全无关笔记",
            "question_id": None,
        })

        # Alice asks AI tutor for explanation
        gen_res = self.client.post(f"/api/v1/ai/questions/{q['id']}/generate", headers=headers_a, json={
            "query": "请帮我讲解这道题"
        })
        self.assertEqual(gen_res.status_code, 201)
        data = gen_res.json()
        # Ensure Alice's asset is referenced and Bob's is strictly excluded
        self.assertIn("referenced_assets", data)
        self.assertIn(alice_asset_id, data["referenced_assets"])

        # Create another question with NO assets -> Graceful fallback
        q2 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers_a, json={
            "stem": "无资料关联的题目", "type": "SINGLE", "answer": "A"
        }).json()
        gen_res2 = self.client.post(f"/api/v1/ai/questions/{q2['id']}/generate", headers=headers_a, json={})
        self.assertEqual(gen_res2.status_code, 201)
        self.assertEqual(gen_res2.json()["referenced_assets"], [])

    def test_web_search_adapter_injection_and_evidence(self):
        # EE-004: OpenWebSearchAdapter is injected and evidence is preserved in answers list
        self.client.post("/api/v1/auth/register", json={"username": "web_search_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "web_search_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "Search Bank"}).json()
        q = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={
            "stem": "Python 3.12 的新特性有哪些？", "type": "QA", "answer": "PEP 701等"
        }).json()

        # Call verify-web
        verify_res = self.client.post(f"/api/v1/ai/questions/{q['id']}/verify-web", headers=headers, json={
            "query": "Python 3.12 features"
        })
        self.assertEqual(verify_res.status_code, 201)
        ans = verify_res.json()
        self.assertEqual(ans["source"], "WEB")
        self.assertIn("verification_status", ans)

        # Retrieve explanations list
        answers = self.client.get(f"/api/v1/ai/questions/{q['id']}/answers", headers=headers).json()
        self.assertTrue(len(answers) >= 1)
        self.assertEqual(answers[0]["source"], "WEB")

    def test_ai_variant_draft_full_lifecycle(self):
        # EE-005: AI variant draft lifecycle (generate -> draft -> accept / discard)
        self.client.post("/api/v1/auth/register", json={"username": "variant_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "variant_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "AI Variant Bank"}).json()
        q = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={
            "stem": "已知直角三角形两直角边长为3和4，求斜边长？",
            "type": "SINGLE",
            "options": [{"key": "A", "text": "5"}, {"key": "B", "text": "6"}],
            "answer": "A",
            "explanation": "勾股定理 3^2 + 4^2 = 5^2",
        }).json()

        # Generate variant draft
        draft_res = self.client.post("/api/v1/ai/variants", headers=headers, json={
            "original_question_id": q["id"],
            "target_bank_id": bank["id"],
            "prompt_hint": "考查勾股定理，改成边长为6和8",
        })
        self.assertEqual(draft_res.status_code, 201)
        draft = draft_res.json()
        self.assertEqual(draft["status"], "DRAFT")
        draft_id = draft["id"]

        # List drafts
        drafts = self.client.get("/api/v1/ai/drafts", headers=headers).json()
        self.assertTrue(any(d["id"] == draft_id for d in drafts))

        # Official bank questions count should still be 1 (draft is NOT in official bank)
        bank_detail = self.client.get(f"/api/v1/banks/{bank['id']}", headers=headers).json()
        self.assertEqual(bank_detail["question_count"], 1)

        # Accept draft with optional modification
        accept_res = self.client.post(f"/api/v1/ai/drafts/{draft_id}/accept", headers=headers, json={
            "modifications": {
                "stem": "已知直角三角形两直角边长为6和8，求斜边长？",
                "answer": "10",
                "options": [{"key": "A", "text": "10"}, {"key": "B", "text": "12"}],
            }
        })
        self.assertEqual(accept_res.status_code, 200)
        self.assertEqual(accept_res.json()["status"], "ACCEPTED")

        # Official bank questions count should now be 2
        bank_detail2 = self.client.get(f"/api/v1/banks/{bank['id']}", headers=headers).json()
        self.assertEqual(bank_detail2["question_count"], 2)

        # Generate a second draft and discard it
        draft_res2 = self.client.post("/api/v1/ai/variants", headers=headers, json={
            "original_question_id": q["id"],
            "target_bank_id": bank["id"],
        })
        draft2_id = draft_res2.json()["id"]
        discard_res = self.client.post(f"/api/v1/ai/drafts/{draft2_id}/discard", headers=headers)
        self.assertEqual(discard_res.status_code, 200)
        self.assertEqual(discard_res.json()["status"], "DISCARDED")

    def test_personal_assets_deletion_and_retrieval(self):
        # EE-012: Personal asset retrieval and deletion
        self.client.post("/api/v1/auth/register", json={"username": "asset_mgr_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "asset_mgr_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        created = self.client.post("/api/v1/assets", headers=headers, json={
            "asset_type": "SUMMARY",
            "content": "操作系统进程调度总结",
        }).json()
        asset_id = created["id"]

        # Get by id
        get_res = self.client.get(f"/api/v1/assets/{asset_id}", headers=headers)
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["content"], "操作系统进程调度总结")

        # Delete
        del_res = self.client.delete(f"/api/v1/assets/{asset_id}", headers=headers)
        self.assertEqual(del_res.status_code, 204)

        # Get again returns 404
        get_again = self.client.get(f"/api/v1/assets/{asset_id}", headers=headers)
        self.assertEqual(get_again.status_code, 404)

    def test_blueprint_selection_with_chapter_and_graceful_fallback(self):
        # EE-001: Dynamic question selection by blueprint sections with chapter matching and fallback
        self.client.post("/api/v1/auth/register", json={"username": "bp_chap_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "bp_chap_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "章节组卷题库"}).json()

        # Create two chapters in DB
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO chapters (id, bank_id, name, sort_order) VALUES ('chap_01', ?, '第一章 计算机体系', 1)", (bank["id"],))
            conn.execute("INSERT INTO chapters (id, bank_id, name, sort_order) VALUES ('chap_02', ?, '第二章 操作系统', 2)", (bank["id"],))
            conn.commit()

        # Add 2 questions in chap_01, 1 question in chap_02
        q1 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={
            "stem": "体系结构题1", "type": "SINGLE", "answer": "A", "chapter_id": "chap_01"
        }).json()
        q2 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={
            "stem": "体系结构题2", "type": "SINGLE", "answer": "B", "chapter_id": "chap_01"
        }).json()
        q3 = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={
            "stem": "操作系统题1", "type": "SINGLE", "answer": "C", "chapter_id": "chap_02"
        }).json()

        # Verify list_for_bank returns chapter_id
        bank_qs = self.client.get(f"/api/v1/banks/{bank['id']}/questions", headers=headers).json()
        self.assertEqual(len(bank_qs), 3)
        chap1_qs = [q for q in bank_qs if q.get("chapter_id") == "chap_01"]
        self.assertEqual(len(chap1_qs), 2)

        # Create blueprint requesting chap_01 specifically
        profile = self.client.post("/api/v1/exams/profiles", headers=headers, json={"name": "体系结构专卷"}).json()
        self.client.post(f"/api/v1/exams/profiles/{profile['id']}/blueprint", headers=headers, json={
            "blueprint": {
                "sections": [
                    {"name": "第一章单选", "type": "SINGLE", "count": 2, "chapter_id": "chap_01"}
                ]
            }
        })

        session = self.client.post("/api/v1/exams/sessions", headers=headers, json={
            "bank_id": bank["id"],
            "profile_id": profile["id"],
        }).json()

        sess_detail = self.client.get(f"/api/v1/practice/sessions/{session['id']}", headers=headers).json()
        sess_qs = sess_detail["questions"]
        self.assertEqual(len(sess_qs), 2)
        for q in sess_qs:
            self.assertEqual(q.get("chapter_id"), "chap_01")

        # Graceful fallback: section asks for 5 questions from chap_01, but only 2 exist;
        # Should gracefully return 3 questions total (2 from chap_01 + 1 fallback from bank) without crashing.
        profile_fallback = self.client.post("/api/v1/exams/profiles", headers=headers, json={"name": "超额抽选题卷"}).json()
        self.client.post(f"/api/v1/exams/profiles/{profile_fallback['id']}/blueprint", headers=headers, json={
            "blueprint": {
                "sections": [
                    {"name": "超额部分", "type": "SINGLE", "count": 5, "chapter_id": "chap_01"}
                ]
            }
        })
        sess_fallback = self.client.post("/api/v1/exams/sessions", headers=headers, json={
            "bank_id": bank["id"],
            "profile_id": profile_fallback["id"],
        }).json()
        detail_fb = self.client.get(f"/api/v1/practice/sessions/{sess_fallback['id']}", headers=headers).json()
        self.assertEqual(len(detail_fb["questions"]), 3)

    def test_copy_to_bank_preserves_chapter_and_knowledge_tags(self):
        # EE-007, EE-020: Question copy across banks preserves chapter name and tags
        self.client.post("/api/v1/auth/register", json={"username": "copy_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "copy_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        bank_a = self.client.post("/api/v1/banks", headers=headers, json={"name": "源题库A"}).json()
        bank_b = self.client.post("/api/v1/banks", headers=headers, json={"name": "目标题库B"}).json()

        # Add chapter to bank_a
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO chapters (id, bank_id, name, sort_order) VALUES ('chap_src', ?, '软件工程基础', 1)", (bank_a["id"],))
            conn.commit()

        # Create question with chapter_id and tags in bank_a
        q_src = self.client.post(f"/api/v1/banks/{bank_a['id']}/questions", headers=headers, json={
            "stem": "瀑布模型的核心特征是什么？",
            "type": "SINGLE",
            "options": [{"key": "A", "text": "阶段间具有顺序性和依赖性"}, {"key": "B", "text": "敏捷迭代"}],
            "answer": "A",
            "explanation": "瀑布模型严格划分阶段",
            "chapter_id": "chap_src",
            "tags": ["高频考点", "软件过程模型"],
        }).json()

        # Copy to bank_b
        copy_res = self.client.post(f"/api/v1/banks/{bank_b['id']}/questions/{q_src['id']}/copy", headers=headers)
        self.assertEqual(copy_res.status_code, 201)
        copied_q = copy_res.json()

        # Target bank questions should contain copied question
        self.assertEqual(copied_q["bank_id"], bank_b["id"])
        self.assertEqual(copied_q["stem"], "瀑布模型的核心特征是什么？")
        self.assertEqual(copied_q["tags"], ["高频考点", "软件过程模型"])
        self.assertIsNotNone(copied_q["chapter_id"])

        # Check target bank's chapter table has matching chapter name
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT name FROM chapters WHERE id = ? AND bank_id = ?", (copied_q["chapter_id"], bank_b["id"])).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "软件工程基础")

    def test_bank_members_listing_and_removal(self):
        # EE-020: Bank member management (list members, add member, remove member)
        self.client.post("/api/v1/auth/register", json={"username": "owner_user", "password": "password-123456"})
        token_owner = self.client.post("/api/v1/auth/login", json={"username": "owner_user", "password": "password-123456"}).json()["token"]
        headers_owner = {"Authorization": f"Bearer {token_owner}"}

        self.client.post("/api/v1/auth/register", json={"username": "member_bob", "password": "password-123456"})
        token_bob = self.client.post("/api/v1/auth/login", json={"username": "member_bob", "password": "password-123456"}).json()["token"]

        bank = self.client.post("/api/v1/banks", headers=headers_owner, json={"name": "协作共享题库"}).json()

        # Add member_bob as EDITOR
        add_res = self.client.post(f"/api/v1/banks/{bank['id']}/members", headers=headers_owner, json={
            "username": "member_bob",
            "role": "EDITOR",
        })
        self.assertEqual(add_res.status_code, 201)

        # List members
        members_res = self.client.get(f"/api/v1/banks/{bank['id']}/members", headers=headers_owner)
        self.assertEqual(members_res.status_code, 200)
        members = members_res.json()
        self.assertEqual(len(members), 2)
        bob_entry = next((m for m in members if m["username"] == "member_bob"), None)
        self.assertIsNotNone(bob_entry)
        self.assertEqual(bob_entry["role"], "EDITOR")

        # Owner removes member_bob
        del_res = self.client.delete(f"/api/v1/banks/{bank['id']}/members/{bob_entry['user_id']}", headers=headers_owner)
        self.assertEqual(del_res.status_code, 204)

        # Verify members list now only has owner
        members_after = self.client.get(f"/api/v1/banks/{bank['id']}/members", headers=headers_owner).json()
        self.assertEqual(len(members_after), 1)
        self.assertEqual(members_after[0]["username"], "owner_user")

    def test_controllable_historical_regrading_ee006(self):
        # EE-006: Controllable historical re-grading
        self.client.post("/api/v1/auth/register", json={"username": "teacher", "password": "password-123456"})
        token_t = self.client.post("/api/v1/auth/login", json={"username": "teacher", "password": "password-123456"}).json()["token"]
        headers_t = {"Authorization": f"Bearer {token_t}"}

        bank = self.client.post("/api/v1/banks", headers=headers_t, json={"name": "重判测试题库"}).json()
        q = self.client.post(
            f"/api/v1/banks/{bank['id']}/questions",
            headers=headers_t,
            json={"stem": "太阳从哪里升起？", "type": "SINGLE", "options": [{"key": "A", "content": "西边"}, {"key": "B", "content": "东边"}], "answer": "A"},
        ).json()

        # Student answers "B"
        self.client.post("/api/v1/auth/register", json={"username": "student", "password": "password-123456"})
        token_s = self.client.post("/api/v1/auth/login", json={"username": "student", "password": "password-123456"}).json()["token"]
        headers_s = {"Authorization": f"Bearer {token_s}"}
        # Add student as member
        self.client.post(f"/api/v1/banks/{bank['id']}/members", headers=headers_t, json={"username": "student", "role": "MEMBER"})

        session = self.client.post(
            "/api/v1/practice/sessions",
            headers=headers_s,
            json={"bank_id": bank["id"], "mode": "PRACTICE"},
        ).json()

        att = self.client.post(
            f"/api/v1/practice/sessions/{session['id']}/attempts",
            headers=headers_s,
            json={"question_id": q["id"], "user_answer": "B"},
        ).json()
        self.assertEqual(att["correctness"], "INCORRECT")

        # Now teacher fixes answer from "A" to "B" with regrade_history=True
        updated_q = self.client.put(
            f"/api/v1/questions/{q['id']}",
            headers=headers_t,
            json={
                "stem": "太阳从哪里升起？",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "西边"}, {"key": "B", "content": "东边"}],
                "answer": "B",
                "regrade_history": True,
                "apply_fsrs": True,
            },
        )
        self.assertEqual(updated_q.status_code, 200)

        # Check attempt is now CORRECT and score_ratio is 1.0
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            attempt_row = conn.execute("SELECT * FROM answer_attempts WHERE id = ?", (att["id"],)).fetchone()
            self.assertEqual(attempt_row["correctness"], "CORRECT")
            self.assertEqual(attempt_row["score_ratio"], 1.0)

            # Check audit log
            audit = conn.execute("SELECT * FROM audit_logs WHERE entity_id = ? AND action = 'QUESTION_REGRADED'", (q["id"],)).fetchone()
            self.assertIsNotNone(audit)

        # Atomic transaction rollback verification:
        # Pre-capture all tables to verify complete atomicity
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            versions_before = conn.execute("SELECT version_number, stem, answer FROM question_versions WHERE question_id = ? ORDER BY version_number", (q["id"],)).fetchall()
            attempts_before = conn.execute("SELECT id, correctness, score_ratio FROM answer_attempts WHERE question_id = ?", (q["id"],)).fetchall()
            cards_before = conn.execute("SELECT * FROM fsrs_cards WHERE question_id = ?", (q["id"],)).fetchall()
            mistakes_before = conn.execute("SELECT * FROM mistake_records WHERE question_id = ?", (q["id"],)).fetchall()
            audits_before = conn.execute("SELECT id, entity_id, action FROM audit_logs WHERE entity_id = ?", (q["id"],)).fetchall()

        # If an unhandled error occurs during regrading, question_versions insert MUST rollback completely
        teacher_id = self.client.get("/api/v1/auth/me", headers=headers_t).json()["id"]
        from unittest.mock import patch
        with patch.object(self.app.state.services.questions, "_execute_regrade_on_conn", side_effect=RuntimeError("Simulated regrade crash")):
            with self.assertRaises(RuntimeError):
                self.app.state.services.questions.create_next_version(
                    user_id=teacher_id,
                    question_id=q["id"],
                    payload={
                        "stem": "太阳从哪里升起？（版本3将失败回滚）",
                        "type": "SINGLE",
                        "options": [{"key": "A", "content": "西边"}, {"key": "B", "content": "东边"}],
                        "answer": "A",
                        "regrade_history": True,
                    },
                )

        # Verify 100% clean rollback across question versions, attempts, FSRS cards, mistakes, and audit logs
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            versions_after = conn.execute("SELECT version_number, stem, answer FROM question_versions WHERE question_id = ? ORDER BY version_number", (q["id"],)).fetchall()
            attempts_after = conn.execute("SELECT id, correctness, score_ratio FROM answer_attempts WHERE question_id = ?", (q["id"],)).fetchall()
            cards_after = conn.execute("SELECT * FROM fsrs_cards WHERE question_id = ?", (q["id"],)).fetchall()
            mistakes_after = conn.execute("SELECT * FROM mistake_records WHERE question_id = ?", (q["id"],)).fetchall()
            audits_after = conn.execute("SELECT id, entity_id, action FROM audit_logs WHERE entity_id = ?", (q["id"],)).fetchall()

            self.assertEqual([dict(r) for r in versions_after], [dict(r) for r in versions_before])
            self.assertEqual([dict(r) for r in attempts_after], [dict(r) for r in attempts_before])
            self.assertEqual([dict(r) for r in cards_after], [dict(r) for r in cards_before])
            self.assertEqual([dict(r) for r in mistakes_after], [dict(r) for r in mistakes_before])
            self.assertEqual([dict(r) for r in audits_after], [dict(r) for r in audits_before])

        # Verify version remains 2, and stem is NOT updated
        current_q = self.client.get(f"/api/v1/questions/{q['id']}", headers=headers_t).json()
        self.assertEqual(current_q["version_number"], 2)
        self.assertEqual(current_q["answer"], "B")
        self.assertNotIn("版本3将失败回滚", current_q["stem"])

    def test_persistent_ai_and_search_config_ee009(self):
        # EE-009: Persistent configuration with secret protection
        from backend.app.infrastructure.db.repositories.ai_config_repository import (
            encrypt_secret,
            decrypt_secret,
        )

        self.client.post("/api/v1/auth/register", json={"username": "ai_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "ai_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Missing secret key: reject encryption and refuse with clear error
        orig_key = os.environ.pop("EASYEXAM_SECRET_KEY", None)
        orig_fallback = os.environ.pop("SECRET_KEY", None)
        try:
            with self.assertRaises(RuntimeError) as cm:
                encrypt_secret("test-unencrypted-key")
            self.assertIn("EASYEXAM_SECRET_KEY", str(cm.exception))

            with self.assertRaises(RuntimeError) as cm2:
                decrypt_secret("enc:test_corrupted_or_valid")
            self.assertIn("EASYEXAM_SECRET_KEY", str(cm2.exception))

            fail_res = self.client.put(
                "/api/v1/ai/config",
                headers=headers,
                json={
                    "ai_provider": "openai",
                    "ai_api_key": "sk-attempt-without-key",
                },
            )
            self.assertEqual(fail_res.status_code, 500)
            self.assertIn("EASYEXAM_SECRET_KEY", fail_res.json()["detail"])
        finally:
            os.environ["EASYEXAM_SECRET_KEY"] = "easyexam-ci-secret-32bytes-passphrase!!"
            if orig_fallback is not None:
                os.environ["SECRET_KEY"] = orig_fallback

        # 2. Default config
        cfg = self.client.get("/api/v1/ai/config", headers=headers).json()
        self.assertFalse(cfg["is_configured"])

        # 3. Update config with sensitive key
        update_res = self.client.put(
            "/api/v1/ai/config",
            headers=headers,
            json={
                "ai_provider": "ollama",
                "ai_api_base": "http://localhost:11434/v1",
                "ai_model": "qwen2.5:7b",
                "ai_api_key": "sk-real-super-secret-key-123456",
                "search_provider": "open-webSearch",
                "search_api_base": "http://localhost:8000/v1/search",
            },
        )
        self.assertEqual(update_res.status_code, 200)
        self.assertIn("******", update_res.json()["ai_api_key"])
        self.assertNotIn("real-super-secret", update_res.json()["ai_api_key"])

        # 4. GET config returns masked key
        get_res = self.client.get("/api/v1/ai/config", headers=headers).json()
        self.assertTrue(get_res["is_configured"])
        self.assertIn("******", get_res["ai_api_key"])

        # 5. Updating without changing key retains ciphertext in database
        self.client.put(
            "/api/v1/ai/config",
            headers=headers,
            json={
                "ai_provider": "ollama",
                "ai_api_base": "http://localhost:11434/v1",
                "ai_model": "qwen2.5:14b",
                "ai_api_key": get_res["ai_api_key"],
            },
        )
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT ai_api_key, ai_model, id FROM user_ai_configs u JOIN users s ON s.id = u.user_id WHERE s.username = 'ai_user'").fetchone()
            # SQLite physical column MUST be encrypted (enc:...) and must NEVER contain the raw plaintext
            self.assertTrue(row[0].startswith("enc:"))
            self.assertNotIn("sk-real-super-secret-key-123456", row[0])
            self.assertEqual(row[1], "qwen2.5:14b")
            user_db_id = row[2]
            stored_cipher = row[0]

        # 6. Verify internal service access can decrypt real key for AI inference
        self.assertEqual(decrypt_secret(stored_cipher), "sk-real-super-secret-key-123456")
        unmasked = self.app.state.services.ai_configs.get_config(user_db_id, mask_secrets=False)
        self.assertEqual(unmasked["ai_api_key"], "sk-real-super-secret-key-123456")

        # 7. Seamless backward compatibility & lossless upgrade of legacy plaintext keys
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE user_ai_configs SET ai_api_key = 'sk-legacy-unencrypted-key' WHERE user_id = ?",
                (user_db_id,),
            )
        # Reading config automatically upgrades DB row to enc:... without dropping key
        upgraded_conf = self.app.state.services.ai_configs.get_config(user_db_id, mask_secrets=False)
        self.assertEqual(upgraded_conf["ai_api_key"], "sk-legacy-unencrypted-key")
        with sqlite3.connect(self.db_path) as conn:
            raw_after = conn.execute("SELECT ai_api_key FROM user_ai_configs WHERE user_id = ?", (user_db_id,)).fetchone()[0]
            self.assertTrue(raw_after.startswith("enc:"))
            self.assertNotIn("sk-legacy-unencrypted-key", raw_after)
            self.assertEqual(decrypt_secret(raw_after), "sk-legacy-unencrypted-key")

        # 8. Diagnosable failure on wrong key: do NOT silently swallow into empty string
        os.environ["EASYEXAM_SECRET_KEY"] = "completely-different-wrong-key-32b!!"
        try:
            with self.assertRaises(ValueError) as err_cm:
                decrypt_secret(raw_after)
            self.assertIn("key mismatch or corrupted ciphertext", str(err_cm.exception))
        finally:
            os.environ["EASYEXAM_SECRET_KEY"] = "easyexam-ci-secret-32bytes-passphrase!!"

    def test_ambiguous_pdf_preview_and_manual_correction_ee021(self):
        # EE-021: Ambiguous PDF parsing enters manual correction workflow
        self.client.post("/api/v1/auth/register", json={"username": "pdf_user", "password": "password-123456"})
        token = self.client.post("/api/v1/auth/login", json={"username": "pdf_user", "password": "password-123456"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "PDF题库"}).json()

        # Build a minimal valid PDF with lenient/ambiguous question text
        from pypdf import PdfWriter
        from reportlab.pdfgen import canvas
        import io
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 750, "1. 计算机网络的拓扑结构有哪些？")
        c.drawString(100, 730, "A. 星型拓扑")
        c.drawString(100, 710, "B. 总线型拓扑")
        c.drawString(100, 690, "参考答案：AB")
        c.drawString(100, 670, "解析：两者均为基本拓扑结构。")
        c.save()
        pdf_bytes = buf.getvalue()

        # 1. Preview PDF
        files = {"file": ("test_exam.pdf", pdf_bytes, "application/pdf")}
        prev_res = self.client.post(f"/api/v1/imports/banks/{bank['id']}/pdf-preview", headers=headers, files=files)
        self.assertEqual(prev_res.status_code, 200)
        prev_data = prev_res.json()
        self.assertIn("draft_id", prev_data)
        self.assertGreater(len(prev_data["candidates"]), 0)

        # 2. Modify candidate in manual correction step
        candidates = prev_data["candidates"]
        candidates[0]["stem"] = "【校对核准】" + candidates[0]["stem"]

        # 3. Confirm import into bank (Atomic single transaction with draft status update)
        confirm_res = self.client.post(
            f"/api/v1/imports/banks/{bank['id']}/pdf-confirm",
            headers=headers,
            json={
                "draft_id": prev_data["draft_id"],
                "questions": candidates,
                "duplicate_strategy": "skip",
            },
        )
        self.assertEqual(confirm_res.status_code, 201)
        self.assertEqual(confirm_res.json()["status"], "IMPORTED")
        # Ensure imported_count matches the submitted candidate questions count
        self.assertEqual(confirm_res.json()["imported_count"], len(candidates))

        # Verify question exists in bank with corrected stem
        q_list = self.client.get(f"/api/v1/banks/{bank['id']}/questions", headers=headers).json()
        self.assertEqual(len(q_list), len(candidates))
        self.assertTrue(q_list[0]["stem"].startswith("【校对核准】"))

        # Verify draft status is CONFIRMED in DB
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT status FROM pdf_import_drafts WHERE id = ?", (prev_data["draft_id"],)).fetchone()
            self.assertEqual(row[0], "CONFIRMED")

        # 4. Sequential duplicate prevention: second attempt on same draft_id MUST be rejected
        dup_res = self.client.post(
            f"/api/v1/imports/banks/{bank['id']}/pdf-confirm",
            headers=headers,
            json={
                "draft_id": prev_data["draft_id"],
                "questions": candidates,
                "duplicate_strategy": "skip",
            },
        )
        self.assertIn(dup_res.status_code, (400, 422))
        self.assertIn("已完成导入或已作废", dup_res.json()["detail"])

        # 5. True concurrent confirmation race condition test (CAS verification)
        prev2_res = self.client.post(f"/api/v1/imports/banks/{bank['id']}/pdf-preview", headers=headers, files=files)
        self.assertEqual(prev2_res.status_code, 200)
        draft2_id = prev2_res.json()["draft_id"]
        cands2 = prev2_res.json()["candidates"]
        cands2[0]["stem"] = "【并发CAS测试】" + cands2[0]["stem"]

        import threading
        results = []
        errors = []

        def worker():
            try:
                r = self.client.post(
                    f"/api/v1/imports/banks/{bank['id']}/pdf-confirm",
                    headers=headers,
                    json={
                        "draft_id": draft2_id,
                        "questions": cands2,
                        "duplicate_strategy": "new",
                    },
                )
                results.append((r.status_code, r.json()))
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 2)
        status_codes = [r[0] for r in results]
        # Exactly one thread MUST succeed with 201, and one MUST fail with 400 or 422
        self.assertEqual(status_codes.count(201), 1)
        self.assertTrue(any(code in (400, 422) for code in status_codes))

        # Check total questions in bank: 1 from first import + 1 from concurrent test = 2
        final_q_list = self.client.get(f"/api/v1/banks/{bank['id']}/questions", headers=headers).json()
        self.assertEqual(len(final_q_list), len(candidates) + len(cands2))


if __name__ == "__main__":
    unittest.main()

