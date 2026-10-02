import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.app.main import create_app


class TestAiBatchAndSequential(unittest.TestCase):
    def test_sequential_practice_order_and_continuity(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = TestClient(create_app(str(Path(tmp) / "db.sqlite")))
            client.post("/api/v1/auth/register", json={"username": "seq_user", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "seq_user", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "顺序通刷测试"}).json()

            # Create 5 questions in specific order
            q_ids = []
            for i in range(5):
                q = client.post(
                    f"/api/v1/banks/{bank['id']}/questions",
                    headers=headers,
                    json={"stem": f"题目第{i+1}道", "answer": "A", "options": [{"key": "A", "content": "对"}]},
                ).json()
                q_ids.append(q["id"])

            # 1. Start sequential session (PRACTICE mode with default total_questions=0)
            session = client.post("/api/v1/practice/sessions", headers=headers, json={"bank_id": bank["id"], "mode": "PRACTICE"}).json()
            self.assertEqual(session["mode"], "PRACTICE")
            self.assertEqual(session["total_questions"], 5)

            # Get session questions - verify they are in EXACT sequential order
            sess_qs = client.get(f"/api/v1/practice/sessions/{session['id']}/questions", headers=headers).json()
            self.assertEqual(len(sess_qs), 5)
            self.assertEqual([q["id"] for q in sess_qs], q_ids)

            # 2. Answer question 1 and 2, save draft with current_index=2
            draft_res = client.post(
                f"/api/v1/practice/sessions/{session['id']}/sync",
                headers=headers,
                json={"current_index": 2, "answers": {q_ids[0]: "A", q_ids[1]: "A"}},
            )
            self.assertEqual(draft_res.status_code, 200)

            # 3. Verify active sessions lists the session with answered_count=2, total=5
            active = client.get("/api/v1/practice/sessions/active", headers=headers).json()
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0]["id"], session["id"])
            self.assertEqual(active[0]["answered_count"], 2)
            self.assertEqual(active[0]["current_index"], 2)

    def test_ai_batch_explanation_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(str(Path(tmp) / "db.sqlite"))
            mock_provider = MagicMock()
            mock_provider.chat_complete.return_value = "Mocked explanation content"
            mock_provider.model = "mock-model"
            app.state.services.ai.provider = mock_provider
            client = TestClient(app)

            client.post("/api/v1/auth/register", json={"username": "batch_user", "password": "password-123456"})
            token = client.post("/api/v1/auth/login", json={"username": "batch_user", "password": "password-123456"}).json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            bank = client.post("/api/v1/banks", headers=headers, json={"name": "批量解析题库"}).json()

            # Create 3 questions: 1 has explanation, 2 do not
            client.post(
                f"/api/v1/banks/{bank['id']}/questions",
                headers=headers,
                json={"stem": "已有官方解析题目", "answer": "A", "explanation": "官方详细说明"},
            )
            q2 = client.post(
                f"/api/v1/banks/{bank['id']}/questions",
                headers=headers,
                json={"stem": "缺少解析题目一", "answer": "B"},
            ).json()
            q3 = client.post(
                f"/api/v1/banks/{bank['id']}/questions",
                headers=headers,
                json={"stem": "缺少解析题目二", "answer": "C"},
            ).json()

            # Check initial batch status
            status_res = client.get(f"/api/v1/ai/banks/{bank['id']}/batch-status", headers=headers)
            self.assertEqual(status_res.status_code, 200)
            status = status_res.json()
            self.assertEqual(status["total"], 3)
            self.assertEqual(status["with_explanation"], 1)
            self.assertEqual(status["without_explanation"], 2)
            self.assertEqual(status["status"], "idle")

            # Start batch generation without overwrite (should target 2 questions)
            gen_res = client.post(f"/api/v1/ai/banks/{bank['id']}/generate-batch", headers=headers, json={"overwrite": False})
            self.assertEqual(gen_res.status_code, 202)
            gen_data = gen_res.json()
            self.assertEqual(gen_data["total"], 2)

            # Wait for background worker to complete
            for _ in range(50):
                time.sleep(0.05)
                st = client.get(f"/api/v1/ai/banks/{bank['id']}/batch-status", headers=headers).json()
                if st["status"] in ("completed", "failed", "stopped"):
                    break

            final_st = client.get(f"/api/v1/ai/banks/{bank['id']}/batch-status", headers=headers).json()
            self.assertEqual(final_st["status"], "completed")
            self.assertEqual(final_st["processed"], 2)
            self.assertEqual(final_st["succeeded"], 2)

            # Verify explanations were generated and stored for q2 and q3
            q2_answers = client.get(f"/api/v1/ai/questions/{q2['id']}/answers", headers=headers).json()
            self.assertTrue(len(q2_answers) >= 1)
            self.assertEqual(q2_answers[0]["source"], "AI")


if __name__ == "__main__":
    unittest.main()
