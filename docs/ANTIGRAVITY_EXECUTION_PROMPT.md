# AntiGravity 启动提示词

本文件模板用于执行**已经审定的单批代码计划**。若当前任务是把已完成的 OSS 调研统合成跨项目总实施计划，应先使用 [OSS 总计划专用提示词](ANTIGRAVITY_OSS_MASTER_PLAN_PROMPT.md)，不得误用下面的单批实现模板，也不得从头重做全量调研。`OSS_REUSE_ROADMAP.md` 是既有候选取舍与顺序的事实基线；总计划应在它之上安排未完成工作，单批计划才进入代码实现。

```text
你在易考宝仓库中负责实现代码。严格遵守仓库根目录 AGENTS.md。

本轮唯一执行计划：[计划文件]

开始前必须阅读：
- AGENTS.md
- SPEC.md
- TESTING.md
- docs/ANTIGRAVITY_WORKFLOW.md
- docs/REQUIREMENTS_TRACEABILITY.md
- docs/research/OSS_REUSE_AUDIT.md
- docs/research/OSS_REUSE_ROADMAP.md
- .agents/skills/easyexam-implementation/SKILL.md（如当前 AntiGravity 版本支持仓库 Skills，请启用并遵循）
- 上面点名的完整计划

按流程先检查 git status、当前 diff、计划涉及代码和测试的真实路径。当前工作树可能含有我或其他 AI 的未提交修改；这些都视为需要保留的既有工作。严禁 reset、clean、restore、checkout 覆盖或顺手整理本计划以外的变更。

本项目的大目标是按 `OSS_REUSE_ROADMAP.md` 对候选开源项目做代码级比较，并有选择地吸收适合的实现；本轮仅完成路线图中的被点名计划。结束时必须说明该路线图条目如何变化、哪些候选仍未采用/待做；不得把“本轮计划完成”说成“整体开源复用目标完成”。

你的任务不是重新设计产品，也不是把模块目录存在当成架构/需求已完成。SPEC 是已确认需求唯一来源；需求追踪矩阵是产品实现状态来源；开源审计记录源码与许可证事实；开源路线图记录跨项目的采用顺序和进度。若这些文档、当前代码与本轮计划互相冲突，先列证据、影响和最小问题，停下来问我；不得自行改变产品规则、扩写 SPEC 或跳过外部源码复用判断。

执行约束：
1. 仅实现被点名计划的范围，一个阶段一次；逐项 TDD，先加测试并实跑确认 RED，再实现并验证 GREEN。
2. 不得删除/放宽既有测试或更改测试预期来迁就实现。发现已有失败要区分本次引入与既存失败，不能遮掩。
3. 需要参考开源代码时，先打开固定 commit 下的实际文件和 LICENSE；适配度高且许可允许时优先选择性复用/改编，不要习惯性重造轮子。保留 NOTICE/版权要求，并更新 OSS_REUSE_AUDIT.md；AGPL/GPL、无 LICENSE 或许可证不清的候选不得直接复制进 MIT 项目，先停下来报告。
4. 外部代码“行为类似”不等于“源码已吸收”。报告中分开列：复制/改编的文件、只参考的行为、自己实现的内容。
5. 按计划跑目标测试；阶段收尾时按 TESTING.md 运行全套后端、前端单测、build、真实浏览器 E2E 和 git diff --check。不得用 Mock/Node 测试冒充浏览器 E2E。逐项报告 pass/fail/skipped；未跑不准说通过。
6. 更新需求追踪状态与证据、计划勾选、路线图中本轮对应条目的状态；只有重要且已确认的决策才追加 DECISIONS.md；README 只记录实际用户能力和真实复用概况。

结束时按 docs/ANTIGRAVITY_WORKFLOW.md 的报告格式回答：改了什么、对应 SPEC、外部代码复用/许可、改动文件、逐条测试结果（含 skipped）、本轮路线图条目状态、仍未完成的路线图项目/阻塞项、是否保留了既有工作树修改。不得声称整体开源复用目标或整个产品“彻底解决”“全绿”或“验收完成”；测试只能证明其实际覆盖范围。
```
