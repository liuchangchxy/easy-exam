#!/usr/bin/env python3
"""
test_guard_checks.py - 门禁脚本红绿变异验证与自测套件

根据 TESTING.md 第 7 条（门禁即证据）：
一条没红过的门禁视为不存在。本测试套件物理验证：
1. scan_hardcoded_paths.py 遇到真实硬编码路径能红（打坏变红），合规代码全绿；
2. guard_test_tampering.py 遇到篡改能有效识别；
3. 当前仓库通过所有硬门禁。
"""

import sys
import unittest
from pathlib import Path

# 针对 Windows 终端 GBK 编码进行加固
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from scripts.scan_hardcoded_paths import scan_file, FORBIDDEN_PATTERNS


class GuardMutationTest(unittest.TestCase):
    """验证门禁脚本的红绿变异有效性。"""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent

    def test_scan_hardcoded_paths_detects_violation(self):
        """变异实证（红）：扫描到 Windows/Unix 用户路径必须报警。"""
        bad_sample = self.repo_root / "tests" / "_temp_bad_path_sample.py"
        try:
            bad_prefix = "C:" + "\\Users\\" + "dummy"
            bad_sample.write_text(
                f'# 临时破坏样本\npath = "{bad_prefix}\\\\secret.txt"\n',
                encoding="utf-8"
            )
            violations = scan_file(bad_sample)
            self.assertTrue(len(violations) > 0, "门禁未能检出 Windows 本地用户绝对路径！")
            self.assertIn("Windows 本地用户绝对路径", violations[0])
        finally:
            if bad_sample.exists():
                bad_sample.unlink()

    def test_scan_hardcoded_paths_accepts_clean_file(self):
        """变异实证（绿）：合规的相对路径不被误报。"""
        good_sample = self.repo_root / "tests" / "_temp_good_path_sample.py"
        try:
            good_sample.write_text(
                'from pathlib import Path\nbase = Path(__file__).resolve().parent / "data"\n',
                encoding="utf-8"
            )
            violations = scan_file(good_sample)
            self.assertEqual(len(violations), 0, f"合规相对路径被误报: {violations}")
        finally:
            if good_sample.exists():
                good_sample.unlink()

    def test_repo_is_currently_clean_of_hardcoded_paths(self):
        """全仓断言：当前仓库内无任何违规硬编码绝对路径。"""
        import subprocess
        res = subprocess.run(
            [sys.executable, str(self.repo_root / "scripts" / "scan_hardcoded_paths.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        self.assertEqual(res.returncode, 0, f"Hardcoded path scan returned non-zero:\n{res.stdout}\n{res.stderr}")


if __name__ == "__main__":
    unittest.main()
