## 关联 Issue

- **Closes / Relates**: <!-- 例如: Part of #1 / Closes #2 -->
- **Issue 链接**: <!-- 例如: https://github.com/liuchangchxy/easy-exam/issues/2 -->
- **Frozen Spec**: <!-- 引用或列出对应 Issue 冻结的规范要求 -->

## 实际改动范围

- <!-- 列出本 PR 涉及修改或新增的文件及范围说明 -->

## 是否偏离 Frozen Spec

- [ ] 完全符合 Frozen Spec，无范围外改动
- [ ] 存在偏离（说明偏离原因，并关联下方后续 Issue）
<!-- 若有偏离，在此详细说明具体原因 -->

## 实际运行的测试命令及结果

> 说明：不得预先勾选通过，也不得将未运行检查默认为通过。提交者无需手工填写 head SHA，head SHA 由 GitHub Actions CI 自动从 `github.event.pull_request.head.sha` 读取并记录。

| 检查项 | 执行命令 | 实际结果（PASS / FAIL / SKIPPED / NOT RUN） | 备注与日志链接 |
|---|---|---|---|
| 空白与 Git diff 检查 | `python scripts/check_whitespace.py`；`git diff --check <base> <head>` |  |  |
| 源码防篡改与绝对路径守卫 | `python scripts/guard_test_tampering.py`；`python scripts/scan_hardcoded_paths.py`；`python -m unittest discover -s tests -p test_guard_checks.py -v` |  |  |
| FPK 打包规范检查 | `python -m unittest tests.test_fpk_packaging -v` |  |  |
| 后端全量测试 | `python -m unittest discover -s tests -v` |  |  |
| 前端双语静态检查 | `npm --prefix frontend run check:localization` |  |  |
| 前端单元测试 | `npm --prefix frontend run test:unit` |  |  |
| 前端生产构建 | `npm --prefix frontend run build` |  |  |
| 双语真实浏览器 E2E | `npm --prefix frontend run test:localization:e2e` |  |  |
| 真实浏览器 E2E 全链路 | `npm --prefix frontend run test:e2e` |  |  |
| 移动端交互 E2E | `node frontend/tests/mobile_interaction_suite.mjs` |  |  |

## 跳过或未运行的检查及原因

| 检查项 | 状态（SKIPPED / NOT RUN） | 原因说明（环境受限、工具暂缺等） | 后续承接位置 |
|---|---|---|---|
| 远程 fnOS API 实机 E2E (`test_remote_fnos_e2e.py`) | SKIPPED | 远程 fnOS 实机在 GitHub-hosted runner 上不可达（环境性跳过） | 后续 Physical Gate 阶段 |
| 自动化对抗审查 (adversarial UI audit) | NOT RUN | REVIEWING.md 定义人工对抗审查方法，仓库目前无独立自动化入口 | 后续独立基础设施任务 |

## 已知问题与后续 Issue (Follow-up Issues)

- <!-- 列出已知问题、环境局限及对应的 follow-up Issue -->
