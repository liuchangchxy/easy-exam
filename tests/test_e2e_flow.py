"""End-to-End (E2E) integration test suite for FnExam FastAPI application.

Verifies the entire lifecycle against a real physical SQLite database:
1. System health check
2. Bank creation, retrieval, and question listing
3. Importing questions from text/markdown into bank
4. Starting a practice session & answering (triggering instant scoring and mistake recording)
5. Draft sync with localStorage client data and flag toggling
6. Mistake elimination practice (2 consecutive correct answers -> is_cleared = True)
7. Completing session and verifying final score report
8. FSRS due review querying
9. Contextual AI tutor SSE streaming chat endpoint (offline fallback & streaming)
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.services.ai_service import OFFLINE_FALLBACK_MESSAGE


class TestE2EFlow(unittest.TestCase):
    """Full lifecycle E2E physical integration tests."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fnexam_e2e_")
        self.db_path = os.path.join(self.temp_dir, "test_physical.db")
        self.app = create_app(db_path=self.db_path)
        self.client = TestClient(self.app)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_health_check(self):
        """GET /api/health should return ok status and app name."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertIn(data.get("app"), ["easy-exam", "fn-exam"])

    def test_02_bank_and_question_crud(self):
        """Test bank creation, listing, detail, and question creation."""
        # Create bank
        create_res = self.client.post(
            "/api/banks",
            json={
                "name": "软件设计师真题",
                "description": "2024软考真题合集",
                "category": "计算机软考",
            },
        )
        self.assertEqual(create_res.status_code, 200)
        bank = create_res.json()
        bank_id = bank["id"]
        self.assertEqual(bank["name"], "软件设计师真题")
        self.assertEqual(bank["category"], "计算机软考")
        self.assertEqual(bank["question_count"], 0)

        # List banks
        list_res = self.client.get("/api/banks")
        self.assertEqual(list_res.status_code, 200)
        banks = list_res.json()
        self.assertTrue(any(b["id"] == bank_id for b in banks))

        # Get bank details
        get_res = self.client.get(f"/api/banks/{bank_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["id"], bank_id)

        # Create question manually
        q_res = self.client.post(
            f"/api/banks/{bank_id}/questions",
            json={
                "stem": "在 OSI 参考模型中，实现数据加密和解密的是哪一层？",
                "type": "SINGLE",
                "options": [
                    {"key": "A", "content": "网络层"},
                    {"key": "B", "content": "传输层"},
                    {"key": "C", "content": "会话层"},
                    {"key": "D", "content": "表示层"},
                ],
                "answer": "D",
                "explanation": "表示层负责数据格式转换、加密解密和数据压缩。",
                "difficulty": 3,
                "tags": ["网络协议", "OSI"],
            },
        )
        self.assertEqual(q_res.status_code, 200)
        q_data = q_res.json()
        self.assertEqual(q_data["stem"], "在 OSI 参考模型中，实现数据加密和解密的是哪一层？")
        self.assertEqual(q_data["answer"], "D")
        self.assertEqual(len(q_data["options"]), 4)

        # List questions in bank
        q_list_res = self.client.get(f"/api/banks/{bank_id}/questions")
        self.assertEqual(q_list_res.status_code, 200)
        q_list = q_list_res.json()
        self.assertEqual(len(q_list), 1)
        self.assertEqual(q_list[0]["id"], q_data["id"])

        # Bank question_count updated
        bank_updated = self.client.get(f"/api/banks/{bank_id}").json()
        self.assertEqual(bank_updated["question_count"], 1)

        # Non-existent bank 404
        non_res = self.client.get("/api/banks/non-existent-id")
        self.assertEqual(non_res.status_code, 404)

    def test_03_import_questions_from_text(self):
        """Test importing questions from text/markdown into question bank."""
        bank_res = self.client.post(
            "/api/banks",
            json={"name": "导入测试题库", "category": "测试"},
        )
        bank_id = bank_res.json()["id"]

        import_text = """
1. Python 中用于定义匿名函数的关键字是？
A. def
B. lambda
C. func
D. anon
【答案】B
【解析】lambda 关键字用于定义匿名函数。
【难度】2
【标签】Python, 基础

2. 下列关于 HTTP 状态码的表述，正确的是？
A. 200 表示成功
B. 404 表示服务器内部错误
C. 500 表示未找到资源
D. 301 表示临时重定向
【答案】A
【解析】200 OK，404 Not Found，500 Internal Error，301 Moved Permanently。
        """

        res = self.client.post(
            f"/api/banks/{bank_id}/import",
            json={"format": "text", "content": import_text},
        )
        self.assertEqual(res.status_code, 200)
        import_data = res.json()
        self.assertEqual(import_data["imported_count"], 2)
        self.assertEqual(len(import_data["questions"]), 2)

        # Verify physical persistence
        list_res = self.client.get(f"/api/banks/{bank_id}/questions")
        questions = list_res.json()
        self.assertEqual(len(questions), 2)
        stems = [q["stem"] for q in questions]
        self.assertTrue(any("匿名函数" in s for s in stems))
        self.assertTrue(any("HTTP 状态码" in s for s in stems))

        # Check bank question_count is 2
        bank_info = self.client.get(f"/api/banks/{bank_id}").json()
        self.assertEqual(bank_info["question_count"], 2)

    def test_04_practice_session_answer_and_mistake_recording(self):
        """Test starting session, answering incorrectly, instant scoring, and mistake recording."""
        # 1. Create bank with 1 question
        bank_res = self.client.post("/api/banks", json={"name": "刷题实战库"})
        bank_id = bank_res.json()["id"]

        q_res = self.client.post(
            f"/api/banks/{bank_id}/questions",
            json={
                "stem": "TCP 协议三次握手第一次发送的报文标志位是？",
                "type": "SINGLE",
                "options": [
                    {"key": "A", "content": "SYN=1, ACK=0"},
                    {"key": "B", "content": "SYN=1, ACK=1"},
                    {"key": "C", "content": "FIN=1, ACK=0"},
                    {"key": "D", "content": "RST=1"},
                ],
                "answer": "A",
                "explanation": "三次握手第一次 client 发送 SYN=1, ACK=0。",
            },
        )
        q_id = q_res.json()["id"]

        # 2. Start PRACTICE session
        session_res = self.client.post(
            "/api/sessions",
            json={
                "bank_id": bank_id,
                "mode": "PRACTICE",
                "total_questions": 1,
            },
        )
        self.assertEqual(session_res.status_code, 200)
        session_id = session_res.json()["id"]

        # 3. Submit wrong answer B with mistake cause OPTION_TRAP
        ans_res = self.client.post(
            f"/api/sessions/{session_id}/answer",
            json={
                "question_id": q_id,
                "user_answer": "B",
                "time_spent_delta": 15,
                "mistake_cause": "OPTION_TRAP",
            },
        )
        self.assertEqual(ans_res.status_code, 200)
        ans_data = ans_res.json()
        self.assertFalse(ans_data["is_correct"])
        self.assertEqual(ans_data["score_ratio"], 0.0)
        self.assertEqual(ans_data["correct_answer"], "A")
        self.assertIn("三次握手第一次", ans_data["explanation"])

        # 4. Check mistake records via GET /api/mistakes
        mistakes_res = self.client.get(f"/api/mistakes?bank_id={bank_id}")
        self.assertEqual(mistakes_res.status_code, 200)
        mistakes = mistakes_res.json()
        self.assertEqual(len(mistakes), 1)
        m = mistakes[0]
        self.assertEqual(m["question_id"], q_id)
        self.assertEqual(m["mistake_cause"], "OPTION_TRAP")
        self.assertFalse(m["is_cleared"])
        self.assertEqual(m["mistake_count"], 1)
        self.assertEqual(m["consecutive_correct"], 0)

        # Filter by taxonomy cause
        cause_res = self.client.get(f"/api/mistakes?cause=OPTION_TRAP")
        self.assertEqual(len(cause_res.json()), 1)
        empty_res = self.client.get(f"/api/mistakes?cause=CALCULATION_ERROR")
        self.assertEqual(len(empty_res.json()), 0)

    def test_05_draft_sync_and_toggle_flag(self):
        """Test client localStorage draft synchronization and question flagging."""
        bank_res = self.client.post("/api/banks", json={"name": "草稿同步题库"})
        bank_id = bank_res.json()["id"]

        sess_res = self.client.post(
            "/api/sessions",
            json={"bank_id": bank_id, "mode": "EXAM", "total_questions": 5, "time_limit": 3600},
        )
        session_id = sess_res.json()["id"]

        # Sync localStorage draft
        draft_payload = {
            "current_index": 3,
            "answers": {
                "q-1": {"user_answer": "A", "time": 10},
                "q-2": {"user_answer": "B", "time": 15},
            },
            "flags": ["q-1", "q-3"],
            "time_spent": 120,
        }
        sync_res = self.client.post(f"/api/sessions/{session_id}/sync", json=draft_payload)
        self.assertEqual(sync_res.status_code, 200)
        synced = sync_res.json()
        self.assertEqual(synced["current_index"], 3)
        self.assertEqual(synced["time_spent"], 120)
        self.assertIn("q-1", synced["flags"])
        self.assertIn("q-3", synced["flags"])
        self.assertEqual(synced["answers"]["q-1"]["user_answer"], "A")

        # Verify persistent read back via GET /api/sessions/{session_id}
        get_sess = self.client.get(f"/api/sessions/{session_id}").json()
        self.assertEqual(get_sess["current_index"], 3)
        self.assertEqual(get_sess["time_spent"], 120)
        self.assertEqual(len(get_sess["flags"]), 2)

        # Toggle flag
        flag_res = self.client.post(
            f"/api/sessions/{session_id}/toggle-flag",
            json={"question_id": "q-4"},
        )
        self.assertEqual(flag_res.status_code, 200)
        self.assertIn("q-4", flag_res.json()["flags"])

        # Toggle again to remove
        flag_res2 = self.client.post(
            f"/api/sessions/{session_id}/toggle-flag",
            json={"question_id": "q-4"},
        )
        self.assertEqual(flag_res2.status_code, 200)
        self.assertNotIn("q-4", flag_res2.json()["flags"])

    def test_06_mistake_elimination_two_consecutive_correct(self):
        """Test mistake elimination practice: 2 consecutive correct answers clear the mistake."""
        bank_res = self.client.post("/api/banks", json={"name": "错题斩杀测试库"})
        bank_id = bank_res.json()["id"]

        q_res = self.client.post(
            f"/api/banks/{bank_id}/questions",
            json={
                "stem": "光速在真空中的传播速度约为？",
                "type": "SINGLE",
                "options": [
                    {"key": "A", "content": "30万公里/秒"},
                    {"key": "B", "content": "340米/秒"},
                ],
                "answer": "A",
            },
        )
        q_id = q_res.json()["id"]

        # Step 1: Make a mistake in practice
        sess_res = self.client.post("/api/sessions", json={"bank_id": bank_id, "mode": "PRACTICE"})
        session_id = sess_res.json()["id"]
        self.client.post(
            f"/api/sessions/{session_id}/answer",
            json={"question_id": q_id, "user_answer": "B", "mistake_cause": "CONCEPT_GAP"},
        )

        # Confirm mistake is active
        m_list = self.client.get(f"/api/mistakes?bank_id={bank_id}").json()
        self.assertEqual(len(m_list), 1)
        self.assertFalse(m_list[0]["is_cleared"])

        # Step 2: Practice round 1 -> Correct answer 'A'
        p1 = self.client.post(f"/api/mistakes/{q_id}/practice", json={"user_answer": "A"}).json()
        self.assertTrue(p1["is_correct"])
        self.assertEqual(p1["consecutive_correct"], 1)
        self.assertFalse(p1["is_cleared"])

        # Confirm still in uncleared mistakes
        m_list_after_1 = self.client.get(f"/api/mistakes?bank_id={bank_id}").json()
        self.assertEqual(len(m_list_after_1), 1)

        # Step 3: Practice round 2 -> Consecutive correct answer 'A' -> ELIMINATED!
        p2 = self.client.post(f"/api/mistakes/{q_id}/practice", json={"user_answer": "A"}).json()
        self.assertTrue(p2["is_correct"])
        self.assertEqual(p2["consecutive_correct"], 2)
        self.assertTrue(p2["is_cleared"])

        # Confirm removed from active uncleared mistakes
        m_list_after_2 = self.client.get(f"/api/mistakes?bank_id={bank_id}").json()
        self.assertEqual(len(m_list_after_2), 0)

        # Step 4: If answered wrong again, reactivate mistake and reset consecutive_correct
        p3 = self.client.post(f"/api/mistakes/{q_id}/practice", json={"user_answer": "B"}).json()
        self.assertFalse(p3["is_correct"])
        self.assertEqual(p3["consecutive_correct"], 0)
        self.assertFalse(p3["is_cleared"])

        # Reactivated in uncleared mistakes
        m_reactivated = self.client.get(f"/api/mistakes?bank_id={bank_id}").json()
        self.assertEqual(len(m_reactivated), 1)

    def test_07_complete_session_and_score_report(self):
        """Test completing session and generating final score report."""
        bank_res = self.client.post("/api/banks", json={"name": "交卷测试库"})
        bank_id = bank_res.json()["id"]

        q1 = self.client.post(
            f"/api/banks/{bank_id}/questions",
            json={"stem": "1+1=?", "type": "SINGLE", "answer": "2", "options": [{"key": "2", "content": "2"}]},
        ).json()["id"]
        q2 = self.client.post(
            f"/api/banks/{bank_id}/questions",
            json={"stem": "2+2=?", "type": "SINGLE", "answer": "4", "options": [{"key": "4", "content": "4"}]},
        ).json()["id"]

        sess = self.client.post(
            "/api/sessions",
            json={"bank_id": bank_id, "mode": "EXAM", "total_questions": 2},
        ).json()
        session_id = sess["id"]

        # Answer q1 correctly, q2 incorrectly
        self.client.post(
            f"/api/sessions/{session_id}/answer",
            json={"question_id": q1, "user_answer": "2", "time_spent_delta": 10},
        )
        self.client.post(
            f"/api/sessions/{session_id}/answer",
            json={"question_id": q2, "user_answer": "5", "time_spent_delta": 20},
        )

        # Complete session
        complete_res = self.client.post(f"/api/sessions/{session_id}/complete")
        self.assertEqual(complete_res.status_code, 200)
        report = complete_res.json()

        self.assertTrue(report["is_completed"])
        self.assertEqual(report["total_questions"], 2)
        self.assertEqual(report["answered_count"], 2)
        self.assertEqual(report["correct_count"], 1)
        self.assertEqual(report["score"], 1.0)
        self.assertEqual(report["accuracy"], 50.0)
        self.assertEqual(report["total_score"], 2.0)
        self.assertEqual(report["passing_score"], 1.2)
        self.assertFalse(report["passed"])  # 1.0 < 1.2
        self.assertEqual(report["answered_questions"], 2)
        self.assertIn("breakdown", report)

    def test_08_fsrs_due_reviews_endpoint(self):
        """Test GET /api/mistakes/due reviews endpoint."""
        res = self.client.get("/api/mistakes/due")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_09_ai_tutor_sse_chat_offline_fallback(self):
        """Test POST /api/ai/tutor/chat graceful offline fallback when no LLM service is running."""
        payload = {
            "question_context": {
                "stem": "简答：什么是操作系统死锁？",
                "options": [],
                "user_answer": "不知道",
                "correct_answer": "多道程序并发执行时，多个进程因争夺资源而造成的一种僵局。",
                "explanation": "产生死锁的四个必要条件：互斥、占有且等待、不可抢占、循环等待。",
                "mistake_cause": "CONCEPT_GAP",
            },
            "user_query": "能通俗给我讲讲死锁吗？",
            "history": [],
        }

        # Request with unreachable LLM port
        with patch.dict(os.environ, {"LLM_BASE_URL": "http://127.0.0.1:59998/v1"}, clear=True):
            app = create_app(db_path=self.db_path)
            client = TestClient(app)
            response = client.post("/api/ai/tutor/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
            body = response.text
            self.assertIn("未检测到可用的大模型服务或网络离线", body)

    def test_10_ai_tutor_sse_chat_mocked_streaming(self):
        """Test POST /api/ai/tutor/chat SSE stream output when LLM returns streamed tokens."""
        payload = {
            "question_context": {
                "stem": "下列属于死锁必要条件的是？",
                "options": [{"key": "A", "content": "互斥条件"}],
                "user_answer": "B",
                "correct_answer": "A",
                "explanation": "互斥条件是死锁的四大必要条件之一。",
                "mistake_cause": "CONCEPT_GAP",
            },
            "user_query": "请解析",
            "history": [],
        }

        sse_lines = [
            b': ping\n',
            'data: {"choices":[{"delta":{"content":"死锁"}}]}\n\n'.encode("utf-8"),
            'data: {"choices":[{"delta":{"content":"的四大"}}]}\n\n'.encode("utf-8"),
            'data: {"choices":[{"delta":{"content":"必要条件"}}]}\n\n'.encode("utf-8"),
            b'data: [DONE]\n\n',
        ]
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = sse_lines
        mock_resp.__exit__.return_value = False

        with patch("urllib.request.urlopen", return_value=mock_resp):
            response = self.client.post("/api/ai/tutor/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.headers["content-type"].startswith("text/event-stream"))
            body = response.text
            self.assertIn("死锁", body)
            self.assertIn("的四大", body)
            self.assertIn("必要条件", body)


if __name__ == "__main__":
    unittest.main()
