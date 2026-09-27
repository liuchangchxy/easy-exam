# 易考宝（EasyExam）

面向家庭/小团队 NAS 的自托管刷题、模考和个人学习档案系统。

## 先看什么

1. [AGENTS.md](AGENTS.md)：协作宪法、复杂度开关和工程红线。
2. [SPEC.md](SPEC.md)：已经确认的产品行为，不是完成报告。
3. [TESTING.md](TESTING.md)：测试层级、命令和证据口径。**当前状态与未关闭缺口以第 7 节为准。**
4. [docs/REQUIREMENTS_TRACEABILITY.md](docs/REQUIREMENTS_TRACEABILITY.md)：源码、测试、运行证据和缺口。
5. [docs/ANTIGRAVITY_WORKFLOW.md](docs/ANTIGRAVITY_WORKFLOW.md)：跨文件批次或 OSS 工作的完整工序。
6. [docs/FNOS_FPK_GUIDE.md](docs/FNOS_FPK_GUIDE.md)：fnOS 打包、安装与运维手册。
7. [docs/superpowers/plans/](docs/superpowers/plans/)：已确认的叶子计划。

## 产品主线

易考宝不以拼接竞品功能为目标，而是围绕每道题建立长期学习记录：

```text
题目版本 → 作答尝试 → 判分/错因 → 官方/AI/联网/用户解释
        → FSRS 复习状态 → 掌握度/斩杀状态 → 下一次复习
```

核心能力包括普通刷题、完整模考、用户级错题本、FSRS、斩杀题库、题目版本、解释版本、学习诊断、动态推荐和多格式导入。AI 是嵌入流程的可选能力，不是核心前置条件。

## 当前状态怎么看

产品目标以 `SPEC.md` 为准；实现完成度只看追踪矩阵中的源码、测试和运行证据。目录存在、接口存在或单元测试通过，都不能单独证明用户链路完成。

截至 2026-09-27（HEAD `48bfa85`），EE-001 至 EE-021 台账项已全部闭环，FPK `1.0.2` 已在 fnOS 6.18 实机完成安装与重启保留验证。

本轮本地复跑：后端 205 通过 / 0 失败 / 1 跳过（**环境性跳过**：远程 fnOS 不可达，不阻断收敛），前端单测 11 通过，Chrome E2E 13 通过，**移动端交互 E2E 11 项全通过**，视觉冒烟通过，构建成功。

**仍未结清的验证缺口**：远程实机 API E2E 未运行（环境不可达）、外部商业搜索服务未联调。二者均属环境性缺口，按 `AGENTS.md` 避坑第 16 条逐项登记即可，但不得据此宣称"测试全绿"。明细见 [TESTING.md 第 7 节](TESTING.md)。

开源候选的固定 commit、许可证和实际采用方式见 [OSS_REUSE_AUDIT.md](docs/research/OSS_REUSE_AUDIT.md)，总体路线见 [OSS_REUSE_ROADMAP.md](docs/research/OSS_REUSE_ROADMAP.md)。

## 运行与测试入口

当前后端入口：`backend.app.main:app`。前端通过 `frontend/src/api/` 和 stores 访问 API；新模块与 `backend/legacy/` 适配层仍在逐项对齐。

常用命令见 [TESTING.md](TESTING.md)。完成跨文件高风险改动前先运行：

```bash
python scripts/checkpoint.py save "变更说明"
```

## 文档扩展

只有触发场景成立时才启用扩展：

- 数据库迁移、批量导入、文件转换：`docs/optional/DATA_SAFETY.md`
- 持久化写入、外部副作用、网络重试：`docs/optional/RELIABILITY.md`
- 确实需要并行调研或独立审查：`docs/optional/MULTI_AGENT_EXECUTION.md`
- 新批次计划、测试证据或 OSS 调研：`docs/templates/`

## 部署与许可证

项目目标是 Docker / fnOS 自托管，使用 SQLite 和版本化 migration。许可证见 [LICENSE](LICENSE)。
