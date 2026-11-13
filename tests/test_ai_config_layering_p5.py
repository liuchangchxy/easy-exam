"""P5 AI/web configuration layering: partial saves and connection probes."""

import http.server
import os
import sqlite3
import tempfile
import threading
import unittest

from fastapi.testclient import TestClient

from backend.app.main import create_app

_SECRET = "easyexam-ci-secret-32bytes-passphrase!!"


class _OkHandler(http.server.BaseHTTPRequestHandler):
    def _reply(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    do_GET = _reply
    do_POST = _reply

    def log_message(self, *args):
        pass


class AiConfigLayeringP5Test(unittest.TestCase):
    def setUp(self):
        self._orig_secret = os.environ.get("EASYEXAM_SECRET_KEY")
        self._orig_search_url = os.environ.get("OPEN_WEBSEARCH_URL")
        self._orig_llm_base = os.environ.get("LLM_BASE_URL")
        os.environ["EASYEXAM_SECRET_KEY"] = _SECRET

        self._temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self._temp_db.name
        self._temp_db.close()
        self.client = TestClient(create_app(db_path=self.db_path))
        self.client.post(
            "/api/v1/auth/register", json={"username": "ai_user", "password": "password-123456"}
        )
        token = self.client.post(
            "/api/v1/auth/login", json={"username": "ai_user", "password": "password-123456"}
        ).json()["token"]
        self.headers = {"Authorization": f"Bearer {token}"}

        self._server = None
        self._server_thread = None

    def tearDown(self):
        self._stop_server()
        for key, value in (
            ("EASYEXAM_SECRET_KEY", self._orig_secret),
            ("OPEN_WEBSEARCH_URL", self._orig_search_url),
            ("LLM_BASE_URL", self._orig_llm_base),
        ):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for suffix in ("", "-wal", "-shm"):
            path = self.db_path + suffix
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    # ------------------------------------------------------------------ helpers

    def _start_server(self) -> str:
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _OkHandler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        return f"http://127.0.0.1:{self._server.server_address[1]}/v1/search"

    def _stop_server(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._server_thread is not None:
            self._server_thread.join(timeout=2)
            self._server_thread = None

    def _row(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT ai_provider, ai_api_base, ai_model, ai_api_key,
                          search_provider, search_api_key, search_api_base
                   FROM user_ai_configs"""
            ).fetchone()
        return dict(row) if row else {}

    # -------------------------------------------------------------- partial save

    def test_patch_partial_does_not_touch_other_columns(self):
        saved = self.client.put(
            "/api/v1/ai/config",
            headers=self.headers,
            json={
                "ai_provider": "ollama",
                "ai_api_base": "http://127.0.0.1:11434/v1",
                "ai_model": "qwen2.5:7b",
                "ai_api_key": "sk-owner-secret-123456",
                "search_provider": "open-webSearch",
                "search_api_base": "http://127.0.0.1:8000/v1/search",
            },
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        before = self._row()

        patched = self.client.patch("/api/v1/ai/config", headers=self.headers, json={"ai_model": "qwen2.5:14b"})
        self.assertEqual(patched.status_code, 200, patched.text)
        body = patched.json()
        self.assertEqual(body["ai_model"], "qwen2.5:14b")
        self.assertEqual(body["search_api_base"], "http://127.0.0.1:8000/v1/search")

        after = self._row()
        self.assertEqual(after["ai_model"], "qwen2.5:14b")
        self.assertEqual(after["search_api_base"], before["search_api_base"])
        self.assertEqual(after["ai_api_base"], before["ai_api_base"])
        self.assertEqual(after["ai_provider"], "ollama")
        # Key ciphertext survives a PATCH that never mentions the key.
        self.assertEqual(after["ai_api_key"], before["ai_api_key"])
        self.assertNotIn("sk-owner-secret-123456", after["ai_api_key"])

    def test_patch_on_fresh_user_does_not_stamp_defaults(self):
        resp = self.client.patch("/api/v1/ai/config", headers=self.headers, json={"ai_model": "only-this-model"})
        self.assertEqual(resp.status_code, 200, resp.text)
        row = self._row()
        self.assertEqual(row["ai_model"], "only-this-model")
        # Untouched columns stay unset instead of being stamped with the
        # hardcoded search/ai defaults that masked instance env configuration.
        self.assertEqual(row["ai_api_base"], "")
        self.assertEqual(row["search_api_base"], "")
        self.assertEqual(row["search_provider"], "")

        # The public shape still reports the documented defaults.
        public = self.client.get("/api/v1/ai/config", headers=self.headers).json()
        self.assertEqual(public["search_api_base"], "http://localhost:8000/v1/search")
        self.assertEqual(public["ai_api_base"], "https://api.openai.com/v1")
        self.assertTrue(public["has_custom_config"])

    def test_put_remains_compatible(self):
        resp = self.client.put(
            "/api/v1/ai/config",
            headers=self.headers,
            json={"ai_provider": "openai", "ai_api_key": "sk-compat-123456789"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn("******", resp.json()["ai_api_key"])
        public = self.client.get("/api/v1/ai/config", headers=self.headers).json()
        self.assertTrue(public["is_configured"])
        self.assertEqual(
            set(public),
            {
                "ai_provider",
                "ai_api_base",
                "ai_model",
                "ai_api_key",
                "search_provider",
                "search_api_key",
                "search_api_base",
                "updated_at",
                "has_custom_config",
                "is_configured",
            },
        )

    # --------------------------------------------------------------- test probe

    def test_test_endpoint_reports_unreachable_without_raising(self):
        self.client.put(
            "/api/v1/ai/config",
            headers=self.headers,
            json={
                "ai_provider": "openai",
                "ai_api_base": "http://127.0.0.1:9/v1",
                "ai_model": "m",
                "ai_api_key": "sk-super-secret-probe-key",
                "search_provider": "open-webSearch",
                "search_api_base": "http://127.0.0.1:9/v1/search",
            },
        )
        for kind in ("ai", "search"):
            resp = self.client.post("/api/v1/ai/config/test", headers=self.headers, json={"kind": kind})
            self.assertEqual(resp.status_code, 200, resp.text)
            body = resp.json()
            self.assertFalse(body["ok"], body)
            self.assertTrue(body["message"])
            self.assertNotIn("sk-super-secret-probe-key", body["message"])
            self.assertNotIn("127.0.0.1", body["message"])

        invalid = self.client.post("/api/v1/ai/config/test", headers=self.headers, json={"kind": "bogus"})
        self.assertEqual(invalid.status_code, 422)

    def test_test_endpoint_uses_instance_env_when_user_has_no_config(self):
        url = self._start_server()
        os.environ["OPEN_WEBSEARCH_URL"] = url

        resp = self.client.post("/api/v1/ai/config/test", headers=self.headers, json={"kind": "search"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["ok"], resp.json())

        # A saved user base overrides the instance default, so an unreachable
        # custom endpoint must fail even though the env endpoint still works.
        self.client.patch(
            "/api/v1/ai/config", headers=self.headers, json={"search_api_base": "http://127.0.0.1:9/custom"}
        )
        resp = self.client.post("/api/v1/ai/config/test", headers=self.headers, json={"kind": "search"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertFalse(resp.json()["ok"], resp.json())


if __name__ == "__main__":
    unittest.main()
