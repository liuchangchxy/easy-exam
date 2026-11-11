"""Route-level contract for practice attempt idempotency.

The optional ``client_attempt_id`` must travel from the HTTP payload through
``PracticeService`` into the repository:

- the same key retried (even with a different payload) is one idempotent
  attempt and returns the first result;
- distinct keys for A→B→A keep three attempts and the newest result;
- legacy clients without a key keep consecutive-retry compatibility but may
  still change an answer back (no permanent per-answer deduplication);
- blank or oversized keys are rejected with 422, and the ``/answer`` alias
  forwards the key exactly like ``/attempts``.
"""
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.main import create_app


class AttemptKeyRouteContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fnexam_attempt_key_")
        self.db_path = os.path.join(self.temp_dir, "attempt_key.db")
        self.app = create_app(db_path=self.db_path)
        self.client = TestClient(self.app)

        self.client.post(
            "/api/v1/auth/register",
            json={"username": "attempt_key_user", "password": "Password123!"},
        )
        login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "attempt_key_user", "password": "Password123!"},
        )
        self.headers = {"Authorization": f"Bearer {login.json()['token']}"}

        bank = self.client.post(
            "/api/v1/banks", json={"name": "Attempt key bank"}, headers=self.headers,
        ).json()
        self.bank_id = bank["id"]
        question = self.client.post(
            f"/api/v1/banks/{self.bank_id}/questions",
            json={
                "type": "SINGLE",
                "stem": "Attempt key question",
                "options": [{"key": "A", "content": "a"}, {"key": "B", "content": "b"}],
                "answer": "A",
            },
            headers=self.headers,
        ).json()
        self.question_id = question["id"]
        self.session_id = self.client.post(
            "/api/v1/practice/sessions",
            json={"bank_id": self.bank_id, "mode": "PRACTICE", "question_ids": [self.question_id]},
            headers=self.headers,
        ).json()["id"]

    def tearDown(self):
        import gc
        import shutil
        gc.collect()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _submit(self, answer, client_attempt_id=None, path="attempts"):
        payload = {"question_id": self.question_id, "user_answer": answer}
        if client_attempt_id is not None:
            payload["client_attempt_id"] = client_attempt_id
        return self.client.post(
            f"/api/v1/practice/sessions/{self.session_id}/{path}",
            json=payload,
            headers=self.headers,
        )

    def _attempt_count(self):
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM answer_attempts WHERE session_id = ? AND question_id = ?",
                (self.session_id, self.question_id),
            ).fetchone()[0]

    def test_same_client_key_is_idempotent_through_the_route(self):
        first = self._submit("A", "route-key-1")
        self.assertEqual(first.status_code, 201)
        retry = self._submit("B", "route-key-1")

        self.assertEqual(retry.status_code, 201)
        self.assertEqual(first.json()["id"], retry.json()["id"])
        self.assertTrue(retry.json()["duplicate"])
        self.assertTrue(retry.json()["idempotent_replay"])
        self.assertEqual(self._attempt_count(), 1)

    def test_distinct_client_keys_for_a_b_a_keep_the_newest_result(self):
        first = self._submit("A", "route-a1")
        middle = self._submit("B", "route-b1")
        third = self._submit("A", "route-a2")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(middle.status_code, 201)
        self.assertEqual(third.status_code, 201)
        self.assertEqual(
            len({first.json()["id"], middle.json()["id"], third.json()["id"]}), 3,
            "不同 client_attempt_id 必须产生三次独立作答",
        )
        self.assertEqual(third.json()["correctness"], "CORRECT")
        self.assertFalse(third.json()["duplicate"])
        self.assertEqual(self._attempt_count(), 3)

    def test_legacy_client_can_change_its_answer_back_without_a_key(self):
        self.assertEqual(self._submit("A").status_code, 201)
        self.assertEqual(self._submit("B").status_code, 201)
        third = self._submit("A")

        self.assertEqual(third.status_code, 201)
        self.assertEqual(third.json()["correctness"], "CORRECT")
        self.assertFalse(third.json()["duplicate"], "合法改回答案不得被判为历史重放")
        self.assertEqual(self._attempt_count(), 3)

    def test_blank_and_oversized_client_keys_are_rejected(self):
        blank = self._submit("A", "   ")
        oversized = self._submit("A", "x" * 201)
        self.assertEqual(blank.status_code, 422)
        self.assertEqual(oversized.status_code, 422)
        self.assertEqual(self._attempt_count(), 0)

    def test_answer_alias_forwards_the_client_key(self):
        first = self._submit("A", "alias-key", path="answer")
        retry = self._submit("B", "alias-key", path="answer")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 201)
        self.assertEqual(first.json()["id"], retry.json()["id"])
        self.assertTrue(retry.json()["duplicate"])
        self.assertEqual(self._attempt_count(), 1)


if __name__ == "__main__":
    unittest.main()
