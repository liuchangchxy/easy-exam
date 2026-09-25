# 开源源码复用审计

审计基准：源码副本 `C:\Users\chang\Desktop\code\fn-exam-source-research-20260923`，按下表固定的 Git commit；当前项目目标许可证为 MIT。此表区分“直接复用代码”“行为/测试参考”和“明确不采用”。阅读或分析某项目不等于吸收了代码。

## 当前结论（2026-09-24）

本审计记录的是“读过/比较过什么”与“实际采用了什么”，两者不可混为一谈。12 个候选仓库副本的 HEAD 均已核对为固定 commit。当前证据显示：**Exameow 表格解析算法已适配移植；MiaowTest 对话/消息模型已作选择性适配；OpenTutor FSRS 数学核心高度对应且历史设计明确记载“直接提取自 OpenTutor”，现已在 `backend/legacy/services/fsrs.py` 头与发布许可证材料（`MIT-OPENTUTOR.txt`、`THIRD_PARTY_NOTICES.md`）补齐 MIT 归属（Copyright (c) 2026 Zijin Zhang），来源治理闭环。经全量排查，此前流传的“41 组差分向量”在双方仓库与 Git 历史中均未找到可复现证据/历史说法未核实，已如实记录并不采信，不编造测试冒充**。EXAM-MASTER 的事务边界与失败回滚测试是行为/测试模式参考，**没有复制其 Flask 应用代码**。其余 8 个项目没有发现当前产品直接移植的代码，详见[逐项目吸收复核与建议](OSS_ABSORPTION_DECISION_REVIEW.md)。

跨项目采用顺序、状态和后续批次见 [开源实现选择路线图](OSS_REUSE_ROADMAP.md)。

## 逐仓库对比

| 项目 / 固定 commit | 许可证（仓库 LICENSE） | 可核查代码位置与价值 | 本项目适配结论 | 当前是否已复用外部代码 |
|---|---|---|---|---|
| [Exameow](https://github.com/heshengtao/exameow) `70e0d70` | Apache-2.0；无 NOTICE 文件；第三方依赖经 `THIRD_PARTY_LICENSES.csv` 审核 | `frontend/src/utils/importParser.ts`、`importParser.test.ts`：表头别名识别、字段映射（题干、答案、题型、解析、难度、标签/章节、独立选项 A-H 及组合选项分隔符提取）、缺失字段推断与测试用例 | **已移植核心算法至 Python**：在 `backend/app/infrastructure/importers/spreadsheet_importer.py` 移植映射算法与测试用例，并在文件头保留 Apache-2.0 归属声明；选择移植在 Python 层以保持后端单一解析管道，前端 `ImportView.vue` 通过预检接口提供用户可视化列映射预览与手动修正 | **已移植**：源 `frontend/src/utils/importParser.ts` 算法移植至 `backend/app/infrastructure/importers/spreadsheet_importer.py`，测试思路移植至 `tests/test_v1_import.py` |
| [EXAM-MASTER](https://github.com/CiE-XinYuChen/EXAM-MASTER) `b7e59fe` | MIT | `db.py` 的 `import_csv` 批量预检与单事务提交/回滚；`tests/test_app.py` 中的整批失败原子回滚测试 | **事务边界与测试场景参考后在本项目重写**：`question_repository.py` 实现批量事务，在 `tests/test_v1_import.py` 用真实 SQLite 触发器验证整批回滚；未复制其 Flask 源码或测试代码 | **行为/测试模式已采用，不是源码移植** |
| [MiaowTest](https://github.com/qijun1900/miaowtest) `803dadc` | MIT | `Express-node/models/AgentMessageModel.js`、`AgentConversationModel.js`：conversation/message identity、sequence、role、status、parent id | **已适配必要的数据模型**：用 SQLite 关联 `user_id + question_version_id`，并实现消息顺序、线程回溯和隔离；不搬 Mongo/Express/Agent 工具系统 | **模型级适配已完成**：`ai_conversation_repository.py` 有来源声明，`licenses/MIT-MIAOWTEST.txt` 与 notices 已附许可；这不等于完整复制 MiaowTest |
| [OpenTutor](https://github.com/zijinz456/OpenTutor) `4f169f5` | MIT | `apps/api/services/spaced_repetition/fsrs.py`、`flashcards.py`、`forgetting_forecast.py` 和 FSRS tests：FSRS 21 参数、初始/迭代公式、状态机与到期预测 | **FSRS 算法适配已完成，来源归属已闭环**：目标 `backend/legacy/services/fsrs.py` 来源于 OpenTutor `apps/api/services/spaced_repetition/fsrs.py`（旧设计明确记载“直接提取”）。已补齐源文件头与 `licenses/THIRD_PARTY_NOTICES.md`、`MIT-OPENTUTOR.txt` 声明（Copyright (c) 2026 Zijin Zhang）。**遗忘预测服务不直接移植**：90% 保持率阈值与易考宝 `due_at` 信号重叠，且强耦合课程树与 SQLAlchemy | **已适配并闭环归属**：目标 `backend/legacy/services/fsrs.py` 完成 MIT 归属标记；“41 组差分向量”核定为**未找到可复现证据/历史说法未核实**，不编造测试。遗忘预测服务已评估但不移植，不扩展未确认产品功能 |
| [Gongkao](https://github.com/mpbfx/gongkao) `71e9dd7` | AGPL-3.0 | `WrongQuestion`、`AgentTutorMessage`、`QuestionMistakeReview`、`AgentNote` 等题目与学习资产实体 | **只参考学习流程/数据关联**，尤其阶段训练、错因复盘、题目上下文助教；实现前需用户和许可策略审查，不复制 AGPL 代码到 MIT 项目 | 否；仅行为参考候选 |
| [Moodle](https://github.com/moodle/moodle) `e68a1418b` | GPL-3.0-or-later | question engine attempts、fraction grading、feedback/regrade 生命周期 | **测试与领域行为参考**：部分得分与正确状态分离、尝试快照、反馈时机。PHP 题库/权限系统过重且许可证有传染性，不移植代码 | 否 |
| [Open edX](https://github.com/openedx/edx-platform) `87d076f` | AGPL-3.0 | `capa_block.py` 的学生答案历史、分数历史、尝试次数、答案揭示时机 | **行为参考**：作答历史和模考揭示边界；XBlock/CAPA 体系不适合 NAS 单体应用，且不直接引入 AGPL 代码 | 否 |
| [Anki](https://github.com/ankitects/anki) `e6fefb2` | AGPL-3.0-or-later（有单独 BSD-3 贡献内容） | scheduler 的 new/learning/review/relearning 状态与遗忘处理 | **仅参考调度状态边界**。Anki 完整调度器、卡片/牌组模型并非需求，不移植；遵守 FSRS 的独立来源与许可要求 | 否 |
| [Frappe LMS](https://github.com/frappe/lms) `4a94730` | AGPL-3.0 | Quiz 生命周期、计时、待复查、提交与结果模型 | **模考用例参考**；ERP/课程依赖、监考能力不搬入当前产品 | 否 |
| [xzs-mysql](https://github.com/mindskip/xzs) `097ef86` | AGPL-3.0 | `ExamPaperAnswerServiceImpl.java`；项目测试目录只发现事件序列化测试 | **中国题库/考试业务行为参考**，特别是考试答题服务边界；代码栈、Spring/MySQL 与本项目不适配，且没有充分测试佐证，不移植 | 否 |
| [Razzia](https://github.com/Ralex91/Razzia) `277a338` | MIT | 多人实时竞赛/活动式问答 | 不是个人长期刷题与复习主线；只可能参考轻交互，不引入实时竞赛子系统 | 否 |
| [pdf-exam-bank](https://github.com/hzhsec/pdf-exam-bank) `4af4e76` | **未发现 LICENSE 文件** | `backend/.../pdf_parser_v2.py` 使用行切片/正则解析 | **不复制代码**。许可证缺失；其规则只可用于测试样例/行为启发，当前 PDF 以可识别性校验为先 | 否 |

## 当前项目对应实现证据（不是外部移植证据）

- 题目版本、作答和复习：`backend/app/application/practice_service.py`、`backend/app/infrastructure/db/repositories/practice_repository.py`、`backend/app/domain/learning/`。
- 外部模型调用边界：`backend/app/infrastructure/ai/provider.py` 是本项目旧服务适配器，不是外部候选项目适配器。
- XLSX 与 CSV 表格导入：`backend/app/infrastructure/importers/spreadsheet_importer.py` 已移植 Exameow 表头别名识别、组合选项分隔符提取、前缀剥离与难度归一化算法；前端 `ImportView.vue` 与 API `/preview-file` 提供了列映射预览与手工修正，分发物包含完整 Apache-2.0 副本与第三方声明。
- 批量题目导入：`backend/app/infrastructure/db/repositories/question_repository.py` 的 `batch_create_or_update_questions` 与 `backend/app/application/import_service.py` 实现了单一数据库事务边界，失败时整批回滚无孤儿记录残留，已由真实 SQLite 触发器中途回滚测试物理验证。
- AI：`backend/app/application/ai_tutor_service.py` 保存回答版本并使用对话仓储；`backend/app/infrastructure/db/repositories/ai_conversation_repository.py` 持久化 MiaowTest 模型启发的 conversation/message 结构。AI 多轮对话的模型适配已落地，但不等于 MiaowTest prompt/Agent 功能整体复用。
- FSRS：`backend/legacy/services/fsrs.py` 当前被 `backend/app/infrastructure/learning/fsrs_adapter.py` 和 `PracticeRepository` 使用；其算法公式来源于 OpenTutor `apps/api/services/spaced_repetition/fsrs.py`（commit `4f169f5`），代码头与根目录/backend 发布目录的 notices 及 `MIT-OPENTUTOR.txt` 已完整补齐 MIT 归属（Copyright (c) 2026 Zijin Zhang）。历史所谓的“41 组差分向量”核定为未找到可复现证据，按实际测试基准记录。
- 个人资料：`asset_repository.py` 是资产记录 CRUD，不构成文档上传、解析、检索增强生成链路。
- PDF：`backend/app/infrastructure/importers/pdf_importer.py` 提取文本并拒绝无文本/不识别结构；这是本项目实现，不是复制 `pdf-exam-bank`。

## 许可证和移植门禁

1. 对直接复制或实质改编的每个文件记录仓库 URL、精确 commit、源路径、许可证、版权/NOTICE 保留方式及本项目目标文件。
2. Apache-2.0/MIT 不是“无条件可复制”；逐文件检查头部、第三方子依赖与许可文件，并保留归属。
3. AGPL/GPL 项目只作为行为/源码阅读参考；没有用户对许可影响的明确决定前，不把其代码合并到当前 MIT 代码库。
4. 没有许可证的项目不复制源码。
5. 引用行为而未复制代码，要标为“行为参考”；完成测试不等同完成源码吸收。
6. 每次合并移植更新本审计表，记录 SHA、文件映射和测试；未完成时保持“否/待移植”，不要在 README 写成已吸收。

