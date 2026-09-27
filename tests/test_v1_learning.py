import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


class TestV1Learning(unittest.TestCase):
    def test_user_flagged_weak_question_enters_recommendations_and_due_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "标记薄弱"}).json()
            question = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "薄弱题", "answer": "A"}).json()
            marked = client.post(f"/api/v1/learning/weak/{question['id']}", headers=headers)
            self.assertEqual(marked.status_code, 201)
            recommendations = client.get(f"/api/v1/learning/recommendations?bank_id={bank['id']}", headers=headers).json()
            self.assertEqual(recommendations[0]["reason"], "标记薄弱")
            due = client.get(f"/api/v1/mistakes/due?bank_id={bank['id']}", headers=headers).json()
            self.assertEqual(due[0]["question_id"], question["id"])

            # EE-016: include_weak=false MUST exclude manually flagged weak question
            filtered = client.get(f"/api/v1/learning/recommendations?bank_id={bank['id']}&include_weak=false", headers=headers).json()
            self.assertEqual(len(filtered), 0)

    def test_plan_respects_time_budget_and_includes_explained_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "计划题库"}).json()
            questions = [
                client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": f"题 {index}", "answer": "A"}).json()
                for index in range(3)
            ]
            client.post(f"/api/v1/learning/weak/{questions[0]['id']}", headers=headers)
            response = client.get(f"/api/v1/learning/plan?bank_id={bank['id']}&minutes_per_day=4&days=1", headers=headers)
            self.assertEqual(response.status_code, 200)
            plan = response.json()
            self.assertEqual(plan["planned_minutes"], 4)
            self.assertEqual(plan["days"][0]["day_number"], 1)
            self.assertEqual(len(plan["days"][0]["items"]), 2)
            self.assertEqual(plan["days"][0]["items"][0]["reason"], "标记薄弱")
    def test_fsrs_review_records_rating_and_rejects_inconsistent_rating(self):
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "db.sqlite"
            client = TestClient(create_app(str(db_path)))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "FSRS 评级"}).json()
            question = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题", "answer": "A"}).json()
            session = client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
            client.post(f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers, json={"question_id": question["id"], "user_answer": "B"})
            review = client.post(
                f"/api/v1/mistakes/{question['id']}/review", headers=headers,
                json={"user_answer": "A", "rating": 4},
            )
            self.assertEqual(review.status_code, 201)
            self.assertEqual(review.json()["fsrs_rating"], 4)
            bad = client.post(
                f"/api/v1/mistakes/{question['id']}/review", headers=headers,
                json={"user_answer": "B", "rating": 4},
            )
            self.assertEqual(bad.status_code, 422)
            conn = sqlite3.connect(db_path)
            try:
                rating = conn.execute("SELECT fsrs_rating FROM answer_attempts WHERE session_id = ? ORDER BY created_at DESC LIMIT 1", (review.json()["session_id"],)).fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(rating, 4)

    def test_first_correct_answer_does_not_create_fsrs_card(self):
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "db.sqlite"
            client = TestClient(create_app(str(db_path)))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "FSRS 新题"}).json()
            question = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题", "answer": "A"}).json()
            session = client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
            client.post(f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers, json={"question_id": question["id"], "user_answer": "A"})
            conn = sqlite3.connect(db_path)
            try:
                cards = conn.execute("SELECT COUNT(*) FROM fsrs_cards").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(cards, 0)

    def test_learning_trends_report_coverage_and_recent_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "趋势题库"}).json()
            first = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "一", "answer": "A"}).json()
            client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "二", "answer": "A"})
            session = client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
            client.post(
                f"/api/v1/practice/sessions/{session['id']}/attempts",
                headers=headers,
                json={"question_id": first["id"], "user_answer": "A"},
            )
            response = client.get(f"/api/v1/learning/trends?bank_id={bank['id']}", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["total_questions"], 2)
            self.assertEqual(response.json()["attempted_questions"], 1)
            self.assertEqual(response.json()["coverage_percent"], 50.0)
            self.assertEqual(response.json()["recent"]["correct_rate"], 100.0)

    def test_learning_trends_includes_weak_points_review_completion_and_time_trends(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "trend_user", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "trend_user", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "全维趋势题库"}).json()
            q1 = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "法律题", "answer": "A", "tags": ["民法"]}).json()
            q2 = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "行测题", "answer": "B", "tags": ["数量关系"]}).json()

            session = client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
            client.post(f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers, json={"question_id": q1["id"], "user_answer": "C"})
            client.post(f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers, json={"question_id": q2["id"], "user_answer": "B"})

            trends = client.get(f"/api/v1/learning/trends?bank_id={bank['id']}", headers=headers).json()
            self.assertIn("weak_points", trends)
            self.assertTrue(any(wp.get("name") == "民法" for wp in trends["weak_points"]))
            self.assertIn("review_completion_rate", trends)
            self.assertIn("avg_time_per_question", trends["recent"])
            self.assertIn("avg_time_per_question", trends["baseline"])

    def test_recommendation_includes_unseen_questions_and_supports_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "新题推荐"}).json()
            question = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "新题", "answer": "A"}).json()
            response = client.get(f"/api/v1/learning/recommendations?bank_id={bank['id']}&limit=1", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()), 1)
            self.assertEqual(response.json()[0]["question_id"], question["id"])
            self.assertEqual(response.json()[0]["reason"], "新题覆盖")
            filtered = client.get(
                f"/api/v1/learning/recommendations?bank_id={bank['id']}&include_new=false",
                headers=headers,
            )
            self.assertEqual(filtered.status_code, 200)
            self.assertEqual(filtered.json(), [])
    def test_first_correct_answer_is_not_reported_as_a_mistake(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "正确题库"}).json()
            question = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题", "answer": "A"}).json()
            session = client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
            client.post(
                f"/api/v1/practice/sessions/{session['id']}/attempts",
                headers=headers,
                json={"question_id": question["id"], "user_answer": "A"},
            )
            self.assertEqual(client.get("/api/v1/mistakes", headers=headers).json(), [])

    def test_wrong_attempt_has_a_separate_private_mistake_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "db.sqlite"
            client = TestClient(create_app(str(db_path)))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "错题结构"}).json()
            question = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题", "answer": "A"}).json()
            session = client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
            attempt = client.post(
                f"/api/v1/practice/sessions/{session['id']}/attempts",
                headers=headers,
                json={"question_id": question["id"], "user_answer": "B"},
            )
            self.assertEqual(attempt.status_code, 201)

            import sqlite3
            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "SELECT user_id, question_id, mistake_count FROM mistake_records"
                ).fetchone()
            finally:
                conn.close()
            self.assertIsNotNone(row)
            self.assertEqual(row[1], question["id"])
            self.assertEqual(row[2], 1)

    def test_recommendation_returns_reasoned_actions_from_private_learning_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "alice", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "推荐题库"}).json()
            question = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题", "answer": "A", "tags": ["网络"]}).json()
            session = client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
            client.post(f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers, json={"question_id": question["id"], "user_answer": "B"})
            response = client.get(f"/api/v1/learning/recommendations?bank_id={bank['id']}", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()[0]["question_id"], question["id"])
            self.assertIn("错题", response.json()[0]["reason"])

    def test_recommendation_supports_difficulty_filtering_with_unclassified_policy(self):
        """SPEC §8 & Confirmed Decision:
        - When a specific difficulty filter is active, unclassified questions (difficulty 0/unspecified) MUST be excluded.
        - When no specific difficulty filter is active, unclassified questions CAN participate.
        - Never infer difficulty from user attempts.
        """
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "diff_user", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "diff_user", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "难度题库"}).json()

            # q_easy: explicit difficulty 1
            q_easy = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "简单题", "answer": "A", "difficulty": 1}).json()
            # q_med: explicit difficulty 3
            q_med = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "中等题", "answer": "B", "difficulty": 3}).json()
            # q_unrated: no difficulty specified (unclassified)
            q_unrated = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "未分级题", "answer": "C"}).json()

            # 1. Query with specific difficulty=3: unrated must be EXCLUDED, easy excluded, med included
            res_diff3 = client.get(f"/api/v1/learning/recommendations?bank_id={bank['id']}&difficulty=3", headers=headers)
            self.assertEqual(res_diff3.status_code, 200)
            q_ids_diff3 = [item["question_id"] for item in res_diff3.json()]
            self.assertIn(q_med["id"], q_ids_diff3)
            self.assertNotIn(q_easy["id"], q_ids_diff3)
            self.assertNotIn(q_unrated["id"], q_ids_diff3)  # unclassified MUST be excluded

            # 2. Query with specific difficulty=1: only easy included
            res_diff1 = client.get(f"/api/v1/learning/recommendations?bank_id={bank['id']}&difficulty=1", headers=headers)
            self.assertEqual(res_diff1.status_code, 200)
            q_ids_diff1 = [item["question_id"] for item in res_diff1.json()]
            self.assertIn(q_easy["id"], q_ids_diff1)
            self.assertNotIn(q_med["id"], q_ids_diff1)
            self.assertNotIn(q_unrated["id"], q_ids_diff1)

            # 3. Query without difficulty filter: unclassified question CAN participate
            res_all = client.get(f"/api/v1/learning/recommendations?bank_id={bank['id']}", headers=headers)
            self.assertEqual(res_all.status_code, 200)
            q_ids_all = [item["question_id"] for item in res_all.json()]
            self.assertIn(q_unrated["id"], q_ids_all)
            self.assertIn(q_easy["id"], q_ids_all)
            self.assertIn(q_med["id"], q_ids_all)

    def test_recommendation_supports_chapter_and_new_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "chap_user", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "chap_user", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "章节比例题库"}).json()

            q_law1 = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "法律题1", "answer": "A", "tags": ["法律", "民法"]}).json()
            q_law2 = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "法律题2", "answer": "B", "tags": ["法律", "刑法"]}).json()
            q_math = client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "数学题", "answer": "C", "tags": ["数量关系"]}).json()

            # Make law1 a mistake (review item)
            session = client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"]}).json()
            client.post(f"/api/v1/practice/sessions/{session['id']}/attempts", headers=headers, json={"question_id": q_law1["id"], "user_answer": "X"})

            # Chapter filter
            res_chap = client.get(f"/api/v1/learning/recommendations?bank_id={bank['id']}&chapter=法律", headers=headers)
            self.assertEqual(res_chap.status_code, 200)
            q_ids_chap = [item["question_id"] for item in res_chap.json()]
            self.assertIn(q_law1["id"], q_ids_chap)
            self.assertIn(q_law2["id"], q_ids_chap)
            self.assertNotIn(q_math["id"], q_ids_chap)

            # Ratio filter: target 50% new
            res_ratio = client.get(f"/api/v1/learning/recommendations?bank_id={bank['id']}&limit=2&new_ratio=0.5", headers=headers)
            self.assertEqual(res_ratio.status_code, 200)
            items = res_ratio.json()
            self.assertEqual(len(items), 2)
            has_new = any(item["reason"] == "新题覆盖" for item in items)
            has_review = any("错题" in item["reason"] for item in items)
            self.assertTrue(has_new)
            self.assertTrue(has_review)

    def test_plan_contract_contains_estimated_minutes_for_frontend(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "plan_user", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "plan_user", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "契约题库"}).json()
            client.post(f"/api/v1/banks/{bank['id']}/questions", headers=headers, json={"stem": "题1", "answer": "A"}).json()

            res = client.get(f"/api/v1/learning/plan?bank_id={bank['id']}&minutes_per_day=30&days=3", headers=headers)
            self.assertEqual(res.status_code, 200)
            days = res.json()["days"]
            self.assertTrue(len(days) >= 1)
            for d in days:
                self.assertIn("estimated_minutes", d)
                self.assertIsInstance(d["estimated_minutes"], int)


if __name__ == "__main__":
    unittest.main()
