"""Regression coverage for the question `archived_at` timestamp (migration 19).

Archiving must stay semantically distinct from deletion: `is_deleted` remains
the visibility source of truth, while `archived_at` records when archiving
happened so callers can tell "put away" apart from "deleted".
"""
import os
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.infrastructure.db.connection import MIGRATIONS, migrate
from backend.app.main import create_app


class ArchiveTimestampTests(unittest.TestCase):
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

    # ----------------------------------------------------------------- helpers

    def _user(self, username):
        self.client.post("/api/v1/auth/register", json={"username": username, "password": "Password123!"})
        payload = self.client.post(
            "/api/v1/auth/login", json={"username": username, "password": "Password123!"}
        ).json()
        return payload["token"], {"Authorization": f"Bearer {payload['token']}"}

    def _bank(self, headers, name):
        resp = self.client.post("/api/v1/banks", headers=headers, json={"name": name, "category": "Test"})
        self.assertEqual(resp.status_code, 201, resp.text)
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
            },
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _batch(self, headers, bank_id, payload):
        return self.client.post(f"/api/v1/banks/{bank_id}/questions/batch", headers=headers, json=payload)

    def _content(self, headers, bank_id, include_archived=False):
        query = "?include_archived=true" if include_archived else ""
        resp = self.client.get(f"/api/v1/banks/{bank_id}/content/questions{query}", headers=headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    def _detail(self, headers, question_id):
        resp = self.client.get(f"/api/v1/questions/{question_id}", headers=headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    # ------------------------------------------------------------------- tests

    def test_archive_sets_timestamp_and_restore_clears_it(self):
        _, headers = self._user("archive_timestamp")
        bank = self._bank(headers, "Archive Timestamp Bank")
        question = self._question(headers, bank["id"], "Archive me")

        before = self._detail(headers, question["id"])
        self.assertFalse(before["archived"])
        self.assertIn("archived_at", before)
        self.assertIsNone(before["archived_at"])

        archived = self._batch(
            headers, bank["id"], {"question_ids": [question["id"]], "operation": "archive"}
        )
        self.assertEqual(archived.status_code, 200, archived.text)

        detail = self._detail(headers, question["id"])
        self.assertTrue(detail["archived"])
        self.assertTrue(detail["archived_at"], "archiving must record a timestamp")

        content = {row["id"]: row for row in self._content(headers, bank["id"], include_archived=True)}
        self.assertIn(question["id"], content)
        self.assertTrue(content[question["id"]]["archived"])
        self.assertIn("archived_at", content[question["id"]])
        self.assertEqual(content[question["id"]]["archived_at"], detail["archived_at"])

        # Default content listing still hides archived rows (visibility unchanged).
        visible_ids = {row["id"] for row in self._content(headers, bank["id"])}
        self.assertNotIn(question["id"], visible_ids)

        restored = self._batch(
            headers, bank["id"], {"question_ids": [question["id"]], "operation": "restore"}
        )
        self.assertEqual(restored.status_code, 200, restored.text)

        detail = self._detail(headers, question["id"])
        self.assertFalse(detail["archived"])
        self.assertIsNone(detail["archived_at"], "restoring must clear the archive timestamp")

        content = {row["id"]: row for row in self._content(headers, bank["id"], include_archived=True)}
        self.assertFalse(content[question["id"]]["archived"])
        self.assertIsNone(content[question["id"]]["archived_at"])

    def test_migration_is_idempotent_and_backfills_archived_rows(self):
        import backend.app.infrastructure.db.connection as conn_mod

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "pre_archive_timestamp.db")

            # Build a pre-migration-19 database using the real runner, then stop
            # before version 19 so the ALTER/backfill path can be exercised.
            original = dict(conn_mod.MIGRATIONS)
            try:
                conn_mod.MIGRATIONS = {v: sql for v, sql in original.items() if v <= 18}
                migrate(db_path)
            finally:
                conn_mod.MIGRATIONS = original

            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    "INSERT INTO users(id, username, password_hash, created_at, updated_at) "
                    "VALUES ('u-archive', 'archive_user', 'x', '2020-01-01 00:00:00', '2020-01-01 00:00:00')"
                )
                conn.execute(
                    "INSERT INTO questions(id, created_by, is_deleted, created_at, updated_at) "
                    "VALUES ('q-archived', 'u-archive', 1, '2020-01-01 00:00:00', '2020-02-03 04:05:06')"
                )
                conn.execute(
                    "INSERT INTO questions(id, created_by, is_deleted, created_at, updated_at) "
                    "VALUES ('q-active', 'u-archive', 0, '2020-01-01 00:00:00', '2020-02-03 04:05:06')"
                )
                conn.commit()
                columns = {row[1] for row in conn.execute("PRAGMA table_info(questions)")}
                self.assertNotIn("archived_at", columns, "precondition: column must not exist before migration 19")
            finally:
                conn.close()

            migrate(db_path)
            # Idempotency: a second run must not fail or duplicate the version row.
            migrate(db_path)

            conn = sqlite3.connect(db_path)
            try:
                rows = {
                    row[0]: row
                    for row in conn.execute(
                        "SELECT id, is_deleted, archived_at, updated_at FROM questions"
                    )
                }
                self.assertEqual(
                    rows["q-archived"][2], "2020-02-03 04:05:06",
                    "backfill must copy updated_at for rows already archived",
                )
                self.assertIsNone(rows["q-active"][2], "active rows must not be backfilled")
                versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations")]
                self.assertEqual(versions.count(19), 1)
                self.assertEqual(versions.count(18), 1)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
