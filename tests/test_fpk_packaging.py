"""Tests for fnOS FPK package specification and packaging scripts."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import yaml

from backend.config import BASE_DIR
from scripts.build_fpk import (
    build_fpk,
    parse_manifest,
    validate_fpk_sources,
    package_fpk_python,
)

FPK_DIR = BASE_DIR / "fpk" / "easy-exam"


class TestFpkPackaging(unittest.TestCase):
    """Verify fnOS FPK source tree, manifest, compose, and archive generation."""

    def test_manifest_specification(self):
        """Manifest must adhere to fnOS specs with pinned version and port 3000."""
        manifest_path = FPK_DIR / "manifest"
        self.assertTrue(manifest_path.is_file(), f"manifest missing at {manifest_path}")

        meta = parse_manifest(manifest_path)
        self.assertEqual(meta.get("appname"), "easy-exam")
        version = meta.get("version")
        self.assertTrue(bool(version), "version must not be empty")
        self.assertIn("易考宝", meta.get("display_name", ""))
        self.assertEqual(meta.get("platform"), "x86")
        self.assertEqual(meta.get("service_port"), "3000")
        self.assertEqual(meta.get("checkport"), "true")
        self.assertEqual(meta.get("ctl_stop"), "true")
        self.assertEqual(meta.get("desktop_uidir"), "ui")
        self.assertEqual(meta.get("desktop_applaunchname"), "easy-exam.main")

    def test_privilege_and_resource_json(self):
        """Privilege and resource files must be valid JSON with correct schemas."""
        priv_path = FPK_DIR / "config" / "privilege"
        res_path = FPK_DIR / "config" / "resource"

        self.assertTrue(priv_path.is_file(), "config/privilege missing")
        self.assertTrue(res_path.is_file(), "config/resource missing")

        priv = json.loads(priv_path.read_text(encoding="utf-8"))
        self.assertIn(priv.get("defaults", {}).get("run-as"), ["package", "root"])
        self.assertEqual(priv.get("username"), "easy_exam")
        self.assertIn("docker", priv.get("join-groups", []))

        res = json.loads(res_path.read_text(encoding="utf-8"))
        projects = res.get("docker-project", {}).get("projects", [])
        self.assertTrue(len(projects) > 0, "No docker projects declared")
        self.assertEqual(projects[0].get("name"), "easy-exam")
        self.assertEqual(projects[0].get("path"), "docker")

    def test_docker_compose_fpk_configuration(self):
        """Compose file in FPK must use fixed pinned image, fnOS TRIM_PKGVAR, and port 3000."""
        manifest_meta = parse_manifest(FPK_DIR / "manifest")
        expected_version = manifest_meta.get("version")
        compose_path = FPK_DIR / "app" / "docker" / "docker-compose.yaml"
        self.assertTrue(compose_path.is_file(), "docker-compose.yaml missing")

        raw = compose_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw)
        svc = parsed["services"]["easy-exam"]

        # Image MUST be pinned to manifest version, NOT latest
        self.assertEqual(svc.get("image"), f"ailm32442/easy-exam:{expected_version}")
        self.assertNotEqual(svc.get("image"), "ailm32442/easy-exam:latest")

        # Container name must exist
        self.assertEqual(svc.get("container_name"), "easy-exam-fpk")

        # Port mapping
        ports = [str(p) for p in svc.get("ports", [])]
        self.assertTrue(any("3000" in p for p in ports), f"Port 3000 missing in {ports}")

        # Persistent volume
        volumes = svc.get("volumes", [])
        self.assertTrue(
            any("/app/data" in v and "TRIM_PKGVAR" in v for v in volumes),
            f"Volume mapping to /app/data with TRIM_PKGVAR missing in {volumes}",
        )

        # Environment variable injection
        env = svc.get("environment", [])
        self.assertTrue(
            any("EASYEXAM_SECRET_KEY=${EASYEXAM_SECRET_KEY}" in str(e) for e in env),
            f"EASYEXAM_SECRET_KEY missing in FPK compose environment: {env}",
        )
        self.assertNotIn("easyexam-secure-vault-default-key-v1", raw)

    def test_ui_config(self):
        """UI config must define desktop iframe entry on port 3000."""
        ui_cfg_path = FPK_DIR / "app" / "ui" / "config"
        self.assertTrue(ui_cfg_path.is_file(), "app/ui/config missing")

        ui_cfg = json.loads(ui_cfg_path.read_text(encoding="utf-8"))
        entry = ui_cfg.get(".url", {}).get("easy-exam.main", {})
        self.assertEqual(entry.get("type"), "iframe")
        self.assertEqual(str(entry.get("port")), "3000")
        self.assertEqual(entry.get("url"), "/")
        self.assertTrue(entry.get("allUsers"))

    def test_cmd_scripts_syntax_and_lf(self):
        """All lifecycle scripts in cmd/ must use Unix LF line endings and no syntax error."""
        cmd_dir = FPK_DIR / "cmd"
        self.assertTrue(cmd_dir.is_dir(), "cmd/ missing")

        required_scripts = ["main", "install_init", "install_callback", "upgrade_callback", "uninstall_callback"]
        for s in required_scripts:
            sp = cmd_dir / s
            self.assertTrue(sp.is_file(), f"cmd/{s} missing")
            content = sp.read_bytes()
            self.assertTrue(content.startswith(b"#!/bin/bash"), f"cmd/{s} missing shebang")
            self.assertNotIn(b"\r\n", content, f"cmd/{s} has Windows CRLF line endings")

    def test_icons_exist_and_dimensions(self):
        """Application icons must exist with 64x64 and 256x256 resolutions."""
        icon_small = FPK_DIR / "ICON.PNG"
        icon_large = FPK_DIR / "ICON_256.PNG"
        ui_icon_64 = FPK_DIR / "app" / "ui" / "images" / "icon_64.png"
        ui_icon_256 = FPK_DIR / "app" / "ui" / "images" / "icon_256.png"

        for p in [icon_small, icon_large, ui_icon_64, ui_icon_256]:
            self.assertTrue(p.is_file(), f"Icon {p} missing")
            self.assertGreater(p.stat().st_size, 100, f"Icon {p} is empty or too small")

    def test_python_packaging_build_and_archive_integrity(self):
        """Python packager produces valid .fpk archive with app.tgz and matching checksum."""
        import tarfile

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "easy-exam-1.0.0.fpk"
            package_fpk_python(FPK_DIR, out_file)

            self.assertTrue(out_file.is_file(), "FPK file not generated")
            self.assertTrue(tarfile.is_tarfile(out_file), "FPK is not a valid tar archive")

            with tarfile.open(out_file, "r:gz") as tar:
                names = set(tar.getnames())
                self.assertIn("app.tgz", names)
                self.assertIn("manifest", names)
                self.assertIn("cmd/main", names)
                self.assertIn("config/privilege", names)
                self.assertIn("config/resource", names)
                self.assertIn("ICON.PNG", names)
                self.assertIn("ICON_256.PNG", names)

                # Verify checksum in manifest matches app.tgz MD5
                app_tgz_bytes = tar.extractfile("app.tgz").read()
                expected_md5 = hashlib.md5(app_tgz_bytes).hexdigest()

                manifest_text = tar.extractfile("manifest").read().decode("utf-8")
                self.assertIn(f"checksum              = {expected_md5}", manifest_text)

                # Verify cmd/main permissions
                main_info = tar.getmember("cmd/main")
                self.assertEqual(main_info.mode, 0o755)

                # Verify inner app.tgz contains compose and ui
                with tarfile.open(fileobj=io.BytesIO(app_tgz_bytes), mode="r:gz") as inner_tar:
                    inner_names = set(inner_tar.getnames())
                    self.assertIn("docker/docker-compose.yaml", inner_names)
                    self.assertIn("ui/config", inner_names)

    def test_install_callback_cryptographic_random_requirement(self):
        """install_callback must forbid weak date/time hash fallback and abort on key generation failure."""
        script_path = FPK_DIR / "cmd" / "install_callback"
        self.assertTrue(script_path.is_file(), "cmd/install_callback missing")

        content = script_path.read_text(encoding="utf-8")

        # 1. Must NOT contain weak date/time hash fallback
        self.assertNotIn("date +%s", content)
        self.assertNotIn("date +", content)
        self.assertNotIn("sha256sum", content)

        # 2. Must use cryptographically secure sources
        self.assertTrue("secrets.token_hex" in content or "openssl rand" in content or "/dev/urandom" in content)

        # 3. Must abort (exit 1) on generation failure with explicit error message
        self.assertIn("exit 1", content)
        self.assertTrue("Cryptographic random source unavailable" in content or "Failed to generate" in content)


if __name__ == "__main__":
    unittest.main()
