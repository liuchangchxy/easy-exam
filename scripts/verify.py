#!/usr/bin/env python3
"""Unified verification entrypoints for EasyExam development workflow.

Usage:
    python scripts/verify.py fast
    python scripts/verify.py ui
    python scripts/verify.py full
"""
import os
import sys
import time
import shutil
import tempfile
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def run_step(name: str, cmd: list[str], env: dict | None = None) -> None:
    print(f"\n[verify] === Running: {name} ===")
    print(f"[verify] Command: {' '.join(cmd)}")
    start = time.time()
    res = subprocess.run(cmd, cwd=REPO_ROOT, env=env, shell=(sys.platform == "win32"))
    elapsed = time.time() - start
    if res.returncode != 0:
        print(f"\n[verify] ❌ Step '{name}' FAILED with exit code {res.returncode} in {elapsed:.2f}s")
        sys.exit(res.returncode)
    print(f"[verify] ✅ Step '{name}' PASSED in {elapsed:.2f}s")

def verify_fast():
    print("[verify] Mode: FAST (Static guards, frontend unit/contracts, and component integration tests)")
    total_start = time.time()
    run_step("Check Whitespace", [sys.executable, "scripts/check_whitespace.py"])
    run_step("Guard Test Tampering", [sys.executable, "scripts/guard_test_tampering.py"])
    run_step("Scan Hardcoded Paths", [sys.executable, "scripts/scan_hardcoded_paths.py"])
    run_step("Frontend Unit & Component Tests", ["npm", "--prefix", "frontend", "run", "test:unit"])
    total_elapsed = time.time() - total_start
    print(f"\n[verify] 🟢 verify:fast COMPLETED SUCCESSFULLY in {total_elapsed:.2f}s")

def verify_ui():
    print("[verify] Mode: UI (Frontend unit/contracts, fast UI interaction, and mobile interaction suite)")
    total_start = time.time()
    run_step("Frontend Unit & Contracts", ["npm", "--prefix", "frontend", "run", "test:unit"])
    run_step("Fast UI Interaction", ["node", "frontend/tests/fast_ui_interaction.test.js"])
    run_step("Mobile Interaction Suite", ["node", "frontend/tests/mobile_interaction_suite.mjs"])
    total_elapsed = time.time() - total_start
    print(f"\n[verify] 🟢 verify:ui COMPLETED SUCCESSFULLY in {total_elapsed:.2f}s")

def verify_full():
    print("[verify] Mode: FULL (Complete required CI gates, clean isolated database)")
    total_start = time.time()

    # 1. Guards & Quality
    run_step("Check Whitespace", [sys.executable, "scripts/check_whitespace.py"])
    run_step("Guard Test Tampering", [sys.executable, "scripts/guard_test_tampering.py"])
    run_step("Scan Hardcoded Paths", [sys.executable, "scripts/scan_hardcoded_paths.py"])

    # 2. Backend Suite with clean isolated database environment
    temp_dir = tempfile.mkdtemp(prefix="easyexam_verify_data_")
    backend_env = os.environ.copy()
    backend_env["DATA_DIR"] = temp_dir
    try:
        run_step("Backend Test Suite", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], env=backend_env)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    run_step("Coordination Cleanup Test", ["node", "--test", "tests/coordination-label-cleanup.test.js"])

    # 3. Frontend Unit, Component & Build
    run_step("Frontend Unit & Component Tests", ["npm", "--prefix", "frontend", "run", "test:unit"])
    run_step("Production Build", ["npm", "--prefix", "frontend", "run", "build"])

    # 4. Browser E2E & Mobile Interaction
    run_step("Fast UI Interaction", ["node", "frontend/tests/fast_ui_interaction.test.js"])
    run_step("Mobile Interaction E2E", ["node", "frontend/tests/mobile_interaction_suite.mjs"])
    run_step("Localization Browser E2E", ["npm", "--prefix", "frontend", "run", "test:localization:e2e"])
    run_step("Full Browser E2E", ["npm", "--prefix", "frontend", "run", "test:e2e"])

    total_elapsed = time.time() - total_start
    print(f"\n[verify] 🟢 verify:full COMPLETED SUCCESSFULLY in {total_elapsed:.2f}s")

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("fast", "ui", "full"):
        print("Usage: python scripts/verify.py [fast|ui|full]")
        sys.exit(1)

    mode = sys.argv[1]
    if mode == "fast":
        verify_fast()
    elif mode == "ui":
        verify_ui()
    elif mode == "full":
        verify_full()

if __name__ == "__main__":
    main()
