import tempfile
import unittest
import sqlite3
import json
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

    def test_p2_2_tag_rename_does_not_mutate_historical_question_versions(self):
        """P2-2: 标签实体以 ID 为权威，重命名标签不改写历史题目版本的 tags_json 快照，维护版本不可变性"""
        # 创建带标签的题目
        q_res = self.client.post(f"/api/v1/banks/{self.b1_id}/questions", json={
            "type": "SINGLE",
            "stem": "标签历史快照测试题",
            "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
            "answer": "A",
            "tags": ["数学", "代数"]
        }, headers=self.headers)
        self.assertEqual(q_res.status_code, 201)
        q_id = q_res.json()["id"]

        # 获取生成的 tag id
        tags = self.client.get(f"/api/v1/banks/{self.b1_id}/tags", headers=self.headers).json()
        tag_math = next(t for t in tags if t["name"] == "数学")

        # 将 "数学" 标签实体名称重命名为 "高等数学"
        update_res = self.client.put(
            f"/api/v1/banks/{self.b1_id}/tags/{tag_math['id']}",
            json={"name": "高等数学"},
            headers=self.headers
        )
        self.assertEqual(update_res.status_code, 200)

        # 检查知识标签实体表更新成功
        tags_after = self.client.get(f"/api/v1/banks/{self.b1_id}/tags", headers=self.headers).json()
        self.assertTrue(any(t["name"] == "高等数学" for t in tags_after))

        # 核心断言：历史题目版本快照（tags_json）保持不可变，仍然完整记录当时的标签 "数学" 和 "代数"
        q_ver = self.client.get(f"/api/v1/questions/{q_id}", headers=self.headers).json()
        self.assertIn("数学", q_ver["tags"])
        self.assertIn("代数", q_ver["tags"])

        # 在底层直接核查 SQLite 中的 question_versions 表原始快照
        with transaction(self.db_path) as conn:
            row = conn.execute("SELECT tags_json FROM question_versions WHERE question_id = ?", (q_id,)).fetchone()
            snapshot_tags = json.loads(row[0])
            self.assertEqual(snapshot_tags, ["数学", "代数"], "历史版本的 tags_json 快照被篡改了！")

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

    def test_ai_draft_accept_transaction_atomicity(self):
        """AI 草稿并发接受与状态一致性：同一事务内原子完成草稿抢占与建题，异常时单事务自动回滚，无中间态补偿"""
        from unittest.mock import patch
        # 创建一个草稿
        draft_row = self.app.state.services.ai.drafts.create_draft(
            self.user_id,
            None,
            self.b1_id,
            {"stem": "AI 变式题", "answer": "A", "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}]}
        )
        draft_id = draft_row["id"]

        # 模拟 create_versioned_question 发生异常
        with patch.object(self.app.state.services.questions, "create_versioned_question", side_effect=ValueError("题库写入故障")):
            with self.assertRaises(ValueError):
                self.app.state.services.ai.accept_variant_draft(self.user_id, draft_id)

        # 检查数据库：在同一个数据库事务回滚后，草稿状态自然保持为 DRAFT
        re_draft = self.app.state.services.ai.drafts.get_draft(self.user_id, draft_id)
        self.assertEqual(re_draft["status"], "DRAFT", "事务未正确回滚草稿状态！")

    def test_import_batch_duplicates_merge_strategy_no_fake_ids(self):
        """P1: 导入批内重复题目选择 merge 时，归并到首条待创建记录中，不伪造数据库 ID"""
        # CSV 中包含两道相同的题目（空题库导入）
        csv_content = (
            "题型,题干,选项A,选项B,正确答案,解析\n"
            "单选题,空题库批内重复合并测试,苹果,香蕉,A,初始解析\n"
            "单选题,空题库批内重复合并测试,苹果,香蕉,A,覆盖更新解析\n"
        )
        res = self.client.post(
            f"/api/v1/imports/banks/{self.b1_id}",
            json={"format": "csv", "content": csv_content, "duplicate_strategy": "merge"},
            headers=self.headers
        )
        self.assertEqual(res.status_code, 201)
        # 题库中应成功创建 1 道题目，且解析为后一条覆盖合并的解析
        q_list = self.client.get(f"/api/v1/banks/{self.b1_id}/questions", headers=self.headers).json()
        self.assertEqual(len(q_list), 1)
        self.assertEqual(q_list[0]["stem"], "空题库批内重复合并测试")
        self.assertEqual(q_list[0]["explanation"], "覆盖更新解析")

    def test_ai_variant_generation_failure_does_not_forge_question(self):
        """P1: AI 变式生成失败时直接报错，绝不使用原题伪造题目返回假成功"""
        from unittest.mock import patch
        # 创建一道原题
        q = self.client.post(f"/api/v1/banks/{self.b1_id}/questions", json={
            "type": "SINGLE", "stem": "变式真实性测试题", "answer": "A",
            "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}]
        }, headers=self.headers).json()

        # 模拟模型输出无法解析为合规 JSON
        with patch.object(self.app.state.services.ai, "_get_provider_for_user") as mock_prov:
            mock_prov.return_value.chat_complete.return_value = "抱歉，由于模型异常无法输出有效题目。"
            res = self.client.post("/api/v1/ai/variants", headers=self.headers, json={
                "original_question_id": q["id"],
                "target_bank_id": self.b1_id,
                "prompt_hint": "生成相似考点题",
            })
            # 必须返回 400 或 422 失败，严禁伪造题目返回 201
            self.assertIn(res.status_code, (400, 422, 500))
            # 校验草稿箱中未生成任何伪造的假题目
            drafts = self.client.get("/api/v1/ai/drafts", headers=self.headers).json()
            self.assertFalse(any("变式真实性测试题" in d.get("stem", "") for d in drafts))

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
