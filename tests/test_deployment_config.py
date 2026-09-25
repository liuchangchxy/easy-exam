"""Tests for containerization, deployment configurations, and fnOS recipes."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import yaml

from backend.config import BASE_DIR, get_settings


class TestDeploymentConfig(unittest.TestCase):
    """Verify Dockerfile, docker-compose.yml, requirements.txt, and deploy scripts."""

    def test_dockerfile_multi_stage_structure(self):
        """Dockerfile must have 2 stages: node builder and python 3.11-alpine runtime."""
        dockerfile_path = BASE_DIR / "Dockerfile"
        self.assertTrue(dockerfile_path.is_file(), f"Dockerfile missing at {dockerfile_path}")

        content = dockerfile_path.read_text(encoding="utf-8")

        # Stage 1: Frontend builder
        self.assertIn("node:20-alpine", content)
        self.assertIn("frontend-builder", content)
        self.assertTrue("npm run build" in content)

        # Stage 2: Minimal python alpine runtime
        self.assertIn("python:3.11-alpine", content)
        self.assertIn("--no-cache-dir", content)
        self.assertIn("COPY backend/", content)
        self.assertIn("/app/frontend/dist", content)

        # Environment & Volume & Port
        self.assertIn("DATA_DIR=/app/data", content)
        self.assertIn("PORT=3000", content)
        self.assertIn("HOST=0.0.0.0", content)
        self.assertIn("PYTHONUNBUFFERED=1", content)
        self.assertIn("VOLUME /app/data", content)
        self.assertIn("EXPOSE 3000", content)

        # Healthcheck & CMD
        self.assertIn("HEALTHCHECK", content)
        self.assertIn("/api/v1/health", content)
        self.assertIn("backend.app.main:app", content)

    def test_docker_compose_fnos_compatibility(self):
        """docker-compose.yml must be valid YAML with fnOS volume mapping and Ollama endpoint."""
        compose_path = BASE_DIR / "docker-compose.yml"
        self.assertTrue(compose_path.is_file(), f"docker-compose.yml missing at {compose_path}")

        raw_yaml = compose_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw_yaml)

        service_name = "easy-exam" if "easy-exam" in parsed["services"] else "fn-exam"
        self.assertIn(service_name, parsed["services"])

        svc = parsed["services"][service_name]
        self.assertIn(svc.get("image"), ["ailm32442/easy-exam:latest", "ailm32442/fn-exam:latest"])
        self.assertEqual(svc.get("restart"), "unless-stopped")

        # Check port mapping: 3000:3000
        ports = [str(p) for p in svc.get("ports", [])]
        self.assertTrue(any("3000:3000" in p for p in ports), f"Port 3000:3000 not in {ports}")

        # Check volume mapping: ./data:/app/data
        volumes = svc.get("volumes", [])
        self.assertTrue(any("./data:/app/data" in v for v in volumes), f"Volume ./data:/app/data not in {volumes}")

        # Check env vars
        env = svc.get("environment", {})
        if isinstance(env, list):
            env_map = {}
            for item in env:
                if "=" in item:
                    k, v = item.split("=", 1)
                    env_map[k] = v
            env = env_map

        self.assertEqual(str(env.get("PORT")), "3000")
        self.assertIn("host.docker.internal:11434/v1", env.get("LLM_BASE_URL", ""))

    def test_requirements_minimal_and_clean(self):
        """requirements.txt must contain only minimal production packages without bloat."""
        req_path = BASE_DIR / "requirements.txt"
        self.assertTrue(req_path.is_file(), f"requirements.txt missing at {req_path}")

        req_content = req_path.read_text(encoding="utf-8").lower()
        self.assertIn("fastapi", req_content)
        self.assertIn("uvicorn", req_content)
        self.assertIn("pydantic", req_content)

        # Zero heavy bloat packages to ensure ultra-lightweight fnOS runtime
        bloat_pkgs = ["torch", "tensorflow", "scipy", "pandas", "numpy", "langchain"]
        for bloat in bloat_pkgs:
            self.assertNotIn(bloat, req_content, f"Bloated dependency {bloat} should not be in production requirements")

    def test_deployment_scripts_exist_and_configured(self):
        """Both Linux shell script and Windows PowerShell deployment script must exist."""
        sh_path = BASE_DIR / "scripts" / "deploy_fnos.sh"
        ps1_path = BASE_DIR / "scripts" / "deploy_fnos.ps1"

        self.assertTrue(sh_path.is_file(), f"deploy_fnos.sh missing at {sh_path}")
        self.assertTrue(ps1_path.is_file(), f"deploy_fnos.ps1 missing at {ps1_path}")

        sh_content = sh_path.read_text(encoding="utf-8")
        self.assertTrue(sh_content.startswith("#!"), "deploy_fnos.sh must have shebang")
        self.assertIn("docker", sh_content)
        self.assertIn("3000", sh_content)
        self.assertIn("/api/health", sh_content)

        ps1_content = ps1_path.read_text(encoding="utf-8")
        self.assertIn("docker", ps1_content)
        self.assertIn("3000", ps1_content)
        self.assertIn("/api/health", ps1_content)

    def test_backend_config_data_dir_env(self):
        """When DATA_DIR is configured, default DB path resolves to $DATA_DIR/fnexam.db."""
        custom_data = "/fnos_pool/appdata/fnexam"
        with patch.dict(os.environ, {"DATA_DIR": custom_data}, clear=False):
            # If DB_PATH is not explicitly set, should default to custom_data / fnexam.db
            if "DB_PATH" in os.environ:
                with patch.dict(os.environ, {"DB_PATH": ""}):
                    settings = get_settings()
            else:
                settings = get_settings()

            expected_prefix = str(Path(custom_data))
            self.assertTrue(
                settings.db_path.startswith(expected_prefix),
                f"db_path {settings.db_path} does not use custom DATA_DIR {custom_data}",
            )

    def test_practice_view_v1_is_active(self):
        """The active practice view uses the modular v1 API client."""
        view_path = BASE_DIR / "frontend" / "src" / "views" / "PracticeViewV1.vue"
        self.assertTrue(view_path.is_file(), f"PracticeViewV1.vue missing at {view_path}")
        view_content = view_path.read_text(encoding="utf-8")
        self.assertIn("submitAttempt", view_content)
        self.assertIn("getSessionQuestions", view_content)


if __name__ == "__main__":
    unittest.main()
