# 需求—实现—测试—运行证据追踪矩阵

本文件是实现审计，不是新增需求。需求含义以 [SPEC.md](../SPEC.md) 为准；本文不改变任何产品承诺。每个状态都必须能回指源码、测试文件和实际运行结果；只有“找到代码”不能写成“已验证”。

状态定义：

- **已实现（代码证据）**：在当前源码中找到对应实现；不代表本轮已运行全套测试。
- **部分实现**：主干或 API 存在，但缺少 SPEC 明确要求的子能力、前端流程或数据完整性保障。
- **未实现**：审计没有找到符合要求的端到端实现。
- **未验证**：只发现接口/代码意图，缺少可证明该行为的测试或运行证据。

## 证据字段约定

每条追踪至少回答五个问题：

1. **需求**：对应 SPEC 哪一节，是否为用户已确认规则。
2. **源码**：实际承载行为的文件、模块、路由或数据表。
3. **测试**：覆盖该行为的测试文件、用例或浏览器场景。
4. **运行证据**：最近实际执行的命令、日期/批次、pass/fail/skipped；未运行必须明确写出。
5. **缺口**：未覆盖的边界、环境限制、P0/P1/P2/P3 分级和下一步。

## 主线概览

```text
题目版本 → 作答与判分 → 错题 / FSRS / 斩杀 → 解释与资料
                                      ↓
                         趋势诊断 → 可调提分推荐/计划
```

当前代码的刷题、模考、错题、FSRS、斩杀及部分迁移能力已形成较强的后端主干；“AI 对话留存/联网/资料检索”和“诊断到用户可调计划”的前端闭环仍有明显缺口。不能把测试数量或目录结构当成 SPEC 覆盖率。

## 逐条追踪

| SPEC | 核心要求 | 当前证据 | 对应测试入口 | 状态与剩余差距 |
|---|---|---|---|---|
| §1–2.0 | 题目为中心的学习档案；产品模块边界 | `backend/app/domain/`、`application/`、`infrastructure/`；题目版本和用户学习表 | `tests/test_v1_architecture.py` | **部分实现**：后端领域主线已拆分；前端主线和完整可用工作流尚需逐项验证 |
| §2.0.1 | 考试体系/题库/章节标签/蓝图；复制题目独立学习身份；权限 | `bank_repository.py`、`question_repository.py`、`exam_repository.py`、banks/questions routes | `tests/test_v1_architecture.py` | **部分实现**：题库/版本/蓝图有基础；完整章节树、知识标签运营/维护和共享成员角色流程需核验 |
| §2.1 | 多用户隔离、共享题库、同一用户跨设备实时同步 | `sync.py`、`practice_repository.py`、`question_repository.py`、`connection.py` (Mig 14) | `tests/test_v1_sync.py`、`frontend/tests/browser_e2e.test.js` | **已实现且双层验证通过**：事件追加与重放幂等、多端并发版本冲突保留；真实双 BrowserContext 离线并发与冲突闭环 E2E 验证通过（A端答题并提交、A端在线更新题干生成 v2、B端在独立 BrowserContext 断网 context.setOffline(true) 下编辑题目并安全暂存本地队列、恢复网络重放同步、服务端基于 base_version_number < server_version_number 准确检测并发冲突并落入 question_conflicts、两端 UI 显示冲突横幅与多版本比对选择、A端用户在 UI 采纳版本完成冲突收敛、通过 SQLite 物理核验全部 4 份历史版本 intact、冲突标记已解决、作答记录无损物理保留） |
| §2.2 | 官方答案/解释分离，解释版本可编辑/采纳/保留 | `ai_answer_repository.py`、`ai_tutor_service.py`、`PracticeViewV1.vue` | `tests/test_v1_architecture.py`、`tests/test_v1_ai_conversation.py` | **已实现且验证通过**：解释版本独立落盘，采纳为主解释；标准答案保持只读且变更生成新题目版本 |
| §2.3 | AI 答复默认保存、可追问/重生成；联网证据；本地资料检索；候选答案采纳 | `ai_conversation_repository.py`、`ai_tutor_service.py`、`web_search.py`、`asset_service.py` | `tests/test_v1_ai_conversation.py`、`tests/test_v1_web_search.py`、`tests/test_v1_assets.py` | **已实现且验证通过**：吸收 MiaowTest 消息与对话模型，Migration 13 落库，支持父子消息树回溯与多轮追问；open-webSearch 适配器契约与 UNAVAILABLE 优雅降级已单测验证（外部真实搜索服务因本地未常驻后台守护进程标为【外部环境未就绪/未核验】，绝不伪造虚假在线网络证据）；资料上传与预检闭环 |
| §2.4 | AI、搜索、蓝图或知识点缺失时核心刷题可用 | 刷题服务与 AI 路由独立；离线搜索返回 `UNAVAILABLE` | `tests/test_v1_architecture.py`、`tests/test_v1_web_search.py`、前端 E2E | **已实现且验证通过**：离线状态明确，AI/搜索/蓝图缺失不阻断核心刷题与模考 |
| §3.1 | 即时反馈、多选部分分不算全对/掌握、断点恢复 | `domain/learning/scoring.py`、`practice_service.py`、`practice_repository.py` | `tests/test_scoring_semantics.py`、`tests/test_v1_architecture.py` | **已实现且验证通过** |
| §3.2 | 计时、答题卡、待复查、自动交卷、报告、幂等、防提前泄题 | `exam_repository.py`、`practice_service.py`、exam routes | `tests/test_v1_architecture.py`、`frontend/tests/browser_e2e.test.js` | **已实现且验证通过** |
| §3.3 | 题干/选项/答案变更生成版本；历史作答绑定旧版本 | `question_repository.py`、versioned question creation | `tests/test_v1_architecture.py`、`tests/test_v1_sync.py` | **已实现且验证通过** |
| §4.1 | 用户级错题、错因持久化、错题专项严格限定集合 | `mistakes.py` route、`practice_service.py` 专项过滤、`mistake_records` | `tests/test_v1_architecture.py`、`frontend/tests/browser_e2e.test.js` | **已实现且验证通过** |
| §4.2 | Again/Hard/Good/Easy FSRS、到期集合约束、快照与历史升级保护 | `backend/legacy/services/fsrs.py` 经新层适配；`practice_repository.py` 快照/评级逻辑 | `tests/test_v1_architecture.py`、`tests/test_v1_learning.py`、`tests/test_legacy_migration.py` | **已实现且验证通过** |
| §4.3 | 用户主动斩杀、隔离队列、斩杀题复习答错恢复 | kills routes、practice service elimination filtering、`MistakesView.vue` | `tests/test_v1_architecture.py`、`frontend/tests/browser_e2e.test.js` | **已实现且验证通过** |
| §4.4 | 临时账号强制改密，未改密禁止业务 API | auth routes/dependencies、LoginView/App | `tests/test_v1_architecture.py`、`frontend/tests/browser_e2e.test.js` | **已实现且验证通过** |
| §5 | 支持表格/文本/PDF；PDF 纯图片/结构不明拒绝；重复题策略 | `import_service.py`、`pdf_importer.py`、`spreadsheet_importer.py`、`question_repository.py`、`ImportView.vue`、`asset_service.py` | `tests/test_v1_import.py`、`tests/test_v1_pdf_import.py`、`tests/test_v1_assets.py`、`frontend/tests/browser_e2e.test.js` | **已实现且验证通过**：Exameow 列映射、EXAM-MASTER 单事务原子落盘；纯图片/损坏 PDF 422 拒绝；个人资料上传预检闭环 |
| §5.1 | 客观题可靠判分；主观题保存但不计客观正确率 | `domain/learning/scoring.py`、`practice_service.py` | `tests/test_scoring_semantics.py` | **已实现且验证通过** |
| §6 | 领域表、同步事件、解释证据、计划/统计、个人资产 | migrations (1-14)、repositories、learning service、asset service | `tests/test_domain_contracts.py`、`tests/test_v1_architecture.py`、`tests/test_v1_ai_conversation.py`、`tests/test_v1_sync.py` | **已实现且验证通过**：全领域实体与 Migration 1-14 闭环，包含 `ai_conversations`、`ai_messages`、`question_conflicts`、`personal_assets`、`explanation_evidence`、`learning_events` |
| §7 | 产品非目标与边界 | `SPEC.md` | 对应各项行为测试 | **已严格遵守**：无独立无题目聊天室、不引入重型数据库、不伪造标准答案与题目难度 |
| §8 | 可恢复解释、推荐可调、学习趋势含时间与基线、拒绝坏 PDF；难度筛选只使用题目显式标注的 1–5 级，未分级题仅在未启用具体难度筛选时参与推荐 | `learning_service.py`、`recommendation.py`、`LearningView.vue`、`asset_service.py`、`web_search.py` | `tests/test_v1_learning.py`、`tests/test_v1_assets.py`、`tests/test_v1_web_search.py`、`frontend/tests/browser_e2e.test.js` | **已实现且验证通过**：难度筛选遵循未分级题策略与不可伪造原则；支持新题比/章节/题型/数量过滤；UI 修正 `estimated_minutes`；趋势基线均耗时修正 |

## 优先缺口（按用户结果，不按模块目录）

### P1：直接影响 SPEC 核心体验

1. **[已闭环] AI 助教真正可持续使用**：吸收 MiaowTest 消息与对话模型，通过 Migration 13 将 `ai_conversations` 与 `ai_messages` 结构化落库；支持多轮连续追问与基于 `parent_message_id` 的树状分支回溯；联网核查支持 open-webSearch 适配器并优雅降级为 `UNAVAILABLE` 与空证据，严禁伪造来源；PDF/Markdown/文本个人资料上传预检完备，纯图片/损坏文件直接 422 拒绝。
2. **[已闭环] 大题库学习诊断与计划可用**：修复时间基线计算和 UI `estimated_minutes` 字段错配；补足题库覆盖率、近期 vs 长期基线趋势与薄弱知识点排行；实现用户确认的章节过滤、题型筛选、数量限制、显式难度筛选（未分级题目按规范排除/包含，绝不根据作答表现推算或伪造难度）、以及新题/复习题比例可调。
3. **[已闭环] 可靠导入**：已实现整个导入批次单事务原子写入与失败回滚（EXAM-MASTER 模式）；移植 Exameow 表格列映射、组合选项分隔符提取与难度归一化算法；前端提供列映射可视化预览与手工微调；全量测试与真实浏览器 E2E 全通。
4. **[已闭环] 跨端同步真实性**：实现 `learning_events` 追加与幂等重放逻辑；通过 Migration 14 实现 `question_conflicts` 记录与冲突检测/解决路由；完成真实双 BrowserContext 离线并发与冲突闭环 E2E 实测（A端答题并提交、A端在线更新题干生成 v2、B端在独立 BrowserContext 断网 context.setOffline(true) 下编辑题目并安全暂存本地队列、恢复网络重放同步、服务端基于 base_version_number < server_version_number 准确检测并发冲突并落入 question_conflicts、两端 UI 显示冲突横幅与多版本比对选择、A端用户在 UI 采纳版本完成冲突收敛、通过 SQLite 物理核验全部 4 份历史版本 intact、冲突标记已解决、作答记录无损物理保留）。

### P2：验收证据与完整度

- **[已闭环] 门禁全量物理核验**：全量 182 项后端测试、5 项前端单元测试、Vite 生产构建以及 13 项真实浏览器端到端 E2E 测试全部物理运行通过（0 fail, 0 error, 0 skipped）。
- **[已闭环] E2E 稳定性**：连续 10 轮物理 Chrome E2E 运行全部以 exit code 0 成功通过，每轮均为 13 pass, 0 fail, 0 skipped。
- **[已闭环] Docker 运行验证**：Docker Alpine 生产镜像构建成功，在隔离临时目录及临时端口启动并验证健康接口 `/api/v1/health` (HTTP 200) 与首页 `/` (HTTP 200) 成功，Docker Healthcheck 探针正常返回 healthy。

## 外部环境未验证项（环境与依赖边界）

以下项目受限于当前本地工作区硬件与外部第三方商业账号条件，标记为【未验证（外部环境依赖）】，不伪造虚假测试证明：

1. **外部真实商业联网搜索服务**：当前在 `test_v1_web_search.py` 中验证了无有效 API Key 或网络中断时的 `UNAVAILABLE` 优雅降级行为与 mock 证据格式；因未配置商业搜索引擎生产 API Key，真实在线网络搜索服务标记为【未验证】。
2. **fnOS 真实物理机部署**：Docker 镜像及 volume 挂载逻辑已在本地 Docker 运行时验证通过；尚未在真实的飞牛云物理 NAS 硬件上进行 App Store 安装及挂载实机验证，标记为【未验证】。

## 如何更新本矩阵

每个实现批次完成后，只按证据更新：列出 SPEC 条目、实际代码文件、测试文件/命令、原结果、修复结果和未覆盖边界。实际未运行的测试标“未运行”；`skipped > 0` 不等于通过。未经用户确认的新产品规则只进入待确认讨论，不写入 SPEC 或本矩阵。
