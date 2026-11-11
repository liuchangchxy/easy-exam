import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.main import create_app


class BankBatchOperationsTests(unittest.TestCase):
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

    def _chapter(self, headers, bank_id, name):
        resp = self.client.post(f"/api/v1/banks/{bank_id}/chapters", headers=headers, json={"name": name})
        assert resp.status_code == 201, resp.text
        return resp.json()

    def _question(self, headers, bank_id, stem, answer="A", chapter_id=None, tags=None):
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
                "tags": tags or [],
                "chapter_id": chapter_id,
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    def _content(self, headers, bank_id, include_archived=False):
        query = "?include_archived=true" if include_archived else ""
        resp = self.client.get(f"/api/v1/banks/{bank_id}/content/questions{query}", headers=headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    def _batch(self, headers, bank_id, payload):
        return self.client.post(f"/api/v1/banks/{bank_id}/questions/batch", headers=headers, json=payload)

    def test_batch_chapter_and_tags_are_atomic_and_do_not_bump_versions(self):
        _, headers = self._user("batch_admin")
        bank = self._bank(headers, "Batch Bank")
        chapter = self._chapter(headers, bank["id"], "Chapter One")
        q1 = self._question(headers, bank["id"], "Question one", tags=["old"])
        q2 = self._question(headers, bank["id"], "Question two")

        resp = self._batch(
            headers,
            bank["id"],
            {"question_ids": [q1["id"], q2["id"]], "operation": "chapter", "chapter_id": chapter["id"]},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["affected"], 2)
        content = {q["id"]: q for q in self._content(headers, bank["id"])}
        self.assertEqual(content[q1["id"]]["chapter_id"], chapter["id"])
        self.assertEqual(content[q2["id"]]["chapter_id"], chapter["id"])
        self.assertEqual(content[q1["id"]]["version_number"], 1)

        resp = self._batch(
            headers,
            bank["id"],
            {"question_ids": [q1["id"], q2["id"]], "operation": "add_tags", "tags": ["new", "shared"]},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        content = {q["id"]: q for q in self._content(headers, bank["id"])}
        self.assertEqual(sorted(content[q1["id"]]["tags"]), ["new", "old", "shared"])
        self.assertEqual(sorted(content[q2["id"]]["tags"]), ["new", "shared"])

        resp = self._batch(
            headers,
            bank["id"],
            {"question_ids": [q1["id"]], "operation": "remove_tags", "tags": ["old"]},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        q1_after = next(q for q in self._content(headers, bank["id"]) if q["id"] == q1["id"])
        self.assertEqual(sorted(q1_after["tags"]), ["new", "shared"])

    def test_invalid_chapter_rejects_whole_batch_without_partial_writes(self):
        _, headers = self._user("batch_atomic")
        source = self._bank(headers, "Atomic Source")
        other = self._bank(headers, "Atomic Other")
        other_chapter = self._chapter(headers, other["id"], "Foreign Chapter")
        q1 = self._question(headers, source["id"], "Atomic one")
        q2 = self._question(headers, source["id"], "Atomic two")

        resp = self._batch(
            headers,
            source["id"],
            {
                "question_ids": [q1["id"], q2["id"]],
                "operation": "chapter",
                "chapter_id": other_chapter["id"],
            },
        )
        self.assertEqual(resp.status_code, 400)
        content = {q["id"]: q for q in self._content(headers, source["id"])}
        self.assertIsNone(content[q1["id"]]["chapter_id"])
        self.assertIsNone(content[q2["id"]]["chapter_id"])

    def test_batch_move_and_copy_respect_target_permissions_and_keep_source_safe(self):
        _, headers = self._user("batch_move_admin")
        source = self._bank(headers, "Move Source")
        target = self._bank(headers, "Move Target")
        chapter = self._chapter(headers, source["id"], "Shared Chapter")
        q1 = self._question(headers, source["id"], "Move me", chapter_id=chapter["id"], tags=["tag-a"])

        resp = self._batch(
            headers,
            source["id"],
            {"question_ids": [q1["id"]], "operation": "copy", "target_bank_id": target["id"]},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        source_content = self._content(headers, source["id"])
        target_content = self._content(headers, target["id"])
        self.assertEqual([q["id"] for q in source_content], [q1["id"]])
        self.assertEqual(len(target_content), 1)
        copied = target_content[0]
        self.assertNotEqual(copied["id"], q1["id"])
        self.assertEqual(sorted(copied["tags"]), ["tag-a"])
        self.assertIsNotNone(copied["chapter_id"])
        copied_version = self.client.get(f"/api/v1/questions/{copied['id']}/versions", headers=headers)
        self.assertEqual(copied_version.status_code, 200)
        self.assertEqual(len(copied_version.json()), 1, "A copy must start at version 1")

        resp = self._batch(
            headers,
            source["id"],
            {"question_ids": [q1["id"]], "operation": "move", "target_bank_id": target["id"]},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self._content(headers, source["id"]), [])
        moved_ids = {q["id"] for q in self._content(headers, target["id"])}
        self.assertIn(q1["id"], moved_ids)

        # A user without target edit rights cannot move or copy into that bank.
        _, member_headers = self._user("batch_move_member")
        self.client.post(
            f"/api/v1/banks/{source['id']}/members",
            headers=headers,
            json={"username": "batch_move_member", "role": "MEMBER"},
        )
        denied = self._batch(
            member_headers,
            source["id"],
            {"question_ids": [q1["id"]], "operation": "copy", "target_bank_id": target["id"]},
        )
        self.assertEqual(denied.status_code, 403)

    def test_batch_archive_hides_from_content_and_practice_until_restored(self):
        _, headers = self._user("batch_archive")
        bank = self._bank(headers, "Archive Bank")
        q1 = self._question(headers, bank["id"], "Archive me")
        q2 = self._question(headers, bank["id"], "Keep me")

        resp = self._batch(
            headers, bank["id"], {"question_ids": [q1["id"]], "operation": "archive"}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        visible_ids = {q["id"] for q in self._content(headers, bank["id"])}
        self.assertNotIn(q1["id"], visible_ids)
        self.assertIn(q2["id"], visible_ids)

        archived = {q["id"]: q for q in self._content(headers, bank["id"], include_archived=True)}
        self.assertTrue(archived[q1["id"]]["archived"])
        self.assertFalse(archived[q2["id"]]["archived"])

        practice = self.client.get(f"/api/v1/banks/{bank['id']}/questions", headers=headers).json()
        self.assertNotIn(q1["id"], [q["id"] for q in practice])

        # Archived questions cannot be edited or metadata-batched until restored.
        edit = self.client.put(
            f"/api/v1/questions/{q1['id']}",
            headers=headers,
            json={
                "stem": "Edited archived",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "one"}, {"key": "B", "content": "two"}],
                "answer": "A",
                "base_version_number": 1,
            },
        )
        self.assertEqual(edit.status_code, 400)

        blocked = self._batch(
            headers, bank["id"], {"question_ids": [q1["id"]], "operation": "add_tags", "tags": ["x"]}
        )
        self.assertEqual(blocked.status_code, 400)

        restored = self._batch(
            headers, bank["id"], {"question_ids": [q1["id"]], "operation": "restore"}
        )
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertIn(q1["id"], {q["id"] for q in self._content(headers, bank["id"])})

    def test_batch_rejects_members_and_locked_batches_atomically(self):
        _, headers = self._user("batch_lock_admin")
        member_token, member_headers = self._user("batch_lock_member")
        bank = self._bank(headers, "Locked Batch")
        chapter = self._chapter(headers, bank["id"], "Lock Target")
        q1 = self._question(headers, bank["id"], "Unlocked question")
        q2 = self._question(headers, bank["id"], "Exam question")
        self.client.post(
            f"/api/v1/banks/{bank['id']}/members",
            headers=headers,
            json={"username": "batch_lock_member", "role": "MEMBER"},
        )

        member_resp = self._batch(
            member_headers,
            bank["id"],
            {"question_ids": [q1["id"]], "operation": "archive"},
        )
        self.assertEqual(member_resp.status_code, 403)

        exam = self.client.post(
            "/api/v1/practice/sessions",
            headers={"Authorization": f"Bearer {member_token}"},
            json={"bank_id": bank["id"], "mode": "EXAM", "total_questions": 1, "question_ids": [q2["id"]]},
        )
        self.assertEqual(exam.status_code, 201, exam.text)

        locked = self._batch(
            headers,
            bank["id"],
            {"question_ids": [q1["id"], q2["id"]], "operation": "chapter", "chapter_id": chapter["id"]},
        )
        self.assertEqual(locked.status_code, 403, locked.text)

        content = {q["id"]: q for q in self._content(headers, bank["id"])}
        self.assertIsNone(content[q1["id"]]["chapter_id"], "Rejected batch must not partially update unlocked rows")

    def test_batch_validation_rejects_empty_and_unknown_operations(self):
        _, headers = self._user("batch_validation")
        bank = self._bank(headers, "Validation Bank")
        q1 = self._question(headers, bank["id"], "Validation")

        empty = self._batch(headers, bank["id"], {"question_ids": [], "operation": "archive"})
        self.assertEqual(empty.status_code, 422)

        unknown = self._batch(
            headers, bank["id"], {"question_ids": [q1["id"]], "operation": "explode"}
        )
        self.assertEqual(unknown.status_code, 400)

        self.assertIn(q1["id"], {q["id"] for q in self._content(headers, bank["id"])})


if __name__ == "__main__":
    unittest.main()
