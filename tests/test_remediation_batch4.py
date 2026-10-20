import tempfile
import unittest
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.infrastructure.db.connection import migrate, transaction, MIGRATIONS

class TestBatch4Remediation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_batch4.db"
        migrate(self.db_path)
        self.app = create_app(self.db_path)
        self.client = TestClient(self.app)

        self.client.post("/api/v1/auth/register", json={"username": "batch4_user", "password": "Password123!"})
        login_res = self.client.post("/api/v1/auth/login", json={"username": "batch4_user", "password": "Password123!"})
        self.token = login_res.json()["token"]
        self.user_id = login_res.json()["user"]["id"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # 题库 1 & 题库 2
        b1 = self.client.post("/api/v1/banks", json={"name": "测试题库1"}, headers=self.headers).json()
        self.b1_id = b1["id"]
        b2 = self.client.post("/api/v1/banks", json={"name": "测试题库2"}, headers=self.headers).json()
        self.b2_id = b2["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_p2_11_migration_atomicity_on_failure(self):
        """P2-11: 数据库迁移必须是严格单事务原子落盘，失败时完整回滚，不留下半批表结构和 migration 记录"""
        import backend.app.infrastructure.db.connection as conn_mod
        test_db = f"{self.temp_dir.name}/test_atomic_migration.db"
        
        # 构造一个包含错误 SQL 的迁移版本
        orig_migrations = dict(conn_mod.MIGRATIONS)
        try:
            # 增加一个在中间失败的 migration 999
            conn_mod.MIGRATIONS[999] = """
            CREATE TABLE migration_temp_ok (id INTEGER PRIMARY KEY);
            THIS IS INVALID SQL COMMAND SYNTAX;
            CREATE TABLE migration_temp_never (id INTEGER PRIMARY KEY);
            """
            with self.assertRaises(Exception):
                conn_mod.migrate(test_db)

            # 校验 migration_temp_ok 表不存在，并且 schema_migrations 中没有 999
            conn = sqlite3.connect(test_db)
            try:
                tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                self.assertNotIn("migration_temp_ok", tables, "迁移失败后，前面的语句未回滚！")
                self.assertNotIn("migration_temp_never", tables)
                migrated_versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()]
                self.assertNotIn(999, migrated_versions, "失败的迁移版本被记入 schema_migrations 了！")
            finally:
                conn.close()
        finally:
            conn_mod.MIGRATIONS = orig_migrations

    def test_p2_2_tag_dual_source_consistency(self):
        """P2-2: 更新或删除 knowledge_tags 时，级联同步 question_versions.tags_json"""
        # 创建带标签的题目
        q_res = self.client.post(f"/api/v1/banks/{self.b1_id}/questions", json={
            "type": "SINGLE",
            "stem": "标签测试题",
            "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
            "answer": "A",
            "tags": ["数学", "代数"]
        }, headers=self.headers)
        self.assertEqual(q_res.status_code, 201)
        q_id = q_res.json()["id"]

        # 获取生成的 tag id
        tags = self.client.get(f"/api/v1/banks/{self.b1_id}/tags", headers=self.headers).json()
        tag_math = next(t for t in tags if t["name"] == "数学")

        # 将 "数学" 重命名为 "高等数学"
        update_res = self.client.put(
            f"/api/v1/banks/{self.b1_id}/tags/{tag_math['id']}",
            json={"name": "高等数学"},
            headers=self.headers
        )
        self.assertEqual(update_res.status_code, 200)

        # 检查题目的 tags 是否同步更新为 "高等数学"
        q_updated = self.client.get(f"/api/v1/questions/{q_id}", headers=self.headers).json()
        self.assertIn("高等数学", q_updated["tags"])
        self.assertNotIn("数学", q_updated["tags"])

        # 删除 "代数" 标签
        tag_algebra = next(t for t in tags if t["name"] == "代数")
        del_res = self.client.delete(f"/api/v1/banks/{self.b1_id}/tags/{tag_algebra['id']}", headers=self.headers)
        self.assertIn(del_res.status_code, (200, 204))

        # 检查题目中的 "代数" 标签已被移除
        q_after_del = self.client.get(f"/api/v1/questions/{q_id}", headers=self.headers).json()
        self.assertNotIn("代数", q_after_del["tags"])
        self.assertIn("高等数学", q_after_del["tags"])

    def test_p2_1_multi_bank_study_plan_tasks(self):
        """P2-1: 跨题库学习计划应包含各题库对应的 bank_tasks，避免丢题或单题库过滤"""
        # 在题库1创建题目
        self.client.post(f"/api/v1/banks/{self.b1_id}/questions", json={
            "type": "SINGLE", "stem": "题库1题", "answer": "A",
            "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}]
        }, headers=self.headers)
        # 在题库2创建题目
        self.client.post(f"/api/v1/banks/{self.b2_id}/questions", json={
            "type": "SINGLE", "stem": "题库2题", "answer": "B",
            "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}]
        }, headers=self.headers)

        # 请求全量跨题库计划 (bank_id=None)
        res = self.client.get("/api/v1/learning/plan?days=1&minutes_per_day=30", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        plan = res.json()
        self.assertGreaterEqual(plan["question_count"], 2)
        day1 = plan["days"][0]
        self.assertIn("bank_tasks", day1)
        # 应该包含两个题库的任务
        bank_ids_in_tasks = {bt["bank_id"] for bt in day1["bank_tasks"]}
        self.assertIn(self.b1_id, bank_ids_in_tasks)
        self.assertIn(self.b2_id, bank_ids_in_tasks)

    def test_ai_draft_accept_atomicity_and_rollback(self):
        """AI 草稿并发接受与状态一致性：若官方创建题目步骤失败，草稿状态回滚为 DRAFT"""
        from unittest.mock import patch
        # 创建一个草稿
        draft_row = self.app.state.services.ai.drafts.create_draft(
            self.user_id,
            None,
            self.b1_id,
            {"stem": "AI 变式题", "answer": "A", "options": [{"key": "A", "content": "1"}]}
        )
        draft_id = draft_row["id"]

        # 模拟 create_versioned_question 发生异常
        with patch.object(self.app.state.services.questions, "create_versioned_question", side_effect=ValueError("题库写入故障")):
            with self.assertRaises(ValueError):
                self.app.state.services.ai.accept_variant_draft(self.user_id, draft_id)

        # 检查草稿状态是否回滚为 DRAFT 而不是滞留在 ACCEPTED
        re_draft = self.app.state.services.ai.drafts.get_draft(self.user_id, draft_id)
        self.assertEqual(re_draft["status"], "DRAFT", "创建题目失败后草稿未回滚为 DRAFT！")

    def test_p1_4_real_concurrent_attempts_submission(self):
        """P1-4 真实多线程并发提交作答，验证不会互相覆盖已保存的 answers_json 且无死锁"""
        # 创建 5 道题
        q_ids = []
        for i in range(5):
            q = self.client.post(f"/api/v1/banks/{self.b1_id}/questions", json={
                "type": "SINGLE", "stem": f"并发测试题 {i}", "answer": "A",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}]
            }, headers=self.headers).json()
            q_ids.append(q["id"])

        # 开启会话
        session = self.client.post("/api/v1/practice/sessions", json={
            "bank_id": self.b1_id,
            "mode": "PRACTICE",
            "question_ids": q_ids
        }, headers=self.headers).json()
        session_id = session["id"]

        def submit_attempt(qid):
            client = TestClient(self.app)
            return client.post(
                f"/api/v1/practice/sessions/{session_id}/attempts",
                json={"question_id": qid, "user_answer": "A"},
                headers=self.headers
            )

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(submit_attempt, qid) for qid in q_ids]
            responses = [f.result() for f in futures]

        for r in responses:
            self.assertEqual(r.status_code, 201)

        # 检查会话的 answers_json，5道题应该都在其中，无一遗漏
        sess_final = self.client.get(f"/api/v1/practice/sessions/{session_id}", headers=self.headers).json()
        answers = sess_final.get("answers", {})
        self.assertEqual(len(answers), 5, f"并发提交后丢失了答案！仅保留了 {len(answers)} 道")
