# 易考宝开源吸收逐项目复核与建议

> **性质**：基于已下载源码和当前工作树的研究结论/建议稿，不新增产品需求，也不代替用户对未明确的产品规则作最终裁决。
>
> **审查基准**：源码副本 `C:\Users\chang\Desktop\code\fn-exam-source-research-20260923`；12 个仓库 HEAD 与 `OSS_REUSE_MASTER_PLAN.md` 所列 commit 一致，工作树均干净。当前项目目标许可证为 MIT。
>
> **口径**：“源码移植/适配”指复制或实质改编了源代码；“模型适配”指从源项目的数据实体设计迁移了必要字段与关系；“行为参考”不是代码移植。测试通过不自动证明采用了某开源项目。

## 结论先行

目前可以从现有代码和历史文档确认/强烈支持的开源吸收有：

1. **Exameow：表格解析算法移植**，已落在 `backend/app/infrastructure/importers/spreadsheet_importer.py`，Apache-2.0 归属材料已存在。
2. **OpenTutor：FSRS 算法核心适配**，`backend/legacy/services/fsrs.py` 与 OpenTutor 的 `apps/api/services/spaced_repetition/fsrs.py`（commit `4f169f5`）使用相同 21 个默认参数和高度对应的公式与调度流程；旧设计文档明确记载“直接提取自 OpenTutor”。现已完成来源治理闭环：在 `backend/legacy/services/fsrs.py` 头与根目录/发布目录的 `licenses/THIRD_PARTY_NOTICES.md`、`MIT-OPENTUTOR.txt` 中完整补齐 MIT 归属声明（Copyright (c) 2026 Zijin Zhang）。历史说法中所称“41 组差分向量”经对当前仓库、测试集、Git 全历史、检查点记录以及 OpenTutor 源仓库详尽排查，确认**未找到可复现证据/历史说法未核实**，已如实更正为未核实并不予采信，未编造测试冒充。OpenTutor 的 `forgetting_forecast.py` 经评估不予移植，其 90% 保持率阈值与本项目已有 `due_at` 信号重叠，且强依赖 OpenTutor 课程树及 SQLAlchemy。
3. **MiaowTest：AI 会话/消息数据模型适配**，必要的 conversation/message 身份、序号、角色、正文、父消息关系被映射到 SQLite；当前仓储和发行包有 MIT 归属材料。不是完整移植 MiaowTest。
4. **EXAM-MASTER：导入事务模式与失败回滚测试思路**，由本项目按自己的 Repository/SQLite 实现；没有移植它的 Flask 应用代码。

除此之外，其余 8 个候选项目没有发现被当前产品直接移植的源码。部分行为已经由本项目依照 SPEC 自行实现，另一些能力不在已确认需求中或不适合直接搬入。OpenTutor 的遗忘预测也已单独评估：它与当前 FSRS `due_at` 到期推荐重叠，且预测服务耦合课程树/SQLAlchemy，不建议整段移植。早期设计稿中“12 个项目的精华都已吸收”属于计划性表述，不能当作实现证据。

## 逐仓决策建议

| 项目 / 许可证 | 源码中实际值得看的部分 | 当前易考宝对应实现与事实 | 建议处置 |
|---|---|---|---|
| **Exameow** `70e0d70` / Apache-2.0 | `frontend/src/utils/importParser.ts`、`importParser.test.ts`：表头别名、选项列/组合选项解析、难度归一化及解析测试；`components/practice/QuestionCard.vue`：提交反馈和答案/解析展示；`stores/wrongQuestions.ts`：按题库存错题及排序，但只写 `localStorage`。 | 表格解析逻辑已适配到 `backend/app/infrastructure/importers/spreadsheet_importer.py`；前端 `ImportView.vue` 提供列预览和手工映射。刷题、错题与答案解释已有服务端实现。 | **保留已完成的解析器移植**。不移植 Exameow 的整张题卡或纯本地错题 Store：组件依赖其 shared 类型、Pinia Store 和样式；本项目服务端用户隔离/同步的数据方案更符合 SPEC。即时反馈可作 UI 对照，不额外复制代码。 |
| **EXAM-MASTER** `b7e59fe` / MIT | `db.py` 的批量导入；`static/app.js` 的本地草稿、答题卡和计时交互；考试会话/历史相关 Flask 路由。 | 单事务导入与物理 SQLite 回滚测试已按本项目结构实现。考试草稿由 `practice_sessions` 和 `PracticeRepository.update_draft` 保存；模考答题卡/计时/待复查/交卷报告已有本项目代码与测试。 | **保留已吸收的事务边界和回滚测试模式**。不复制 Flask/浏览器本地存储代码；本项目服务端草稿更适配多设备。答题卡、计时等属于功能行为已自行实现，不应写成复制了 EXAM-MASTER 代码。 |
| **MiaowTest** `803dadc` / MIT | `Express-node/models/AgentMessageModel.js`、`AgentConversationModel.js`：会话/消息身份、序号、角色、状态、`parentMessageId` 等。 | `ai_conversation_repository.py` 实现会话、保序消息、父子线程和用户隔离；`ai_tutor_service.py` 调用并保存多轮消息。当前第三方声明包含 MiaowTest MIT。 | **保留模型级选择性适配，已落地**。不搬 Mongo/Mongoose、工具调用、Agent 市场和 token 计量。源项目其他 prompt 不是“题目助教 prompt 已复用”的证据；易考宝当前 prompt 应按本项目需求独立维护。 |
| **OpenTutor** `4f169f5` / MIT | `apps/api/services/spaced_repetition/fsrs.py`：21 参数、FSRS 初始化/难度/稳定度/遗忘曲线/同日复习等公式；`flashcards.py`、FSRS 测试提供卡片状态与评级用法；`forgetting_forecast.py`：按 FSRS 保持率阈值预测未来复习紧迫度。 | `backend/legacy/services/fsrs.py` 采用相同 21 参数与高度对应的公式及调度流程；历史设计 `docs/superpowers/specs/2026-09-22-fn-exam-design.md` §2、§6.2 明确记载“直接提取自 OpenTutor”。已补齐代码头及 `licenses/THIRD_PARTY_NOTICES.md`、`MIT-OPENTUTOR.txt` 归属（Copyright (c) 2026 Zijin Zhang）。全库与源仓排查确认“41 组差分向量”**未找到可复现证据/历史说法未核实**。预测服务只按 90% 保持率算 `days_until_threshold`/紧迫度，并依赖 `LearningProgress`、`CourseContentTree` 与 SQLAlchemy；易考宝已为每题保存 FSRS `due_at`，并在推荐中纳入到期题。 | **FSRS 算法适配已完成，来源归属已闭环**：代码头与许可证材料已补齐；“41 组差分向量”核定为历史未核实说法，不伪造测试。**不直接移植遗忘预测服务**：预测阈值与易考宝 `due_at` 重叠，且带入课程树耦合；核心刷题复习按当前架构运转，不扩展无需求的功能。 |
| **Gongkao** `71e9dd7` / AGPL-3.0 | `prisma/schema.prisma` 中 `WrongQuestion`、`QuestionMistakeReview`、`AgentTutorMessage` 等题目、练习、错因/助教关系。 | 易考宝有独立 `mistake_records`、`answer_attempts.mistake_cause`、题目版本绑定的 AI 对话/解释；业务表和权限模型不同。 | **不复制 AGPL 代码**。错题、错因与题目助教在当前 SPEC 已有对应能力；Gongkao 的关系模型可作行为/结构参考，不足以要求再加一套平行数据模型。 |
| **Moodle** `e68a1418b` / GPL-3.0-or-later | `public/question/type/multichoice/question.php`：多选答案可按每个选项的 `fraction` 累加并裁剪，再映射评分状态；题目引擎还支持尝试与反馈生命周期。 | `score_answer()` 对“只选中正确答案的子集”固定给 `0.5`，选错项则 `0`；易考宝题目模型当前只存标准答案，未存逐选项分值。SPEC 规定允许部分得分，但没有定具体公式。 | **不移植 Moodle PHP 代码**。其 per-option fraction 是值得用户决定的判分规则，不是可直接拷贝的代码任务。我的建议是首期保留简单、可解释的固定部分分，不引入逐选项权重和 Moodle 级重判引擎；若要按考试大纲配置部分分，再单独确认产品规则。 |
| **Open edX** `87d076f` / AGPL-3.0 | `xmodule/capa_block.py`：尝试次数、学生答案/分数历史、反馈与答案揭示时机。 | 易考宝有 `answer_attempts`、题目版本快照、模考提交前隐藏答案以及交卷后重算报告；相应测试在 `test_v1_architecture.py`。 | **不复制 AGPL/CAPA/XBlock 代码**。尝试留痕和不提前泄题的行为已被本项目实现；没有证据需要再搬 Open edX 架构。 |
| **Anki** `e6fefb2` / AGPL-3.0-or-later（部分文件另有 BSD） | `pylib/anki/scheduler/v3.py`：Again/Hard/Good/Easy 映射到新调度状态，并由 Rust backend 计算安排。 | 易考宝已有题目级 Again/Hard/Good/Easy、FSRS 卡片状态、快照和错题队列，不使用 Anki 牌组模型。 | **不复制 Anki 调度代码**。其复习状态是行为参考；当前能力与题目级 FSRS 需求已对应，且 Anki 调度由 Rust backend 支撑，不是可独立搬用的 Python 算法文件。 |
| **Frappe LMS** `4a94730` / AGPL-3.0 | `frontend/src/components/Quiz.vue`：倒计时、标记复查、自动交卷、提交结果及错误反馈；同组件也含监考/违规流程。 | 易考宝已有模考计时、待复查、自动交卷、幂等提交和报告；用户的产品边界明确不需要监考。 | **不复制 Vue/Frappe 代码**。只把考试状态转移作为行为参考；目标链路已有本地实现，监考/ERP/LMS 依赖与产品定位相反。 |
| **xzs-mysql** `097ef86` / AGPL-3.0 | `ExamPaperAnswerServiceImpl.java`：组卷作答提交、判分、题目答案明细持久化。仓库主要是 Java/Spring/MySQL；此前审计只找到有限测试。 | 易考宝的 `PracticeService`、`ExamRepository` 和考试报告负责相同业务边界，并采用 SQLite/题目版本数据模型。 | **不复制 AGPL/Java 服务代码**。可作为中文考试系统业务流程参考；没有发现高于当前实现且能独立抽取的代码单元。 |
| **Razzia** `277a338` / MIT | `packages/web/`：自托管活动式多人 quiz；README 明确是小型活动主办/参与模式。 | 易考宝是个人/家庭题目学习档案；已确认 SPEC 不含实时多人竞赛。 | **不采用该子系统**。多人竞赛、Combo/排行等不是当前需求，避免为了“吸收项目”扩展产品范围。 |
| **pdf-exam-bank** `4af4e76` / 未发现许可证 | `parser/pdf_parser_v2.py`：基于文本行、题号和 A-D 前缀的规则拆题；同仓其他 PDF parser 含更多启发式逻辑。 | 易考宝 `pdf_importer.py` 提取可读文本并对无法确认结构的输入拒绝；SPEC 禁止自动 OCR。 | **不复制无许可证源码**。其规则不比“无法确认就拒绝”更适合当前上传红线；可用来构造合成边界测试，但不能拿来补源码。 |

## 尚未确认、不得由源码审计代替的产品规则

Moodle 提供的是“每个选项单独配置分值”的多选评分，易考宝目前是“答中部分正确选项固定 0.5，选错项 0 分”。SPEC §3.2 允许按考试配置标准得分、部分得分和负分，但没有指定多选题逐选项权重。建议源码吸收批次不移植 Moodle PHP 引擎，也不擅自增加选项权重模型；若之后要让不同正确选项贡献不同分值，应作为独立产品规则由用户确认。OpenTutor 的到期前遗忘预测则不在当前 SPEC 明确要求内，本次仅记录为已评估、不新增功能。

## 文档/代码处理边界

- 本次复核不改 `SPEC.md`、`README.md` 或业务源码：没有得到新的产品规则确认，README 目前只是链接到审计文档。
- 已同步修正 `OSS_REUSE_AUDIT.md`、`OSS_REUSE_ROADMAP.md` 和 `OSS_REUSE_MASTER_PLAN.md`：OpenTutor MIT 来源归属已补齐（Track A2 闭环），“41 组向量”核实为无复现证据的历史陈述，遗忘预测服务评估为不移植。
- 相关源文件/版本：OpenTutor `4f169f5`；目标 FSRS `backend/legacy/services/fsrs.py`；历史来源声明 `docs/superpowers/specs/2026-09-22-fn-exam-design.md`；当前许可证索引 `licenses/THIRD_PARTY_NOTICES.md` 与 `licenses/MIT-OPENTUTOR.txt`。
