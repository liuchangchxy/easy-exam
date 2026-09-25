import json
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


class TestV1Architecture(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = str(Path(self.temp_dir.name) / "easyexam-v1.db")
        self.client = TestClient(create_app(self.db_path))

    def tearDown(self):
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        self.client.post("/api/v1/auth/register", json={"username": "bob", "password": "REDACTED_TEST_PASSWORD"})
        alice_token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
        bob_token = self.client.post("/api/v1/auth/login", json={"username": "bob", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
        self.client.post("/api/v1/banks", headers={"Authorization": f"Bearer {alice_token}"}, json={"name": "Alice 私有题库"})
        bob_banks = self.client.get("/api/v1/banks", headers={"Authorization": f"Bearer {bob_token}"})
        self.assertEqual(bob_banks.status_code, 200)
        self.assertEqual(bob_banks.json(), [])

    def test_bank_admin_can_share_bank_with_member(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        self.client.post("/api/v1/auth/register", json={"username": "bob", "password": "REDACTED_TEST_PASSWORD"})
        alice = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
        bob = self.client.post("/api/v1/auth/login", json={"username": "bob", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
        bank = self.client.post("/api/v1/banks", headers={"Authorization": f"Bearer {alice}"}, json={"name": "共享题库"}).json()
        member = self.client.post(f"/api/v1/banks/{bank['id']}/members", headers={"Authorization": f"Bearer {alice}"}, json={"username": "bob", "role": "MEMBER"})
        self.assertEqual(member.status_code, 201)
        self.assertEqual(len(self.client.get("/api/v1/banks", headers={"Authorization": f"Bearer {bob}"}).json()), 1)

    def test_wrong_attempt_enters_private_mistake_list(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "bob-scoped", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "bob-scoped", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "carol-kill", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "carol-kill", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "dave-fsrs", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "dave-fsrs", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "frank-rating", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "frank-rating", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "eve-idempotent", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "eve-idempotent", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "frank-pwd", "password": "old-REDACTED_TEST_PASSWORD"})
        login_res = self.client.post("/api/v1/auth/login", json={"username": "frank-pwd", "password": "old-REDACTED_TEST_PASSWORD"}).json()
        token = login_res["token"]
        self.assertFalse(login_res["user"]["must_change_password"])

        headers = {"Authorization": f"Bearer {token}"}
        # Change password with wrong old password fails
        bad_change = self.client.post("/api/v1/auth/change-password", headers=headers, json={"old_password": "wrong", "new_password": "new-REDACTED_TEST_PASSWORD"})
        self.assertEqual(bad_change.status_code, 400)

        # Change password with correct old password succeeds
        good_change = self.client.post("/api/v1/auth/change-password", headers=headers, json={"old_password": "old-REDACTED_TEST_PASSWORD", "new_password": "new-REDACTED_TEST_PASSWORD"})
        self.assertEqual(good_change.status_code, 200)

        # Login with old password fails
        old_login = self.client.post("/api/v1/auth/login", json={"username": "frank-pwd", "password": "old-REDACTED_TEST_PASSWORD"})
        self.assertEqual(old_login.status_code, 401)

        # Login with new password succeeds
        new_login = self.client.post("/api/v1/auth/login", json={"username": "frank-pwd", "password": "new-REDACTED_TEST_PASSWORD"})
        self.assertEqual(new_login.status_code, 200)

    def test_exam_profile_blueprint_and_exam_session_are_versioned(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "exam_student", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "exam_student", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "sync_user", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "sync_user", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "分类题库"}).json()
        chapter = self.client.post(f"/api/v1/banks/{bank['id']}/chapters", headers=headers, json={"name": "第一章"})
        tag = self.client.post(f"/api/v1/banks/{bank['id']}/tags", headers=headers, json={"name": "网络"})
        self.assertEqual(chapter.status_code, 201)
        self.assertEqual(tag.status_code, 201)
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank['id']}/chapters", headers=headers).json()[0]["name"], "第一章")
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank['id']}/tags", headers=headers).json()[0]["name"], "网络")

    def test_personal_assets_are_private_and_queryable(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = self.client.post("/api/v1/assets", headers=headers, json={"asset_type": "NOTE", "content": "记住这个公式"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.get("/api/v1/assets", headers=headers).json()[0]["content"], "记住这个公式")

    def test_question_bank_and_question_version_are_created_for_current_user(self):
        self.client.post(
            "/api/v1/auth/register",
            json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"},
        )
        login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"},
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
            json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"},
        )
        login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"},
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        login = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=headers, json={"name": "AI离线题库"}).json()
        question = self.client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题", "answer": "A"}).json()
        generated = self.client.post(f"/api/v1/ai/questions/{question['id']}/generate", headers=headers, json={"query": "解释一下"})
        self.assertEqual(generated.status_code, 201)
        self.assertEqual(generated.json()["source"], "AI")
        self.assertTrue(generated.json()["content"])

    def test_web_verification_saves_a_separate_explanation_and_evidence_state(self):
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "alice", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "user_single_step", "password": "REDACTED_TEST_PASSWORD"})
        token_a = self.client.post("/api/v1/auth/login", json={"username": "user_single_step", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}
        bank_a = self.client.post("/api/v1/banks", headers=headers_a, json={"name": "题库A"}).json()
        q_a = self.client.post(f"/api/v1/banks/{bank_a['id']}/questions", headers=headers_a, json={"stem": "测试题A", "answer": "A"}).json()

        # 用户 B：两步流程（先提交答案，再提交 rating=4）
        self.client.post("/api/v1/auth/register", json={"username": "user_two_step", "password": "REDACTED_TEST_PASSWORD"})
        token_b = self.client.post("/api/v1/auth/login", json={"username": "user_two_step", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "legacy_user", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "legacy_user", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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
        self.client.post("/api/v1/auth/register", json={"username": "legacy_sched_user", "password": "REDACTED_TEST_PASSWORD"})
        token = self.client.post("/api/v1/auth/login", json={"username": "legacy_sched_user", "password": "REDACTED_TEST_PASSWORD"}).json()["token"]
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


if __name__ == "__main__":
    unittest.main()



