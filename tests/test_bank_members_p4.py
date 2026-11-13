"""Bank member listing semantics and user search for P4 collaboration."""

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.main import create_app

PASSWORD = "password-123456"


class BankMembersP4Tests(unittest.TestCase):
    def setUp(self):
        self._temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self._temp_db.name
        self._temp_db.close()
        self.app = create_app(db_path=self.db_path)
        self.client = TestClient(self.app)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            path = self.db_path + suffix
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    # ----------------------------------------------------------------- helpers

    def _user(self, username):
        self.client.post(
            "/api/v1/auth/register", json={"username": username, "password": PASSWORD}
        )
        resp = self.client.post(
            "/api/v1/auth/login", json={"username": username, "password": PASSWORD}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()["token"], {"Authorization": f"Bearer {resp.json()['token']}"}

    def _bank(self, headers, name="协作题库"):
        resp = self.client.post("/api/v1/banks", headers=headers, json={"name": name})
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    def _add(self, headers, bank_id, username, role):
        return self.client.post(
            f"/api/v1/banks/{bank_id}/members",
            headers=headers,
            json={"username": username, "role": role},
        )

    def _members(self, headers, bank_id):
        resp = self.client.get(f"/api/v1/banks/{bank_id}/members", headers=headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    # ------------------------------------------------------------- ordering

    def test_member_order_is_owner_editor_member_then_username(self):
        _, owner = self._user("zeta_owner")
        _, editor = self._user("alpha_editor")
        self._user("mike_member")
        self._user("aaa_member")
        bank = self._bank(owner)

        for username, role in (
            ("mike_member", "MEMBER"),
            ("alpha_editor", "EDITOR"),
            ("aaa_member", "MEMBER"),
        ):
            resp = self._add(owner, bank["id"], username, role)
            self.assertEqual(resp.status_code, 201, resp.text)

        members = self._members(owner, bank["id"])
        self.assertEqual(
            [row["username"] for row in members],
            ["zeta_owner", "alpha_editor", "aaa_member", "mike_member"],
        )
        self.assertEqual(
            [row["role"] for row in members], ["ADMIN", "EDITOR", "MEMBER", "MEMBER"]
        )
        for row in members:
            self.assertIn("joined_at", row)
            self.assertIsNotNone(row["joined_at"])
        owner_row = members[0]
        self.assertTrue(owner_row["is_self"])
        self.assertFalse(any(row["is_self"] for row in members[1:]))

        # The flag follows the caller, not the owner.
        editor_view = self._members(editor, bank["id"])
        self.assertEqual(
            [row["username"] for row in editor_view if row["is_self"]], ["alpha_editor"]
        )

    # ------------------------------------------------------------- conflict

    def test_duplicate_add_returns_409_and_keeps_existing_role(self):
        _, owner = self._user("conflict_owner")
        self._user("conflict_member")
        bank = self._bank(owner)

        first = self._add(owner, bank["id"], "conflict_member", "MEMBER")
        self.assertEqual(first.status_code, 201, first.text)

        again = self._add(owner, bank["id"], "conflict_member", "EDITOR")
        self.assertEqual(again.status_code, 409, again.text)
        self.assertIn("already a member", again.json()["detail"])

        members = self._members(owner, bank["id"])
        self.assertEqual(len(members), 2)
        target = next(row for row in members if row["username"] == "conflict_member")
        self.assertEqual(target["role"], "MEMBER")

    # --------------------------------------------------------------- search

    def test_user_search_is_prefix_case_insensitive_and_excludes_caller(self):
        _, alice = self._user("alice")
        self._user("albert")
        self._user("alfred")
        self._user("bob")

        resp = self.client.get("/api/v1/users/search", headers=alice, params={"q": "al"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(
            [row["username"] for row in resp.json()], ["albert", "alfred"]
        )
        for row in resp.json():
            self.assertEqual(set(row), {"id", "username"})

        upper = self.client.get("/api/v1/users/search", headers=alice, params={"q": "AL"})
        self.assertEqual(
            [row["username"] for row in upper.json()], ["albert", "alfred"]
        )
        self.assertEqual(
            [row["username"] for row in self.client.get(
                "/api/v1/users/search", headers=alice, params={"q": "bob"}
            ).json()],
            ["bob"],
        )
        self.assertEqual(
            self.client.get("/api/v1/users/search", headers=alice, params={"q": ""}).json(), []
        )

    def test_user_search_requires_auth_and_caps_results_at_ten(self):
        _, caller = self._user("search_caller")
        for index in range(11):
            self._user(f"bulk_user_{index:02d}")

        self.assertEqual(
            self.client.get("/api/v1/users/search", params={"q": "bulk"}).status_code, 401
        )
        resp = self.client.get("/api/v1/users/search", headers=caller, params={"q": "bulk"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(len(resp.json()), 10)


if __name__ == "__main__":
    unittest.main()
