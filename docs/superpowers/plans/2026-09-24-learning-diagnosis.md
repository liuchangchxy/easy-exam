# 学习诊断与提分计划闭环

> **执行规则：** 按本仓库 `easyexam-implementation` skill 与 `docs/ANTIGRAVITY_WORKFLOW.md` 执行。一次只做一个任务；每项先测 RED，再改代码。需求只依据 `SPEC.md` §2.4、§8，不扩写产品策略。

**目标：** 让用户看得到真实趋势、薄弱点与复习完成度，并能调节 SPEC 承诺的推荐参数；计划页面使用后端真实返回字段。保持离线、可解释和非 AI 依赖。

**当前证据：** `backend/app/domain/learning/recommendation.py` 只有 new/weak/due 开关、limit；API 有题型筛选；前端 `LearningView.vue` 只暴露部分过滤器。SPEC 承诺章节、数量、难度、新题/复习题比例。`study_plan.py` 输出 `estimated_minutes`，当前 view 却在 day 标题读 `total_minutes`。trend 长期基线 SQL 尚需检查耗时聚合。

## 任务 1：补齐并验证趋势指标

**文件：** `backend/app/infrastructure/db/repositories/practice_repository.py`、`backend/app/application/learning_service.py`、`tests/test_v1_learning.py`。

- [ ] 为近期/长期窗口分别构造有真实 `time_spent` 的作答数据，写测试断言每题平均耗时非零且基线窗口结果独立；先跑确认失败。
- [ ] 写薄弱点、复习到期/完成数量和覆盖率测试，限定统计必须按用户和可选题库隔离。
- [ ] 用这些测试确认现有 SQL/DTO 哪些缺字段；避免改变已确认口径（近期窗口由 SPEC 确认默认值以代码现状为基准，若要改默认先问用户）。
- [ ] 修复近期与长期聚合的 `time_spent` 来源和 division-by-zero/空样本语义；不得把无作答数据伪造成零耗时样本。
- [ ] 运行 `python -m unittest tests.test_v1_learning -v`，再运行全后端套件。

## 任务 2：修复学习计划响应/视图契约

**文件：** `backend/app/domain/learning/study_plan.py`、`frontend/src/views/LearningView.vue`、`tests/test_v1_learning.py`、`frontend/tests/exam.test.js`。

- [ ] 写响应契约测试锁定计划日的 `estimated_minutes` 及当天题目列表；锁定前端消费字段必须与 API 一致。
- [ ] 将 `day.total_minutes` 与实际 schema 错配修正为一个明确的共享契约，不静默添加重复字段。
- [ ] 渲染非空计划、空计划、用户设定每日分钟数等场景并运行前端 build/单测。

## 任务 3：实现 SPEC 承诺的推荐调节项

**文件：** `backend/app/domain/learning/recommendation.py`、`backend/app/application/learning_service.py`、`backend/app/api/routes/learning.py`、`frontend/src/api/learning.js`、`frontend/src/stores/learningStore.js`、`frontend/src/views/LearningView.vue`、`tests/test_v1_learning.py`、`frontend/tests/exam.test.js`。

- [ ] 在 API/domain 测试先覆盖题型、章节、难度、数量、新题/复习题目标比例等 SPEC §8 条件及参数越界；过滤条件不得返回别的用户/题库题目。
- [ ] 若现有数据模型缺少题目难度/章节的用户可识别输入，先报告证据并停问；不得假造默认难度或偷偷改数据库业务语义。
- [ ] 实现确定性可解释过滤/排序，推荐响应给每题短原因；比例以用户设置为目标构成，缺少对应候选题时明确返回实际构成，不伪造满足比例。
- [ ] 前端提供调节入口并在重新加载后保持当前筛选状态；可调整之后再看推荐，且无 AI 可用。
- [ ] 跑后端 learning tests、前端 unit/build，并通过浏览器 E2E 验证用户实际能调整这些参数并看到结果。

## 阶段验收

- [ ] `python -m unittest discover -s tests -v`
- [ ] `npm --prefix frontend run test:unit`
- [ ] `npm --prefix frontend run build`
- [ ] `npm --prefix frontend run test:e2e`（pass/fail/skipped 分开报告）
- [ ] 更新需求追踪 §2.4/§8 的代码文件、测试和状态；没有证据的子项保持部分/未验证。
- [ ] `git diff --check`
