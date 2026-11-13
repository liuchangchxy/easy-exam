"""Regression coverage for first-class session outcomes (migration 20).

A completed practice/exam session must keep its report, expose it through the
session API, distinguish ``completed`` from ``abandoned``, and let mock-exam
mistakes enter the review queue exactly once.
"""
import os
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.infrastructure.db.connection import MIGRATIONS, migrate
from backend.app.main import create_app


class SessionReportPersistenceTests(unittest.TestCase):
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
        self.client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": "Password123!"},
        )
        payload = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "Password123!"},
        ).json()
        return payload["user"]["id"], {"Authorization": f"Bearer {payload['token']}"}

    def _bank(self, headers, name):
        resp = self.client.post("/api/v1/banks", headers=headers, json={"name": name})
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _question(self, headers, bank_id, stem, answer="A"):
        resp = self.client.post(
            f"/api/v1/banks/{bank_id}/questions",
            headers=headers,
            json={
                "stem": stem,
                "type": "SINGLE",
                "options": [{"key": "A", "content": "one"}, {"key": "B", "content": "two"}],
                "answer": answer,
                "explanation": "because",
                "difficulty": 2,
                "tags": [],
            },
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _start(self, headers, bank_id, question_ids, mode="PRACTICE", record_mistakes=None):
        body = {
            "bank_id": bank_id,
            "mode": mode,
            "total_questions": len(question_ids),
            "question_ids": question_ids,
        }
        if record_mistakes is not None:
            body["record_mistakes"] = record_mistakes
        resp = self.client.post("/api/v1/practice/sessions", headers=headers, json=body)
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _submit(self, headers, session_id, question_id, answer):
        resp = self.client.post(
            f"/api/v1/practice/sessions/{session_id}/attempts",
            headers=headers,
            json={"question_id": question_id, "user_answer": answer},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _complete(self, headers, session_id):
        resp = self.client.post(
            f"/api/v1/practice/sessions/{session_id}/complete", headers=headers
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    def _stored_session(self, session_id):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM practice_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _fsrs_rows(self, user_id):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM fsrs_cards WHERE user_id = ? ORDER BY question_id",
                    (user_id,),
                ).fetchall()
            ]
        finally:
            conn.close()

    # ------------------------------------------------------------------- tests

    def test_complete_report_is_persisted_and_exposed_by_get_session(self):
        user_id, headers = self._user("report_persist")
        bank = self._bank(headers, "Persist Bank")
        q1 = self._question(headers, bank["id"], "Q1")
        q2 = self._question(headers, bank["id"], "Q2")

        session = self._start(headers, bank["id"], [q1["id"], q2["id"]])
        self._submit(headers, session["id"], q1["id"], "A")
        self._submit(headers, session["id"], q2["id"], "B")

        report = self._complete(headers, session["id"])

        self.assertEqual(report["score"], 1.0)
        self.assertEqual(report["accuracy"], 50.0)
        self.assertEqual(report["total_questions"], 2)
        self.assertEqual(report["answered_count"], 2)
        self.assertEqual(report["correct_count"], 1)
        self.assertEqual(report["incorrect_count"], 1)
        self.assertEqual(report["unanswered_count"], 0)
        self.assertEqual(report["answers"][q1["id"]]["correctness"], "CORRECT")
        self.assertEqual(report["answers"][q2["id"]]["correctness"], "INCORRECT")

        stored = self._stored_session(session["id"])
        self.assertIsNotNone(stored["result_json"], "the completed report must be persisted")
        self.assertEqual(stored["score"], 1.0)
        self.assertEqual(stored["time_spent"], report["time_spent"])

        fetched = self.client.get(
            f"/api/v1/practice/sessions/{session['id']}", headers=headers
        )
        self.assertEqual(fetched.status_code, 200, fetched.text)
        body = fetched.json()
        self.assertIn("report", body)
        self.assertEqual(
            body["report"],
            report,
            "GET /sessions/{id} must expose the same report that complete returned",
        )

    def test_status_transitions_and_completed_at(self):
        _user_id, headers = self._user("status_flow")
        bank = self._bank(headers, "Status Bank")
        question = self._question(headers, bank["id"], "Status question")

        active = self._start(headers, bank["id"], [question["id"]])
        row = self._stored_session(active["id"])
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["is_completed"], 0)
        self.assertIsNone(row["completed_at"])

        abandoned_resp = self.client.post(
            f"/api/v1/practice/sessions/{active['id']}/abandon", headers=headers
        )
        self.assertEqual(abandoned_resp.status_code, 200, abandoned_resp.text)
        row = self._stored_session(active["id"])
        self.assertEqual(row["status"], "abandoned")
        self.assertEqual(row["is_completed"], 1, "is_completed stays the derived visibility column")
        self.assertIsNone(row["completed_at"], "abandoning is not completing")

        finishing = self._start(headers, bank["id"], [question["id"]])
        self._submit(headers, finishing["id"], question["id"], "A")
        report = self._complete(headers, finishing["id"])
        self.assertTrue(report["is_completed"])

        row = self._stored_session(finishing["id"])
        self.assertEqual(row["status"], "completed")
        self.assertEqual(row["is_completed"], 1)
        self.assertTrue(row["completed_at"], "completion must record a timestamp")

        body = self.client.get(
            f"/api/v1/practice/sessions/{finishing['id']}", headers=headers
        ).json()
        self.assertEqual(body["status"], "completed")
        self.assertTrue(body["completed_at"])
        self.assertEqual(body["is_completed"], True)

    def test_repeated_complete_returns_identical_report_without_rescheduling(self):
        user_id, headers = self._user("repeat_complete")
        bank = self._bank(headers, "Repeat Bank")
        question = self._question(headers, bank["id"], "Wrong answer")

        session = self._start(
            headers, bank["id"], [question["id"]], mode="EXAM", record_mistakes=True
        )
        self._submit(headers, session["id"], question["id"], "B")
        self.assertEqual(self._fsrs_rows(user_id), [], "exams do not schedule per-answer FSRS")

        first = self._complete(headers, session["id"])
        cards_after_first = self._fsrs_rows(user_id)
        self.assertEqual(len(cards_after_first), 1, "the exam mistake must enter the review queue")

        second = self._complete(headers, session["id"])
        self.assertEqual(second, first, "repeated completion must return the stored report verbatim")
        self.assertEqual(
            self._fsrs_rows(user_id),
            cards_after_first,
            "repeated completion must not reschedule FSRS",
        )

    def test_exam_record_mistakes_controls_completion_time_fsrs(self):
        user_id, headers = self._user("exam_fsrs")
        bank = self._bank(headers, "Exam FSRS Bank")
        recorded = self._question(headers, bank["id"], "Recorded mistake")
        ignored = self._question(headers, bank["id"], "Ignored mistake")

        with_mistakes = self._start(
            headers, bank["id"], [recorded["id"]], mode="EXAM", record_mistakes=True
        )
        self._submit(headers, with_mistakes["id"], recorded["id"], "B")
        self._complete(headers, with_mistakes["id"])

        cards = {row["question_id"]: row for row in self._fsrs_rows(user_id)}
        self.assertIn(recorded["id"], cards, "record_mistakes=True must schedule the mistake")

        without_mistakes = self._start(
            headers, bank["id"], [ignored["id"]], mode="EXAM", record_mistakes=False
        )
        self._submit(headers, without_mistakes["id"], ignored["id"], "B")
        self._complete(headers, without_mistakes["id"])

        cards = {row["question_id"]: row for row in self._fsrs_rows(user_id)}
        self.assertNotIn(
            ignored["id"],
            cards,
            "record_mistakes=False must never schedule exam mistakes",
        )

    def test_migration_backfills_completed_sessions_and_creates_index(self):
        import backend.app.infrastructure.db.connection as conn_mod

        with tempfile.TemporaryDirectory() as tmp:
            fresh_path = os.path.join(tmp, "fresh.db")
            migrate(fresh_path)
            conn = sqlite3.connect(fresh_path)
            try:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(practice_sessions)")}
                self.assertTrue({"status", "completed_at", "result_json"} <= columns)
                index = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index' "
                    "AND name = 'idx_practice_sessions_user_status'"
                ).fetchone()
                self.assertIsNotNone(index, "migration 20 must create the status index")
            finally:
                conn.close()

            pre_path = os.path.join(tmp, "pre20.db")
            original = dict(conn_mod.MIGRATIONS)
            try:
                conn_mod.MIGRATIONS = {
                    version: sql for version, sql in original.items() if version <= 19
                }
                migrate(pre_path)
            finally:
                conn_mod.MIGRATIONS = original

            conn = sqlite3.connect(pre_path)
            try:
                conn.execute(
                    "INSERT INTO users(id, username, password_hash) VALUES ('u1', 'u1', 'x')"
                )
                conn.execute(
                    "INSERT INTO question_banks(id, name, created_by) VALUES ('b1', 'B', 'u1')"
                )
                conn.execute(
                    "INSERT INTO practice_sessions("
                    "id, user_id, bank_id, mode, is_completed, created_at, updated_at"
                    ") VALUES ('s-done', 'u1', 'b1', 'PRACTICE', 1, "
                    "'2020-01-01 00:00:00', '2020-02-03 04:05:06')"
                )
                conn.execute(
                    "INSERT INTO practice_sessions("
                    "id, user_id, bank_id, mode, is_completed, created_at, updated_at"
                    ") VALUES ('s-active', 'u1', 'b1', 'PRACTICE', 0, "
                    "'2020-01-01 00:00:00', '2020-02-03 04:05:06')"
                )
                conn.commit()
                columns = {row[1] for row in conn.execute("PRAGMA table_info(practice_sessions)")}
                self.assertNotIn("status", columns, "precondition: migration 20 is not applied yet")
            finally:
                conn.close()

            migrate(pre_path)
            # Idempotency: a second run must not fail or duplicate the version row.
            migrate(pre_path)

            conn = sqlite3.connect(pre_path)
            try:
                rows = {
                    row[0]: row
                    for row in conn.execute(
                        "SELECT id, status, completed_at, is_completed FROM practice_sessions"
                    )
                }
                self.assertEqual(rows["s-done"][1], "completed")
                self.assertEqual(
                    rows["s-done"][2],
                    "2020-02-03 04:05:06",
                    "backfill must use updated_at as the completion time",
                )
                self.assertEqual(rows["s-active"][1], "active")
                self.assertIsNone(rows["s-active"][2])
                versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations")]
                self.assertEqual(versions.count(20), 1)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
