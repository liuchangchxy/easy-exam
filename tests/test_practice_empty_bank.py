"""Guards for the workspace/practice contract added in the P2 UX pass."""

import unittest

from fastapi.testclient import TestClient

from backend.app.main import create_app


class PracticeEmptyBankTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path

        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "empty_bank.sqlite3")
        self.app = create_app(db_path=self.db_path)
        self.client = TestClient(self.app)
        self.client.post("/api/v1/auth/register", json={"username": "empty", "password": "password-123456"})
        token = self.client.post(
            "/api/v1/auth/login", json={"username": "empty", "password": "password-123456"}
        ).json()["token"]
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        self._tmp.cleanup()

    def test_starting_practice_on_an_empty_bank_is_refused(self):
        bank = self.client.post("/api/v1/banks", headers=self.headers, json={"name": "空题库"}).json()
        resp = self.client.post(
            "/api/v1/practice/sessions", headers=self.headers, json={"bank_id": bank["id"]}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("没有符合条件", resp.json()["detail"])
        # No half-created session may be left behind for the practice page to open.
        self.assertEqual(self.client.get("/api/v1/practice/sessions/active", headers=self.headers).json(), [])

    def test_content_list_exposes_updated_at_for_sorting(self):
        bank = self.client.post("/api/v1/banks", headers=self.headers, json={"name": "排序题库"}).json()
        self.client.post(
            f"/api/v1/banks/{bank['id']}/questions",
            headers=self.headers,
            json={"stem": "题目", "answer": "A", "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}]},
        )
        rows = self.client.get(
            f"/api/v1/banks/{bank['id']}/content/questions", headers=self.headers
        ).json()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].get("updated_at"))
        self.assertTrue(rows[0].get("created_at"))


if __name__ == "__main__":
    unittest.main()
