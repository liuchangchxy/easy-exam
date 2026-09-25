# 文档体系重构 Implementation Plan

> **For agentic workers:** 本计划由主 Agent 直接执行；每个任务完成后进行对应的文档结构检查与验证。

**Goal:** 将云端 Vibe Coding Starter 的通用精华与本地 EasyExam 的真实工程经验重组为一套职责清晰、按复杂度启用、可持续维护的本地文档体系。

**Architecture:** 采用“入口宪法—产品真理源—执行与证据—专项扩展—可复制模板”五层结构。`AGENTS.md` 只保留 AI 必须遵守的触发器与硬约束；`SPEC.md` 只保留用户确认的产品规则；追踪、测试、决策、OSS、迁移和可靠性分别归档，避免互相冒充。

**Tech Stack:** Markdown、Python checkpoint/whitespace scripts、现有 pytest/Node/浏览器测试体系。

**Spec:** `AGENTS.md`、`SPEC.md`、`TESTING.md` 与 `docs/ANTIGRAVITY_WORKFLOW.md`。

## Global Constraints

- 不覆盖或回滚当前工作区已有代码与文档改动。
- 不把“待验证”写成“已实现”；所有完成状态必须有追踪或运行证据。
- 不修改既有测试断言来迁就文档重构。
- 小任务不强制启用 Master Plan、Multi-Agent、OSS 或数据迁移流程。
- 文档内容必须保持 EasyExam 的产品规则、真实 E2E 边界、迁移安全和幂等约束。

## Review Focus

- 新 AI 是否能在 5 分钟内找到入口、真理源、测试命令和当前状态。
- 模糊需求是否会先停在确认门，而不是直接污染 SPEC 或代码。
- 追踪矩阵是否明确区分需求、实现、测试、运行证据和未覆盖边界。
- 数据迁移、批量导入和重试是否仍保留源数据保护、原子性、unconverted 和幂等规则。
- 文档之间是否出现重复且可能互相矛盾的规则。

### Task 1: 统一文档职责与入口

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/ANTIGRAVITY_WORKFLOW.md`
- Modify: `DECISIONS.md`

- [x] 将 AGENTS 重组为入口、复杂度开关、三大引擎、硬约束、领域红线、动态教训、文档地图。
- [x] 将 README 改成新协作者的导航页，不重复完整规范。
- [x] 将 AntiGravity 流程改成按任务规模选择流程的执行手册。
- [x] 追加一次文档体系重构决策记录。

### Task 2: 重构产品真理源与证据链

**Files:**
- Modify: `SPEC.md`
- Modify: `docs/REQUIREMENTS_TRACEABILITY.md`
- Modify: `TESTING.md`

- [x] 保留现有已确认产品规则和验收基线，并补充 SPEC 维护规则。
- [x] 统一追踪矩阵字段约定：需求、源码、测试、运行证据、状态、缺口。
- [x] 统一测试层级、skipped 口径、DoD 和本地命令。

### Task 3: 补齐通用扩展和模板

**Files:**
- Create: `docs/optional/DATA_SAFETY.md`
- Create: `docs/optional/RELIABILITY.md`
- Create: `docs/optional/MULTI_AGENT_EXECUTION.md`
- Create: `docs/templates/PLAN_TEMPLATE.md`
- Create: `docs/templates/TEST_EVIDENCE_TEMPLATE.md`
- Create: `docs/templates/OSS_REUSE_AUDIT_TEMPLATE.md`
- Create: `docs/templates/OSS_REUSE_ROADMAP_TEMPLATE.md`
- Create: `.agents/skills/sdd-implementation/SKILL.md`

- [x] 从云端版本抽取通用内容，并改写为适配本地项目的可选模块。
- [x] 模板只提供结构，不伪造 EasyExam 的具体事实。
- [x] 通用 Skill 明确最小节拍：确认、快照、回归测试、实现、分层验证、证据更新。

### Task 4: 文档一致性与回归验证

**Files:**
- Modify: `scripts/check_whitespace.py` only if needed for docs checks.

- [x] 检查全部文档链接和引用路径。
- [x] 检查标题层级、重复规则和占位词。
- [x] 运行现有文档/代码测试、空白检查和 `git diff --check`。
- [x] 输出逐项重构结果与仍待验证项。
