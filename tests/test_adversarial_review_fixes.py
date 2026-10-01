import io
import json
import sqlite3
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from backend.app.application.ai_tutor_service import AiTutorService
from backend.app.application.auth_service import AuthService
from backend.app.application.bank_service import BankService
from backend.app.application.import_service import ImportService
from backend.app.application.learning_service import LearningService
from backend.app.application.practice_service import PracticeService
from backend.app.infrastructure.db.connection import migrate
from backend.app.infrastructure.db.repositories.bank_repository import BankRepository
from backend.app.infrastructure.db.repositories.practice_repository import PracticeRepository
from backend.app.infrastructure.db.repositories.question_repository import QuestionRepository
from backend.app.infrastructure.db.repositories.user_repository import UserRepository, UserSessionRepository
from backend.app.infrastructure.importers.spreadsheet_importer import normalize_difficulty, parse_rows_with_mapping
from backend.app.infrastructure.importers.pdf_importer import parse_pdf_questions


class TestAdversarialReviewFixes(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test_adv.db"
        migrate(self.db_path)
        self.users = UserRepository(self.db_path)
        self.sessions = UserSessionRepository(self.db_path)
        self.banks = BankRepository(self.db_path)
        self.questions = QuestionRepository(self.db_path)
        self.practices = PracticeRepository(self.db_path)

        self.auth_service = AuthService(self.users, self.sessions)
        self.bank_service = BankService(self.banks, self.questions)
        self.practice_service = PracticeService(self.practices, self.questions, self.banks)
        self.learning_service = LearningService(self.practices)

        user_info = self.auth_service.register("testuser", "Password123")
        self.user_id = user_info["id"]
        _, self.token = self.auth_service.login("testuser", "Password123")

        self.bank = self.bank_service.create_bank(self.user_id, {"name": "AdvBank"})
        self.bank_id = self.bank["id"]

    def tearDown(self):
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_adv_004_exam_active_hides_answers_in_general_apis(self):
        """发现 1: 模考进行中，普通题目详情与题库列表必须脱敏该模考题目答案与解析"""
        q1 = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "考题1",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "选项A"}, {"key": "B", "content": "选项B"}],
            "answer": "A",
            "explanation": "秘密解析1",
        })
        # 启动模考
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="EXAM", total_questions=1, time_limit=30, question_ids=[q1["id"]],
        )

        # 模考未完成前：查询单题或题库列表，不能暴露答案和解析
        q_detail = self.questions.get_for_user(q1["id"], self.user_id)
        self.assertEqual(q_detail["answer"], "", "模考未交卷前，题目详情不得泄露标准答案")
        self.assertEqual(q_detail["explanation"], "", "模考未交卷前，题目详情不得泄露解析")

        bank_qs = self.questions.list_for_bank(self.bank_id, self.user_id)
        target_q = next(item for item in bank_qs if item["id"] == q1["id"])
        self.assertEqual(target_q["answer"], "", "模考未交卷前，题库列表不得泄露标准答案")

        # 交卷后：恢复显示
        self.practice_service.complete_session(self.user_id, session["id"])
        q_detail_after = self.questions.get_for_user(q1["id"], self.user_id)
        self.assertEqual(q_detail_after["answer"], "A", "模考交卷后，应恢复显示标准答案")
        self.assertEqual(q_detail_after["explanation"], "秘密解析1")

    def test_adv_002_exam_attempt_does_not_advance_fsrs_or_learning_records(self):
        """发现 2: 模考单题提交不能自动推进 FSRS 调度，当 record_mistakes=False 时不增加错题数"""
        q1 = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "模考错题",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}, {"key": "B", "content": "B"}],
            "answer": "A",
            "explanation": "解析",
        })
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="EXAM", total_questions=1, time_limit=30,
            question_ids=[q1["id"]], record_mistakes=False,
        )

        # 提交错误答案 B
        self.practice_service.submit_attempt(self.user_id, session["id"], q1["id"], "B")

        # 校验 fsrs_cards 绝不能被模考单题提交自动推进调度
        with sqlite3.connect(self.db_path) as conn:
            card = conn.execute("SELECT * FROM fsrs_cards WHERE user_id = ? AND question_id = ?", (self.user_id, q1["id"])).fetchone()
            self.assertIsNone(card, "模考单题提交不得自动创建或推进 FSRS 卡片调度")

            lr = conn.execute("SELECT mistake_count FROM learning_records WHERE user_id = ? AND question_id = ?", (self.user_id, q1["id"])).fetchone()
            mistake_count = lr[0] if lr else 0
            self.assertEqual(mistake_count, 0, "record_mistakes=False 时不得计入错题统计")

    def test_adv_005_exam_time_limit_enforced_on_server(self):
        """发现 3: 服务端必须对模考超时做硬性判定，超时后拒绝作答与草稿同步"""
        q1 = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "限时题目",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}],
            "answer": "A",
        })
        session = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="EXAM", total_questions=1, time_limit=1,
            question_ids=[q1["id"]],
        )

        # 将创建时间篡改为 10 分钟前（超过 1 分钟限时）
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE practice_sessions SET created_at = ? WHERE id = ?", (past_time, session["id"]))

        with self.assertRaises(ValueError) as ctx:
            self.practice_service.submit_attempt(self.user_id, session["id"], q1["id"], "A")
        self.assertIn("超时", str(ctx.exception).lower() + "考试时间已到")

    def test_adv_006_difficulty_discrete_levels_and_unclassified_default(self):
        """发现 4: 批量导入必须保留 1..5 级离散级别，缺失难度必须默认 0（未分级）"""
        self.assertEqual(normalize_difficulty("1"), 1)
        self.assertEqual(normalize_difficulty("2"), 2, "2级难度不能被篡改为3")
        self.assertEqual(normalize_difficulty("3"), 3)
        self.assertEqual(normalize_difficulty("4"), 4, "4级难度不能被篡改为5")
        self.assertEqual(normalize_difficulty("5"), 5)
        self.assertEqual(normalize_difficulty(None), 0, "无难度必须为0（未分级）")
        self.assertEqual(normalize_difficulty(""), 0, "空难度必须为0（未分级）")

        rows = [["题目1", "A", None]]
        mapping = {"stem": 0, "answer": 1, "difficulty": 2}
        parsed = parse_rows_with_mapping(rows, mapping)
        self.assertEqual(parsed[0]["difficulty"], 0, "未标注难度的题目必须为0（未分级）")

    def test_adv_021_pdf_uncertain_rejected_for_direct_import(self):
        """发现 5: 结构不确定（UNCERTAIN）的 PDF 严禁直接入库，必须报错引导校对"""
        # 构造纯文本但缺少答案与选项格式的损坏/不确定 PDF 字节模拟
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        # 用伪造的非标内容测试
        fake_pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
        with self.assertRaises(ValueError):
            parse_pdf_questions(fake_pdf)

    def test_adv_001_recommendation_candidates_includes_chapter_id(self):
        """发现 6: recommendation_candidates 必须包含 chapter_id 以支持章节筛选"""
        ch = self.banks.create_chapter(self.bank_id, self.user_id, "第一章")
        q = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "章节考题",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}],
            "answer": "A",
            "chapter_id": ch["id"],
        })
        candidates = self.practices.recommendation_candidates(self.user_id, self.bank_id)
        matched = next((c for c in candidates if c["question_id"] == q["id"]), None)
        self.assertIsNotNone(matched)
        self.assertEqual(matched.get("chapter_id"), ch["id"], "候选集必须透传 chapter_id")

        recs = self.learning_service.recommendations(self.user_id, self.bank_id, chapter=ch["id"])
        self.assertTrue(any(r["question_id"] == q["id"] for r in recs), "应能按 chapter_id 筛选推荐")

    def test_adv_007_trends_weak_points_does_not_multiply_versions(self):
        """发现 7: trends 弱项统计不得因为题目有多个历史版本而重复放大计数"""
        q = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "多版本错题",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}],
            "answer": "A",
            "tags": ["高频考点"],
        })
        # 做错一次
        sess = self.practice_service.start_session(self.user_id, self.bank_id, mode="PRACTICE", total_questions=1)
        self.practice_service.submit_attempt(self.user_id, sess["id"], q["id"], "B")

        # 产生两个新版本（共3个版本）
        self.questions.create_next_version(self.user_id, q["id"], {"stem": "v2", "type": "SINGLE", "options": [{"key": "A", "content": "A"}], "answer": "A", "tags": ["高频考点"]})
        self.questions.create_next_version(self.user_id, q["id"], {"stem": "v3", "type": "SINGLE", "options": [{"key": "A", "content": "A"}], "answer": "A", "tags": ["高频考点"]})

        trends = self.learning_service.trends(self.user_id, self.bank_id)
        weak = next(item for item in trends["weak_points"] if item["name"] == "高频考点")
        self.assertEqual(weak["mistakes"], 1, "错题数应为1，不能被3个版本放大为3")

    def test_adv_008_trends_due_reviews_matches_list_due_reviews(self):
        """发现 8: trends 的 due_reviews 统计必须与 list_due_reviews 集合一致（排除斩杀等）"""
        q = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "到期题",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}],
            "answer": "A",
        })
        self.practices.mark_weak(self.user_id, q["id"])
        # 斩杀此题
        self.practices.kill(self.user_id, q["id"])

        trends = self.learning_service.trends(self.user_id, self.bank_id)
        dues = self.practices.list_due_reviews(self.user_id, self.bank_id)
        self.assertEqual(len(dues), 0, "斩杀题不应在 list_due_reviews 中")
        self.assertEqual(trends["due_reviews"], 0, "trends due_reviews 必须排除已斩杀题目")

    def test_adv_009_trends_review_completion_rate_only_counts_fsrs_reviews(self):
        """发现 9: 普通刷题不应计入 reviews_completed"""
        q = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "普通练习题",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}],
            "answer": "A",
        })
        sess = self.practice_service.start_session(self.user_id, self.bank_id, mode="PRACTICE", total_questions=1)
        self.practice_service.submit_attempt(self.user_id, sess["id"], q["id"], "B")

        trends = self.learning_service.trends(self.user_id, self.bank_id)
        self.assertEqual(trends["reviews_completed"], 0, "普通练习作答不应计入 reviews_completed")

    def test_adv_010_trends_recent_accuracy_excludes_subjective_questions(self):
        """发现 10: trends 客观正确率分母必须排除主观题"""
        q_sub = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "主观论述题",
            "type": "ESSAY",
            "options": [],
            "answer": "参考解答",
        })
        sess = self.practice_service.start_session(self.user_id, self.bank_id, mode="PRACTICE", total_questions=1)
        self.practice_service.submit_attempt(self.user_id, sess["id"], q_sub["id"], "我的作答")

        trends = self.learning_service.trends(self.user_id, self.bank_id)
        # 仅有主观题时，客观 attempts 应为 0，不能把主观题当作客观错题拉低正确率
        self.assertEqual(trends["recent"]["attempts"], 0, "客观正确率统计分母应排除主观题")

    def test_adv_019_bank_chapters_and_tags_management_and_cycle_prevention(self):
        """发现 11 & 12: 章节/标签更新删除，parent_id 防跨库与循环，标签创建防重复报错"""
        ch1 = self.banks.create_chapter(self.bank_id, self.user_id, "章1")
        ch2 = self.banks.create_chapter(self.bank_id, self.user_id, "章2", parent_id=ch1["id"])

        # 更新章节名与父章节
        updated = self.banks.update_chapter(self.bank_id, self.user_id, ch2["id"], name="章2改", parent_id=None)
        self.assertEqual(updated["name"], "章2改")
        self.assertIsNone(updated["parent_id"])

        # 循环引用拒绝
        with self.assertRaises(ValueError):
            self.banks.update_chapter(self.bank_id, self.user_id, ch1["id"], name="章1", parent_id=ch1["id"])

        # 删除章节
        self.assertTrue(self.banks.delete_chapter(self.bank_id, self.user_id, ch2["id"]))

        # 标签创建幂等（防500）
        t1 = self.banks.create_tag(self.bank_id, self.user_id, "重点")
        t2 = self.banks.create_tag(self.bank_id, self.user_id, "重点")
        self.assertEqual(t1["id"], t2["id"], "同名标签应幂等返回同一标签实体")

        # 标签更新与删除
        up_tag = self.banks.update_tag(self.bank_id, self.user_id, t1["id"], "核心考点")
        self.assertEqual(up_tag["name"], "核心考点")
        self.assertTrue(self.banks.delete_tag(self.bank_id, self.user_id, t1["id"]))

    def test_adv_024_draft_and_flag_reject_unrelated_questions_and_bounds(self):
        """发现 13 & 14: 草稿与标记禁止注入非本会话题目，约束 current_index 与 time_spent 边界"""
        q1 = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "会话内题目",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}],
            "answer": "A",
        })
        sess = self.practice_service.start_session(self.user_id, self.bank_id, mode="PRACTICE", total_questions=1, question_ids=[q1["id"]])

        # 注入非法题目 ID 到草稿
        fake_qid = str(uuid.uuid4())
        draft_res = self.practice_service.sync_draft(self.user_id, sess["id"], {
            "current_index": -5,
            "answers": {fake_qid: "A", q1["id"]: "A"},
            "flags": [fake_qid, q1["id"]],
            "time_spent": -100,
        })
        self.assertNotIn(fake_qid, draft_res["answers"], "草稿必须过滤非本会话的非法题目ID")
        self.assertNotIn(fake_qid, draft_res["flags"], "标记必须过滤非本会话的非法题目ID")
        self.assertGreaterEqual(draft_res["current_index"], 0, "current_index 不得为负数")
        self.assertGreaterEqual(draft_res["time_spent"], 0, "time_spent 不得为负数")

        with self.assertRaises(LookupError):
            self.practice_service.toggle_flag(self.user_id, sess["id"], fake_qid)

    def test_adv2_001_list_versions_desensitizes_during_exam(self):
        """发现 ADV2-001: 模考进行中，list_versions 必须脱敏所有版本的标准答案与解析"""
        q = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "考题_全版本",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "选项A"}],
            "answer": "A",
            "explanation": "深度解析A",
        })
        # 产生第2个版本
        self.questions.create_next_version(self.user_id, q["id"], {
            "stem": "考题_全版本_v2",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "选项A"}],
            "answer": "A",
            "explanation": "深度解析A_v2",
        })

        # 启动模考
        sess = self.practice_service.start_session(
            self.user_id, self.bank_id, mode="EXAM", total_questions=1, time_limit=30, question_ids=[q["id"]]
        )

        versions = self.questions.list_versions(q["id"], self.user_id)
        self.assertEqual(len(versions), 2)
        for v in versions:
            self.assertEqual(v["answer"], "", "模考进行中，历史版本答案必须脱敏")
            self.assertEqual(v["explanation"], "", "模考进行中，历史版本解析必须脱敏")

        # 交卷后恢复
        self.practice_service.complete_session(self.user_id, sess["id"])
        versions_after = self.questions.list_versions(q["id"], self.user_id)
        for v in versions_after:
            self.assertEqual(v["answer"], "A", "模考交卷后，历史版本答案必须恢复")
            self.assertTrue(v["explanation"].startswith("深度解析A"))

    def test_adv2_002_member_cannot_modify_or_regrade_or_resolve(self):
        """发现 ADV2-002: 共享题库只读/普通成员 MEMBER 禁止修改题目、重判历史及解决冲突"""
        u2_info = self.auth_service.register("member_user", "Password123")
        u2 = u2_info["id"]
        self.banks.add_member(self.bank_id, self.user_id, "member_user", "MEMBER")

        q = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "保护题目",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}],
            "answer": "A",
        })

        # 1. 尝试修改版本 -> 必须 403 / PermissionError
        with self.assertRaises(PermissionError):
            self.questions.create_next_version(u2, q["id"], {"stem": "被篡改题干", "type": "SINGLE", "options": [{"key": "A", "content": "A"}], "answer": "A"})

        # 2. 尝试重判历史 -> 必须 403 / PermissionError
        with self.assertRaises(PermissionError):
            self.questions.regrade_question_history(u2, q["id"])

        # 3. 尝试解决冲突 -> 必须 403 / PermissionError
        with self.assertRaises(PermissionError):
            self.questions.resolve_conflict(u2, q["id"], 1)

    def test_adv2_003_review_answer_closes_session(self):
        """发现 ADV2-003: review_answer 提交后必须立即完结会话，不得遗留僵尸活跃会话"""
        q = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "单题复习题",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}],
            "answer": "A",
        })

        res = self.practice_service.review_answer(self.user_id, q["id"], "A", 3)
        self.assertEqual(res["fsrs_rating"], 3)

        # 检查 active sessions，必须为 0
        active_fsrs = self.practice_service.list_active_sessions(self.user_id, mode="FSRS")
        self.assertEqual(len(active_fsrs), 0, "单题复习后不得在活跃会话列表中遗留未完成会话")

    def test_adv2_004_kill_requires_bank_membership_and_prevents_leak(self):
        """发现 ADV2-004: 斩杀必须校验题库成员资格，禁止未授权跨租户嗅探题干"""
        u2_info = self.auth_service.register("stranger", "Password123")
        u2 = u2_info["id"]

        q = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "绝密私有题干",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}],
            "answer": "A",
        })

        # u2 无权访问该题库，kill 必须报错
        with self.assertRaises(PermissionError):
            self.practices.kill(u2, q["id"])

        # u2 的已斩杀列表不能包含此题
        killed = self.practices.list_killed(u2)
        self.assertFalse(any(k["question_id"] == q["id"] for k in killed), "已斩杀列表不得泄露未授权题目的元数据")

    def test_adv2_005_summary_excludes_subjective(self):
        """发现 ADV2-005: summary 统计分母必须排除主观题"""
        q_obj = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "客观题",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "A"}],
            "answer": "A",
        })
        q_sub = self.bank_service.create_question(self.user_id, self.bank_id, {
            "stem": "主观简答题",
            "type": "ESSAY",
            "options": [],
            "answer": "参考解答",
        })

        sess = self.practice_service.start_session(self.user_id, self.bank_id, mode="PRACTICE", total_questions=2)
        self.practice_service.submit_attempt(self.user_id, sess["id"], q_obj["id"], "A")
        self.practice_service.submit_attempt(self.user_id, sess["id"], q_sub["id"], "我的作答")

        sum_res = self.practices.summary(self.user_id)
        self.assertEqual(sum_res["attempts"], 1, "summary 客观 attempts 必须排除主观题")
        self.assertEqual(sum_res["correct"], 1)


if __name__ == "__main__":
    unittest.main()

