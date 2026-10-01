# 需求追踪与未关闭问题台账

> 本文件是 EasyExam 当前实现状态、未完成能力、已确认缺陷和验证缺口的唯一汇总入口。产品行为仍以 [SPEC.md](../SPEC.md) 为准；本文件不新增或改变产品要求。测试方法以 [TESTING.md](../TESTING.md) 为准。
>
> 台账合并了三轮审查：本地源码/测试审查、Antigravity 后端架构审查、Antigravity 飞牛 NAS 对抗与真实浏览器审查。不同审查环境的结果分开记录，不把报告中的结果伪装成当前轮重跑结果。

## 1. 审计与执行快照

- **最新执行日期**：2026-09-27
- **执行范围**：EE-001 至 EE-021 台账闭环复核 + FPK 离线安装时序修复（commit `48bfa85`）的源码、实机与本地全套复跑。
- **代码状态**：工作树在 HEAD `48bfa85` 上无未提交改动（仅一个未跟踪的 `NUL` 文件）。FPK `1.0.2` 已实机安装验证。
- **验证结论汇总（2026-09-27 本轮实跑）**：
  - Python 后端全量测试：`python -m unittest discover -s tests` → **205 通过、0 失败、0 错误、1 跳过** (104.8s)。唯一跳过项为 `test_remote_fnos_e2e.setUpClass`，原因"远程 fnOS 不可达 (HTTP 404)"。
  - 前端单元/契约测试：`npm --prefix frontend run test:unit` → **11 通过、0 失败、0 跳过** (197ms)。
  - 本地真实 Chrome 浏览器端到端测试：`npm --prefix frontend run test:e2e` → **13 通过、0 失败、0 跳过** (13.6s)。
  - 前端生产构建：`npm --prefix frontend run build` → Vite v5.4.21 成功，exit code 0。
  - 移动端交互 E2E：`node frontend/tests/mobile_interaction_suite.mjs` → **11 项检查全部通过**（已修复脚本自身三处缺陷并完成红色实证）。明细见 [TESTING.md 第 7.4 节](../TESTING.md)。
  - 视觉冒烟：`node tests/visual_smoke/run.mjs` → 真实 `frontend/dist` 通过四道正身信号；另有对"有内容的网关占位页"的红色实证。
- **部署状态**：EE-015 已闭环。FPK `1.0.2` 已在 fnOS 6.18 实机（`192.168.x.x`）完成安装、启动、健康检查与重启后数据/主密钥保留验证；健康接口 `commit_sha` 字段提供版本追溯能力。

### 状态口径

- **已修复并通过测试**：已完成源码修复，并在对应层级的单元测试/构建/真实浏览器 E2E 中产出可复查的通过证据。
- **已闭环（实机核验）**：除源码与本地测试证据外，还需在目标物理环境取得运行证据；仅当物理证据存在时才可使用此口径，并须注明设备与环境。

## 2. 当前结论

截至 2026-09-27，EE-001 至 EE-021 **全部 21 项**均已完成源码实现、测试与所需的环境级验证闭环；此前唯一挂起的 EE-015（飞牛 NAS 物理部署映射）已在 `1.0.2` 实机安装中核验通过。

针对此前复核发现的缺口已全数深层闭环：
1. **EE-001 蓝图组卷**：题目版本读取查询带入 `chapter_id`，蓝图根据章节按需筛选并在不足时优雅降级补齐。
2. **EE-006 历史重判单事务原子性**：版本创建与历史会话重判、FSRS 状态重算、错题本状态更新以及审计日志记录完全纳入**同一数据库单事务**中。若重判步骤发生异常，版本创建与作答更新同时自动完整回滚，题库版本、作答记录、FSRS 卡片、错题本、审计日志均 100% 保持未被污染；单测 `test_controllable_historical_regrading_ee006` 全面断言全量实体在崩溃时未被污染。
3. **EE-009 持久化 AI 与搜索配置落库加密与密钥安全**：彻底移除源码内置默认密钥后门，未配置 `EASYEXAM_SECRET_KEY` 时明确拒绝加密并报错；数据库物理列仅存储 Fernet 对称密文（`enc:...`）；API 响应层星号脱敏；读取时自动无损升级旧明文数据；密钥不匹配或密文损坏时明确抛出诊断异常（非静默置空）；单测覆盖缺失密钥拒绝、只存密文、正常解密、旧明文无损升级与错误密钥拒绝诊断全部 5 种场景。
4. **EE-018 跨设备同步游标与账号切换竞态防护**：游标存储键按用户安全隔离（`easyexam_sync_cursor_${userId}`）；引入请求序号锁与用户一致性校验；前端单元测试 `frontend/tests/sync.test.js` 增加真实在途（in-flight suspended）网络请求切换用户隔离测试，验证旧账号事件被完全丢弃，不派发给新账号，新旧账号游标均不被污染。
5. **EE-021 歧义 PDF 校正与单事务原子入库**：修复批量入库返回计数（`imported_count` 精确返回成功入库条数，解决未提交事务隔离导致计数为 0 的问题）；在草稿确认转正时采用基于数据库原子 CAS 的状态机流转（`UPDATE ... WHERE status = 'PENDING'`）并与题目批量落盘在单一原子事务中执行；单测增加真实多线程并发确认竞态测试（2 线程并发，严格保证 1 成功 1 拦截且题库零重复写入）。

## 3. 未关闭问题台账

| ID | 等级 / 类型 | 状态 | 未完成项或缺陷 | 证据、影响和关闭标准 |
|---|---|---|---|---|
| EE-001 | P2 / SPEC 缺口 | 已修复并通过测试 | **考试蓝图动态组卷已完整闭环。**题目查询已将 `chapter_id` 带入候选集，蓝图算法支持章节、题型、数量筛选，超额时优雅降级补齐。 | `blueprint.py`；`question_repository.py`；单测 `test_blueprint_selection_with_chapter_and_graceful_fallback` (通过)。 |
| EE-002 | P1 / Bug | 已修复并通过测试 | **模考错题入库策略开关已加入。**数据库扩展 `config_json`，`record_mistakes = False` 跳过写入错题。 | `practice_repository.py`；单测 `test_exam_record_mistakes_strategy_switchable` (通过)；真实浏览器 E2E 模考通过。 |
| EE-003 | P2 / SPEC 缺口 | 已修复并通过测试 | **个人资料 RAG 检索已接入。**实现基于用户隔离的个人资料检索并注入系统 Prompt，返回追溯依据。 | `asset_repository.py`；`ai_tutor_service.py`；单测 `test_personal_assets_rag_retrieval_and_isolation` (通过)。 |
| EE-004 | P2 / SPEC 缺口 | 已修复并通过测试 | **生产 AI 助教已注入联网适配器。**默认支持本地 `open-webSearch` 且可环境变量配置，返回证据落库。 | `main.py`；`ai_tutor_service.py`；单测 `test_web_search_adapter_injection_and_evidence` (通过)。 |
| EE-005 | P2 / SPEC 缺口 | 已修复并通过测试 | **AI 变式题草稿全流程与用户界面已闭环。**后端支持草稿生成/暂存/转正入库/丢弃；前端 `HomeView.vue` 提供变式草稿箱界面，`PracticeViewV1.vue` 提供一键生成入口。 | `ai_draft_repository.py`；`HomeView.vue`；`PracticeViewV1.vue`；单测 `test_ai_variant_draft_full_lifecycle` (通过)；前端构建通过。 |
| EE-006 | P2 / SPEC 条件能力 | 已修复并通过测试 | **可控历史重判机制已单事务原子闭环。**修改标准答案时提供可选重判选项，版本创建与历史会话作答重判、FSRS 状态与学习记录重算、`audit_logs` 审计记录完全运行在单一原子事务中，失败则自动回滚；提供 `POST /questions/{id}/regrade` 独立端点，前端编辑面板集成重判开关。 | `connection.py` (Migration 17)；`question_repository.py`；`PracticeViewV1.vue`；单测 `test_controllable_historical_regrading_ee006` (包含正常重判及模拟崩溃原子回滚全量实体未受污染测试通过)。 |
| EE-007 | P2 / SPEC 缺口 | 已修复并通过测试 | **知识点与章节实体关联已完整。**写入、读取与跨库复制均完整保留并级联章节实体与知识点标签。 | `connection.py` (Migration 16)；`question_repository.py`；单测 `test_copy_to_bank_preserves_chapter_and_knowledge_tags` (通过)。 |
| EE-008 | P2 / 兼容能力 | 已修复并通过测试 | **题库多格式导出前后端下载流程已闭环。**后端提供 JSON/CSV/TXT/XLSX 导出端点，前端 `HomeView.vue` 提供格式选择与鉴权文件下载。 | `backend/app/api/routes/banks.py`；`HomeView.vue`；单测 `test_bank_export_supports_multiple_formats` (通过)；前端构建通过。 |
| EE-009 | P2 / SPEC 缺口 | 已修复并通过测试 | **持久化 AI 与搜索配置落库加密与保护已完整实现。**数据库 `user_ai_configs` 表通过 Fernet 对称加密存储敏感密钥（物理列为 `enc:...` 密文，不落明文），彻底移除内置默认后门密钥，缺少环境变量时明确报错拒绝，旧明文无损透明升级，错误密钥明确抛出诊断异常；前端 `HomeView.vue` 增加配置管理弹窗。<br>**部署前置条件**：生产部署必须在 `.env` 或持久卷 `/vol*/@appdata/easy-exam/.env` 中配置 `EASYEXAM_SECRET_KEY`，容器重建时必须保持同一主密钥不变。 | `connection.py` (Migration 17)；`ai_config_repository.py`；`ai.py`；`docker-compose.yml`；`fpk/.../docker-compose.yaml`；`docs/FNOS_FPK_GUIDE.md`；单测 `test_persistent_ai_and_search_config_ee009` 与 `test_deployment_secret_key_exposure_and_no_committed_secrets` (全部通过)。 |
| EE-010 | P2 / SPEC 缺口 | 已修复并通过测试 | **考试蓝图规则可视化编辑器已实现。**前端 `HomeView.vue` 提供档案新建、章节/题型规则配比、负分分值配置。 | `exams.py`；`HomeView.vue`；单测 `test_exam_profiles_and_blueprint_listing_apis` (通过)；前端构建通过。 |
| EE-011 | P2 / SPEC 部分缺口 | 已修复并通过测试 | **手动录入单题与全属性编辑已闭环。**`HomeView.vue` 增加录入弹窗，`PracticeViewV1.vue` 增加全字段编辑。 | 真实 Chrome 浏览器端到端测试覆盖；前端构建通过。 |
| EE-012 | P2 / 用户流程缺口 | 已修复并通过测试 | **个人资料管理界面与删除已实现。**后端提供查询与删除端点，前端 `HomeView.vue` 提供完整管理弹窗（笔记/上传/删除）。 | `assets.py`；`HomeView.vue`；单测 `test_personal_assets_deletion_and_retrieval` (通过)；前端构建通过。 |
| EE-013 | P1 / 数据隔离与可靠性风险 | 已修复并通过测试 | **离线编辑队列按用户严格隔离与原子同步。**队列项记录 `userId` 属主，用户过滤安全重放，原子出队，杜绝跨账号串扰。 | `PracticeViewV1.vue`；真实 Chrome 浏览器端到端测试 11 (通过)。 |
| EE-014 | P2 / 测试维护缺陷 | 已修复并通过测试 | **本地真实浏览器 E2E 测试全绿。**DOM 选择器与流程无障碍约定同步，真实 Chrome 浏览器无头运行通过。 | `frontend/tests/browser_e2e.test.js`；实测结果：13 通过、0 失败、0 跳过。 |
| EE-015 | P2 / 部署证据缺口 | **已闭环（2026-09-27 实机核验）** | **健康接口输出 commit SHA，并在 fnOS 物理实机完成版本追溯核验。**后端 `/api/v1/health` 返回 `commit_sha`；FPK `1.0.2` 已实机安装运行，安装不再回滚，重启后数据与主密钥保留。 | `system.py`（`commit_sha`）；`tests/test_fpk_packaging.py`；实机证据：fnOS 6.18 `192.168.x.x`，`appcenter-cli install-fpk` 成功、容器 `easy-exam-fpk` 起于 3000 端口、`/api/v1/health` 200。 |
| EE-016 | P1 / Bug | 已修复并通过测试 | **推荐算法薄弱筛选已修正。**使用结构化字段 `WEAK` 代替模糊文本匹配。 | `recommendation.py`；单测 `test_recommendations_exclude_weak` (通过)。 |
| EE-017 | P1 / Bug | 已修复并通过测试 | **跨题库推荐丢题已修复。**前端学习页提供按题库分组与明确启动题数。 | `LearningView.vue`；真实 Chrome 浏览器 E2E 测试 9 (通过)。 |
| EE-018 | P1 / SPEC 缺口 | 已修复并通过测试 | **跨设备事件同步与并发冲突检测完整闭环。**前端 `useSyncLoop.js` 游标按用户安全隔离（`easyexam_sync_cursor_${userId}`），并加入在途请求序号锁与用户一致性校验，杜绝账号切换时的竞态写入或跨账号事件派发；单测 `frontend/tests/sync.test.js` 包含在途挂起请求切换用户隔离测试；业务操作通过 `triggerSyncEvent` 实时上报，多视图消费刷新并检测版本并发冲突。 | `useSyncLoop.js`；`App.vue`；`sync.js`；`HomeView.vue`；`PracticeViewV1.vue`；`frontend/tests/sync.test.js` (通过)；真实 Chrome 浏览器 E2E 测试 11 (通过)。 |
| EE-019 | P1 / 会话恢复缺口 | 已修复并通过测试 | **未完成会话与模考草稿断点恢复。**后端提供 `/sessions/active`，前端首页横幅支持一键恢复作答。 | `practice.py`；`HomeView.vue`；单测 `test_list_active_sessions_returns_incomplete_sessions` (通过)。 |
| EE-020 | P2 / 用户流程缺口 | 已修复并通过测试 | **共享题库管理前端与跨库复制已闭环。**前端 `HomeView.vue` 提供成员列表展示、角色管理、成员移除与题目跨库复制小工具。 | `banks.py`；`HomeView.vue`；单测 `test_bank_members_listing_and_removal` (通过)；单测 `test_copy_to_bank_preserves_chapter_and_knowledge_tags` (通过)。 |
| EE-021 | P2 / SPEC 缺口 | 已修复并通过测试 | **歧义 PDF 解析人工校对与单事务原子入库完整闭环。**针对格式不规则或置信度不确定的 PDF 提取为校对候选草稿（`pdf_import_drafts`），前端 `ImportView.vue` 提供题目拆分、合并、编辑；修复入库条数计数（`imported_count`）；转正时通过原子 CAS 状态机锁（`UPDATE ... WHERE status = 'PENDING'`）防重复提交，并在单一原子事务中落盘草稿状态与题目数据；单测覆盖多线程真实并发导入拦截与零重复落盘。 | `connection.py` (Migration 17)；`pdf_importer.py`；`import_service.py`；`question_repository.py`；`ImportView.vue`；单测 `test_ambiguous_pdf_preview_and_manual_correction_ee021` (验证单事务入库计数与多线程并发 CAS 拦截通过)。 |

## 4. 审查提出但尚不能算作已确认缺陷的事项

| 项目 | 当前判定 | 后续处理 |
|---|---|---|
| 每日学习目标是否跨设备持久化 | SPEC 有每日/每周计划概念，但没有明确承诺“目标设置必须保存为用户设置”。不能仅凭没有设置表判定违反 SPEC。 | 若用户确认需要保存，作为产品需求补进 SPEC，再实现；否则保持为本地/请求参数行为。 |
| 必须接入 Bing、Tavily、SerpAPI 等商业搜索 | SPEC 要求默认本地 `open-webSearch` 并允许配置其他搜索服务，没有点名商业提供方。 | 先完成 EE-004 的适配器可配置和真实联调；商业供应商选择作为独立决策。 |
| 必须采用随机蓝图抽题 | SPEC 要求蓝图约束题目组成，没有规定随机算法细节。 | 先实现蓝图参与组卷；抽样策略作为实现设计，不把“随机”新增成产品承诺。 |
| 学习推荐算法除 EE-016、EE-017 外是否整体符合用户预期 | 首轮已确认并记录了薄弱题开关与跨题库启动两个具体缺陷；其余排序权重是否符合用户预期没有可复现失败用例。 | 先修复 EE-016、EE-017；其他算法调整须以新的输入/预期/实际证据为依据，不据此无限扩充范围。 |

## 5. 已有验证证据与边界

| 环境/层级 | 证据 | 结论与边界 |
|---|---|---|
| 飞牛 NAS，第三轮对抗 API 测试 | 用户提供的报告称 10 项通过、0 失败；脚本 `.agent/adversarial_e2e_test.py` 现存。 | 覆盖认证/改密、导入原子性、多选语义、错题状态、专项集合、斩杀恢复、模考泄题/终结状态、FSRS 评级、AI/搜索离线降级等。报告未覆盖蓝图抽题或模考错题开关，因此不关闭 EE-001/002。 |
| 飞牛 NAS，第三轮真实浏览器 E2E | 用户提供的报告称 8 个流程通过：注册、建库、导入、键盘刷题、错题/斩杀、模考报告、学习诊断。脚本 `frontend/tests/physical_fnos_browser_e2e.mjs` 现存。 | 这是已部署版本的真实浏览器流程证据。未覆盖手动新增/完整编辑题目、蓝图配置、资料 RAG、AI 设置、导出、重判或跨账号离线队列。此次未重跑。 |
| 本地后端/前端/构建，上一轮源码审查 | 上一轮记录：后端 187 项中 186 通过、1 跳过；前端单元测试 6 通过、0 失败、0 跳过；Vite 构建成功。 | 这是先前工作区快照的结果；当前工作区存在未提交改动，本次未重跑，不能作为当前代码全绿声明。 |
| 本地浏览器 E2E，上一轮源码审查 | 上一轮记录：3 通过、10 失败、0 跳过，首个失败为过时选择器并导致后续场景级联。 | 这是测试脚本/工作区那一轮结果，与 NAS 报告的 8 个流程不是同一套测试、同一环境或可直接对比的统计。 |
| 2026-09-25 早期本地 Docker/E2E 记录 | 旧快照记录后端 182 通过、前端单测 5 通过、连续 10 轮每轮 13 个 E2E 通过、Docker 健康检查通过。 | 只代表当日固定代码快照，不覆盖后续工作区或飞牛物理部署；保留为历史证据，不用于声明当前所有测试通过。 |
| 飞牛 NAS，2026-09-27 FPK 1.0.2 物理安装 | `appcenter-cli install-fpk` 安装成功且不再回滚；容器 `easy-exam-fpk` 起于 3000 端口；`/api/v1/health` 返回 200；`stop`/`start` 后已注册账号仍可登录、`var/.env` 主密钥 md5 不变。 | **本轮已运行**。这是 EE-015 闭环的物理证据，也验证了离线镜像加载时序修复（commit `48bfa85`）。边界：未覆盖多机型、未覆盖并发安装。 |
| 本地全套复跑，2026-09-27 HEAD `48bfa85` | 后端 205 通过 / 1 跳过；前端单测 11 通过；Chrome E2E 13 通过；移动端交互 E2E 11 项全通过；视觉冒烟通过；Vite 构建成功；`git diff --check` 与空白检查 0 错误。 | **本轮已运行**。唯一跳过为远程 fnOS 不可达（环境性）。 |
| 在线真实搜索 | 当前有适配器契约和离线降级测试；未见本轮真实第三方搜索结果的可追溯证据。 | 外部服务与生产适配器未验证，按 EE-004 跟踪。 |

## 6. 当前工作区中已出现、但尚未关闭的问题

EE-001 至 EE-021 **全部 21 项**已完成源码级修复、单元测试、前端生产构建与真实 Chrome 浏览器端到端流程验证；最后一项 EE-015 亦已通过 FPK `1.0.2` 的 fnOS 物理实机安装完成闭环。

**仍未关闭的验证缺口（不属于 EE 台账，单列跟踪）**：

1. `tests/test_remote_fnos_e2e.py` 因远程环境当前不可达而跳过（`skipped=1`）。属**环境性跳过**，按 `AGENTS.md` 避坑第 16 条不阻断收敛；NAS 可达时需另行执行并单独登记结果。
2. 外部真实商业搜索服务仍未联调（无生产 API Key），仅验证了 `UNAVAILABLE` 降级路径。

以上 2 项均为环境性缺口，必须逐项登记。按 [TESTING.md](../TESTING.md) 第 1 节门禁与避坑第 16 条，**不得笼统宣称"测试全绿"**，但收敛判定不受环境性跳过阻断。

**已关闭**：`frontend/tests/mobile_interaction_suite.mjs` 的三处脚本缺陷已修复并完成红色实证，11 项检查全通过（2026-09-27）。

## 7. 更新规则

1. 新条目必须有唯一 ID、类型、影响、证据、严重度/优先级、下一步和关闭标准。
2. SPEC 明确要求的行为缺口进入正式台账；超出 SPEC 的旧功能兼容、建议和候选需求必须单独标识，不能伪装成产品违约。
3. 报告、源码、测试和运行证据分层记录。用户/代理报告的结果标为“报告结果”；只有本轮实际执行才标为“本轮已运行”。
4. 一个缺陷关闭需要修复实现、相关回归测试通过，并完成该条目要求的真实用户流程验证；只更新文档、API 单测或构建成功都不能关闭 E2E 缺口。
5. 遇到 `skipped > 0`、环境未就绪、部署版本未知或工作区与部署不同步时，显式保留这些限制，不称为全绿。
6. 已关闭项保留关闭日期、修复提交和验证证据；不要删除历史失败来制造全绿。

## 8. 2026-09-30 对抗审查与修复批次

本节基于当前工作区 HEAD `582345c` 和当时未提交的文件状态复核；保留此前工作区改动，不以本节覆盖历史部署或历史测试快照。此次审查要求至少 30 项，但只将有源码位置的可复核事项纳入候选；其中“需要动态验证”不计为已确认缺陷。

### 本批已修复与闭环（对抗性审查 14 处不一致与缺口）

| ID | 等级 | 问题与修复 | 证据/验证 |
|---|---|---|---|
| ADV-001 | P2 / 推荐算法 | 推荐候选集遗漏 `chapter_id`；现在在 `recommendation_candidates` 中联结查询带入 `qv.chapter_id`。 | `practice_repository.py:recommendation_candidates`；`test_adv_001_recommendation_includes_chapter_id` (先红后绿)。 |
| ADV-002 | P1 / 会话语义 | 模考单题作答推进了 FSRS 卡片且在 `record_mistakes=False` 时仍记录错题；现在在 `save_attempt` 中在模考模式下禁止 FSRS 调度，并严格遵循 `record_mistakes` 配置。 | `practice_repository.py:save_attempt`；`test_adv_002_exam_attempt_does_not_advance_fsrs_and_honors_mistake_switch` (先红后绿)。 |
| ADV-003 | P1 / 并发与幂等 | 作答服务层完成状态检查与仓储事务落盘之间存在竞态；现在 `save_attempt` 在写入事务中重新校验会话属主与完成状态。 | `practice_service.py:submit_attempt` + `practice_repository.py:save_attempt`；现有终态幂等测试与新增终态作答回归。 |
| ADV-004 | P1 / 安全泄题 | 模考进行中可能通过普通题目详情或列表接口读取标准答案和解析；现在 `QuestionRepository.get_for_user` 与 `list_for_bank` 动态检测用户活动模考，自动脱敏答案与解析。 | `question_repository.py:_get_active_exam_question_ids`；`test_adv_004_exam_active_desensitizes_questions` (先红后绿)。 |
| ADV-005 | P1 / 会话超时 | 服务端未对模考时间做硬性拒绝校验；现在 `practice_service.py` 增加 `_check_exam_timeout`（限时 + 60s 宽限），超时拒绝提交与草稿同步（返回 409）。 | `practice_service.py:_check_exam_timeout`；`test_adv_005_exam_timeout_server_enforcement` (先红后绿)。 |
| ADV-006 | P1 / 数据导入 | 表格导入难度归一化缺失 0（未分级）离散映射且缺失时错误默认；现在保留 1~5 离散整数，无法识别或缺失规范映射为 0。 | `spreadsheet_importer.py:normalize_difficulty`；`test_adv_006_spreadsheet_discrete_difficulty_mapping` (先红后绿)。 |
| ADV-007 | P2 / 统计准确性 | 弱项统计按历史全部 question_versions 聚合导致旧版本重复影响排名；现在在 `trends` 的 `weak_rows` 查询中限定 `MAX(version_number)`。 | `practice_repository.py:trends`；`test_adv_007_learning_weak_points_latest_version_only` (先红后绿)。 |
| ADV-008 | P2 / 统计准确性 | 到期复习统计未排除已淘汰斩杀题目；现在在 `trends` 查询中与 `list_due_reviews` 逻辑统一（排除 `status='MASTERED'` 并关联有效错题/薄弱项）。 | `practice_repository.py:trends`；`test_adv_008_learning_due_reviews_excludes_eliminated` (先红后绿)。 |
| ADV-009 | P2 / 统计准确性 | 学习完成率分子混入非 FSRS 复习模式的作答；现在在 `trends` 的 `reviews_done` 查询中严格限定 `s.mode = 'FSRS'`。 | `practice_repository.py:trends`；`test_adv_009_learning_completion_rate_mode_filtered` (先红后绿)。 |
| ADV-010 | P2 / 统计准确性 | 客观正确率基线与近期统计混入主观题；现在在 `trends` 的 `recent` 与 `baseline` 查询中显式排除主观题型 `('ESSAY', 'SHORT_ANSWER', 'SUBJECTIVE')`。 | `practice_repository.py:trends`；`test_adv_010_objective_accuracy_excludes_subjective` (先红后绿)。 |
| ADV-019 | P2 / 题库权限与完整性 | 题库章节与标签缺少修改与删除 REST 路由，且缺少父级层级归属和循环引用校验；现在补充 `update_chapter`、`delete_chapter`、`update_tag`、`delete_tag` 及其路由端点，并加入循环父级检查。 | `bank_repository.py`；`backend/app/api/routes/banks.py`；`test_adv_019_chapter_tag_crud_and_parent_validation` (先红后绿)。 |
| ADV-021 | P1 / 导入置信度 | PDF 提取置信度不确定的题目可能绕过人工校对草稿箱直接批量入库；现在 `parse_pdf_questions` 当 `confidence == 'UNCERTAIN'` 时严格拒绝直接入库。 | `pdf_importer.py:parse_pdf_questions`；`test_adv_021_uncertain_pdf_must_use_draft_box` (先红后绿)。 |
| ADV-024 | P2 / 数据防篡改 | 会话草稿 answers、flags 允许越界非法题目 ID 注入，`current_index` 负数越界，`time_spent` 负数或无界；现在在 `update_draft` 与 `toggle_flag` 中限定只接受会话快照内的题目，并对游标和耗时施加边界约束。 | `practice_repository.py:update_draft/toggle_flag`；`test_adv_024_draft_and_flag_boundary_guards` (先红后绿)。 |
| ADV-032 | P2 / 服务端依赖解耦 | `backend/legacy/services` 与 `backend/services` 存在循环导出风险；现在统一使用相对导入与显式名称导出，根除动态导入异常。 | `backend/legacy/services/__init__.py`；`backend/services/__init__.py`；全量发现测试通过。 |

本轮目标用例：12 项专项对抗测试先红后绿全数通过（`tests/test_adversarial_review_fixes.py`）。

### 第二轮深度对抗审查与加固（ADV2-001 ~ ADV2-007）

| ID | 等级 | 问题与修复 | 证据/验证 |
|---|---|---|---|
| ADV2-001 | P1 / 安全泄题 | 模考进行中 `QuestionRepository.list_versions` 未脱敏标准答案与解析，考生可绕过 `get_for_user` 获取答案；现在 `list_versions` 动态检测活动模考并统一脱敏 `answer` 和 `explanation`。 | `question_repository.py:list_versions`；`test_adv2_001_list_versions_desensitizes_during_exam` (先红后绿)。 |
| ADV2-002 | P1 / 权限越权 | 题目版本演化（`create_next_version`）、历史重判（`regrade_question_history`）与冲突解决（`resolve_conflict`）仅校验题库成员资格，未限制角色，导致只读普通成员 `MEMBER` 具备编辑与重判越权；现统一严格限定 `m.role IN ('ADMIN', 'EDITOR')`。 | `question_repository.py`；`test_adv2_002_member_cannot_modify_or_regrade_or_resolve` (先红后绿)。 |
| ADV2-003 | P1 / 会话生命周期 | `PracticeService.review_answer` 为单题创建 FSRS 复习会话并提交 attempt 后未调用 `complete_session`，导致数据库遗留未完结僵尸会话；现提交作答后立即完成并关闭该单题会话。 | `practice_service.py:review_answer`；`test_adv2_003_review_answer_closes_session` (先红后绿)。 |
| ADV2-004 | P2 / 多租户隔离 | 题目斩杀 `kill` 接收任意题目 ID 未校验题库成员资格，`list_killed` 未联结 `question_bank_members`，允许跨租户嗅探题干与题型；现增加成员资格鉴权（未授权拒绝 403）并限定仅列出所属题库斩杀题目。 | `practice_repository.py:kill/list_killed`；`test_adv2_004_kill_requires_bank_membership_and_prevents_leak` (先红后绿)。 |
| ADV2-005 | P2 / 统计准确性 | 刷题摘要 `PracticeRepository.summary` 在计算总尝试次数时未排除主观题，稀释客观题正确率；现显式排除主观题型 `UPPER(qv.type) NOT IN ('ESSAY', 'SHORT_ANSWER', 'SUBJECTIVE')` 并限定租户所属题库。 | `practice_repository.py:summary`；`test_adv2_005_summary_excludes_subjective` (先红后绿)。 |
| ADV2-006 | P3 / 跨平台兼容 | Windows 环境下 `subprocess.run(text=True)` 未显式指定 UTF-8 编码，可能受系统本地代码页（如 GBK）干扰；现统一显式指定 `encoding="utf-8", errors="replace"`。 | `backend/app/api/routes/system.py`；`scripts/setup-hooks.py`；代码静态审计。 |
| ADV2-007 | P3 / 交付版本对齐 | `frontend/package.json` 中的 `version` 遗留在 `1.0.0`，与 `manifest` 和 `docker-compose.yaml` 的 `1.0.8` 产生漂移；现推进同步至 `1.0.8`。 | `frontend/package.json`；前端测试与构建验证通过。 |

**最新全套验证结果（2026-09-30 深度加固后实跑）**：
- 专项对抗测试套件：`python -m unittest tests/test_adversarial_review_fixes.py -v` → **17 项全通过**（含 5 项 ADV2 新增变异实证用例）。
- 后端全量测试：`python -m unittest discover -s tests -v` → **224 通过、0 失败、0 错误、1 跳过**（118.2s），唯一跳过项为 `test_remote_fnos_e2e.py`（远程 fnOS 外部环境性跳过）。
- 前端单元/契约测试：`npm --prefix frontend run test:unit` → **14 通过、0 失败、0 跳过** (208ms)。
- 本地真实 Chrome 浏览器 E2E：`npm --prefix frontend run test:e2e` → **13 通过、0 失败、0 跳过** (14.3s)。
- 移动端交互 E2E：`node frontend/tests/mobile_interaction_suite.mjs` → **11 项全部通过**。
- 视觉冒烟：`node tests/visual_smoke/run.mjs` → 四道正身信号通过。
- 前端生产构建：`npm --prefix frontend run build` → Vite v5.4.21 成功（exit code 0）。
- 代码与空白检查：`git diff --check` → 0 错误。




**2026-09-30 FPK 测试包交付**：按当前工作区 `fpk/easy-exam/manifest` 与 Compose 的 `1.0.8` 构建传统 Docker archive 格式的离线 FPK：`dist/fpk-test-20260930/easy-exam-1.0.8.fpk`。验证：FPK 打包测试 8/8 通过；包内 MD5 与 manifest 一致、镜像 tag 为 `ailm32442/easy-exam:1.0.8`、平台 `linux/amd64`；临时容器 health 返回 `ok`；包已上传至 NAS `/tmp/easy-exam-1.0.8-test-20260930.fpk`，两端 SHA-256 均为 `a627918055c8e88cadee297d32cadf1e0ea00cbb25ab6a3f304f19ea8a696d36`。首次对已安装的 1.0.7 直接执行 `install-fpk` 只返回“已安装”，复核确认它没有替换现有版本。随后创建并验证持久目录备份 `/tmp/easy-exam-pre-1.0.8-20260930.tar.gz`（权限 600，SHA-256 `09c8c0b7c164a90bcc2f81ed950958b848332a0c996f91e6484d75f955739ef8`），按该 FPK 的卸载钩子保留 `/vol4/@appdata/easy-exam` 后重新安装并启动。**fnOS 实机验收通过**：应用中心显示 1.0.8 running，容器镜像 tag 为 `ailm32442/easy-exam:1.0.8` 且镜像配置摘要与包内 Docker archive 一致，health 200，数据库 `integrity_check=ok`；users/banks/questions/versions/sessions/attempts/mistakes 数量分别为 9/5/145/145/24/29/14，升级前后相同；`.env` 哈希与备份相同。health 的 `commit_sha` 仍为 `unknown`，因此以本次 FPK SHA-256 和镜像摘要关联构建，不声称 Git commit 追溯。
**2026-09-30 方向 A 主题改造（本地源码验证）**：新增浅色默认与本地持久化的深色切换，主题入口覆盖侧栏/移动导航、登录、沉浸式练习与模考；核心内容页统一使用温纸白与松绿语义色。证据：`frontend/tests/theme.test.js` 5/5；`npm --prefix frontend run test:unit` 19/19（现有 `useSyncLoop` 生命周期告警仍在）；`npm --prefix frontend run build` 成功；真实 Chrome `npm --prefix frontend run test:e2e` 13/13、0 skipped。真实浏览器多视口截图位于 `screenshots/current_source_full_review_20260930_1719/direction-a-final/`（桌面 1280、手机 375/390）；深色判题反馈专图 `desktop-09-practice-result-dark.png`。这批证据不代表 fnOS 部署验证。

**2026-09-30 EasyExam 1.0.9 FPK 打包与上传**：版本号同步为 1.0.9（manifest、前端 package、Compose 镜像标签），构建 Linux/AMD64 镜像 `ailm32442/easy-exam:1.0.9` 并制作离线包 `dist/fpk-1.0.9/easy-exam-1.0.9.fpk`（38,149,504 bytes）。验证：FPK 打包测试 8/8；后端 unittest 224 通过、0 失败、1 环境性跳过（远程测试固定地址 `192.168.1.100` 不可达）；前端单元 19/19、真实 Chrome E2E 13/13、构建成功。包 SHA-256 `8f57442cfae95a9038e6a64511f232069817f878289d1dfd35aad781e23548d9`，本机与 NAS 一致；已上传至 NAS `nas:/tmp/easy-exam-1.0.9-test-20260930.fpk`。上传后应用中心仍显示 1.0.8 running；本次未安装或替换运行版本，fnOS 实机运行验收尚未进行。
