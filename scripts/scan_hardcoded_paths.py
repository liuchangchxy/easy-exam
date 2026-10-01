#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_hardcoded_paths.py - 源码硬编码绝对路径扫描门禁
扫描项目源码中是否存在硬编码的系统级绝对路径（如 C:\\Users\\, /home/user/ 等）。
必须使用相对基准路径（如 Path(__file__).resolve().parent）或环境变量进行动态定位。
"""

import os
import re
import sys
from pathlib import Path

# 针对 Windows 终端 GBK 编码进行加固
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 排除目录
IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".idea", ".vscode", "dist", "build", "coverage", ".pytest_cache"
}

# 忽略的文件后缀 (Markdown 文档包含反面示例说明，门禁聚焦代码执行源文件与配置文件)
IGNORED_EXTENSIONS = {
    ".pyc", ".png", ".jpg", ".jpeg", ".ico", ".svg", ".lock", ".log", ".md"
}

# 违规硬编码绝对路径模式
FORBIDDEN_PATTERNS = [
    (re.compile(r'[a-zA-Z]:\\+(?:Users|Documents|Desktop|Projects|code)\\+', re.IGNORECASE), "Windows 本地用户绝对路径"),
    (re.compile(r'[a-zA-Z]:/(?:Users|Documents|Desktop|Projects|code)/', re.IGNORECASE), "Windows 正斜杠用户绝对路径"),
    (re.compile(r'/(?:Users|home)/[a-zA-Z0-9_\-]+/', re.IGNORECASE), "Unix/macOS 用户家目录绝对路径"),
]

def scan_file(file_path: Path) -> list[str]:
    violations = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return violations

    for line_num, line in enumerate(content.splitlines(), start=1):
        for pattern, desc in FORBIDDEN_PATTERNS:
            if pattern.search(line):
                violations.append(f"{file_path}:{line_num} -> [{desc}] {line.strip()[:100]}")
    return violations

def main():
    root_dir = Path(__file__).resolve().parent.parent
    total_violations = []

    for root, dirs, files in os.walk(root_dir):
        # 过滤目录
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in IGNORED_EXTENSIONS:
                continue
            # 排除当前扫描脚本自身以及规则说明文档中举反例的地方
            if p.name in ["scan_hardcoded_paths.py", "FAQ.md", "AGENTS.md", "README.md", "I18N_AND_THEME_ARCHITECTURE.md"]:
                continue

            violations = scan_file(p)
            total_violations.extend(violations)

    if total_violations:
        print("\n❌ [硬编码路径门禁拦截 (Hardcoded Path Gate)]", file=sys.stderr)
        print("检测到代码中存在硬编码物理绝对路径！这会导致代码在他人机器或 CI 环境中直接崩溃。", file=sys.stderr)
        print("必须使用相对基准定位（如 Path(__file__).resolve().parent / import.meta.url）或环境变量。\n", file=sys.stderr)
        for v in total_violations:
            print(f"  🔴 {v}", file=sys.stderr)
        sys.exit(1)

    print("✅ [硬编码路径检查通过] 未发现写死物理绝对路径。")
    sys.exit(0)

if __name__ == "__main__":
    main()
