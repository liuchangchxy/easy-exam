"""The unified review queue has four sources; each must be reachable on its own.

`/mistakes/due` only reports weak flags that already have a due FSRS card, so the
queue would never show a question that was just flagged weak. `/mistakes/weak`
is the authoritative weak source; these tests pin that contract.
"""

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.main import create_app


class ReviewQueueSourcesTest(unittest.TestCase):
    def setUp(self):
        self._temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self._temp_db.name
        self._temp_db.close()
        self.client = TestClient(create_app(db_path=self.db_path))
        self.client.post("/api/v1/auth/register", json={"username": "weakling", "password": "password-123456"})
        token = self.client.post(
            "/api/v1/auth/login", json={"username": "weakling", "password": "password-123456"}
        ).json()["token"]
        self.headers = {"Authorization": f"Bearer {token}"}
        bank = self.client.post("/api/v1/banks", headers=self.headers, json={"name": "复习题库"}).json()
        self.bank_id = bank["id"]
        self.question = self._create_question("弱项题目")

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            path = self.db_path + suffix
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _create_question(self, stem):
        resp = self.client.post(
            f"/api/v1/banks/{self.bank_id}/questions",
            headers=self.headers,
            json={
                "stem": stem,
                "type": "SINGLE",
                "answer": "A",
                "options": [{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
            },
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _mark_weak(self, question_id):
        resp = self.client.post(f"/api/v1/learning/weak/{question_id}", headers=self.headers)
        self.assertEqual(resp.status_code, 201, resp.text)

    def test_weak_flag_outlives_its_due_card(self):
        import sqlite3

        self._mark_weak(self.question["id"])
        # Flagging weak opens the question for review today, so it is due...
        due = self.client.get("/api/v1/mistakes/due", headers=self.headers).json()
        self.assertEqual([row["question_id"] for row in due], [self.question["id"]])

        # ...but after a review pushes the card into the future the due queue
        # drops it while the flag stands. The queue's 薄弱 source must still
        # find it, which the due payload alone can never do.
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE fsrs_cards SET due_at = '2099-01-01T00:00:00+00:00'")
        self.assertEqual(self.client.get("/api/v1/mistakes/due", headers=self.headers).json(), [])
        weak = self.client.get("/api/v1/mistakes/weak", headers=self.headers).json()
        self.assertEqual(len(weak), 1)
        self.assertEqual(weak[0]["question_id"], self.question["id"])
        self.assertEqual(weak[0]["bank_id"], self.bank_id)
        self.assertTrue(weak[0]["stem"])
        self.assertTrue(weak[0]["type"])

    def test_unflagging_removes_it_from_the_weak_source(self):
        self._mark_weak(self.question["id"])
        resp = self.client.delete(f"/api/v1/learning/weak/{self.question['id']}", headers=self.headers)
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.client.get("/api/v1/mistakes/weak", headers=self.headers).json(), [])

    def test_killed_questions_stay_out_of_the_weak_source(self):
        self._mark_weak(self.question["id"])
        killed = self.client.post(
            f"/api/v1/kills/{self.question['id']}",
            headers=self.headers,
            json={"cause": "MEMORY"},
        )
        self.assertIn(killed.status_code, (200, 201), killed.text)
        self.assertEqual(self.client.get("/api/v1/mistakes/weak", headers=self.headers).json(), [])

    def test_bank_filter_applies_to_the_weak_source(self):
        self._mark_weak(self.question["id"])
        other = self.client.post("/api/v1/banks", headers=self.headers, json={"name": "另一个题库"}).json()
        self.assertEqual(
            self.client.get(f"/api/v1/mistakes/weak?bank_id={other['id']}", headers=self.headers).json(),
            [],
        )
        self.assertEqual(
            len(self.client.get(f"/api/v1/mistakes/weak?bank_id={self.bank_id}", headers=self.headers).json()),
            1,
        )


if __name__ == "__main__":
    unittest.main()
