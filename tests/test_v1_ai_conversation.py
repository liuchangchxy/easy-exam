import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from backend.app.main import create_app


class TestV1AiConversation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.app = create_app(db_path=self.tmp.name)
        self.client = TestClient(self.app)

        # User 1
        self.client.post("/api/v1/auth/register", json={"username": "user1", "password": "password123"})
        res1 = self.client.post("/api/v1/auth/login", json={"username": "user1", "password": "password123"})
        self.token1 = res1.json()["token"]
        self.auth1 = {"Authorization": f"Bearer {self.token1}"}

        # User 2
        self.client.post("/api/v1/auth/register", json={"username": "user2", "password": "password123"})
        res2 = self.client.post("/api/v1/auth/login", json={"username": "user2", "password": "password123"})
        self.token2 = res2.json()["token"]
        self.auth2 = {"Authorization": f"Bearer {self.token2}"}

        # Create bank and question as user 1
        bank_res = self.client.post("/api/v1/banks", headers=self.auth1, json={"name": "AI Test Bank"})
        self.bank_id = bank_res.json()["id"]

        q_res = self.client.post(
            f"/api/v1/banks/{self.bank_id}/questions",
            headers=self.auth1,
            json={
                "stem": "关于行政复议，下列哪一说法是正确的？",
                "type": "SINGLE",
                "options": [
                    {"key": "A", "content": "复议机关只能是上级行政机关"},
                    {"key": "B", "content": "申请人可以口头提出复议申请"},
                    {"key": "C", "content": "复议决定书自作出之日起生效"},
                    {"key": "D", "content": "对复议决定不服不得再提起行政诉讼"},
                ],
                "answer": "B",
                "explanation": "法定可以书面或口头申请复议。",
                "difficulty": 3,
            },
        )
        self.question = q_res.json()
        self.question_id = self.question["id"]

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            os.unlink(self.tmp.name)

    def test_multi_turn_conversation_sequence_and_branching(self):
        """
        Track A (MiaowTest adaptation):
        Verify sequential message ordering, role tagging, and branching with parent_message_id.
        """
        # 1. Send first question message
        res1 = self.client.post(
            f"/api/v1/ai/questions/{self.question_id}/messages",
            headers=self.auth1,
            json={"content": "为什么选项 B 是正确的？口头申请的法定依据是什么？"},
        )
        self.assertEqual(res1.status_code, 201, res1.text)
        data1 = res1.json()
        conv_id = data1["conversation"]["id"]
        user_msg1 = data1["user_message"]
        ai_msg1 = data1["assistant_message"]

        self.assertEqual(user_msg1["sequence"], 1)
        self.assertEqual(user_msg1["role"], "user")
        self.assertEqual(user_msg1["message_status"], "success")
        self.assertIsNone(user_msg1["parent_message_id"])

        self.assertEqual(ai_msg1["sequence"], 2)
        self.assertEqual(ai_msg1["role"], "assistant")
        self.assertEqual(ai_msg1["parent_message_id"], user_msg1["id"])

        # 2. Follow-up turn 2 (replying to ai_msg1)
        res2 = self.client.post(
            f"/api/v1/ai/questions/{self.question_id}/messages",
            headers=self.auth1,
            json={
                "conversation_id": conv_id,
                "content": "那如果是口头申请，行政机关需要当场制作记录吗？",
                "parent_message_id": ai_msg1["id"],
            },
        )
        self.assertEqual(res2.status_code, 201)
        data2 = res2.json()
        user_msg2 = data2["user_message"]
        ai_msg2 = data2["assistant_message"]

        self.assertEqual(user_msg2["sequence"], 3)
        self.assertEqual(user_msg2["parent_message_id"], ai_msg1["id"])
        self.assertEqual(ai_msg2["sequence"], 4)
        self.assertEqual(ai_msg2["parent_message_id"], user_msg2["id"])

        # 3. Branching turn 3: alternative follow-up also branching from ai_msg1
        res3 = self.client.post(
            f"/api/v1/ai/questions/{self.question_id}/messages",
            headers=self.auth1,
            json={
                "conversation_id": conv_id,
                "content": "选项 C 为什么错？生效时间如何确定？",
                "parent_message_id": ai_msg1["id"],
            },
        )
        self.assertEqual(res3.status_code, 201)
        data3 = res3.json()
        user_msg3 = data3["user_message"]
        ai_msg3 = data3["assistant_message"]
        self.assertEqual(user_msg3["sequence"], 5)
        self.assertEqual(user_msg3["parent_message_id"], ai_msg1["id"])
        self.assertEqual(ai_msg3["parent_message_id"], user_msg3["id"])

        # 4. Thread traversal for branch 3: should walk root -> user1 -> ai1 -> user3 -> ai3
        thread_res = self.client.get(
            f"/api/v1/ai/messages/{ai_msg3['id']}/thread",
            headers=self.auth1,
        )
        self.assertEqual(thread_res.status_code, 200)
        thread = thread_res.json()
        self.assertEqual(len(thread), 4)
        self.assertEqual([m["id"] for m in thread], [user_msg1["id"], ai_msg1["id"], user_msg3["id"], ai_msg3["id"]])
        # Note user_msg2 and ai_msg2 should NOT be in this branch
        self.assertNotIn(user_msg2["id"], [m["id"] for m in thread])

    def test_user_isolation_and_question_version_isolation(self):
        """
        Verify privacy:
        - User 2 cannot access User 1's AI conversations or messages.
        - Red line: AI tutor messages NEVER modify the standard answer.
        """
        # User 1 creates a message
        res1 = self.client.post(
            f"/api/v1/ai/questions/{self.question_id}/messages",
            headers=self.auth1,
            json={"content": "请解析行政复议管辖"},
        )
        conv_id = res1.json()["conversation"]["id"]
        msg_id = res1.json()["assistant_message"]["id"]

        # User 2 tries to read user 1's conversation
        res_u2_conv = self.client.get(
            f"/api/v1/ai/conversations/{conv_id}/messages",
            headers=self.auth2,
        )
        self.assertEqual(res_u2_conv.status_code, 404)

        # User 2 tries to read user 1's message thread
        res_u2_thread = self.client.get(
            f"/api/v1/ai/messages/{msg_id}/thread",
            headers=self.auth2,
        )
        self.assertEqual(res_u2_thread.status_code, 404)

        # User 2 list conversations for question returns empty
        res_u2_list = self.client.get(
            f"/api/v1/ai/questions/{self.question_id}/conversations",
            headers=self.auth2,
        )
        self.assertEqual(res_u2_list.status_code, 200)
        self.assertEqual(len(res_u2_list.json()), 0)

        # Red line check: question standard answer remains 'B'
        q_check = self.client.get(f"/api/v1/questions/{self.question_id}", headers=self.auth1)
        self.assertEqual(q_check.status_code, 200)
        self.assertEqual(q_check.json()["answer"], "B")
