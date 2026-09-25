# 易考宝全流程按 Spec 深度重构与差距补全计划

> **已被取代（2026-09-24）：** 本计划是重构早期草案，包含过时目录、测试命令和未核对任务，不得直接执行或将未勾选任务视为当前状态。按本仓库 `docs/ANTIGRAVITY_WORKFLOW.md`，改用 `docs/superpowers/plans/2026-09-24-*.md` 中由用户点名的单一活动计划；原文保留仅供历史审计。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 SPEC.md 与真实代码核查，完整补齐普通刷题、模考、错题/FSRS/斩杀、AI/联网解释、文档导入、学习诊断、多端同步与旧库迁移的全部差距，确保系统实现端到端闭环且全量测试 100% 绿灯（`skipped=0`）。

**Architecture:** 维持 FastAPI + SQLite WAL + 自建 Repository 架构，保持 `/api/v1` 模块化单体与 Vue 3 前端 API/store 分层；所有业务功能均具备完全离线与无 AI 降级能力，严格隔离用户学习记录与版本链。

**Tech Stack:** Python 3.12+, FastAPI, SQLite 3 (WAL mode), Pydantic v2, Vue 3, Vite, Node.js.

**Spec:** [SPEC.md](file:///c:/Users/chang/Desktop/code/飞牛刷题软件/SPEC.md)

## Global Constraints

- 绝不引入 SQLAlchemy 或 PostgreSQL，使用原生 SQLite + 自建 Repository。
- 绝不使用 `git reset --hard`、`git checkout --`、`git clean` 或删除 `backend/legacy`。
- 绝不篡改已有测试的预期值或删除旧用例；任何行为改动必须先写回归测试并确认其在实现前失败（RED）。
- 交付前全量测试（后端 unittest、前端 npm run build、前端 node --test）必须 100% 通过且 `skipped=0`。
- 高风险变动前运行 `python scripts/checkpoint.py save "<说明>"`。
- AI、联网、考试蓝图和复杂配置绝不能成为核心刷题的前置条件。

## Review Focus

1. **多选部分分与主观题客观正确率**：多选少选得 0.5 分但 `correctness="PARTIAL"`，不可清除错题；主观题作答可保存，但客观正确率分母/分子不计入主观题。
2. **模考交卷前零泄露与完整报告**：交卷前任何 API 严禁返回标准答案、解析或判分结果；交卷后前端报告必须完整呈现分数、耗时、客观正确率、题型统计与知识点统计。
3. **错题/FSRS/斩杀闭环**：仅错题与标记薄弱题进入 FSRS 队列；斩杀题目从普通练习队列排除，斩杀查漏补缺中答错自动恢复未斩杀；FSRS 评级受评分约束。
4. **AI 与联网核查真实性与完整交互**：无 AI 时核心刷题完全可用；联网不可用时如实返回 UNAVAILABLE 且不伪造来源；前端真正支持查看、自定义追问、在线编辑保存个人解释、采纳及联网核查。
5. **PDF 导入与重复题策略**：纯图片或无结构 PDF 明确拒绝且记录审计日志；PDF 导入与文件导入一致支持重复题目预检及 skip/new/merge 策略。
6. **学习诊断全维度与可调推荐**：趋势返回覆盖率、正确率、薄弱点、复习完成度、耗时趋势及近期 vs 长期基线；推荐支持新题/薄弱题/到期题及题型可调开关并在前端提供交互。
7. **多端同步版本与冲突合并**：草稿同步具备时间戳/版本保护与答案自动合并（union），拒绝静默覆盖丢失作答；事件同步返回冲突详情。
8. **旧库迁移只读保护与零静默丢弃**：源库以 URI 只读模式打开，自动备份，外键校验强制执行，任何未转换或跳过的孤立记录必须写入报告 `unconverted`。
9. **前端从 UI 完成全业务流程**：支持在 UI 完成题库创建、文件导入、普通刷题（含主观题与 AI 交互）、模考完整流程、错题消灭与斩杀复习、学习诊断与推荐调参。

---

## 阶段执行任务列表 (Tasks)

### Task 1: 普通刷题与主观题客观正确率隔离 (Objective vs Subjective Accuracy)

**Files:**
- Modify: `backend/app/application/practice_service.py`
- Modify: `backend/app/domain/learning/scoring.py`
- Test: `tests/test_scoring_semantics.py`

**Interfaces:**
- `PracticeService.complete_session(user_id, session_id)`:
  - 统计客观题总数 `objective_total`，`accuracy = round(correct_count / max(1, objective_total) * 100, 2) if objective_total > 0 else 0.0`
  - 主观题作答不计入客观题目正确率分母，不被视为客观判分错误。

- [ ] **Step 1: Write failing tests for subjective question accuracy isolation**
- [ ] **Step 2: Run tests and verify they fail as expected**
- [ ] **Step 3: Implement objective accuracy calculation in PracticeService**
- [ ] **Step 4: Run tests and verify they pass**

---

### Task 2: 模考交卷前安全校验与题型/知识点报告展示 (Mock Exam Leaks & Report Stats)

**Files:**
- Modify: `backend/app/application/practice_service.py`
- Modify: `frontend/src/features/exam/ExamView.vue`
- Test: `tests/test_v1_architecture.py`
- Test: `frontend/tests/exam.test.js`

**Interfaces:**
- `get_session` 与 `get_session_questions` 在 `mode="EXAM"` 且未交卷时严禁携带 `answer`, `explanation`, `correctness`, `score_ratio`。
- `ExamView.vue`: 渲染考试报告中的 `report.type_stats` 与 `report.tag_stats`，清晰展示客观题各题型与各知识点掌握情况。

- [ ] **Step 1: Write failing tests for exam session information leakage prevention & domain reports**
- [ ] **Step 2: Run tests to verify failure**
- [ ] **Step 3: Implement frontend and backend improvements**
- [ ] **Step 4: Verify test suite and frontend build pass**

---

### Task 3: 错题、FSRS 与斩杀题库全链路补齐 (Mistakes, FSRS & Elimination UI/API)

**Files:**
- Create: `frontend/src/api/kills.js`
- Modify: `frontend/src/api/mistakes.js`
- Modify: `frontend/src/views/MistakesView.vue`
- Modify: `frontend/src/views/PracticeViewV1.vue`
- Modify: `frontend/src/views/HomeView.vue`
- Test: `tests/test_v1_architecture.py`

**Interfaces:**
- `frontend/src/api/kills.js`: `listKills(token)`, `killQuestion(token, questionId)`, `unkillQuestion(token, questionId)`
- `MistakesView.vue`:
  - 错题卡片支持标记/修改错因（审题遗漏、概念欠缺、思路不熟、陷阱诱导、计算错误、其他手误）；
  - 支持一键进入“错题刷题”与“FSRS 到期复习”；
  - 支持切换查看“已斩杀题库”并可一键启动“斩杀查漏补缺 (ELIMINATION)”；
  - 错题卡片上提供“斩杀此题”与“解除斩杀”操作。
- `PracticeViewV1.vue`:
  - 支持“标记薄弱题 / 取消薄弱标记”；
  - 支持“斩杀此题”按钮；
  - 在 FSRS 复习模式下提供 Again(1), Hard(2), Good(3), Easy(4) 评级选择。

- [ ] **Step 1: Write failing tests for kills and mistake workflows**
- [ ] **Step 2: Verify test fails**
- [ ] **Step 3: Implement kills.js API and update MistakesView, PracticeViewV1, HomeView**
- [ ] **Step 4: Verify frontend build and node tests**

---

### Task 4: AI 解释查看、追问、编辑保存与联网核查 (AI Tutor Full Interaction)

**Files:**
- Modify: `frontend/src/api/ai.js`
- Modify: `frontend/src/views/PracticeViewV1.vue`
- Test: `tests/test_ai_service.py`
- Test: `tests/test_v1_architecture.py`

**Interfaces:**
- `frontend/src/api/ai.js`: 补充 `verifyWeb(token, questionId, query)`
- `PracticeViewV1.vue`:
  - 支持用户输入追问内容向 AI 提问；
  - 支持一键触发“联网核查”，展示联网证据（标题、来源、摘要、时间）及 UNAVAILABLE 真实状态；
  - 支持在历史解释中点击“编辑”，修改内容后另存为个人解释（`PERSONAL` 版本），不覆盖原版本；
  - 支持对任意解释版本执行“采纳为个人主解释”。

- [ ] **Step 1: Write failing tests for AI tutor full capabilities**
- [ ] **Step 2: Verify test fails**
- [ ] **Step 3: Implement frontend AI enhancements & verify-web integration**
- [ ] **Step 4: Verify frontend build and tests pass**

---

### Task 5: 导入重复预检与审计无死角 (Import Audit & Duplicate Policy)

**Files:**
- Modify: `backend/app/application/import_service.py`
- Test: `tests/test_v1_pdf_import.py`
- Test: `tests/test_v1_import.py`

**Interfaces:**
- `ImportService.import_pdf` 与 `import_file`: 对 PDF 格式同样进行 `_find_duplicates` 预检，当遇到重复题且 `duplicate_strategy="prompt"` 时抛出 `DuplicateImportError` 并记录 `import_jobs` 状态为 `PRECHECK_FAILED`，杜绝静默导入。

- [ ] **Step 1: Write failing test verifying PDF imports honor duplicate prechecks & strategies**
- [ ] **Step 2: Verify test fails**
- [ ] **Step 3: Implement duplicate precheck in import_pdf and import_file**
- [ ] **Step 4: Verify test passes**

---

### Task 6: 学习诊断全维度分析与提分推荐可调性 (Learning Trends & Configurable Recommendations)

**Files:**
- Modify: `backend/app/infrastructure/db/repositories/practice_repository.py`
- Modify: `frontend/src/views/LearningView.vue`
- Modify: `frontend/src/stores/learningStore.js`
- Test: `tests/test_v1_learning.py`

**Interfaces:**
- `PracticeRepository.trends`:
  - 返回 `weak_points`: 错误率最高或薄弱题最多的标签与题型列表；
  - 返回 `review_completion`: 统计窗口期内复习完成度；
  - 返回 `time_trend`: 近期单题平均耗时与长期基线单题平均耗时对比。
- `LearningView.vue`:
  - 展示近期 vs 长期基线对比卡片（正确率、单题平均耗时、尝试次数）；
  - 展示薄弱知识点排行榜与复习完成度指标；
  - 提分推荐增加可调过滤器：新题开关、薄弱题开关、到期题开关、题型筛选下拉框。

- [ ] **Step 1: Write failing tests for extended learning trends (weak points, completion, time trend)**
- [ ] **Step 2: Verify test fails**
- [ ] **Step 3: Implement backend trends calculation and frontend LearningView controls**
- [ ] **Step 4: Verify tests and frontend build pass**

---

### Task 7: 多端同步版本冲突保护与状态合并 (Multi-device Sync Conflicts & Merging)

**Files:**
- Modify: `backend/app/infrastructure/db/repositories/practice_repository.py`
- Modify: `backend/app/application/practice_service.py`
- Modify: `backend/app/api/routes/sync.py`
- Test: `tests/test_v1_architecture.py`

**Interfaces:**
- `PracticeService.sync_draft(user_id, session_id, payload)`:
  - 接收 `client_updated_at` 或客户端时间戳；
  - 自动合并两端作答答案（已答答案取并集，不被空答案覆盖）；
  - 确保断网后多设备草稿合并不会静默覆盖已答进度。

- [ ] **Step 1: Write failing tests for cross-device draft conflict & answer merge**
- [ ] **Step 2: Verify test fails**
- [ ] **Step 3: Implement draft merging logic in practice_repository / practice_service**
- [ ] **Step 4: Verify tests pass**

---

### Task 8: 旧库迁移安全性与零丢弃保证 (Migration Read-Only, FK Checks & Unconverted Audit)

**Files:**
- Modify: `scripts/migrate_legacy_db.py`
- Test: `tests/test_legacy_migration.py`

**Interfaces:**
- `migrate_legacy_db`:
  - 源库通过 `file:{source_path}?mode=ro` (URI 模式) 打开，物理禁止写操作；
  - 任何因外键或格式不符跳过的孤立记录收集到 `result["unconverted"]`；
  - 迁移事务完成后强制执行 `PRAGMA foreign_key_check` 并写入报告；若有外键错误立即中止并报错。

- [ ] **Step 1: Write failing test verifying read-only source, unconverted auditing, and FK verification**
- [ ] **Step 2: Verify test fails**
- [ ] **Step 3: Implement safeguards in migrate_legacy_db.py**
- [ ] **Step 4: Verify test passes**

---

### Task 9: 前端核心 UI 闭环补全 (Frontend UI Completeness)

**Files:**
- Modify: `frontend/src/views/HomeView.vue`
- Modify: `frontend/src/views/PracticeViewV1.vue`
- Test: `tests/test_frontend_architecture.py`
- Test: `frontend/tests/exam.test.js`

**Interfaces:**
- `HomeView.vue`: 增加“创建题库”弹窗与表单（名称、描述、分类），打通从 UI 创建空白题库并导入题目的链路；增加“斩杀题库”快捷入口。
- `PracticeViewV1.vue`: 增加主观题（`ESSAY` / `SUBJECTIVE`）文本作答框，支持主观题作答与查看参考解析。

- [ ] **Step 1: Write failing tests for new frontend contracts and UI components**
- [ ] **Step 2: Verify test fails**
- [ ] **Step 3: Implement UI features**
- [ ] **Step 4: Verify npm run build and node tests**

---

### Task 10: 全量自动化回归与端到端物理验收 (Full Regression & E2E Verification)

**Files:**
- Run: `python -m unittest discover -s tests -v`
- Run: `npm run build` in `frontend`
- Run: `node --test tests/exam.test.js` in `frontend`
- Run: `git diff --check`
- Update: `DECISIONS.md`, `README.md`

- [ ] **Step 1: Run full backend test suite and verify 0 failures and 0 skipped**
- [ ] **Step 2: Run frontend build and frontend tests**
- [ ] **Step 3: Update DECISIONS.md with architectural records**
- [ ] **Step 4: Produce comprehensive SPEC verification matrix report**
