"""Integration tests for frontend static file hosting in FastAPI."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from backend.config import BASE_DIR
from backend.main import create_app


class TestFrontendIntegration(unittest.TestCase):
    """Verify frontend static asset mounting, PWA meta tags, and root routing."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fnexam_front_")
        self.db_path = os.path.join(self.temp_dir, "test.db")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mock_dist_served_at_root(self):
        """When a dist directory exists, FastAPI mounts it at / while preserving /api/*."""
        mock_dist = Path(self.temp_dir) / "mock_dist"
        mock_dist.mkdir(parents=True)
        (mock_dist / "index.html").write_text(
            "<!DOCTYPE html><html><head><title>FnExam Mock</title></head><body><div id=\"app\"></div></body></html>",
            encoding="utf-8",
        )
        assets_dir = mock_dist / "assets"
        assets_dir.mkdir()
        (assets_dir / "mock.js").write_text("console.log('fn-exam-mock');", encoding="utf-8")

        app = create_app(db_path=self.db_path, dist_dir=mock_dist)
        client = TestClient(app)

        # 1. Root / serves index.html
        res_root = client.get("/")
        self.assertEqual(res_root.status_code, 200)
        self.assertIn("FnExam Mock", res_root.text)
        self.assertIn('<div id="app"></div>', res_root.text)

        # 2. Asset file is served
        res_asset = client.get("/assets/mock.js")
        self.assertEqual(res_asset.status_code, 200)
        self.assertIn("fn-exam-mock", res_asset.text)

        # 3. API route is not shadowed
        res_api = client.get("/api/health")
        self.assertEqual(res_api.status_code, 200)
        self.assertEqual(res_api.json().get("status"), "ok")

    def test_real_frontend_dist_exists_and_served(self):
        """Verify the built frontend/dist exists, has PWA metadata, and is served by default create_app()."""
        dist_dir = BASE_DIR / "frontend" / "dist"
        if not dist_dir.exists() and (BASE_DIR / "frontend" / "package.json").exists():
            import subprocess
            subprocess.run(
                ["npm", "run", "build"],
                cwd=str(BASE_DIR / "frontend"),
                shell=True,
                check=True,
                encoding="utf-8",
                errors="replace",
            )
        self.assertTrue(dist_dir.is_dir(), f"frontend/dist directory does not exist at {dist_dir}")
        index_file = dist_dir / "index.html"
        self.assertTrue(index_file.is_file(), f"frontend/dist/index.html does not exist at {index_file}")

        html_content = index_file.read_text(encoding="utf-8")
        self.assertIn('id="app"', html_content)
        self.assertIn("viewport", html_content)
        self.assertIn("apple-mobile-web-app-capable", html_content)

        # Default create_app() should mount BASE_DIR / frontend / dist
        app = create_app(db_path=self.db_path)
        client = TestClient(app)

        res = client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertIn('id="app"', res.text)
