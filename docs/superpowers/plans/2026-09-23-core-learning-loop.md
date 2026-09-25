# Core Learning Loop Implementation Plan

> **已被取代（2026-09-24）：** 本计划基于重构前目录与旧测试布局，任务状态不再是当前代码状态，不得继续照此实现。使用 `docs/superpowers/plans/2026-09-24-*.md` 中经用户指定的活动计划；原文保留仅供历史审计。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将已确认的刷题产品主线先落地为可验证的核心学习闭环，并为后续题库版本、AI答案留存和离线能力保留清晰接口。

**Architecture:** 先修正评分结果与掌握状态的边界，再在会话答案和错题记录中持久化可解释的结果；随后补充 AI 助教答案版本留存，最后扩展导入校验和前端展示。每个阶段都独立通过后端测试，避免把未完成的高级能力混入核心刷题路径。

**Tech Stack:** Python, FastAPI, SQLite/repository layer, pytest, Vue 3.

**Spec:** `SPEC.md`

## Global Constraints

- 无 AI、无蓝图配置时，核心刷题流程必须可用。
- 部分得分不等同于“答对”；错题清除只能由完整正确结果触发。
- 客观题自动判分；主观题可保存但不承诺自动评分。
- 不静默导入不可识别的文档；导入失败必须给出原因。
- 不改变既有测试的断言来伪造通过。

## Review Focus

- 多选少选获得部分分时，不得清除错题：由 Task 1 的回归测试覆盖。
- 未作答、空答案和未知题型必须保持可解释的错误结果：由 Task 1 覆盖。
- 会话答案与报告中的正确数必须使用同一语义：由 Task 2 覆盖。
- AI 服务不可用时，核心会话不得失败：由 Task 3 覆盖。
- AI 生成答案必须区分候选答案、用户采纳答案和官方答案：由 Task 3 覆盖。

### Task 1: 评分结果语义

**Files:**
- Modify: `backend/services/scoring.py`
- Modify: `backend/services/session_service.py`
- Test: `tests/test_scoring_semantics.py`

**Interfaces:**
- `Scorer.evaluate(...)` 保持现有二元返回兼容性。
- 新增 `Scorer.result(...) -> dict`，返回 `is_correct`, `score_ratio`, `mastery_status`。
- `SessionService.submit_answer` 返回并持久化 `mastery_status`。

- [ ] 写失败测试：多选部分得分的 `is_correct` 必须为 `False` 且状态为 `PARTIAL`；完整正确为 `CORRECT`；空答为 `UNANSWERED`。
- [ ] 运行 `pytest tests/test_scoring_semantics.py -q`，确认在实现前失败。
- [ ] 用最小改动实现 `Scorer.result`，让 `evaluate` 继续兼容旧调用。
- [ ] 在会话提交中使用统一结果，并让错题服务只接收完整正确语义。
- [ ] 运行该测试及现有 session/fsrs 测试，确认通过。

### Task 2: 报告与掌握状态一致性

**Files:**
- Modify: `backend/services/session_service.py`
- Modify: `backend/services/mistake_service.py`
- Test: `tests/test_session_sync.py`
- Test: `tests/test_e2e_flow.py`

**Interfaces:**
- 错题记录继续使用 `is_correct: bool`，但只由 `mastery_status == CORRECT` 映射而来。
- 报告增加 `partial_count` 和 `unanswered_count`，不改变现有字段含义。

- [ ] 写失败测试：部分得分进入报告分数但不计入 `correct_count`，且连续正确清除计数不增加。
- [ ] 运行目标测试确认失败。
- [ ] 实现报告统计和错题服务的统一映射。
- [ ] 运行完整后端测试并确认 `skipped=0`。

### Task 3: AI 答案留存接口

**Files:**
- Modify: `backend/services/ai_service.py`
- Modify: `backend/main.py`
- Create: `backend/services/ai_answer_service.py`
- Test: `tests/test_ai_answer_persistence.py`

**Interfaces:**
- `AiAnswerService.save_candidate(...) -> dict`
- `AiAnswerService.adopt_personal_answer(...) -> dict`
- `AiAnswerService.list_answers(question_id) -> list[dict]`
- 官方答案字段与 AI 候选/个人采纳答案分离。

- [ ] 写失败测试覆盖候选保存、用户采纳、来源和版本链。
- [ ] 运行目标测试确认失败。
- [ ] 添加 SQLite 表和 repository/service 最小实现；AI 不可用时不阻断会话。
- [ ] 暴露只读查询和采纳接口，运行 AI 与端到端测试。

### Task 4: 文档导入可识别性校验

**Files:**
- Modify: `backend/services/importer.py`
- Modify: `backend/main.py`
- Test: `tests/test_importer.py`

**Interfaces:**
- 导入器在解析前返回结构化预检结果：`accepted`, `reason`, `question_count`, `format`。
- 纯图片 PDF、损坏 PDF、题目结构无法识别时拒绝且不写入数据库。

- [ ] 写失败测试覆盖纯图片/损坏/结构不明输入。
- [ ] 运行目标测试确认失败。
- [ ] 实现无 OCR 的文本提取与题目结构预检。
- [ ] 运行导入和 E2E 测试，确认失败路径无副作用。

### Task 5: 前端核心结果与答案留存展示

**Files:**
- Modify: `frontend/src/components/AiTutorDrawer.vue`
- Modify: `frontend/src/components/QuestionCard.vue`
- Test: `tests/test_frontend_integration.py`

**Interfaces:**
- AI 抽屉显示历史答案版本、来源和采纳状态。
- 题目结果显示“正确/部分得分/错误/未作答”，不把部分得分渲染为正确。

- [ ] 写前端集成失败测试。
- [ ] 实现最小展示和离线空态。
- [ ] 运行前端构建和集成测试。
