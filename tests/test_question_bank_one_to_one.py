"""Lock the product rule "一道题只属于一个题库" (question <-> bank is 1:1).

The schema keeps `bank_question_items(bank_id, question_id)` with a composite
primary key only — there is no UNIQUE index on `question_id`. The invariant is
therefore maintained by construction: `copy` creates a brand-new `questions`
row in the target bank, while `move` deletes the source item row before adding
the target one. These tests exercise the real HTTP surface and then assert the
invariant directly against the SQLite file the app was created with, so a future
implementation that starts to share one question id across two banks fails here
without needing a schema migration.

Migration 23 (decision 2 in docs/UX_CORE_REDESIGN_2026-11-13.md) additionally
enforces the invariant at the write layer with triggers on
`bank_question_items`; the cases below cover direct SQL rejection and the
upgrade path for databases that already hold historical duplicates.
"""
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing

from fastapi.testclient import TestClient

from backend.app.infrastructure.db.connection import get_connection, migrate
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

    def _membership_count(self):
        with closing(get_connection(self.db_path)) as conn:
            return conn.execute("SELECT COUNT(*) FROM bank_question_items").fetchone()[0]

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

    def test_import_creates_fresh_identities_and_keeps_one_to_one(self):
        _, headers = self._user("one_to_one_import")
        bank = self._bank(headers, "Import Bank")
        csv_content = (
            "题型,题干,选项A,选项B,正确答案,解析\n"
            "单选题,导入题一,苹果,香蕉,A,解析一\n"
            "单选题,导入题二,苹果,香蕉,B,解析二\n"
        )

        resp = self.client.post(
            f"/api/v1/imports/banks/{bank['id']}",
            headers=headers,
            json={"format": "csv", "content": csv_content, "duplicate_strategy": "skip"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(2, resp.json()["imported_count"])

        imported_ids = self._content_ids(headers, bank["id"])
        self.assertEqual(2, len(imported_ids))
        for question_id in imported_ids:
            self.assertEqual([bank["id"]], self._item_banks(question_id))
        self._assert_no_shared_question()

    # ------------------------------------------- write-layer trigger enforcement

    def test_direct_insert_of_second_membership_is_rejected(self):
        _, headers = self._user("one_to_one_trigger_insert")
        bank_a = self._bank(headers, "Trigger Source")
        bank_b = self._bank(headers, "Trigger Target")
        question = self._question(headers, bank_a["id"], "One home only")
        before = self._membership_count()

        with closing(get_connection(self.db_path)) as conn:
            with self.assertRaises(sqlite3.IntegrityError) as ctx:
                conn.execute(
                    "INSERT INTO bank_question_items(bank_id, question_id) VALUES (?, ?)",
                    (bank_b["id"], question["id"]),
                )
            conn.rollback()

        self.assertIn("already belongs to a bank", str(ctx.exception))
        self.assertEqual(before, self._membership_count(), "rejected insert must not add a row")
        self.assertEqual([bank_a["id"]], self._item_banks(question["id"]))
        self._assert_no_shared_question()

    def test_repository_maps_second_membership_to_domain_conflict(self):
        from backend.app.infrastructure.db.repositories.question_repository import (
            QuestionBankConflictError,
            QuestionRepository,
        )

        _, headers = self._user("one_to_one_conflict_mapping")
        bank_a = self._bank(headers, "Mapping Source")
        bank_b = self._bank(headers, "Mapping Target")
        question = self._question(headers, bank_a["id"], "Mapping home")

        with closing(get_connection(self.db_path)) as conn:
            with self.assertRaises(QuestionBankConflictError):
                QuestionRepository._insert_bank_question_item(conn, bank_b["id"], question["id"])
            conn.rollback()

        # Routes catch ValueError (banks.py, imports.py), so this is a 4xx.
        self.assertTrue(issubclass(QuestionBankConflictError, ValueError))
        self.assertEqual([bank_a["id"]], self._item_banks(question["id"]))
        self._assert_no_shared_question()

    def test_update_question_id_to_existing_membership_is_rejected(self):
        _, headers = self._user("one_to_one_trigger_update")
        bank_a = self._bank(headers, "Update Source")
        bank_b = self._bank(headers, "Update Target")
        first = self._question(headers, bank_a["id"], "First home")
        second = self._question(headers, bank_b["id"], "Second home")
        before = self._membership_count()

        with closing(get_connection(self.db_path)) as conn:
            with self.assertRaises(sqlite3.IntegrityError) as ctx:
                conn.execute(
                    "UPDATE bank_question_items SET question_id = ? WHERE question_id = ?",
                    (first["id"], second["id"]),
                )
            conn.rollback()
            self.assertEqual([bank_b["id"]], [
                row["bank_id"]
                for row in conn.execute(
                    "SELECT bank_id FROM bank_question_items WHERE question_id = ?",
                    (second["id"],),
                ).fetchall()
            ])
            # Writing the same value back must not trip the guard.
            conn.execute(
                "UPDATE bank_question_items SET question_id = question_id WHERE question_id = ?",
                (first["id"],),
            )
            conn.commit()

        self.assertIn("already belongs to a bank", str(ctx.exception))
        self.assertEqual(before, self._membership_count(), "rejected update must not move a row")
        self.assertEqual([bank_a["id"]], self._item_banks(first["id"]))
        self._assert_no_shared_question()

    def test_migration_23_upgrades_legacy_duplicates_without_touching_them(self):
        import backend.app.infrastructure.db.connection as conn_mod

        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "legacy_duplicate.db")

            # Build a v22-shaped database: the pre-trigger schema allowed one
            # question to be linked to two banks.
            original = dict(conn_mod.MIGRATIONS)
            try:
                conn_mod.MIGRATIONS = {v: sql for v, sql in original.items() if v <= 22}
                migrate(db_path)
            finally:
                conn_mod.MIGRATIONS = original

            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    "INSERT INTO users(id, username, password_hash) VALUES ('legacy-user', 'legacy_user', 'x')"
                )
                conn.execute(
                    "INSERT INTO question_banks(id, name, created_by) VALUES "
                    "('legacy-bank-a', 'Legacy A', 'legacy-user'), "
                    "('legacy-bank-b', 'Legacy B', 'legacy-user'), "
                    "('legacy-bank-c', 'Legacy C', 'legacy-user')"
                )
                conn.execute(
                    "INSERT INTO questions(id, created_by) VALUES ('legacy-q', 'legacy-user')"
                )
                conn.execute(
                    "INSERT INTO bank_question_items(bank_id, question_id) "
                    "VALUES ('legacy-bank-a', 'legacy-q'), ('legacy-bank-b', 'legacy-q')"
                )
                conn.commit()
                self.assertEqual(
                    2,
                    conn.execute(
                        "SELECT COUNT(*) FROM bank_question_items WHERE question_id = 'legacy-q'"
                    ).fetchone()[0],
                    "precondition: the v22 schema must accept the legacy duplicate",
                )
            finally:
                conn.close()

            migrate(db_path)
            migrate(db_path)  # idempotent: schema_migrations prevents a re-run

            with closing(get_connection(db_path)) as conn:
                legacy_rows = conn.execute(
                    "SELECT bank_id FROM bank_question_items "
                    "WHERE question_id = 'legacy-q' ORDER BY bank_id"
                ).fetchall()
                self.assertEqual(
                    ["legacy-bank-a", "legacy-bank-b"],
                    [row["bank_id"] for row in legacy_rows],
                    "upgrade must not delete or re-home legacy duplicate rows",
                )
                triggers = {
                    row["name"]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                    ).fetchall()
                }
                self.assertIn("trg_bank_question_single_bank", triggers)
                self.assertIn("trg_bank_question_single_bank_update", triggers)

                count_before = conn.execute(
                    "SELECT COUNT(*) FROM bank_question_items"
                ).fetchone()[0]
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        "INSERT INTO bank_question_items(bank_id, question_id) "
                        "VALUES ('legacy-bank-c', 'legacy-q')"
                    )
                conn.rollback()
                self.assertEqual(
                    count_before,
                    conn.execute("SELECT COUNT(*) FROM bank_question_items").fetchone()[0],
                    "the new trigger must guard writes after a legacy upgrade",
                )


if __name__ == "__main__":
    unittest.main()
