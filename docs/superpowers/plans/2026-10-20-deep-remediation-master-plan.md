# 深度审查问题清单修复实施计划 (Codebase Deep Remediation Plan)

审查基线：`main / 65b99726`
清单基线：`docs/reviews/2026-10-20-codebase-deep-review.md`

## 修复批次规划

- [ ] **Batch 1: 安全与防作弊 (Security & Exam Integrity)**
  - P1-1: 密码哈希脱敏 (`user_repository.py`, `auth.py`)
  - P1-2: 模考答案遮蔽 (`practice_service.py` 统一切断模考期间普通练习接口泄题)
  - P1-3: 错题接口题库成员鉴权与防作弊脱敏 (`practice_repository.py`)
  - P2-4: 冲突信息查询增加题库成员权限校验 (`question_repository.py`)

- [ ] **Batch 2: 答题、同步与版本可靠性 (Practice, Sync & Versioning)**
  - P1-4: 并发提交答案原子合并 (`practice_service.py`, `practice_repository.py`)
  - P1-5: 编辑重试幂等 (`PracticeViewV1.vue`, `question_repository.py`)
  - P1-6: 增量同步改用严格自增事件 ID 游标 (`connection.py`, `practice_repository.py`)
  - P2-3: 草稿清空答案与取消标记语义 (`practice_repository.py`)
  - O-1: 模考交卷精简冗余的逐题提交循环 (`ExamView.vue`)
  - O-2 & O-8: 前端离线编辑队列与冲突规则收口

- [ ] **Batch 3: 业务与数据一致性 (Business & Data Consistency)**
  - P2-1: 跨题库学习计划保留多题库分组 (`study_plan.py`)
  - P2-2: 统一标签权威事实源 (`bank_repository.py`)
  - P2-5: 尊重用户搜索配置开关 (`ai_tutor_service.py`)
  - P2-6: 模考蓝图缺题禁止静默修改题型配比 (`blueprint.py`)
  - P2-7: 导入单批内部维护去重指纹 (`import_service.py`)
  - P2-8: 取消薄弱标记不删有复习历史的 FSRS 卡片 (`practice_repository.py`)
  - P2-9 & P2-10: AI 变式失败不伪造原题 + 题型枚举统一为 MULTI (`ai_tutor_service.py`)
  - P2-11: 数据库迁移 DDL 与版本号单事务原子化 (`connection.py`)
  - P2-12: 题库编辑锁剔除超时模考 (`question_repository.py`)
  - P2-13: 题目章节校验必须归属同一题库 (`question_repository.py`)

- [ ] **Batch 4: 条件性风险验证与架构瘦身 (Risk Verification & Pruning)**
  - △-1: AI 草稿并发接受靶场测试与修复
  - △-2: FSRS 历史重算边界靶场测试
  - O-5, O-6, O-7: 重复实现合并与前端冗余锁探测清理
  - P3-1: PDF 手动拆题交互改善 (`ImportView.vue`)
  - L-1 ~ L-3: 确认无调用者的旧入口清理与全量回归测试
