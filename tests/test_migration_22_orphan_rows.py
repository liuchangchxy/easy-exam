"""Migration 22 must survive a database whose history predates FK enforcement.

Production carried an `import_jobs` row whose user had been deleted long ago.
Migration 22 rebuilds that table, and re-inserting the orphan under foreign-key
enforcement aborted the whole upgrade (observed on a copy of the live fnOS
database, 2026-11-13). SQLite's documented rebuild procedure runs with foreign
keys disabled for exactly this reason, so the runner now does that for rebuild
migrations and restores enforcement immediately afterwards.
"""
import os
import sqlite3
import tempfile
import unittest

from backend.app.infrastructure.db.connection import (
    MIGRATIONS,
    _split_sql_statements,
    get_connection,
    migrate,
)

ORPHAN_USER = "user-that-was-deleted"
ORPHAN_JOB = "job-orphaned-by-user-deletion"
VALID_USER = "user-still-present"
VALID_JOB = "job-with-live-owner"


def _build_v21_database(path: str) -> None:
    conn = get_connection(path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        for version in range(1, 22):
            conn.execute("BEGIN IMMEDIATE")
            for statement in _split_sql_statements(MIGRATIONS[version]):
                conn.execute(statement)
            conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
            conn.commit()

        # Older releases could write this row while enforcement was off; the
        # test has to recreate that state the same way.
        conn.commit()
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "INSERT INTO users(id, username, password_hash) VALUES (?, ?, ?)",
            (VALID_USER, "survivor", "hash"),
        )
        conn.execute(
            "INSERT INTO question_banks(id, name, created_by) VALUES (?, ?, ?)",
            ("bank-1", "验收题库", VALID_USER),
        )
        # The orphan is already an FK violation, exactly like the production row;
        # it only exists because older code could leave it behind.
        conn.execute(
            "INSERT INTO import_jobs(id, user_id, bank_id, filename, format, status, imported_count)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ORPHAN_JOB, ORPHAN_USER, "bank-1", "legacy.xlsx", "xlsx", "IMPORTED", 141),
        )
        conn.execute(
            "INSERT INTO import_jobs(id, user_id, bank_id, filename, format, status, imported_count)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (VALID_JOB, VALID_USER, "bank-1", "ok.csv", "csv", "IMPORTED", 3),
        )
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")
    finally:
        conn.close()


class Migration22OrphanRowsTest(unittest.TestCase):
    def test_rebuild_preserves_an_orphaned_import_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "orphans.db")
            _build_v21_database(path)

            migrate(path)

            conn = get_connection(path)
            try:
                version = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
                self.assertEqual(version, 23, "迁移不能因为历史孤儿行停在 22 之前")
                rows = {
                    row["id"]: dict(row)
                    for row in conn.execute("SELECT * FROM import_jobs")
                }
                self.assertIn(VALID_JOB, rows)
                self.assertIn(
                    ORPHAN_JOB,
                    rows,
                    "孤儿导入任务必须原样保留，迁移不能删除用户数据",
                )
                self.assertEqual(rows[ORPHAN_JOB]["user_id"], ORPHAN_USER)
                self.assertEqual(rows[ORPHAN_JOB]["imported_count"], 141)
                self.assertEqual(rows[ORPHAN_JOB]["status"], "IMPORTED")
                self.assertEqual(rows[ORPHAN_JOB]["progress"], 0, "新列使用默认值")
                self.assertEqual(rows[ORPHAN_JOB]["total"], 0)
            finally:
                conn.close()

    def test_foreign_keys_are_enforced_again_after_the_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fk-restored.db")
            _build_v21_database(path)
            migrate(path)

            conn = get_connection(path)
            try:
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        "INSERT INTO import_jobs(id, user_id, format, status)"
                        " VALUES ('new-orphan', 'missing-user', 'csv', 'PENDING')"
                    )
            finally:
                conn.close()
