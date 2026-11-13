import json
import os
import sqlite3
import tempfile
import unittest
import uuid

from fastapi.testclient import TestClient

from backend.app.main import create_app


class BankManagementCompletionTests(unittest.TestCase):
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

    def _me(self, headers):
        return self.client.get("/api/v1/auth/me", headers=headers).json()

    def _bank(self, headers, name, category="Test"):
        resp = self.client.post(
            "/api/v1/banks", headers=headers, json={"name": name, "category": category, "description": "desc"}
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _chapter(self, headers, bank_id, name, parent_id=None):
        resp = self.client.post(
            f"/api/v1/banks/{bank_id}/chapters", headers=headers,
            json={"name": name, "parent_id": parent_id},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _question(self, headers, bank_id, stem, answer="A", tags=None, chapter_id=None):
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
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _insert_active_exam(self, user_id, bank_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO practice_sessions(id, user_id, bank_id, mode, total_questions,
                                                 is_completed, questions_json)
                   VALUES (?, ?, ?, 'EXAM', 1, 0, ?)""",
                (str(uuid.uuid4()), user_id, bank_id, json.dumps([{"question_id": "q-x"}])),
            )
            conn.commit()

    def _content(self, headers, bank_id, include_archived=False):
        query = "?include_archived=true" if include_archived else ""
        resp = self.client.get(f"/api/v1/banks/{bank_id}/content/questions{query}", headers=headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    # ------------------------------------------------------------ bank object

    def test_bank_update_rename_and_permissions(self):
        _, owner = self._user("owner_update")
        _, member = self._user("member_update")
        bank = self._bank(owner, "Rename Me")
        self.client.post(f"/api/v1/banks/{bank['id']}/members", headers=owner,
                         json={"username": "member_update", "role": "MEMBER"})

        resp = self.client.patch(f"/api/v1/banks/{bank['id']}", headers=owner,
                                 json={"name": "Renamed", "category": "NewCat", "description": "new"})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["name"], "Renamed")
        self.assertEqual(body["category"], "NewCat")
        self.assertEqual(body["description"], "new")

        forbidden = self.client.patch(f"/api/v1/banks/{bank['id']}", headers=member, json={"name": "Nope"})
        self.assertEqual(forbidden.status_code, 403)
        missing = self.client.patch(f"/api/v1/banks/{uuid.uuid4()}", headers=owner, json={"name": "Nope"})
        self.assertEqual(missing.status_code, 404)

    def test_soft_delete_restore_and_recycle_bin(self):
        _, owner = self._user("owner_delete")
        bank = self._bank(owner, "Delete Me")
        self._question(owner, bank["id"], "Q1")

        deleted = self.client.delete(f"/api/v1/banks/{bank['id']}", headers=owner)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertTrue(deleted.json()["deleted"])
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank['id']}", headers=owner).status_code, 404)

        active = self.client.get("/api/v1/banks", headers=owner).json()
        self.assertNotIn(bank["id"], [b["id"] for b in active])
        recycle = self.client.get("/api/v1/banks", headers=owner, params={"deleted": 1}).json()
        self.assertIn(bank["id"], [b["id"] for b in recycle])
        self.assertTrue(recycle[0]["deleted"])

        restored = self.client.post(f"/api/v1/banks/{bank['id']}/restore", headers=owner)
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank['id']}", headers=owner).status_code, 200)

    def test_list_orders_by_recent_update(self):
        _, owner = self._user("owner_recent_order")
        bank_a = self._bank(owner, "Recent A")
        bank_b = self._bank(owner, "Recent B")

        # Pin explicit timestamps: SQLite's CURRENT_TIMESTAMP only has second
        # granularity, so creating both banks in the same second would make the
        # assertion depend on arbitrary tie-breaking.
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE question_banks SET created_at = ?, updated_at = ? WHERE id = ?",
                ("2020-01-01 00:00:00", "2020-01-01 00:00:00", bank_a["id"]),
            )
            conn.execute(
                "UPDATE question_banks SET created_at = ?, updated_at = ? WHERE id = ?",
                ("2020-01-01 00:00:05", "2020-01-01 00:00:05", bank_b["id"]),
            )
            conn.commit()

        listed = [b["id"] for b in self.client.get("/api/v1/banks", headers=owner).json()]
        self.assertEqual(listed, [bank_b["id"], bank_a["id"]])

        # Renaming bumps updated_at, so the edited bank must move to the top.
        updated = self.client.patch(f"/api/v1/banks/{bank_a['id']}", headers=owner,
                                    json={"name": "Recent A Renamed"})
        self.assertEqual(updated.status_code, 200, updated.text)

        listed = [b["id"] for b in self.client.get("/api/v1/banks", headers=owner).json()]
        self.assertEqual(listed, [bank_a["id"], bank_b["id"]])

        # Recycle bin listing keeps working with the same recency ordering.
        deleted = self.client.delete(f"/api/v1/banks/{bank_a['id']}", headers=owner)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        active = [b["id"] for b in self.client.get("/api/v1/banks", headers=owner).json()]
        self.assertEqual(active, [bank_b["id"]])
        recycle = self.client.get("/api/v1/banks", headers=owner, params={"deleted": 1}).json()
        self.assertEqual([b["id"] for b in recycle], [bank_a["id"]])
        self.assertTrue(recycle[0]["deleted"])

    def test_delete_blocked_by_active_exam(self):
        _, owner = self._user("owner_exam")
        bank = self._bank(owner, "Exam Locked")
        me = self._me(owner)
        self._insert_active_exam(me["id"], bank["id"])
        resp = self.client.delete(f"/api/v1/banks/{bank['id']}", headers=owner)
        self.assertEqual(resp.status_code, 422, resp.text)
        self.assertIn("exam", str(resp.json()["detail"]).lower())

    def test_batch_bank_operations_are_atomic(self):
        _, owner_a = self._user("owner_batch_a")
        _, owner_b = self._user("owner_batch_b")
        bank_a = self._bank(owner_a, "Batch A")
        bank_b = self._bank(owner_b, "Batch B")

        # owner_a has no permission on bank_b: the whole batch must roll back.
        resp = self.client.post("/api/v1/banks/batch", headers=owner_a,
                                json={"bank_ids": [bank_a["id"], bank_b["id"]], "operation": "archive"})
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank_a['id']}", headers=owner_a).status_code, 200)

        ok = self.client.post("/api/v1/banks/batch", headers=owner_a,
                              json={"bank_ids": [bank_a["id"]], "operation": "archive"})
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(ok.json()["affected"], 1)
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank_a['id']}", headers=owner_a).status_code, 404)

        restore = self.client.post("/api/v1/banks/batch", headers=owner_a,
                                   json={"bank_ids": [bank_a["id"]], "operation": "restore"})
        self.assertEqual(restore.status_code, 200, restore.text)
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank_a['id']}", headers=owner_a).status_code, 200)

    def test_category_rename_and_delete(self):
        _, owner = self._user("owner_category")
        bank_a = self._bank(owner, "Cat A1", category="Alpha")
        bank_b = self._bank(owner, "Cat A2", category="Alpha")
        bank_c = self._bank(owner, "Cat B", category="Beta")

        categories = {row["name"]: row["count"] for row in
                      self.client.get("/api/v1/banks/categories", headers=owner).json()}
        self.assertEqual(categories.get("Alpha"), 2)

        renamed = self.client.post("/api/v1/banks/categories/rename", headers=owner,
                                   json={"old_name": "Alpha", "new_name": "Gamma"})
        self.assertEqual(renamed.status_code, 200, renamed.text)
        self.assertEqual(renamed.json()["affected"], 2)
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank_a['id']}", headers=owner).json()["category"], "Gamma")
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank_b['id']}", headers=owner).json()["category"], "Gamma")

        removed = self.client.post("/api/v1/banks/categories/delete", headers=owner, json={"name": "Gamma"})
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank_a['id']}", headers=owner).json()["category"], "默认分类")
        self.assertEqual(self.client.get(f"/api/v1/banks/{bank_c['id']}", headers=owner).json()["category"], "Beta")

        missing = self.client.post("/api/v1/banks/categories/rename", headers=owner,
                                   json={"old_name": "DoesNotExist", "new_name": "X"})
        self.assertEqual(missing.status_code, 404)

    def test_question_count_excludes_archived(self):
        _, owner = self._user("owner_counts")
        bank = self._bank(owner, "Count Bank")
        q1 = self._question(owner, bank["id"], "Count Q1")
        q2 = self._question(owner, bank["id"], "Count Q2")
        batch = self.client.post(
            f"/api/v1/banks/{bank['id']}/questions/batch", headers=owner,
            json={"question_ids": [q2["id"]], "operation": "archive"},
        )
        self.assertEqual(batch.status_code, 200, batch.text)
        body = self.client.get(f"/api/v1/banks/{bank['id']}", headers=owner).json()
        self.assertEqual(body["question_count"], 1)
        self.assertEqual(body["archived_question_count"], 1)

    # --------------------------------------------------------------- members

    def test_member_role_change_leave_and_transfer(self):
        _, owner = self._user("owner_roles")
        owner_id = self._me(owner)["id"]
        _, _ = self._user("member_roles")
        member_token, member_headers = self._user("member_roles")
        bank = self._bank(owner, "Role Bank")
        add = self.client.post(f"/api/v1/banks/{bank['id']}/members", headers=owner,
                               json={"username": "member_roles", "role": "MEMBER"})
        self.assertEqual(add.status_code, 201, add.text)
        member_id = add.json()["user_id"]

        changed = self.client.patch(f"/api/v1/banks/{bank['id']}/members/{member_id}",
                                    headers=owner, json={"role": "EDITOR"})
        self.assertEqual(changed.status_code, 200, changed.text)
        members = {m["user_id"]: m["role"] for m in
                   self.client.get(f"/api/v1/banks/{bank['id']}/members", headers=owner).json()}
        self.assertEqual(members[member_id], "EDITOR")

        forbidden = self.client.patch(f"/api/v1/banks/{bank['id']}/members/{owner_id}",
                                      headers=member_headers, json={"role": "MEMBER"})
        self.assertEqual(forbidden.status_code, 403)
        owner_change = self.client.patch(f"/api/v1/banks/{bank['id']}/members/{owner_id}",
                                         headers=owner, json={"role": "MEMBER"})
        self.assertEqual(owner_change.status_code, 422)

        transferred = self.client.post(f"/api/v1/banks/{bank['id']}/transfer", headers=owner,
                                       json={"username": "member_roles"})
        self.assertEqual(transferred.status_code, 200, transferred.text)
        members = {m["user_id"]: m["role"] for m in
                   self.client.get(f"/api/v1/banks/{bank['id']}/members", headers=member_headers).json()}
        self.assertEqual(members[member_id], "ADMIN")
        self.assertEqual(members[owner_id], "EDITOR")
        self.assertEqual(self.client.patch(f"/api/v1/banks/{bank['id']}", headers=owner,
                                           json={"name": "Nope"}).status_code, 403)

        left = self.client.post(f"/api/v1/banks/{bank['id']}/leave", headers=owner)
        self.assertEqual(left.status_code, 200, left.text)
        self.assertNotIn(owner_id, [m["user_id"] for m in
                                    self.client.get(f"/api/v1/banks/{bank['id']}/members", headers=member_headers).json()])

    def test_owner_cannot_leave(self):
        _, owner = self._user("owner_leave")
        bank = self._bank(owner, "No Leave")
        resp = self.client.post(f"/api/v1/banks/{bank['id']}/leave", headers=owner)
        self.assertEqual(resp.status_code, 422, resp.text)

    # -------------------------------------------------------------- structure

    def test_chapter_reorder_and_cycle_rejection(self):
        _, owner = self._user("owner_chapters")
        bank = self._bank(owner, "Tree Bank")
        root = self._chapter(owner, bank["id"], "Root")
        child = self._chapter(owner, bank["id"], "Child", parent_id=root["id"])
        grand = self._chapter(owner, bank["id"], "Grand", parent_id=child["id"])

        resp = self.client.post(
            f"/api/v1/banks/{bank['id']}/chapters/reorder", headers=owner,
            json={"items": [
                {"id": root["id"], "parent_id": None, "sort_order": 0},
                {"id": child["id"], "parent_id": root["id"], "sort_order": 0},
                {"id": grand["id"], "parent_id": child["id"], "sort_order": 0},
            ]},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(len(resp.json()), 3)

        cycle = self.client.post(
            f"/api/v1/banks/{bank['id']}/chapters/reorder", headers=owner,
            json={"items": [
                {"id": root["id"], "parent_id": grand["id"], "sort_order": 0},
                {"id": child["id"], "parent_id": root["id"], "sort_order": 0},
                {"id": grand["id"], "parent_id": child["id"], "sort_order": 0},
            ]},
        )
        self.assertEqual(cycle.status_code, 422, cycle.text)
        self.assertIn("circular", str(cycle.json()["detail"]).lower())

    def test_chapter_missing_returns_404_not_500(self):
        _, owner = self._user("owner_chapter_404")
        bank = self._bank(owner, "404 Bank")
        missing_chapter = self.client.put(
            f"/api/v1/banks/{bank['id']}/chapters/{uuid.uuid4()}", headers=owner, json={"name": "X"}
        )
        self.assertEqual(missing_chapter.status_code, 404, missing_chapter.text)
        bad_parent = self.client.post(
            f"/api/v1/banks/{bank['id']}/chapters", headers=owner,
            json={"name": "Child", "parent_id": str(uuid.uuid4())},
        )
        self.assertEqual(bad_parent.status_code, 422, bad_parent.text)

    # ------------------------------------------------------------------- tags

    def test_tag_rename_and_delete_rewrite_question_tags(self):
        _, owner = self._user("owner_tags")
        bank = self._bank(owner, "Tag Bank")
        question = self._question(owner, bank["id"], "Tagged?", tags=["alpha", "keep"])
        tags = {t["name"]: t for t in self.client.get(f"/api/v1/banks/{bank['id']}/tags", headers=owner).json()}
        self.assertIn("alpha", tags)
        self.assertEqual(tags["alpha"]["question_count"], 1)

        renamed = self.client.put(f"/api/v1/banks/{bank['id']}/tags/{tags['alpha']['id']}",
                                  headers=owner, json={"name": "beta"})
        self.assertEqual(renamed.status_code, 200, renamed.text)
        content = {q["id"]: q for q in self._content(owner, bank["id"])}
        self.assertIn("beta", content[question["id"]]["tags"])
        self.assertNotIn("alpha", content[question["id"]]["tags"])

        tags = {t["name"]: t for t in self.client.get(f"/api/v1/banks/{bank['id']}/tags", headers=owner).json()}
        removed = self.client.delete(f"/api/v1/banks/{bank['id']}/tags/{tags['beta']['id']}", headers=owner)
        self.assertEqual(removed.status_code, 204, removed.text)
        content = {q["id"]: q for q in self._content(owner, bank["id"])}
        self.assertNotIn("beta", content[question["id"]]["tags"])
        self.assertIn("keep", content[question["id"]]["tags"])

        missing = self.client.put(f"/api/v1/banks/{bank['id']}/tags/{uuid.uuid4()}",
                                  headers=owner, json={"name": "x"})
        self.assertEqual(missing.status_code, 404, missing.text)

    # ------------------------------------------------------------------ audit

    def test_bank_audit_lists_management_actions(self):
        _, owner = self._user("owner_audit")
        bank = self._bank(owner, "Audit Bank")
        self.client.patch(f"/api/v1/banks/{bank['id']}", headers=owner, json={"description": "audited"})
        resp = self.client.get(f"/api/v1/banks/{bank['id']}/audit", headers=owner)
        self.assertEqual(resp.status_code, 200, resp.text)
        actions = {row["action"] for row in resp.json()}
        self.assertIn("BANK_CREATED", actions)
        self.assertIn("BANK_UPDATED", actions)

        _, other = self._user("other_audit")
        self.client.post(f"/api/v1/banks/{bank['id']}/members", headers=owner,
                         json={"username": "other_audit", "role": "MEMBER"})
        denied = self.client.get(f"/api/v1/banks/{bank['id']}/audit", headers=other)
        self.assertEqual(denied.status_code, 403)

    # ---------------------------------------------------------- import/export

    def test_import_history_lists_jobs(self):
        _, owner = self._user("owner_imports")
        bank = self._bank(owner, "Import Bank")
        resp = self.client.post(
            f"/api/v1/imports/banks/{bank['id']}", headers=owner,
            json={"format": "text", "content": "1. 1+1=?\nA. 1\nB. 2\n【答案】B", "duplicate_strategy": "skip"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        jobs = self.client.get(f"/api/v1/banks/{bank['id']}/imports", headers=owner)
        self.assertEqual(jobs.status_code, 200, jobs.text)
        self.assertGreaterEqual(len(jobs.json()), 1)
        self.assertEqual(jobs.json()[0]["format"], "text")

    def test_export_uses_bank_content_not_personal_kill_list(self):
        _, owner = self._user("owner_export")
        bank = self._bank(owner, "Export Bank")
        q1 = self._question(owner, bank["id"], "Export Q1")
        q2 = self._question(owner, bank["id"], "Export Q2")
        self.client.post(f"/api/v1/kills/{q2['id']}", headers=owner)

        exported = self.client.get(f"/api/v1/banks/{bank['id']}/export", headers=owner, params={"format": "json"})
        self.assertEqual(exported.status_code, 200, exported.text)
        rows = json.loads(exported.text)
        stems = {row["stem"] for row in rows}
        self.assertIn("Export Q1", stems)
        self.assertIn("Export Q2", stems, "killed questions must not be dropped from a bank export")

        self.client.post(f"/api/v1/banks/{bank['id']}/questions/batch", headers=owner,
                         json={"question_ids": [q1["id"]], "operation": "archive"})
        default_rows = json.loads(self.client.get(f"/api/v1/banks/{bank['id']}/export", headers=owner,
                                                  params={"format": "json"}).text)
        self.assertNotIn("Export Q1", {row["stem"] for row in default_rows})
        archived_rows = json.loads(self.client.get(
            f"/api/v1/banks/{bank['id']}/export", headers=owner,
            params={"format": "json", "include_archived": 1},
        ).text)
        self.assertIn("Export Q1", {row["stem"] for row in archived_rows})

    # -------------------------------------------------------- version delete

    def test_version_delete_protects_current_and_missing(self):
        _, owner = self._user("owner_versions")
        bank = self._bank(owner, "Version Bank")
        question = self._question(owner, bank["id"], "V1 stem")
        update = self.client.put(
            f"/api/v1/questions/{question['id']}", headers=owner,
            json={
                "stem": "V2 stem",
                "type": "SINGLE",
                "options": [{"key": "A", "content": "one"}, {"key": "B", "content": "two"}],
                "answer": "A",
                "explanation": "because",
                "difficulty": 2,
                "tags": [],
                "chapter_id": None,
                "base_version_number": 1,
                "regrade_history": False,
            },
        )
        self.assertEqual(update.status_code, 200, update.text)
        versions = self.client.get(f"/api/v1/questions/{question['id']}/versions", headers=owner).json()
        self.assertEqual(len(versions), 2)
        current = max(versions, key=lambda v: v["version_number"])
        old = min(versions, key=lambda v: v["version_number"])

        deleted = self.client.delete(f"/api/v1/questions/{question['id']}/versions/{old['id']}", headers=owner)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(len(self.client.get(f"/api/v1/questions/{question['id']}/versions",
                                             headers=owner).json()), 1)

        current_delete = self.client.delete(f"/api/v1/questions/{question['id']}/versions/{current['id']}",
                                            headers=owner)
        self.assertEqual(current_delete.status_code, 400, current_delete.text)
        missing = self.client.delete(f"/api/v1/questions/{question['id']}/versions/{uuid.uuid4()}", headers=owner)
        self.assertEqual(missing.status_code, 404, missing.text)

        _, member = self._user("member_versions")
        self.client.post(f"/api/v1/banks/{bank['id']}/members", headers=owner,
                         json={"username": "member_versions", "role": "MEMBER"})
        forbidden = self.client.delete(f"/api/v1/questions/{question['id']}/versions/{current['id']}",
                                       headers=member)
        self.assertEqual(forbidden.status_code, 403)


if __name__ == "__main__":
    unittest.main()
