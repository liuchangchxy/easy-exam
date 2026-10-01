# 全项目对抗性审查 7 项缺陷修复实施计划

**目标：** 彻底修复对抗性审查中确认的 3 项 P1、2 项 P2、2 项 P3 缺陷，清零阻断性安全与数据一致性问题。

## 缺陷清单与目标

1. **ADV2-001 (P1)**: `QuestionRepository.list_versions` 脱敏漏网：进行中模考题目必须脱敏所有版本的 `answer` 和 `explanation`。
2. **ADV2-002 (P1)**: `QuestionRepository.create_next_version`, `regrade_question_history`, `resolve_conflict` 权限守卫：只允许 `ADMIN` 和 `EDITOR`，拒绝普通 `MEMBER` 越权。
3. **ADV2-003 (P1)**: `PracticeService.review_answer`：单题快捷复习后立即 `self.complete_session(user_id, session["id"])`，消灭僵尸会话。
4. **ADV2-004 (P2)**: `PracticeRepository.kill` 增加题库成员资格校验；`list_killed` 联结 `question_bank_members` 过滤，杜绝跨租户嗅探。
5. **ADV2-005 (P2)**: `PracticeRepository.summary` 统计排除主观题 `('ESSAY', 'SHORT_ANSWER', 'SUBJECTIVE')`，客观 attempts 与 correct 语义严格对齐。
6. **ADV2-006 (P3)**: `backend/app/api/routes/system.py` 与 `scripts/setup-hooks.py` 中的 `subprocess.run(text=True)` 补齐 `encoding="utf-8", errors="replace"`。
7. **ADV2-007 (P3)**: `frontend/package.json` 版本号推进至 `1.0.8`。

## 执行步骤

- [x] 1. 编写 5 项业务逻辑回归测试（`test_adv2_001_list_versions_desensitizes_during_exam`、`test_adv2_002_member_cannot_modify_or_regrade_or_resolve`、`test_adv2_003_review_answer_closes_session`、`test_adv2_004_kill_requires_bank_membership_and_prevents_leak`、`test_adv2_005_summary_excludes_subjective`），并运行确认失败（变异实证）。
- [x] 2. 实现修复：
  - `question_repository.py`：`list_versions` 检查活动模考并脱敏；`create_next_version`、`regrade_question_history`、`resolve_conflict` 添加 `m.role IN ('ADMIN', 'EDITOR')` 鉴权。
  - `practice_service.py`：`review_answer` 提交作答后立即完结会话。
  - `practice_repository.py`：`kill` 校验题目题库成员资格，`list_killed` 添加成员资格联结；`summary` 联结 `question_versions` 排除主观题。
  - `system.py` 与 `setup-hooks.py`：补齐 `encoding="utf-8", errors="replace"`。
  - `frontend/package.json`：更新版本为 `1.0.8`。
- [x] 3. 运行新增回归测试确认变绿；运行全量后端与前端测试集。
- [x] 4. 更新追踪矩阵台账与决策日志。
