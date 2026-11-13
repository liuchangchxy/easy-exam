"""Instance administration, registration gate and session lifecycle (P4).

The frontend already read `auth.user.is_admin`; these tests pin the backend
contract that makes it real: one bootstrapped admin, guarded user management,
a registration switch, and sessions that can actually be revoked.
"""

import os
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.app.main import create_app


class InstanceAdminTests(unittest.TestCase):
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

    def _register(self, username, password="password-123456"):
        return self.client.post(
            "/api/v1/auth/register", json={"username": username, "password": password}
        )

    def _login(self, username, password="password-123456", user_agent=None):
        headers = {"User-Agent": user_agent} if user_agent else None
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()["token"], {"Authorization": f"Bearer {resp.json()['token']}"}

    def _admin_and_member(self):
        admin_resp = self._register("instance_admin")
        self.assertEqual(admin_resp.status_code, 201, admin_resp.text)
        self.assertTrue(admin_resp.json()["is_admin"])
        member_resp = self._register("plain_member")
        self.assertEqual(member_resp.status_code, 201, member_resp.text)
        self.assertFalse(member_resp.json()["is_admin"])
        _, admin = self._login("instance_admin")
        _, member = self._login("plain_member")
        return admin, member

    # ------------------------------------------------------------ bootstrap

    def test_first_user_becomes_admin_and_bootstrap_is_idempotent(self):
        first = self._register("first_member")
        self.assertEqual(first.status_code, 201, first.text)
        self.assertTrue(first.json()["is_admin"])
        self._register("second_member")

        # A restart must not promote a second admin.
        create_app(db_path=self.db_path)
        users = self.app.state.services.users.list_all()
        admins = [row["username"] for row in users if row["is_admin"]]
        self.assertEqual(admins, ["first_member"])

    def test_bootstrap_honours_admin_username_env_for_existing_users(self):
        self._register("earlier_user")
        self._register("target_admin")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE users SET is_admin = 0")
        os.environ["EASYEXAM_ADMIN_USERNAME"] = "target_admin"
        try:
            restarted = create_app(db_path=self.db_path)
        finally:
            os.environ.pop("EASYEXAM_ADMIN_USERNAME", None)
        users = restarted.state.services.users.list_all()
        admins = [row["username"] for row in users if row["is_admin"]]
        self.assertEqual(admins, ["target_admin"])

        # The bootstrap only fills an empty slot; a later restart keeps it.
        create_app(db_path=self.db_path)
        admins = [
            row["username"]
            for row in self.app.state.services.users.list_all()
            if row["is_admin"]
        ]
        self.assertEqual(admins, ["target_admin"])

    # ----------------------------------------------------- registration gate

    def test_registration_switch_blocks_second_user_but_not_first(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO instance_settings(key, value) VALUES ('allow_registration', 'false')"
            )
        first = self._register("first_bootstrap")
        self.assertEqual(first.status_code, 201, first.text)

        blocked = self._register("late_joiner")
        self.assertEqual(blocked.status_code, 403, blocked.text)
        self.assertIn("registration is disabled", blocked.json()["detail"])

        _, admin = self._login("first_bootstrap")
        current = self.client.get("/api/v1/admin/settings", headers=admin)
        self.assertEqual(current.status_code, 200, current.text)
        self.assertFalse(current.json()["allow_registration"])

        opened = self.client.put(
            "/api/v1/admin/settings", headers=admin, json={"allow_registration": True}
        )
        self.assertEqual(opened.status_code, 200, opened.text)
        self.assertTrue(opened.json()["allow_registration"])
        self.assertEqual(self._register("late_joiner").status_code, 201)

    def test_admin_endpoints_reject_non_admins_and_anonymous(self):
        admin, member = self._admin_and_member()
        member_id = self.client.get("/api/v1/auth/me", headers=member).json()["id"]
        for method, path, body in (
            ("get", "/api/v1/admin/users", None),
            ("patch", f"/api/v1/admin/users/{member_id}", {"is_active": False}),
            ("post", f"/api/v1/admin/users/{member_id}/reset-password", None),
            ("get", "/api/v1/admin/settings", None),
            ("put", "/api/v1/admin/settings", {"allow_registration": False}),
        ):
            call = getattr(self.client, method)
            resp = call(path, headers=member, **({"json": body} if body is not None else {}))
            self.assertEqual(resp.status_code, 403, f"{method} {path}: {resp.text}")
            anon = call(path, **({"json": body} if body is not None else {}))
            self.assertEqual(anon.status_code, 401, f"anon {method} {path}: {anon.text}")

    # --------------------------------------------------------- user listing

    def test_list_and_patch_users_with_guards(self):
        admin, member = self._admin_and_member()
        member_id = self.client.get("/api/v1/auth/me", headers=member).json()["id"]
        admin_id = self.client.get("/api/v1/auth/me", headers=admin).json()["id"]

        listing = self.client.get("/api/v1/admin/users", headers=admin)
        self.assertEqual(listing.status_code, 200, listing.text)
        rows = {row["username"]: row for row in listing.json()}
        self.assertEqual(set(rows), {"instance_admin", "plain_member"})
        self.assertTrue(rows["instance_admin"]["is_admin"])
        self.assertFalse(rows["plain_member"]["is_admin"])
        self.assertTrue(rows["plain_member"]["is_active"])
        self.assertEqual(rows["plain_member"]["bank_count"], 0)
        for key in ("id", "created_at", "must_change_password", "bank_count"):
            self.assertIn(key, rows["plain_member"])

        bank = self.client.post("/api/v1/banks", headers=admin, json={"name": "Admin Bank"})
        self.assertEqual(bank.status_code, 201, bank.text)
        rows = {
            row["username"]: row
            for row in self.client.get("/api/v1/admin/users", headers=admin).json()
        }
        self.assertEqual(rows["instance_admin"]["bank_count"], 1)
        self.assertEqual(rows["plain_member"]["bank_count"], 0)

        promoted = self.client.patch(
            f"/api/v1/admin/users/{member_id}", headers=admin, json={"is_admin": True}
        )
        self.assertEqual(promoted.status_code, 200, promoted.text)
        self.assertTrue(promoted.json()["is_admin"])

        disabled = self.client.patch(
            f"/api/v1/admin/users/{member_id}", headers=admin, json={"is_active": False}
        )
        self.assertEqual(disabled.status_code, 200, disabled.text)
        self.assertFalse(disabled.json()["is_active"])
        # Disabling is immediate: the device that was already signed in loses
        # access now, not when its 30-day token happens to expire.
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=member).status_code, 401)
        blocked_login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "plain_member", "password": "password-123456"},
        )
        self.assertEqual(blocked_login.status_code, 401)

        self.assertEqual(
            self.client.patch(
                f"/api/v1/admin/users/{admin_id}", headers=admin, json={"is_admin": False}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/v1/admin/users/{admin_id}", headers=admin, json={"is_active": False}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                "/api/v1/admin/users/does-not-exist", headers=admin, json={"is_active": False}
            ).status_code,
            404,
        )

    # -------------------------------------------------------- password reset

    def test_reset_password_issues_temp_password_and_revokes_sessions(self):
        admin, member = self._admin_and_member()
        member_id = self.client.get("/api/v1/auth/me", headers=member).json()["id"]
        _, second_device = self._login("plain_member", user_agent="second-device")

        reset = self.client.post(
            f"/api/v1/admin/users/{member_id}/reset-password", headers=admin
        )
        self.assertEqual(reset.status_code, 200, reset.text)
        body = reset.json()
        self.assertGreaterEqual(len(body["temporary_password"]), 12)
        self.assertTrue(body["user"]["must_change_password"])
        self.assertFalse(body["user"]["is_admin"])

        for headers in (member, second_device):
            self.assertEqual(
                self.client.get("/api/v1/auth/me", headers=headers).status_code, 401
            )
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/login",
                json={"username": "plain_member", "password": "password-123456"},
            ).status_code,
            401,
        )

        temp_token, temp_headers = self._login(
            "plain_member", password=body["temporary_password"]
        )
        self.assertTrue(temp_token)
        me = self.client.get("/api/v1/auth/me", headers=temp_headers)
        self.assertEqual(me.status_code, 200, me.text)
        self.assertTrue(me.json()["must_change_password"])

    # ------------------------------------------------------------- sessions

    def test_sessions_are_listed_and_other_devices_revoked(self):
        self._register("session_user")
        token_a, headers_a = self._login("session_user", user_agent="device-a")
        token_b, headers_b = self._login("session_user", user_agent="device-b")

        listing = self.client.get("/api/v1/auth/sessions", headers=headers_a)
        self.assertEqual(listing.status_code, 200, listing.text)
        sessions = listing.json()
        self.assertEqual(len(sessions), 2)
        current = [row for row in sessions if row["current"]]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["user_agent"], "device-a")
        self.assertIsNotNone(current[0]["last_seen_at"])
        self.assertEqual(
            sorted(row["user_agent"] for row in sessions), ["device-a", "device-b"]
        )
        for key in ("id", "created_at", "last_seen_at", "current"):
            self.assertIn(key, sessions[0])

        revoked = self.client.delete("/api/v1/auth/sessions", headers=headers_a)
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertEqual(revoked.json(), {"revoked": 1})
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers=headers_b).status_code, 401
        )
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers=headers_a).status_code, 200
        )
        self.assertEqual(
            self.client.get("/api/v1/auth/sessions").status_code, 401
        )

    def test_change_password_keeps_current_session_and_revokes_others(self):
        self._register("password_user")
        _, current = self._login("password_user")
        _, other = self._login("password_user")

        changed = self.client.post(
            "/api/v1/auth/change-password",
            headers=current,
            json={"old_password": "password-123456", "new_password": "new-password-123"},
        )
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers=other).status_code, 401
        )
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers=current).status_code, 200
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/login",
                json={"username": "password_user", "password": "password-123456"},
            ).status_code,
            401,
        )
        self._login("password_user", password="new-password-123")

    def test_auth_payloads_expose_instance_admin_role(self):
        admin, member = self._admin_and_member()
        self.assertTrue(self.client.get("/api/v1/auth/me", headers=admin).json()["is_admin"])
        self.assertFalse(self.client.get("/api/v1/auth/me", headers=member).json()["is_admin"])


if __name__ == "__main__":
    unittest.main()
