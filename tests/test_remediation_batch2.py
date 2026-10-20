import tempfile
import unittest
import time
import json
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.infrastructure.db.connection import migrate, transaction

class TestBatch2Remediation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_batch2.db"
        migrate(self.db_path)
        self.app = create_app(self.db_path)
        self.client = TestClient(self.app)

        # 注册并登录测试用户
        self.client.post("/api/v1/auth/register", json={"username": "batch2_user", "password": "Password123!"})
        login_res = self.client.post("/api/v1/auth/login", json={"username": "batch2_user", "password": "Password123!"})
        self.token = login_res.json()["token"]
        self.user_id = login_res.json()["user"]["id"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # 创建一个题库和两道题目
        bank_res = self.client.post("/api/v1/banks", json={"name": "批次2测试题库"}, headers=self.headers)
        self.bank_id = bank_res.json()["id"]

        q1 = self.client.post(f"/api/v1/banks/{self.bank_id}/questions", json={
            "type": "SINGLE", "stem": "题目1",
            "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
            "answer": "A"
        }, headers=self.headers).json()
        self.q1_id = q1["id"]

        q2 = self.client.post(f"/api/v1/banks/{self.bank_id}/questions", json={
            "type": "SINGLE", "stem": "题目2",
            "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
            "answer": "B"
        }, headers=self.headers).json()
        self.q2_id = q2["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_p1_4_concurrent_submit_attempts_retain_both_answers(self):
        """P1-4: 提交不同题目作答时，最新答案在事务内原子合并，而不是用老快照整列覆盖"""
        sess = self.client.post("/api/v1/practice/sessions", json={"bank_id": self.bank_id, "mode": "ALL"}, headers=self.headers).json()
        sess_id = sess["id"]

        # 模拟设备 A 提交 q1
        res1 = self.client.post(f"/api/v1/practice/sessions/{sess_id}/attempts", json={
            "question_id": self.q1_id,
            "user_answer": ["A"],
            "time_spent": 2
        }, headers=self.headers)
        self.assertEqual(res1.status_code, 201)

        # 模拟设备 B 提交 q2
        res2 = self.client.post(f"/api/v1/practice/sessions/{sess_id}/attempts", json={
            "question_id": self.q2_id,
            "user_answer": ["B"],
            "time_spent": 3
        }, headers=self.headers)
        self.assertEqual(res2.status_code, 201)

        # 检查会话详情，q1 和 q2 的答案都必须存在
        sess_detail = self.client.get(f"/api/v1/practice/sessions/{sess_id}", headers=self.headers).json()
        self.assertIn(self.q1_id, sess_detail["answers"])
        self.assertIn(self.q2_id, sess_detail["answers"])

    def test_p2_3_draft_sync_supports_clearing_answers_and_unflagging(self):
        """P2-3: 草稿同步支持显式清空答案与取消标记"""
        sess = self.client.post("/api/v1/practice/sessions", json={"bank_id": self.bank_id, "mode": "ALL"}, headers=self.headers).json()
        sess_id = sess["id"]

        # 先同步一个有答案和标记的草稿
        d1 = self.client.post(f"/api/v1/practice/sessions/{sess_id}/sync", json={
            "current_index": 0,
            "answers": {self.q1_id: "A"},
            "flags": [self.q1_id]
        }, headers=self.headers).json()
        self.assertIn(self.q1_id, d1["answers"])
        self.assertIn(self.q1_id, d1["flags"])

        # 现在客户端显式清空答案 (answers 为空字典或空值) 并取消标记 (flags 为空列表)
        d2 = self.client.post(f"/api/v1/practice/sessions/{sess_id}/sync", json={
            "current_index": 0,
            "answers": {self.q1_id: ""},
            "flags": []
        }, headers=self.headers).json()
        # 清空答案后，该题答案应为空或空字符串，flags 应该为空列表
        ans_val = d2["answers"].get(self.q1_id)
        if isinstance(ans_val, dict):
            raw = ans_val.get("user_answer") or ans_val.get("answer") or ""
        else:
            raw = ans_val or ""
        self.assertEqual(raw, "", f"草稿清空答案未生效: {d2['answers']}")
        self.assertEqual(d2["flags"], [], f"草稿取消标记未生效: {d2['flags']}")

    def test_p1_6_monotonic_event_id_sync_no_drops(self):
        """P1-6: 增量同步支持基于单调严格递增事件 ID / 游标的分页，避免同秒漏事件"""
        # 写入 5 个同秒产生的事件
        events = [
            {"id": f"evt_{i}", "event_type": "PRACTICE_SUBMITTED", "aggregate_type": "SESSION", "aggregate_id": f"sess_{i}", "payload": {"idx": i}}
            for i in range(5)
        ]
        res = self.client.post("/api/v1/sync/events", json={"events": events}, headers=self.headers)
        self.assertEqual(res.status_code, 201)

        # 获取全部事件
        evts = self.client.get("/api/v1/sync/events", headers=self.headers).json()
        self.assertEqual(len(evts), 5)

        # 测试使用事件 ID / 游标进行增量同步 (after = 第二个事件的 id)
        second_id = evts[1]["id"]
        incremental = self.client.get(f"/api/v1/sync/events?after={second_id}", headers=self.headers).json()
        # 应该精确返回后 3 个事件 (idx 2, 3, 4)
        inc_ids = [e["id"] for e in incremental]
        self.assertEqual(inc_ids, [evts[2]["id"], evts[3]["id"], evts[4]["id"]])
