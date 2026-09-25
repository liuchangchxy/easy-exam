import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.infrastructure.ai.web_search import WebSearchAdapter


class MockWebSearchAdapter(WebSearchAdapter):
    def __init__(self, name="mock-search", should_fail=False):
        self.name = name
        self.should_fail = should_fail

    def search(self, query: str) -> dict:
        if self.should_fail:
            return {
                "status": "UNAVAILABLE",
                "message": "搜索服务暂时无法连接。",
                "results": [],
            }
        return {
            "status": "VERIFIED",
            "message": f"成功检索关于【{query}】的官方法律法规证据。",
            "results": [
                {
                    "title": "中华人民共和国行政复议法",
                    "url": "http://www.gov.cn/flfg/2023-09/01/content.htm",
                    "summary": "第十一条：公民、法人或者其他组织可以书面申请，也可以口头申请行政复议。",
                },
                {
                    "title": "最高人民法院公报案例",
                    "url": "http://gongbao.court.gov.cn/al/12345.htm",
                    "summary": "口头提出行政复议申请的，行政复议机构应当当场制作笔录。",
                },
            ],
        }


class TestV1WebSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.app = create_app(db_path=self.tmp.name)
        self.client = TestClient(self.app)

        # User
        self.client.post("/api/v1/auth/register", json={"username": "search_user", "password": "password123"})
        res = self.client.post("/api/v1/auth/login", json={"username": "search_user", "password": "password123"})
        self.token = res.json()["token"]
        self.auth = {"Authorization": f"Bearer {self.token}"}

        # Bank and question
        bank_res = self.client.post("/api/v1/banks", headers=self.auth, json={"name": "Search Bank"})
        self.bank_id = bank_res.json()["id"]
        q_res = self.client.post(
            f"/api/v1/banks/{self.bank_id}/questions",
            headers=self.auth,
            json={
                "stem": "行政复议口头申请是否合法？",
                "type": "JUDGE",
                "options": [{"key": "T", "content": "正确"}, {"key": "F", "content": "错误"}],
                "answer": "T",
                "explanation": "根据行政复议法第十一条，可以口头申请。",
                "difficulty": 2,
            },
        )
        self.question = q_res.json()
        self.question_id = self.question["id"]

    def tearDown(self):
        try:
            if os.path.exists(self.tmp.name):
                os.unlink(self.tmp.name)
        except Exception:
            pass

    def test_default_web_search_fallback_to_unavailable_without_fabricated_sources(self):
        """When web search is unconfigured / offline, returns UNAVAILABLE and empty evidence without faking sources."""
        res = self.client.post(
            f"/api/v1/ai/questions/{self.question_id}/verify-web",
            headers=self.auth,
            json={"query": "行政复议口头申请"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["source"], "WEB")
        self.assertEqual(data["verification_status"], "UNAVAILABLE")
        self.assertEqual(len(data["evidence"]), 0)

        # Check standard answer is preserved
        q_res = self.client.get(f"/api/v1/questions/{self.question_id}", headers=self.auth)
        self.assertEqual(q_res.json()["answer"], "T")

    def test_configured_web_search_attaches_evidence_records(self):
        """When web search succeeds (mocked service contract), records separate WEB explanation and explanation_evidence rows."""
        # Inject mock search adapter into app state services
        self.app.state.services.ai.web_search = MockWebSearchAdapter(name="open-webSearch")

        res = self.client.post(
            f"/api/v1/ai/questions/{self.question_id}/verify-web",
            headers=self.auth,
            json={"query": "行政复议口头申请"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["source"], "WEB")
        self.assertEqual(data["verification_status"], "VERIFIED")
        self.assertEqual(len(data["evidence"]), 2)
        self.assertEqual(data["evidence"][0]["title"], "中华人民共和国行政复议法")
        self.assertTrue(data["evidence"][0]["url"].startswith("http"))
        self.assertIn("口头申请", data["evidence"][0]["summary"])

        # Verify evidence persisted in SQLite explanation_evidence table
        import sqlite3
        conn = sqlite3.connect(self.tmp.name)
        rows = conn.execute("SELECT title, url, summary FROM explanation_evidence WHERE explanation_id = ?", (data["id"],)).fetchall()
        conn.close()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "中华人民共和国行政复议法")

    def test_live_open_websearch_adapter_reports_unavailable_when_service_daemon_missing(self):
        """Verify OpenWebSearchAdapter against real endpoint URL when daemon is not running.

        Ensures system gracefully returns UNAVAILABLE without unhandled crash or falsifying search hits.
        """
        from backend.app.infrastructure.ai.web_search import OpenWebSearchAdapter
        live_adapter = OpenWebSearchAdapter(endpoint_url="http://127.0.0.1:8000/v1/search")
        self.app.state.services.ai.web_search = live_adapter

        res = self.client.post(
            f"/api/v1/ai/questions/{self.question_id}/verify-web",
            headers=self.auth,
            json={"query": "宪法第一条规定"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["source"], "WEB")
        self.assertEqual(data["verification_status"], "UNAVAILABLE")
        self.assertEqual(len(data["evidence"]), 0)
        self.assertIn("当前未配置可用联网核查服务或连接超时", data["content"])

