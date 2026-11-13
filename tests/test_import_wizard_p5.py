"""P5 import wizard: resumable drafts and cancellable asynchronous jobs."""

import os
import sqlite3
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from backend.app.main import create_app


def _question_text(index: int) -> str:
    return (
        f"{index}. 第 {index} 题：以下说法正确的是？\n"
        "A. 选项甲\n"
        "B. 选项乙\n"
        "C. 选项丙\n"
        "D. 选项丁\n"
        "【答案】A\n\n"
    )


def _question_batch(count: int) -> str:
    return "".join(_question_text(i) for i in range(1, count + 1))


class ImportWizardP5Test(unittest.TestCase):
    def setUp(self):
        self._temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self._temp_db.name
        self._temp_db.close()
        self.client = TestClient(create_app(db_path=self.db_path))
        self.owner_headers = self._register("owner")
        self.owner_bank = self.client.post(
            "/api/v1/banks", headers=self.owner_headers, json={"name": "导入向导题库"}
        ).json()
        self.bank_id = self.owner_bank["id"]

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            path = self.db_path + suffix
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    # ------------------------------------------------------------------ helpers

    def _register(self, username: str) -> dict:
        self.client.post(
            "/api/v1/auth/register", json={"username": username, "password": "password-123456"}
        )
        token = self.client.post(
            "/api/v1/auth/login", json={"username": username, "password": "password-123456"}
        ).json()["token"]
        return {"Authorization": f"Bearer {token}"}

    def _add_member(self, username: str, role: str = "MEMBER") -> dict:
        headers = self._register(username)
        resp = self.client.post(
            f"/api/v1/banks/{self.bank_id}/members",
            headers=self.owner_headers,
            json={"username": username, "role": role},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return headers

    def _draft(self, **overrides):
        payload = {"source_kind": "file", "filename": "questions.csv", "step": 1, "state": {"mapping": {"stem": 0}}}
        payload.update(overrides)
        resp = self.client.post(f"/api/v1/imports/banks/{self.bank_id}/drafts", headers=self.owner_headers, json=payload)
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _wait_job(self, job_id: str, headers: dict | None = None, deadline: float = 10.0) -> dict:
        headers = headers or self.owner_headers
        end = time.time() + deadline
        last = None
        while time.time() < end:
            resp = self.client.get(f"/api/v1/imports/jobs/{job_id}", headers=headers)
            self.assertEqual(resp.status_code, 200, resp.text)
            last = resp.json()
            if last["status"] not in ("PENDING", "RUNNING"):
                return last
            time.sleep(0.02)
        self.fail(f"job {job_id} did not finish within {deadline}s: {last}")

    def _question_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM bank_question_items WHERE bank_id = ?", (self.bank_id,)
            ).fetchone()[0]

    # --------------------------------------------------------------- draft CRUD

    def test_draft_create_list_get_update_delete(self):
        created = self._draft()
        self.assertEqual(created["bank_id"], self.bank_id)
        self.assertEqual(created["filename"], "questions.csv")
        self.assertEqual(created["state"], {"mapping": {"stem": 0}})
        self.assertEqual(created["status"], "OPEN")

        listed = self.client.get(
            f"/api/v1/imports/banks/{self.bank_id}/drafts", headers=self.owner_headers
        ).json()
        self.assertEqual([row["id"] for row in listed], [created["id"]])
        self.assertNotIn("state", listed[0])

        fetched = self.client.get(f"/api/v1/imports/drafts/{created['id']}", headers=self.owner_headers).json()
        self.assertEqual(fetched["state"], {"mapping": {"stem": 0}})
        self.assertEqual(fetched["step"], 1)

        updated = self.client.put(
            f"/api/v1/imports/drafts/{created['id']}",
            headers=self.owner_headers,
            json={"step": 3, "state": {"mapping": {"stem": 1}, "confirmed": True}},
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        body = updated.json()
        self.assertEqual(body["step"], 3)
        self.assertEqual(body["state"], {"mapping": {"stem": 1}, "confirmed": True})
        # Omitted fields stay untouched.
        self.assertEqual(body["filename"], "questions.csv")
        self.assertEqual(body["source_kind"], "file")

        deleted = self.client.delete(f"/api/v1/imports/drafts/{created['id']}", headers=self.owner_headers)
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(
            self.client.get(f"/api/v1/imports/drafts/{created['id']}", headers=self.owner_headers).status_code, 404
        )
        self.assertEqual(
            self.client.delete(f"/api/v1/imports/drafts/{created['id']}", headers=self.owner_headers).status_code, 404
        )

    def test_draft_status_filtering_hides_consumed_by_default(self):
        keep = self._draft(filename="open.csv")
        consumed = self._draft(filename="done.csv")
        self.client.put(
            f"/api/v1/imports/drafts/{consumed['id']}",
            headers=self.owner_headers,
            json={"status": "CONSUMED"},
        )
        default_list = self.client.get(
            f"/api/v1/imports/banks/{self.bank_id}/drafts", headers=self.owner_headers
        ).json()
        self.assertEqual([row["id"] for row in default_list], [keep["id"]])

        consumed_list = self.client.get(
            f"/api/v1/imports/banks/{self.bank_id}/drafts?status=CONSUMED", headers=self.owner_headers
        ).json()
        self.assertEqual([row["id"] for row in consumed_list], [consumed["id"]])
        # History stays readable by id even though it is not listed by default.
        self.assertEqual(
            self.client.get(f"/api/v1/imports/drafts/{consumed['id']}", headers=self.owner_headers).json()["status"],
            "CONSUMED",
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/imports/banks/{self.bank_id}/drafts?status=BOGUS", headers=self.owner_headers
            ).status_code,
            422,
        )

    def test_draft_state_over_two_megabytes_is_rejected(self):
        huge = {"blob": "x" * (2 * 1024 * 1024 + 1)}
        resp = self.client.post(
            f"/api/v1/imports/banks/{self.bank_id}/drafts",
            headers=self.owner_headers,
            json={"source_kind": "file", "state": huge},
        )
        self.assertEqual(resp.status_code, 413, resp.text)

        draft = self._draft()
        resp = self.client.put(
            f"/api/v1/imports/drafts/{draft['id']}", headers=self.owner_headers, json={"state": huge}
        )
        self.assertEqual(resp.status_code, 413, resp.text)

    def test_draft_access_is_isolated_by_owner_and_bank_role(self):
        draft = self._draft()
        stranger = self._register("stranger")
        for method, path, kwargs in (
            ("get", f"/api/v1/imports/drafts/{draft['id']}", {}),
            ("put", f"/api/v1/imports/drafts/{draft['id']}", {"json": {"step": 9}}),
            ("delete", f"/api/v1/imports/drafts/{draft['id']}", {}),
        ):
            resp = getattr(self.client, method)(path, headers=stranger, **kwargs)
            self.assertEqual(resp.status_code, 404, f"{method} leaked another user's draft: {resp.text}")

        # A MEMBER of the bank still may not import.
        member = self._add_member("reader", "MEMBER")
        resp = self.client.post(
            f"/api/v1/imports/banks/{self.bank_id}/drafts", headers=member, json={"state": {}}
        )
        self.assertEqual(resp.status_code, 403, resp.text)

        # An editor gets their own draft list, not the owner's personal draft.
        editor = self._add_member("editor", "EDITOR")
        editor_draft = self.client.post(
            f"/api/v1/imports/banks/{self.bank_id}/drafts", headers=editor, json={"state": {"mine": True}}
        )
        self.assertEqual(editor_draft.status_code, 201, editor_draft.text)
        editor_list = self.client.get(
            f"/api/v1/imports/banks/{self.bank_id}/drafts", headers=editor
        ).json()
        self.assertEqual([row["id"] for row in editor_list], [editor_draft.json()["id"]])
        self.assertEqual(
            self.client.get(f"/api/v1/imports/drafts/{draft['id']}", headers=editor).status_code, 404
        )
        self.assertEqual(
            self.client.get(f"/api/v1/imports/banks/{self.bank_id}/drafts", headers=stranger).status_code, 404
        )

    # ----------------------------------------------------------------- async jobs

    def test_job_runs_to_completion_with_progress_totals(self):
        resp = self.client.post(
            f"/api/v1/imports/banks/{self.bank_id}/jobs",
            headers=self.owner_headers,
            json={"format": "text", "content": _question_batch(60), "duplicate_strategy": "prompt"},
        )
        self.assertEqual(resp.status_code, 202, resp.text)
        created = resp.json()
        self.assertEqual(created["status"], "RUNNING")
        final = self._wait_job(created["job_id"])
        self.assertEqual(final["id"], created["job_id"])
        self.assertEqual(final["status"], "COMPLETED")
        self.assertEqual(final["progress"], 60)
        self.assertEqual(final["total"], 60)
        self.assertEqual(final["imported_count"], 60)
        self.assertEqual(self._question_count(), 60)

        # Polling is read-only: a second observation must not re-import.
        again = self._wait_job(created["job_id"])
        self.assertEqual(again["imported_count"], 60)
        self.assertEqual(self._question_count(), 60)

    def test_cancel_mid_run_finishes_cancelled_without_duplicates(self):
        resp = self.client.post(
            f"/api/v1/imports/banks/{self.bank_id}/jobs",
            headers=self.owner_headers,
            json={"format": "text", "content": _question_batch(2000), "duplicate_strategy": "prompt"},
        )
        self.assertEqual(resp.status_code, 202, resp.text)
        job_id = resp.json()["job_id"]
        cancel = self.client.post(f"/api/v1/imports/jobs/{job_id}/cancel", headers=self.owner_headers)
        self.assertEqual(cancel.status_code, 200, cancel.text)

        final = self._wait_job(job_id)
        self.assertEqual(final["status"], "CANCELLED", final)
        self.assertLess(final["progress"], final["total"])
        self.assertEqual(self._question_count(), final["imported_count"])

        # A second poll and a second cancel must change nothing.
        again = self._wait_job(job_id)
        self.assertEqual(again["status"], "CANCELLED")
        self.assertEqual(again["imported_count"], final["imported_count"])
        second_cancel = self.client.post(f"/api/v1/imports/jobs/{job_id}/cancel", headers=self.owner_headers)
        self.assertEqual(second_cancel.status_code, 200)
        self.assertEqual(second_cancel.json()["status"], "CANCELLED")
        self.assertEqual(self._question_count(), final["imported_count"])

    def test_failed_parse_ends_failed_with_reason(self):
        resp = self.client.post(
            f"/api/v1/imports/banks/{self.bank_id}/jobs",
            headers=self.owner_headers,
            json={"format": "json", "content": "{not valid json"},
        )
        self.assertEqual(resp.status_code, 202, resp.text)
        final = self._wait_job(resp.json()["job_id"])
        self.assertEqual(final["status"], "FAILED")
        self.assertTrue(final["reason"])
        self.assertNotEqual(final["status"], "RUNNING")
        self.assertEqual(self._question_count(), 0)

    def test_multipart_job_upload_completes(self):
        csv_content = (
            "stem,answer,options\n"
            "2+2 等于几？,A,选项甲|选项乙\n"
            "3+3 等于几？,A,选项甲|选项乙\n"
        ).encode("utf-8")
        resp = self.client.post(
            f"/api/v1/imports/banks/{self.bank_id}/jobs",
            headers=self.owner_headers,
            files={"file": ("questions.csv", csv_content, "text/csv")},
            data={"duplicate_strategy": "skip"},
        )
        self.assertEqual(resp.status_code, 202, resp.text)
        final = self._wait_job(resp.json()["job_id"])
        self.assertEqual(final["status"], "COMPLETED", final)
        self.assertEqual(final["format"], "csv")
        self.assertEqual(final["imported_count"], 2)
        self.assertEqual(self._question_count(), 2)

    def test_member_cannot_start_or_read_foreign_jobs(self):
        resp = self.client.post(
            f"/api/v1/imports/banks/{self.bank_id}/jobs",
            headers=self._register("outsider"),
            json={"format": "text", "content": _question_text(1)},
        )
        self.assertEqual(resp.status_code, 404, resp.text)

        member = self._add_member("member-two", "MEMBER")
        resp = self.client.post(
            f"/api/v1/imports/banks/{self.bank_id}/jobs",
            headers=member,
            json={"format": "text", "content": _question_text(1)},
        )
        self.assertEqual(resp.status_code, 403, resp.text)


if __name__ == "__main__":
    unittest.main()
