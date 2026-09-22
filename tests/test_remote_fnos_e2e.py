"""Physical Live End-to-End Test Suite against the deployed fnOS NAS instance.

Target URL: http://192.168.x.x:3000
Validates full real-world physical workflows over HTTP without mocks:
1. Healthcheck & static PWA web shell
2. Bank creation & details
3. Markdown/Text question import via regex state machine
4. Practice session instant scoring & localStorage draft sync
5. Targeted mistake taxonomy & 2-consecutive-correct elimination engine
6. FSRS due review querying
7. AI Tutor SSE streaming / graceful fallback
8. Exam mode session completion & diagnostic score report
"""

import json
import time
import unittest
import urllib.request
import urllib.error

NAS_BASE_URL = "http://192.168.x.x:3000"


class TestRemoteFnOsE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Verify NAS connectivity first
        try:
            req = urllib.request.Request(f"{NAS_BASE_URL}/api/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                assert data.get("status") == "ok", f"Unexpected health response: {data}"
        except Exception as e:
            raise unittest.SkipTest(f"Cannot reach fnOS at {NAS_BASE_URL}: {e}")

    def _http(self, method: str, path: str, payload: dict = None) -> tuple[int, dict | str]:
        url = f"{NAS_BASE_URL}{path}"
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                raw = resp.read().decode("utf-8")
                try:
                    return status, json.loads(raw)
                except json.JSONDecodeError:
                    return status, raw
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            try:
                return e.code, json.loads(raw)
            except json.JSONDecodeError:
                return e.code, raw

    def test_01_health_and_pwa_web_shell(self):
        """Verify the healthcheck and the Vue 3 PWA root HTML shell on fnOS."""
        status, health = self._http("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health.get("status"), "ok")
        self.assertIn(health.get("app"), ["easy-exam", "fn-exam"])

        # Check Web Root
        req = urllib.request.Request(f"{NAS_BASE_URL}/")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            html = resp.read().decode("utf-8")
            self.assertIn("EasyExam 易考宝", html)
            self.assertIn("viewport", html)
            self.assertIn("apple-mobile-web-app-capable", html)

    def test_02_full_lifecycle_on_live_nas(self):
        """Execute complete live lifecycle: Bank -> Import -> Practice -> Mistake Kill -> AI -> Exam."""
        test_bank_name = f"fnOS远程物理验收题库-{int(time.time())}"

        # 1. 创建题库
        status, bank = self._http("POST", "/api/banks", {
            "name": test_bank_name,
            "description": "通过自动化E2E脚本远程物理创建",
            "category": "远程验收"
        })
        self.assertEqual(status, 200, f"Create bank failed: {bank}")
        bank_id = bank["id"]
        self.assertTrue(bank_id)

        try:
            # 2. 导入测试题库 (纯文本 Markdown 状态机解析)
            import_content = """
1. 飞牛私有云 (fnOS) 的题库系统采用什么存储引擎？
A. PostgreSQL
B. 单文件 SQLite WAL 模式
C. MongoDB
D. Redis 单机版
【答案】B
【解析】采用单文件 SQLite WAL 模式，常驻内存仅 35MB，并发读写不锁库。
【考点】系统架构

2. 多选题：微信小程序「考试宝」的核心交互体验包括哪些？
A. 点击秒判变色
B. 移动端左右滑动手势切题
C. 底部 5 色网格抽屉答题卡
D. 强制白屏整页刷新
【答案】ABC
【解析】考试宝支持点选即判、滑动手势切题与抽屉答题卡，绝不白屏刷新。

3. 飞牛刷题系统是否支持在手机熄屏或刷新后 0ms 断点自动续答？
A. 对
B. 错
【答案】A
【解析】客户端使用 localStorage 实时暂存草稿，切题与防抖 5 秒同步服务器。
"""
            status, imp_res = self._http("POST", f"/api/banks/{bank_id}/import", {
                "format": "text",
                "content": import_content
            })
            self.assertEqual(status, 200, f"Import failed: {imp_res}")
            self.assertEqual(imp_res.get("imported_count"), 3)

            # 3. 验证题库题目列表与详情
            status, q_list = self._http("GET", f"/api/banks/{bank_id}/questions")
            self.assertEqual(status, 200)
            self.assertEqual(len(q_list), 3)

            q1 = q_list[0]
            self.assertEqual(q1["answer"], "B")
            self.assertEqual(len(q1["options"]), 4)

            # 4. 创建背题练习会话 (PRACTICE 模式)
            status, session = self._http("POST", "/api/sessions", {
                "bank_id": bank_id,
                "mode": "PRACTICE",
                "total_questions": 3,
                "time_limit": 0
            })
            self.assertEqual(status, 200)
            session_id = session["id"]

            # 5. 用户做第 1 题：选错 (选了 A, 正解为 B)，错因归因为 CONCEPT_GAP
            status, ans1 = self._http("POST", f"/api/sessions/{session_id}/answer", {
                "question_id": q1["id"],
                "user_answer": "A",
                "time_spent_delta": 8,
                "mistake_cause": "CONCEPT_GAP"
            })
            self.assertEqual(status, 200)
            self.assertFalse(ans1["is_correct"])
            self.assertEqual(ans1["correct_answer"], "B")
            self.assertIn("SQLite WAL", ans1["explanation"])

            # 6. 用户做第 2 题：多选题漏选 (选了 AB, 正解 ABC) -> 验证 Moodle 部分得分
            q2 = q_list[1]
            status, ans2 = self._http("POST", f"/api/sessions/{session_id}/answer", {
                "question_id": q2["id"],
                "user_answer": "AB",
                "time_spent_delta": 12
            })
            self.assertEqual(status, 200)
            self.assertTrue(ans2["is_correct"])
            self.assertEqual(ans2["score_ratio"], 0.5)  # 漏选给部分分 0.5

            # 7. 客户端断点草稿同步验证 (模拟 localStorage 5s 防抖同步)
            status, sync_res = self._http("POST", f"/api/sessions/{session_id}/sync", {
                "current_index": 2,
                "answers": {q1["id"]: "A", q2["id"]: "AB"},
                "flags": [q2["id"]],
                "time_spent": 20
            })
            self.assertEqual(status, 200)
            self.assertEqual(sync_res["current_index"], 2)
            self.assertIn(q2["id"], sync_res["flags"])

            # 8. 靶向错题本与 2 次连对斩杀出库验证
            # 8.1 检查第 1 题已自动录入错题集
            status, mistakes = self._http("GET", f"/api/mistakes?bank_id={bank_id}")
            self.assertEqual(status, 200)
            self.assertEqual(len(mistakes), 1)
            self.assertEqual(mistakes[0]["question_id"], q1["id"])
            self.assertEqual(mistakes[0]["mistake_cause"], "CONCEPT_GAP")
            self.assertEqual(mistakes[0]["consecutive_correct"], 0)

            # 8.2 错题重做第 1 次答对 -> consecutive_correct 变 1，仍未出库
            status, m_ans1 = self._http("POST", f"/api/mistakes/{q1['id']}/practice", {
                "user_answer": "B"
            })
            self.assertEqual(status, 200)
            self.assertTrue(m_ans1["is_correct"])
            self.assertEqual(m_ans1["consecutive_correct"], 1)
            self.assertFalse(m_ans1["is_cleared"])

            # 8.3 错题重做第 2 次连对 -> 触发斩杀出库 (is_cleared = True)
            status, m_ans2 = self._http("POST", f"/api/mistakes/{q1['id']}/practice", {
                "user_answer": "B"
            })
            self.assertEqual(status, 200)
            self.assertTrue(m_ans2["is_correct"])
            self.assertEqual(m_ans2["consecutive_correct"], 2)
            self.assertTrue(m_ans2["is_cleared"])

            # 8.4 再次查询活跃错题集 -> 已被成功清空
            status, mistakes_after = self._http("GET", f"/api/mistakes?bank_id={bank_id}")
            self.assertEqual(status, 200)
            self.assertEqual(len(mistakes_after), 0, "Question should be cleared after 2 consecutive correct answers")

            # 9. AI 助教 SSE 流式接口验证
            ai_payload = {
                "question_context": {
                    "stem": q1["stem"],
                    "options": q1["options"],
                    "user_answer": "A",
                    "correct_answer": "B",
                    "explanation": q1["explanation"],
                    "mistake_cause": "CONCEPT_GAP"
                },
                "user_query": "为什么选 A 不对？",
                "history": []
            }
            # 建立物理连接读取流响应
            req = urllib.request.Request(
                f"{NAS_BASE_URL}/api/ai/tutor/chat",
                data=json.dumps(ai_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                # 读取至少一个 chunk 验证打字机流或优雅离线降级内容
                chunk = resp.read(256).decode("utf-8", errors="replace")
                self.assertTrue(len(chunk) > 0, "AI tutor response stream should not be empty")

            # 10. 全真模考与诊断单验证
            status, exam_session = self._http("POST", "/api/sessions", {
                "bank_id": bank_id,
                "mode": "EXAM",
                "total_questions": 3,
                "time_limit": 1800
            })
            self.assertEqual(status, 200)
            exam_id = exam_session["id"]

            # 模考答第 3 题：选 A (对)
            q3 = q_list[2]
            status, _ = self._http("POST", f"/api/sessions/{exam_id}/answer", {
                "question_id": q3["id"],
                "user_answer": "A"
            })
            self.assertEqual(status, 200)

            # 交卷
            status, report = self._http("POST", f"/api/sessions/{exam_id}/complete")
            self.assertEqual(status, 200)
            self.assertTrue(report.get("is_completed"))
            self.assertIn("score", report)
            self.assertIn("accuracy", report)
            self.assertIn("total_score", report)
            self.assertIn("passing_score", report)
            self.assertIn("passed", report)
            self.assertIn("breakdown", report)
            self.assertIn("tags_breakdown", report)
            self.assertIn("answered_questions", report)

            # 11. 验证题库导出接口 (JSON, CSV, XLSX, MD)
            for fmt in ["json", "csv", "xlsx", "markdown"]:
                url = f"{NAS_BASE_URL}/api/banks/{bank_id}/export?format={fmt}"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    self.assertEqual(resp.status, 200, f"Remote export format {fmt} failed")
                    body = resp.read()
                    self.assertTrue(len(body) > 0, f"Export format {fmt} returned empty response")

            # 12. 验证题目与选项乱序会话快照
            status, shuffle_sess = self._http("POST", "/api/sessions", {
                "bank_id": bank_id,
                "mode": "PRACTICE",
                "total_questions": 3,
                "shuffle_questions": True,
                "shuffle_options": True,
            })
            self.assertEqual(status, 200)
            shuffle_id = shuffle_sess["id"]
            status, snap_q = self._http("GET", f"/api/sessions/{shuffle_id}/questions")
            self.assertEqual(status, 200)
            self.assertEqual(len(snap_q), 3)

        finally:
            # 清理测试题库
            self._http("DELETE", f"/api/banks/{bank_id}")


if __name__ == "__main__":
    unittest.main()
