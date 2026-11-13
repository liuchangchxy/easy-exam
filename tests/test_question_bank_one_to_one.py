"""Lock the product rule "一道题只属于一个题库" (question <-> bank is 1:1).

The schema keeps `bank_question_items(bank_id, question_id)` with a composite
primary key only — there is no UNIQUE index on `question_id`. The invariant is
therefore maintained by construction: `copy` creates a brand-new `questions`
row in the target bank, while `move` deletes the source item row before adding
the target one. These tests exercise the real HTTP surface and then assert the
invariant directly against the SQLite file the app was created with, so a future
implementation that starts to share one question id across two banks fails here
without needing a schema migration.
"""
import os
import tempfile
import unittest
from contextlib import closing

from fastapi.testclient import TestClient

from backend.app.infrastructure.db.connection import get_connection
from backend.app.main import create_app


class QuestionBankOneToOneTests(unittest.TestCase):
    def setUp(self):
        self._temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self._temp_db.name
        self._temp_db.close()
        self.app = create_app(db_path=self.db_path)
        self.client = TestClient(self.app)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass
        for suffix in ("-wal", "-shm"):
            path = self.db_path + suffix
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    # ------------------------------------------------------------------ helpers

    def _user(self, username):
        self.client.post("/api/v1/auth/register", json={"username": username, "password": "Password123!"})
        payload = self.client.post(
            "/api/v1/auth/login", json={"username": username, "password": "Password123!"}
        ).json()
        return payload["token"], {"Authorization": f"Bearer {payload['token']}"}

    def _bank(self, headers, name):
        resp = self.client.post("/api/v1/banks", headers=headers, json={"name": name, "category": "Test"})
        assert resp.status_code == 201, resp.text
        return resp.json()

    def _question(self, headers, bank_id, stem):
        resp = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            headers=headers,
            json={
                "stem": stem,
                "type": "SINGLE",
                "options": [{"key": "A", "content": "one"}, {"key": "B", "content": "two"}],
                "answer": "A",
                "explanation": "because",
                "difficulty": 2,
                "tags": [],
                "chapter_id": None,
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    def _content_ids(self, headers, bank_id):
        resp = self.client.get(f"/api/v1/banks/{bank_id}/content/questions", headers=headers)
        assert resp.status_code == 200, resp.text
        return [q["id"] for q in resp.json()]

    def _practice_ids(self, headers, bank_id):
        resp = self.client.get(f"/api/v1/banks/{bank_id}/questions", headers=headers)
        assert resp.status_code == 200, resp.text
        return [q["id"] for q in resp.json()]

    def _item_banks(self, question_id):
        with closing(get_connection(self.db_path)) as conn:
            rows = conn.execute(
                "SELECT bank_id FROM bank_question_items WHERE question_id = ? ORDER BY bank_id",
                (question_id,),
            ).fetchall()
        return [row["bank_id"] for row in rows]

    def _assert_no_shared_question(self):
        """No question_id may belong to more than one bank."""
        with closing(get_connection(self.db_path)) as conn:
            duplicates = conn.execute(
                """SELECT question_id, COUNT(*) AS c
                   FROM bank_question_items
                   GROUP BY question_id
                   HAVING c > 1"""
            ).fetchall()
        self.assertEqual(
            [],
            [(row["question_id"], row["c"]) for row in duplicates],
            "a question must never be linked to more than one bank",
        )

    # -------------------------------------------------------------------- tests

    def test_single_copy_creates_new_question_id_in_target_only(self):
        _, headers = self._user("one_to_one_copy")
        bank_a = self._bank(headers, "Copy Source")
        bank_b = self._bank(headers, "Copy Target")
        original = self._question(headers, bank_a["id"], "Copy me")

        resp = self.client.post(
            f"/api/v1/banks/{bank_b['id']}/questions/{original['id']}/copy", headers=headers
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        copied_id = resp.json()["id"]
        self.assertNotEqual(copied_id, original["id"], "copy must allocate a new question identity")

        self.assertEqual([original["id"]], self._content_ids(headers, bank_a["id"]))
        self.assertEqual([copied_id], self._content_ids(headers, bank_b["id"]))

        # DB: each identity is linked to exactly one bank, the original stays in A.
        self.assertEqual([bank_a["id"]], self._item_banks(original["id"]))
        self.assertEqual([bank_b["id"]], self._item_banks(copied_id))
        self._assert_no_shared_question()

    def test_single_batch_move_relocates_identity_without_duplicating_links(self):
        _, headers = self._user("one_to_one_move")
        bank_a = self._bank(headers, "Move Source")
        bank_b = self._bank(headers, "Move Target")
        question = self._question(headers, bank_a["id"], "Move me")

        resp = self.client.post(
            f"/api/v1/banks/{bank_a['id']}/questions/batch",
            headers=headers,
            json={
                "operation": "move",
                "question_ids": [question["id"]],
                "target_bank_id": bank_b["id"],
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        self.assertIn(question["id"], self._content_ids(headers, bank_b["id"]))
        self.assertNotIn(question["id"], self._content_ids(headers, bank_a["id"]))
        self.assertNotIn(
            question["id"],
            self._practice_ids(headers, bank_a["id"]),
            "GET /banks/{id}/questions must no longer expose a moved question",
        )

        # The same identity now maps to exactly one bank: the target.
        self.assertEqual([bank_b["id"]], self._item_banks(question["id"]))
        self._assert_no_shared_question()

    def test_batch_copy_creates_new_identity_and_preserves_one_to_one(self):
        _, headers = self._user("one_to_one_batch_copy")
        bank_a = self._bank(headers, "Batch Copy Source")
        bank_b = self._bank(headers, "Batch Copy Target")
        original = self._question(headers, bank_a["id"], "Batch copy me")

        resp = self.client.post(
            f"/api/v1/banks/{bank_a['id']}/questions/batch",
            headers=headers,
            json={
                "operation": "copy",
                "question_ids": [original["id"]],
                "target_bank_id": bank_b["id"],
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        self.assertIn(original["id"], self._content_ids(headers, bank_a["id"]))
        target_ids = self._content_ids(headers, bank_b["id"])
        self.assertEqual(1, len(target_ids), target_ids)
        copied_id = target_ids[0]
        self.assertNotEqual(copied_id, original["id"])

        self.assertEqual([bank_a["id"]], self._item_banks(original["id"]))
        self.assertEqual([bank_b["id"]], self._item_banks(copied_id))
        self._assert_no_shared_question()


if __name__ == "__main__":
    unittest.main()
