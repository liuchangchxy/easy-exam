#!/usr/bin/env python3
"""Universal smoke test for Vibe Coding Starter template.

Ensures the testing harness is fully operational right after cloning.
"""
import json
import unittest
from pathlib import Path


class TestSmoke(unittest.TestCase):
    """Smoke test to verify test harness and environment health."""

    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent

    def test_environment_healthy(self):
        """Verify baseline test environment passes."""
        self.assertTrue(True, "Environment is operational.")

    def test_spec_exists(self):
        """Verify SPEC.md exists as the Single Source of Truth."""
        spec_file = self.root / "SPEC.md"
        self.assertTrue(spec_file.exists(), "SPEC.md must exist in project root.")

    def test_agents_rule_exists(self):
        """Verify AGENTS.md exists for AI agents."""
        agents_file = self.root / "AGENTS.md"
        self.assertTrue(agents_file.exists(), "AGENTS.md must exist in project root.")

    def test_checkpoint_script_exists(self):
        """Verify checkpoint manager script exists."""
        cp_file = self.root / "scripts" / "checkpoint.py"
        self.assertTrue(cp_file.exists(), "scripts/checkpoint.py must exist.")

    def test_devcontainer_valid(self):
        """Verify .devcontainer/devcontainer.json exists and is valid JSON."""
        dc_file = self.root / ".devcontainer" / "devcontainer.json"
        self.assertTrue(dc_file.exists(), ".devcontainer/devcontainer.json must exist.")
        data = json.loads(dc_file.read_text(encoding="utf-8"))
        self.assertIn("name", data)

    def test_specs_directory_exists(self):
        """Verify modular specs directory exists for scaling."""
        specs_dir = self.root / "specs"
        self.assertTrue(specs_dir.is_dir(), "specs/ directory must exist.")

    def test_sponsor_and_faq_exist(self):
        """Verify SPONSOR.md and FAQ.md exist in project root."""
        self.assertTrue((self.root / "SPONSOR.md").exists(), "SPONSOR.md must exist.")
        self.assertTrue((self.root / "SPONSOR.zh-CN.md").exists(), "SPONSOR.zh-CN.md must exist.")
        self.assertTrue((self.root / "FAQ.md").exists(), "FAQ.md must exist.")
        self.assertTrue((self.root / "FAQ.zh-CN.md").exists(), "FAQ.zh-CN.md must exist.")

    def test_guard_scripts_exist(self):
        """Verify anti-tampering and path scan guard scripts exist."""
        self.assertTrue((self.root / "scripts" / "guard_test_tampering.py").exists(), "scripts/guard_test_tampering.py must exist.")
        self.assertTrue((self.root / "scripts" / "scan_hardcoded_paths.py").exists(), "scripts/scan_hardcoded_paths.py must exist.")

    def test_no_hardcoded_paths_in_repo(self):
        """Verify zero hardcoded absolute paths exist in codebase."""
        import subprocess
        import sys
        res = subprocess.run(
            [sys.executable, str(self.root / "scripts" / "scan_hardcoded_paths.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        self.assertEqual(res.returncode, 0, f"Hardcoded path scan failed: {res.stderr}\n{res.stdout}")


if __name__ == "__main__":
    unittest.main()
