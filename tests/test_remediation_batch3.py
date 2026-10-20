import tempfile
import unittest
import json
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.infrastructure.db.connection import migrate, transaction

class TestBatch3Remediation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_batch3.db"
        migrate(self.db_path)
        self.app = create_app(self.db_path)
        self.client = TestClient(self.app)

        self.client.post("/api/v1/auth/register", json={"username": "batch3_user", "password": "Password123!"})
        login_res = self.client.post("/api/v1/auth/login", json={"username": "batch3_user", "password": "Password123!"})
        self.token = login_res.json()["token"]
        self.user_id = login_res.json()["user"]["id"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # 题库 1
        b1 = self.client.post("/api/v1/banks", json={"name": "题库1"}, headers=self.headers).json()
        self.b1_id = b1["id"]
        # 题库 2
        b2 = self.client.post("/api/v1/banks", json={"name": "题库2"}, headers=self.headers).json()
        self.b2_id = b2["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_p2_13_cross_bank_chapter_assignment_rejected(self):
        """P2-13: 题目绑定 chapter_id 时必须校验该章节是否归属于本题库，跨题库章节引用应拒绝或置空"""
        # 在题库 2 下创建一个章节
        with transaction(self.db_path) as conn:
            conn.execute("INSERT INTO chapters(id, bank_id, name) VALUES ('chap_b2', ?, '题库2章节')", (self.b2_id,))

        # 尝试在题库 1 中创建题目并关联题库 2 的章节 chap_b2
        res = self.client.post(f"/api/v1/banks/{self.b1_id}/questions", json={
            "type": "SINGLE",
            "stem": "跨题库测试题",
            "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
            "answer": "A",
            "chapter_id": "chap_b2"
        }, headers=self.headers)
        # 应报错 400 Bad Request 或者创建时拒绝非法章节
        self.assertEqual(res.status_code, 400, "允许了跨题库章节引用！")

    def test_p2_7_single_batch_import_deduplication(self):
        """P2-7: 单批导入内部如果包含重复题目，应在同批次扫描时去重，避免生成两条重复题目"""
        csv_content = (
            "题型,题干,选项A,选项B,正确答案\n"
            "单选题,同批重复题目,苹果,香蕉,A\n"
            "单选题,同批重复题目,苹果,香蕉,A\n"
        )
        res = self.client.post(
            f"/api/v1/imports/banks/{self.b1_id}",
            json={"format": "csv", "content": csv_content, "duplicate_strategy": "skip"},
            headers=self.headers
        )
        self.assertEqual(res.status_code, 201)
        # 题库中应该只有 1 道题目
        q_list = self.client.get(f"/api/v1/banks/{self.b1_id}/questions", headers=self.headers).json()
        self.assertEqual(len(q_list), 1, f"单批内重复题目未去重，创建了多条: {len(q_list)}")

    def test_p2_8_unmark_weak_does_not_delete_reviewed_fsrs_cards(self):
        """P2-8: 取消薄弱标记不能删除已有真实学习复习记录的 FSRS 卡片"""
        q = self.client.post(f"/api/v1/banks/{self.b1_id}/questions", json={
            "type": "SINGLE", "stem": "复习卡片题",
            "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
            "answer": "A"
        }, headers=self.headers).json()
        q_id = q["id"]

        # 标记为薄弱
        self.client.post(f"/api/v1/learning/weak/{q_id}", headers=self.headers)

        # 模拟产生过一次复习记录 (更新 fsrs_cards 的 last_review_at)
        with transaction(self.db_path) as conn:
            conn.execute("UPDATE fsrs_cards SET last_review_at = CURRENT_TIMESTAMP WHERE user_id = ? AND question_id = ?", (self.user_id, q_id))

        # 取消薄弱标记
        del_res = self.client.delete(f"/api/v1/learning/weak/{q_id}", headers=self.headers)
        self.assertEqual(del_res.status_code, 204)

        # 校验 fsrs_cards 仍然存在，因为已有复习历史！
        with transaction(self.db_path) as conn:
            card = conn.execute("SELECT * FROM fsrs_cards WHERE user_id = ? AND question_id = ?", (self.user_id, q_id)).fetchone()
            self.assertIsNotNone(card, "有复习历史的 FSRS 卡片被误删了！")
