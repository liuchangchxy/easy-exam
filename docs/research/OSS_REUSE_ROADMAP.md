# 开源项目优点吸收路线图

> 状态基准：2026-09-24。此文回答“哪些项目值得吸收、吸收什么、是复用源码还是只借鉴行为、目前做到哪、下一步是什么”。源仓库、固定 commit、代码路径和许可证详见 [开源源码复用审计](OSS_REUSE_AUDIT.md)。

## 项目总目标

易考宝的目标是帮助用户通过刷题记住正确答案并提高考试成绩。开源项目是可复用实现和成熟行为的证据来源，不是要把候选仓库拼成一个产品。每项能力都分开记录：

- **源码复用**：复制或实质改编了候选项目的代码，并记录来源、commit、许可证和目标文件。
- **行为吸收**：理解成熟产品的行为后，在本项目里自行实现；这不是“复制了源码”。
- **仅评估/不采用**：记录适配度、许可证或重复实现等原因，不为追求“吸收数量”而增加功能或替换现有代码。

本路线图是跨项目总图。历史全局实施计划及 AntiGravity 的完成报告只证明各实施批次的状态，不等于整个开源吸收判断天然完备。当前 12 项的源码、目标实现、取舍与未决点汇总在[逐项目吸收复核与建议](OSS_ABSORPTION_DECISION_REVIEW.md)；计划执行记录见[开源项目吸收全局实施总计划](OSS_REUSE_MASTER_PLAN.md)。

## 候选项目与当前处置

| 候选项目 / commit | 值得吸收的部分 | 采用方式与原因 | 当前实际状态 | 后续动作 |
|---|---|---|---|---|
| [Exameow](https://github.com/heshengtao/exameow) `70e0d70` | 表格表头别名、选项列/组合选项识别、难度归一化及对应解析测试 | **适配移植源码**。Apache-2.0；把核心算法移到 Python 后端，保持 XLSX/CSV 单一解析入口；保留许可证和归属 | **已完成**：`spreadsheet_importer.py` 适配移植；列预览、手工 A–H 映射及稀疏键位有后端和浏览器验证 | 当前批次关闭；新发现的导入缺陷另开小计划，不继续无边界扩展 |
| [EXAM-MASTER](https://github.com/CiE-XinYuChen/EXAM-MASTER) `b7e59fe` | 整批预检、单事务提交、出错整批回滚及对应测试思路 | **只吸收事务行为/测试模式，不复制 Flask 源码**。MIT；其事务边界适用于本项目，原应用栈不适合直接搬入 | **已完成**：本项目 repository 批量事务；真实 SQLite 触发器制造中途失败并验证无部分数据残留 | 当前批次关闭；后续若加导入入口，复用本项目事务接口并保持回归测试 |
| [MiaowTest](https://github.com/qijun1900/miaowtest) `803dadc` | 对话与消息身份、顺序、角色、追问关联、生成状态 | **已完成 SQLite 模型级选择性适配**，不是搬 Mongo/Express。MIT；只纳入题目版本上下文所需的字段 | **已落地**：`ai_conversations` / `ai_messages`、多轮历史、线程回溯和用户隔离；有来源代码头与 MIT 分发材料 | 当前模型批次关闭；不把 token/工具调用/Agent 市场移植进产品 |
| [OpenTutor](https://github.com/zijinz456/OpenTutor) `4f169f5` | FSRS 参数、难度/稳定度/遗忘曲线公式、状态与复习评级；`forgetting_forecast.py` 的到期前保持率/紧迫度估算 | **FSRS 核心算法适配，来源于 OpenTutor**。目标算法与 OpenTutor `apps/api/services/spaced_repetition/fsrs.py` 对应，旧设计明确记载“直接提取”。遗忘预测服务也已评估：主要价值与当前 `due_at` 重叠且耦合课程树 | **已完成闭环**：目标文件 `backend/legacy/services/fsrs.py` 头与根/backend 发布目录补齐 MIT 归属及 notices（Copyright (c) 2026 Zijin Zhang）；“41 组差分向量”核定为**未找到可复现证据/历史说法未核实**；遗忘预测服务不予移植 | 批次关闭；核心调度继续由当前 `fsrs.py` 与 `fsrs_adapter.py` 提供，保持现有测试防护，不引入冗余预测服务 |
| [Gongkao](https://github.com/mpbfx/gongkao) `71e9dd7` | 阶段训练、错因复盘、题目上下文助教与学习资产关联 | **只作行为参考，不合并源码**。AGPL-3.0 与本项目 MIT 发行目标存在许可风险 | **未做候选代码移植**；错题/错因已有本项目实现，但尚未逐能力证明来自该项目 | 仅当 SPEC 有对应体验缺口时，提取可验收行为要求；不要复制 AGPL 代码 |
| [Moodle](https://github.com/moodle/moodle) `e68a1418b` | 多选部分分、作答尝试快照、反馈/重判时机 | **只作领域行为/测试参考**。GPL-3.0-or-later，PHP 题目引擎也明显超出本项目边界 | **未复制源码**；本项目部分得分与尝试快照有自建实现，不能仅凭相似就宣称吸收自 Moodle | 如需证明行为吸收，补 SPEC 对照和差异测试；不移植 Moodle 引擎 |
| [Open edX](https://github.com/openedx/edx-platform) `87d076f` | 学生答案/分数历史、尝试次数、答案揭示边界 | **只作行为参考，不引入 CAPA/XBlock 源码**。AGPL-3.0，架构过重 | **未复制源码**；模考防提前泄题等行为已有本项目测试，但来源应标为参考，非移植 | 只对照当前模考 SPEC 查遗漏；不另造 Open edX 子系统 |
| [Anki](https://github.com/ankitects/anki) `e6fefb2` | new/learning/review/relearning 状态及遗忘处理边界 | **只参考状态语义，不复制完整调度器/牌组模型**。AGPL-3.0-or-later；本项目只需要题目复习闭环 | **未复制源码**；FSRS 自身来源与项目许可需独立管理 | 不单独移植；仅在 FSRS 状态测试缺口时用作行为对照 |
| [Frappe LMS](https://github.com/frappe/lms) `4a94730` | 测验计时、待复查、交卷、结果生命周期 | **只作模考行为参考，不搬 ERP/LMS/监考体系**。AGPL-3.0 且依赖栈不适配 | **未复制源码**；本项目已有模考主干，仍需完整 UI 验收 | 对照 SPEC §3.2/§8 补遗漏测试，不引入 Frappe 代码 |
| [xzs-mysql](https://github.com/mindskip/xzs) `097ef86` | 中国题库/考试答题服务的业务边界 | **只作有限行为参考**。AGPL-3.0、Spring/MySQL 与本项目不适配，审计未找到足以支撑移植的测试 | **未复制源码** | 没有 SPEC 明确缺口时不安排移植计划 |
| [Razzia](https://github.com/Ralex91/Razzia) `277a338` | 轻量问答交互；其核心偏多人竞赛 | **不采用其多人实时竞赛代码/子系统**。MIT 许可证可读，但产品目标不匹配 | **未复制源码** | 不安排；除非用户确认要加入竞赛类产品能力 |
| [pdf-exam-bank](https://github.com/hzhsec/pdf-exam-bank) `4af4e76` | PDF 题目结构识别可作为输入样例/行为启发 | **不复制源码**：审计未发现 LICENSE，来源代码许可不清 | **未复制源码**；当前 PDF 可识别性预检由本项目自建 | 保持明确拒绝不可识别 PDF；若要借鉴具体规则，先确认许可和来源 |

## 实施顺序与当前事实

1. **已完成：可靠导入。** Exameow 解析算法适配移植 + EXAM-MASTER 原子事务行为/测试模式；计划为 `docs/superpowers/plans/2026-09-24-import-reliability-and-reuse.md`。
2. **已完成：MiaowTest 对话模型适配。** 持久 AI conversation/message 与恢复追问已由 SQLite 仓储实现；真实联网 provider 和个人资料检索属于独立自研功能。
3. **已完成：OpenTutor FSRS 算法适配与来源归属闭环。** `backend/legacy/services/fsrs.py` 代码头与分发物已补齐 OpenTutor MIT 完整归属；“41 组差分向量”经全量审计确认为无复现证据的历史陈述，已更正并不予采信；遗忘预测服务经评估不予移植（与 `due_at` 重叠且存在课程树耦合）。
4. **其余候选保持行为参考/不采用。** 用户若不决定增加新产品能力，不因审计过某项目就自动生成代码任务。Moodle 的逐选项分值属于一个尚未由 SPEC 确定的判分规则，见逐项目复核稿。

## 状态门禁

- 一项候选能力只有在源文件、commit、许可证、目标文件和测试都记录后，才能标成“源码适配已完成”。
- “行为相似”只可标“行为参考/本项目实现”，不能标“移植源码”。
- 每次 AntiGravity 报告只更新本轮触及的行；没有源代码或测试证据的格子标“未验证/未实现”。
- 路线图整体不设虚构完成百分比。当前代码级吸收记录为：**Exameow 表格解析算法适配；OpenTutor FSRS 核心适配（来源归属已补齐）；MiaowTest 对话模型适配；EXAM-MASTER 事务/回滚测试行为模式参考**。另外 8 个候选未发现代码移植。逐项源码、目标实现和建议处置见[逐项目吸收复核稿](OSS_ABSORPTION_DECISION_REVIEW.md)。
