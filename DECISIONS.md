# 决策与演进时间线 (DECISIONS.md)

> 本文档用于以微日志（Lightweight ADR）的形式记录项目的重大架构调整、需求变更及背后的原因。
> **目的**：防止数周或数月后遗忘“当初为什么把那个逻辑改成这样”，杜绝需求反复横跳。

---

## 变更记录模板格式
```markdown
### [YYYY-MM-DD] [变更标题]
- **触发背景**：用户反馈 / 性能瓶颈 / 测试异常
- **核心决策**：将原本的 XXX 规则改为 YYY
- **对应 SPEC 章节**：SPEC.md 第 X.X 节
- **影响范围**：[列出涉及的模块或文件]
```

---

### [2026-11-12] W2-3：退役不可达的旧版组卷 / AI 配置弹窗
- **触发背景**：W1 波次已把智能组卷改为跳转 `/exams`（由考试中心的单一蓝图抽屉编辑），AI 配置改为跳转 `/settings?section=ai`；命令面板也不再有这两项入口。但 `AppLayout.vue` 仍导入并渲染 `BlueprintModal` 与 `AiConfigModal`，`handleSidebarAction` 仍映射 `blueprint` / `ai`。全仓 census 后确认：`easyexam:open-dialog` 只投递 `drafts`（首页 `easyexam:action` 与题库管理页），命令面板只保留 `drafts` 行，键盘监听只有 Escape；没有任何可达 UI 路径能产生 `activeDialog === 'blueprint' | 'ai'`。
- **核心决策**：
  1. **删除两个不可达组件**：`BlueprintModal.vue` 与 `AiConfigModal.vue` 连同 `AppLayout` 的导入、渲染分支和 `blueprint` / `ai` 侧栏动作映射一并移除；`handleSidebarAction` 只保留仍可达的 `drafts`。
  2. **保留 `AiDraftsModal`**：命令面板「AI 智能出题」行、首页 `easyexam:action === 'drafts'`（含 `/?action=drafts`）以及题库管理页「打开草稿」三条路径均可触发，未退役。
  3. **同步清理只被退役组件消费的词典键**：`blueprint.*` 命名空间、`sidebar.blueprint`，以及仅由这两个组件引用的 70 个 `ui.kNNNN` 键；`ep.*` 中同名字符串仍被 `ExamCenterView` / `SettingsView` / `AiDraftsModal` 使用，全部保留。JS 词典与生成 JSON 同步删除并通过 `tests/locale.test.js` 的 deepEqual 平价。
  4. **测试随组件退役（`guard_test_tampering.py` 登记）**：`frontend/tests/components/blueprint_modal.test.js` 测的是已不存在的组件与已被考试中心抽屉取代的 simple/advanced 组卷交互，无法迁移到新编辑器（drawer 的 DOM 与数据模型不同）。因此随组件删除，而非放宽或改写断言；`guard_test_tampering.py` 会把文件删除记为“断言被删除”并告警，按该门禁要求在提交说明与本条登记：这是合法退役，不是为制造成全绿而删测试。
  5. **脚本中的陈旧引用一并清理**：`scan_localized_templates.js` 移除 `AiConfigModal` 白名单项（同名 URL/密钥占位串在 `SettingsView` 仍被使用）；`verify_and_capture_ui.mjs` 删除已失效的 `.sidebar-nav-item.sub:has-text("智能组卷")` 截图步骤及复制映射。
- **对应 SPEC 章节**：SPEC.md 前端信息架构（考试中心为唯一组卷编辑器；AI 配置归属设置页）。
- **影响范围**：`frontend/src/layouts/AppLayout.vue`, `frontend/src/components/{BlueprintModal,AiConfigModal}.vue`（删除）, `frontend/tests/components/blueprint_modal.test.js`（删除）, `frontend/src/locales/{en-US,zh-CN}.{js,json}`, `frontend/src/locales/{ui-en-US,ui-zh-CN}.js`, `frontend/scripts/{scan_localized_templates.js,verify_and_capture_ui.mjs}`, `DECISIONS.md`。

### [2026-11-12] W2-2：页面级对话框迁移到 AppDialog，并保留 NotesView 双重守卫互不干扰
- **触发背景**：`新建笔记`、`新建题库`、首页 `创建题库` 与刷题页 `退出练习` 四个对话框各自在 backdrop 上绑定 `keydown.esc`，Escape 只在焦点恰好位于遮罩内时生效；打开时也不移动焦点。W1-2 已为笔记阅读器加入未保存守卫，若直接迁移，create 对话框的 Escape 会继续冒泡到 reader 的 window 监听，误触发关闭/未保存提示。
- **核心决策**：
  1. **统一使用 `AppDialog`**：四个对话框改为共享组件，Escape 由 document capture 监听处理，打开后焦点进入首个字段（刷题页为「继续练习」），Tab 循环限制在面板内，关闭时焦点回到触发按钮。
  2. **保留刷题页退出策略**：遮罩点击与 Escape 仍表示「取消退出」，不静默放弃作答；确认按钮才真正保存并退出。
  3. **双重守卫显式隔离**：`NotesView` 的 reader keydown 监听在 `event.defaultPrevented` 时直接返回。`AppDialog` 已在 capture 阶段 `preventDefault`，因此关闭 create 对话框不会同时关闭 reader 或弹出未保存提示；打开 create 对话框也不经过 reader 的守卫路径。
  4. **测试选择器按新标记更新（非弱化断言）**：`browser_e2e.test.js` 的题库创建对话框选择器由 `.exam-setup-dialog` 改为 `[data-testid="bank-create-dialog"]`，退出确认的取消按钮由 `.dialog-actions .btn` 改为 `.exit-actions .btn`。两者都是因为对话框根节点已迁移到 `AppDialog` 的 `.app-dialog-panel`，原类名不再描述真实结构；断言强度与操作语义不变。笔记创建对话框仍保留 `library-dialog` 类，既有 E2E 选择器无需改动。
- **对应 SPEC 章节**：SPEC.md 前端交互与可访问性规范。
- **影响范围**：`frontend/src/views/NotesView.vue`, `frontend/src/views/BanksView.vue`, `frontend/src/views/HomeView.vue`, `frontend/src/views/PracticeViewV1.vue`, `frontend/tests/browser_e2e.test.js`, `frontend/tests/components/{notes_view,banks_view,home_view,practice_view}.test.js`, `DECISIONS.md`。

### [2026-10-23] Issue #11：fnOS 物理验收测试入口按真实 API/UI 契约重写
- **触发背景**：`tests/test_remote_fnos_e2e.py` 与 `frontend/tests/physical_fnos_browser_e2e.mjs` 基于历史 API（无 `/api/v1` 前缀、无 Bearer 认证）与旧版扁平导航（`button:has-text("导入题目")` 等）编写，在真实 fnOS 上必然失败或整包 skip；同时脚本写死了 NAS 地址、Chrome 安装路径和默认测试密码。Issue #11 要求在不改业务功能、不建 CI 物理门禁的前提下，让这两个入口在真实 fnOS 上可执行并完成一次核心链路验收。
- **核心决策**：
  1. **测试入口对齐真实现行契约，而非回退产品**：API 入口改用 `/api/v1` 与注册/登录后的 Bearer Token；浏览器入口改用侧边栏导航（导入题库 / 错题攻克 / 复习中心）、真实交卷与返回按钮文案、注册页双密码字段。
  2. **环境参数显式化**：`FNOS_BASE_URL` 变为必填（缺省即 `SkipTest` / exit 2），不再回退到某个固定内网地址；`CHROME_PATH` 改为可选，缺省使用 Playwright 自带 Chromium；测试密码默认每次运行生成，不再假设固定的 `Password123!`。
  3. **重启持久性拆为两阶段**：`FNOS_E2E_PHASE=chain` 建数据并写状态文件，运维在 NAS 上执行 `cmd/main stop/start` 后，`FNOS_E2E_PHASE=post-restart` 用同一账号复验题库、题目、错题与已提交模考报告；不引入自托管 Runner 或排班。（两个阶段都必须同时带 `FNOS_E2E_EXPECTED_SHA`，见下方 2026-10-26 条目；缺该变量时 `test_01` / `test_03` 会直接失败而不是 skip。）
  4. **不把已修复缺陷写成新断言**：部署镜像 `1.0.19`（分支 `1797a03`）上 `/auth/me` 仍泄露 `password_hash`、JUDGE 选项未归一化；这两项在 `main` 已由 #61 修复。本次物理链路改用 SINGLE + MULTI，不为此修改业务代码，缺陷作为部署漂移在 PR 中报告。
  5. **断言强度不降低**：旧健康检查断言被保留为 `self.health.get("status") == "ok"`；`guard_test_tampering.py` 因断言行重排会告警，按该门禁要求在此登记：这是合法测试契约重写（旧测试从未执行过），不是放宽预期。
- **对应 SPEC 章节**：SPEC.md 验收与测试口径（真实物理环境不得以 Mock/API 冒充）。
- **影响范围**：`tests/test_remote_fnos_e2e.py`, `frontend/tests/physical_fnos_browser_e2e.mjs`, `TESTING.md`, `docs/REQUIREMENTS_TRACEABILITY.md`。

### [2026-10-26] Issue #11 修复：证据必须归属于被验收的那一个 revision
- **触发背景**：上一轮把镜像 `ailm32442/easy-exam:1.0.19`（分支提交 `1797a03`）上的实跑结果写成了本 PR 的验收证据。维护者冻结补充要求"从 exact HEAD 构建部署、核对实机 revision 等于目标 SHA、三项验证都在该构建上做"，并明确旧镜像结果不作数。两个入口本身并不检查自己连的是哪个版本，所以"跑通了"和"证明了本 PR"之间原本没有任何强制关联。
- **核心决策**：
  1. **revision 成为硬门禁而非口头约定**：两个入口新增必填 `FNOS_E2E_EXPECTED_SHA`，读实机 `/api/v1/health` 的 `commit_sha` 并强断言相等；未设置该变量一律拒绝执行。理由：版本不符时最危险的失败形态是"全绿但证明不了任何东西"，因此必须让它当场变红，而不是依赖执行者自觉核对。
  2. **重新从 exact HEAD 构建部署，不复用旧产物**：用 `git archive` 取被验收 revision 的树在 fnOS 上构建，并用镜像内 95 个后端文件 + 前端产物的逐个 SHA-256 证明产物与该 revision 一致；`commit_sha` 通过 `EASYEXAM_BUILD_SHA` 注入部署编排。被验收 revision 必须是**当轮 HEAD 本身**，不能是上一轮 HEAD：入口脚本就在 HEAD 上，若拿旧 HEAD 的构建配新 HEAD 的脚本，验的仍是旧入口。因此每次入口脚本变更后都要重新构建部署并重新实跑。
  3. **旧镜像的两个缺陷不写入本 PR 结论**：`/auth/me` 泄露 `password_hash` 与 JUDGE 未归一化在 exact-head 代码中已修复（#61），它们是旧镜像的事实；本轮不再以"待重新部署验证项"的形式与本 PR 证据混写。
  4. **浏览器脚本等待正确信号**：模考段原先等 `.exam-page`，而该容器先于题目渲染（`ExamView.vue` 中 `.answer-grid` 位于 `v-else-if="question"` 分支），导致读到 0 题。改为等待 `.answer-grid button`。这属于入口自身的过时假设，不改业务代码。
- **对应 SPEC 章节**：SPEC.md 验收与测试口径；Frozen Issue #11「验收对象澄清」节。
- **影响范围**：`tests/test_remote_fnos_e2e.py`, `frontend/tests/physical_fnos_browser_e2e.mjs`, `TESTING.md`, `docs/REQUIREMENTS_TRACEABILITY.md`, `DECISIONS.md`。

---

### [2026-10-19] PR #55 第二轮 Review 阻断修复：章节更新三元语义、409 并发覆盖拦截与避免伪造答案
- **触发背景**：PR #55 独立 Reviewer 第二轮审查提出两项 BLOCKER 和一项 MINOR：1. `QuestionUpdate.chapter_id` 默认 None 导致 `payload.model_dump()` 吞没未提供语义并清空章节；2. 过期 `base_version_number` 返回 200 并生成新版本静默覆盖当前最新版本；3. 题型切换若旧答案不兼容时自动选取首选项伪造正确答案。
- **核心决策**：
  1. **章节更新三元语义**：通过 `payload.model_fields_set` 严格区分未提供（从 update 字典中排除，仓储层保留原章节）、显式 null/空（清空章节为 None）与显式 ID（更新章节）；既有 PracticeView 编辑路径不发 chapter_id，百分之百保留既有章节；
  2. **409 并发覆盖拦截与版本历史保护**：若提交的 `base_version_number` 小于当前最新版本，默认直接记录冲突并抛出 `VersionConflictError` 返回 HTTP 409，严禁生成新版本覆盖最新内容；针对 PracticeView 离线多版本分支合并工作流支持 `allow_stale_branch=True` 兼容模式；前端编辑弹窗与管理页均提供醒目冲突警报及一键“重新加载最新版本”；
  3. **不兼容答案安全置空**：抽取 `adaptAnswerOnTypeChange` 纯领域函数，当题型切换答案不兼容时坚决清空答案并提示用户重新选择，杜绝自动伪造首选项为正确答案。
- **对应 SPEC 章节**：EASYEXAM_QUESTION_BANK_CONTENT_MANAGEMENT_V1_FROZEN.
- **影响范围**：`backend/app/infrastructure/db/repositories/question_repository.py`, `backend/app/api/routes/questions.py`, `frontend/src/domain/bankManage.js`, `frontend/src/components/QuestionEditModal.vue`, `frontend/src/views/BankManageView.vue`, `frontend/src/views/PracticeViewV1.vue`, `frontend/src/locales/*`, `frontend/tests/bank_manage.test.js`, `frontend/tests/bank_manage_e2e.test.js`, `tests/test_question_bank_content_management.py`。

### [2026-10-19] PR #55 题库内容管理 v1 审查反馈修复与测试框架对齐
- **触发背景**：PR #55 独立 Review 提出 4 项必须修复和 4 项细节完善：1. `test_question_bank_content_management.py` 使用 pytest 导致无 pytest 环境的 CI 失败；2. 浏览器 CI 未纳管 `bank_manage_e2e.test.js` 且需补齐模考脱敏断言；3. `QuestionEditModal.vue` 题型切换/选项清理与校验；4. 并发编辑冲突提示与保留；5. 允许清空章节、中英文判断题支持、移动端弹窗背景加固。
- **核心决策**：
  1. **测试框架标准对齐**：将 `test_question_bank_content_management.py` 转为标准 `unittest.TestCase`，兼容 CI 的 `python -m unittest discover -s tests -v`；
  2. **E2E 纳入门禁与脱敏实断言**：在 `frontend/package.json` 的 `test:e2e` 中串联 `bank_manage_e2e.test.js`，增加模考期间 API 与 DOM 脱敏的真实断言；
  3. **前端表单严校验与清理**：在 `bankManage.js` 增加 `validateQuestionEdit` 与 `sanitizeAnswerOnOptionRemove`，杜绝空/无效答案，类型转换不兼容时合理重置；
  4. **并发冲突持久化追踪与显式警报**：保存基于过期 `base_version_number` 时保留冲突快照，管理页展示醒目黄色冲突提示 Banner。
- **对应 SPEC 章节**：EASYEXAM_QUESTION_BANK_CONTENT_MANAGEMENT_V1_FROZEN.
- **影响范围**：`backend/app/infrastructure/db/repositories/question_repository.py`, `frontend/src/components/QuestionEditModal.vue`, `frontend/src/domain/bankManage.js`, `frontend/src/views/BankManageView.vue`, `frontend/src/locales/*`, `frontend/tests/bank_manage.test.js`, `frontend/tests/bank_manage_e2e.test.js`, `tests/test_question_bank_content_management.py`, `tests/visual_smoke/*`。

### [2026-10-02] v1.0.16: 工具弹窗顶层调度（彻底消除背景跳转）、用户账户纯净解耦与首页幽灵代码彻底清理
- **触发背景**：用户反馈：1. 在复习中心、错题、笔记等非首页视图点击侧边栏的“配置与工具”（智能组卷/AI出题/AI配置）时，背景会强行跳回首页概览；2. 用户中心气泡菜单中依然混杂着“知识笔记”链接，与侧边栏独立一级“知识笔记”工作区重复混淆；3. 首页存在大量已被全局替代的旧版内联弹窗代码和冗余状态。
- **核心决策**：
  1. **工具弹窗全路由顶层就地唤起（Zero Background Jump）**：
     - 将【智能组卷】(`BlueprintModal.vue`)、【AI出题】(`AiDraftsModal.vue`) 和【AI配置】(`AiConfigModal.vue`) 封装为独立组件，统一挂载在顶层容器 `AppLayout.vue`；
     - 侧边栏及命令面板点击时直接通过响应式变量激活对应顶层遮罩，当前路由与背景页面 100% 保持不动，彻底消灭背景跳转和时序竞态；
  2. **用户账户与知识笔记完全解耦**：
     - 知识笔记作为一级独立路由（`/notes`）独占管理；
     - 用户头像气泡菜单彻底剥离任何与知识笔记绑定的逻辑，仅保留账号基本信息、角色标识、密码修改弹窗（`ChangePasswordModal.vue`）和退出登录，职责完全正交化；
  3. **首页彻底清理幽灵内联弹窗**：
     - 从 `HomeView.vue` 中物理删除已被提升的 3 个旧内联弹窗模板（超 300 行）及关联的响应式变量与方法，首页通过触发全局自定义事件无缝转接顶层弹窗。
- **对应 SPEC 章节**：SPEC.md 前端架构与导航规范。
- **影响范围**：`frontend/src/layouts/AppLayout.vue`, `frontend/src/views/HomeView.vue`, `frontend/src/components/AppSidebar.vue`, `frontend/src/components/ChangePasswordModal.vue`, `frontend/src/components/BlueprintModal.vue`, `frontend/src/components/AiDraftsModal.vue`, `frontend/src/components/AiConfigModal.vue`, `fpk/easy-exam/*`。

### [2026-10-02] v1.0.15: 跨路由动作竞态加固、移动端导航闭环与全端布局防溢出
- **触发背景**：用户反馈：1. 在非首页路由下点击侧边栏工具存在偶发不响应或时序竞态；2. 侧边栏底栏由于按钮较多在窄屏下存在横向溢出隐患；3. 移动端底栏缺少笔记与指令中心；4. 移动端学习计划抽屉在小屏下展示不全。
- **核心决策**：
  1. 采用 `query: { action }` 路由传参 + `HomeView` 首帧同步监听；
  2. 侧边栏底栏采用双层工学布局；
  3. 移动端补齐知识笔记与指令中枢，统一题库大厅文案；
  4. 学习计划任务抽屉全端自适应优化，彻底清理老首页幽灵残存代码。
- **对应 SPEC 章节**：SPEC.md 前端架构与导航规范。
- **影响范围**：`frontend/src/layouts/AppLayout.vue`, `frontend/src/views/HomeView.vue`, `frontend/src/components/AppSidebar.vue`, `frontend/src/components/MobileNav.vue`, `frontend/src/views/LearningView.vue`。

### [2026-10-02] v1.0.14: 现代化前端架构重塑（App Shell + Vue Router）、人体工学抽屉、双模组卷与平实术语规范
- **触发背景**：用户反馈：1. 前端采用大单体条件渲染导致伪多页面、状态缠绕、无法通过 URL 准确定位与刷新；2. 题目展开列表横向撑出屏幕，缺乏系统性工程设计；3. “考试蓝图”、“AI变式草稿箱”、“错题斩杀”等术语晦涩花哨，缺乏平实指引；4. 个人笔记与知识总结被压缩在用户页左下角缺乏独立工作区；5. 应用图标（小闪电）与系统图标（试卷）不一致且主题切换触控目标过小。
- **核心决策**：
  1. **现代前端体系重塑（App Shell + Vue Router）**：
     - 引入 `vue-router`（4.x），使用 `createWebHashHistory` 避免飞牛反向代理/静态文件路径丢失路由问题；
     - 拆解为 AppLayout 页面骨架、一级视图（HomeView, LearningView, MistakesView, ImportView, NotesView）以及独立沉浸式视图（PracticeViewV1, ExamView）；
  2. **人体工学抽屉组件替代行内展开**：题目清单展开彻底摒弃行内流式插入，重构为标准 Slide-over Drawer（抽屉遮罩 + 侧滑面板 + 滚动隔离），彻底消灭窄屏溢出与行内挤压；
  3. **智能组卷简易/高级双模分层与平实术语**：
     - 考试蓝图改名“智能组卷”，默认开启“简易模式”（仅需配置各题型数量与分值比例），“高级模式”容纳知识点权重与难度过滤；
     - 全站术语直白化（“AI出题”、“错题攻克”、“复习中心”），新功能指引卡片附带“不再提示”并持久化记忆，不常态化侵占首屏；
  4. **一级工作区与品牌规范化**：
     - 将知识笔记从用户弹窗剥离为一级导航核心工作区 `NotesView`，打通学习笔记、心得与 AI 知识库关联；
     - 替换应用内小闪电为官方正牌试卷图标（`AppBrandIcon`），深浅主题与双语切换按钮优化为符合移动端与触控可达性规范的大尺寸圆角按钮。
- **对应 SPEC 章节**：SPEC.md 前端架构、用户体验与导航规范、AGENTS.md 第 17 条（渐进式指引与平实命名）。
- **影响范围**：`frontend/src/router/*`, `frontend/src/layouts/*`, `frontend/src/views/*`, `frontend/src/components/*`, `frontend/src/locales/*`, `fpk/easy-exam/*`。

### [2026-10-01] v1.0.13: 题库顺序通刷与记忆、后台一键批量预生成 AI 解析
- **触发背景**：用户反馈：1. 刷题时需要支持严格按照题库录入原始物理顺序（1 到 N）从头到尾刷一遍，具备断点续刷与进度可视化；2. AI 解析每次答题时现场生成等待耗时，希望在题库级一键直接在后台全部预生成，落盘持久化，后续刷题秒开。
- **核心决策**：
  1. **全库顺序通刷与断点自动恢复**：
     - `question_repository.py` 严格保证 `ORDER BY q.created_at ASC, q.rowid ASC` 确定性物理录入顺序；
     - 题库卡片实时计算并展示通刷进度条（已完成题数/总题数及百分比），根据是否有未完成练习动态呈现“继续顺序通刷 (第 X 题)”与“重新通刷”；
     - 刷题端 `PracticeViewV1.vue` 建立断点记忆（支持 `syncDraft` 同步 `current_index`，复用或中途返回时自动定位至首个未答题目），顶栏标题切换为“顺序通刷”；
  2. **后台异步批量预生成 AI 解析**：
     - 后端 `AiTutorService` 增加线程安全的任务队列与锁调度，支持增量扫描（仅补缺失解析）或全量覆盖；
     - 提供 REST 端点 `POST /api/v1/ai/banks/{bank_id}/generate-batch` (202 Accepted)、`GET /api/v1/ai/banks/{bank_id}/batch-status` 与 `POST /api/v1/ai/banks/{bank_id}/batch-stop`；
     - 解析内容作为官方/辅助解析永久更新落盘至数据库题目标准版本，刷题与复习时零等待秒开；生成过程严格遵从领域红线（只充实官方/AI解析，绝不篡改标准答案）；
     - 前端首页卡片集成“AI 批量解析”工作台弹窗，支持全量/增量选项、任务实时轮询、实时进度条、耗时估算与随时暂停。
- **对应 SPEC 章节**：SPEC.md 核心刷题与 AI 智能辅导章节。
- **影响范围**：`backend/app/application/ai_tutor_service.py`, `backend/app/api/routes/ai.py`, `backend/app/infrastructure/db/repositories/question_repository.py`, `frontend/src/views/HomeView.vue`, `frontend/src/views/PracticeViewV1.vue`, `frontend/src/api/ai.js`, `frontend/src/locales/*`, `fpk/easy-exam/*`。

### [2026-10-01] v1.0.11: 学习看板重塑、学习计划配额化、错题双模切换、拖拽导入与弹窗互斥
- **触发背景**：用户反馈：1. 学习计划选择 1 天目标时死板锁定为 15 题（硬编码时长整除导致）；2. 学习看板单列无限纵向堆叠、缺乏重点与行动引导；3. 错题展开卡片过大过占空间，需要紧凑高效查看；4. 题库导入缺少文件拖拽交互；5. 首页配置与工具模态弹窗可同时开启并堆叠重叠。
- **核心决策**：
  1. **学习计划算法解绑与多维配额支持**：解除每日题量与 `minutes // 2` 的单一硬编码绑定，支持 `questions_per_day` 显式配额（15/30/50/100/全部）或时长预算，目标天数为 1 时支持单日极速冲刺全部题目；后端领域层、服务层与路由统一透传 `questions_per_day`；
  2. **学习看板重塑为行动第一的工作区**：顶部设立“今日智能学习任务”Hero 行动发射台与 `▶ 立即开始今日计划` 主行动按钮，内嵌参数调优栏；下方采用响应式双栏工作区（左侧日程时间线，右侧薄弱考点与提分推荐）；底部基线对比改为可折叠卡片，彻底消灭纵向失焦滚动；
  3. **错题斩杀本双模态视图与持久化**：新增“紧凑列表”与“展开卡片”模式切换按钮，紧凑模式下单行呈现题型、题库、截断题干、错误统计与一键操作，极大提升信息扫描密度；偏好自动持久化至 `localStorage`；
  4. **全格式拖拽 Dropzone 交互**：支持直接拖拽 `.xlsx`、`.csv`、`.json`、`.txt`、`.md`、`.pdf` 文件入上传卡片，支持悬停高亮、即时格式校验、文件信息展示与一键更换；
  5. **首页模态弹窗全局互斥排他机制**：在 `HomeView.vue` 引入 `closeAllModals()` 状态机调度，打开任一工具弹窗（AI配置、草稿箱、考试蓝图、个人资产、创建题库等）强制自动清理并关闭既有其他弹窗，彻底杜绝多弹窗重叠。
- **对应 SPEC 章节**：SPEC.md 核心刷题、错题本与学习计划章节。
- **影响范围**：`backend/app/domain/learning/study_plan.py`, `backend/app/application/learning_service.py`, `backend/app/api/routes/learning.py`, `frontend/src/views/LearningView.vue`, `frontend/src/views/MistakesView.vue`, `frontend/src/views/ImportView.vue`, `frontend/src/views/HomeView.vue`, `frontend/src/locales/*`, `fpk/easy-exam/*`。

### [2026-09-30] 第二轮对抗性审查与安全漏洞加固 (ADV2-001 ~ ADV2-007)
- **触发背景**：对全项目进行第二轮深度对抗性审查（涵盖模考旁路版本泄露、只读成员越权写入/重判/解冲突、FSRS 僵尸会话泄漏、多租户题目斩杀嗅探、刷题摘要统计口径以及跨平台与版本对齐）。
- **核心决策**：
  1. **版本列表模考动态脱敏**：在 `QuestionRepository.list_versions` 中接入 `_get_active_exam_question_ids`，杜绝考生通过历史版本列表端点窃取正在进行的模考题目标准答案与官方解析；
  2. **严格收紧题目版本与历史重判权限**：`create_next_version`、`regrade_question_history` 和 `resolve_conflict` 统一要求题库角色为 `ADMIN` 或 `EDITOR`，杜绝只读普通成员 `MEMBER` 越权修改题目、重判全库作答或解决冲突；
  3. **单题复习会话闭环完结**：`PracticeService.review_answer` 在单题作答提交后立即调用 `complete_session` 关闭会话，杜绝产生未关闭的僵尸会话；
  4. **斩杀多租户鉴权与信息隔离**：`kill` 必须校验当前用户对目标题目所属题库的成员资格，`list_killed` 限定仅列出当前用户有权访问的题库内的题目，杜绝非授权租户嗅探私有题目的题干和题型；
  5. **刷题摘要剥离主观题**：`summary` 查询显式排除主观题型 `UPPER(qv.type) NOT IN ('ESSAY', 'SHORT_ANSWER', 'SUBJECTIVE')` 并限定租户所属题库，防止非客观作答稀释正确率；
  6. **Windows 平台子进程 UTF-8 声明**：`system.py` 与 `setup-hooks.py` 中的 `subprocess.run(text=True)` 统一补齐 `encoding="utf-8", errors="replace"`；
  7. **前端包版本同步**：`frontend/package.json` 中的版本号由 `1.0.0` 推进同步至 `1.0.8`，彻底消除交付清单间的版本漂移。
- **对应 SPEC 章节**：SPEC.md 第 2.1、2.2、3.1、3.2、5 节。
- **影响范围**：`backend/app/infrastructure/db/repositories/question_repository.py`, `backend/app/infrastructure/db/repositories/practice_repository.py`, `backend/app/application/practice_service.py`, `backend/app/api/routes/system.py`, `scripts/setup-hooks.py`, `frontend/package.json`。

### [2026-09-30] 全面修复对抗性审查 14 处规范不一致与安全/数据完整性缺陷
- **触发背景**：对需求文档（SPEC.md）与既有代码进行深度对抗性静态与动态审计，审查出模考防泄题、会话超时硬判定、FSRS/错题开关语义隔离、导入难度与置信度归一化、学习指标计算口径、题库元数据完整性与草稿防篡改等 14 处不一致与缺口。
- **核心决策**：
  1. **模考防作弊动态脱敏**：在 `QuestionRepository` 查询层检查当前用户是否存在活跃未完成模考会话，若是则动态清空标准答案与官方解析，防止通过普通题目详情或列表接口泄题；
  2. **模考 FSRS 与错题隔离**：模考会话单题提交禁止推进 `fsrs_cards` 复习调度，并严格遵循会话 `record_mistakes` 开关；
  3. **服务端硬限时**：`PracticeService` 引入 `_check_exam_timeout` 校验（限时 + 60s 宽限），超时严格拒绝作答与草稿同步（HTTP 409），终结纯前端倒计时漏洞；
  4. **导入健壮性**：表格导入修复 1~5 难度离散映射，缺失/无法识别规范映射为 0（未分级）；PDF 导入对 `UNCERTAIN` 置信度题目强制拒绝直接批量入库，收敛至校对草稿箱；
  5. **学习趋势指标科学收敛**：弱项统计限定题目最新版本号 `MAX(version_number)`；到期复习统计排除已斩杀题目；学习完成率仅统计 `s.mode = 'FSRS'`；客观正确率基线完全剥离主观题；
  6. **题库元数据安全与完整性**：章节与标签补全修改与删除 REST 路由，施加 ADMIN/EDITOR 权限校验与循环父级检查；
  7. **草稿防篡改**：会话草稿严格校验只接受会话快照内题目 ID，并限制 `current_index` 与 `time_spent` 合法范围。
- **对应 SPEC 章节**：SPEC.md 第 2.2、3.2、4.1、5、8 节。
- **影响范围**：`backend/app/infrastructure/db/repositories/*`, `backend/app/application/practice_service.py`, `backend/app/infrastructure/importers/*`, `backend/app/api/routes/banks.py`, `backend/legacy/services/__init__.py`。

### [2026-09-28] 前端全站视觉与交互深度重构：落地工作台侧边栏、Cmd+K 指令面板、全仓去 Emoji (v1.0.7)
- **触发背景**：用户反馈单纯的 CSS 颜色替换仅是“换了个主题”，要求深入底层 DOM、宏观信息架构与组件触感进行真正的结构性重新设计。
- **核心决策**：
  1. **全局工作台 Shell**：新增左侧高密度工作台侧边栏 (`AppSidebar.vue`) 与移动端底部沉浸条 (`MobileNav.vue`)，集成全局 `Ctrl/Cmd + K` 快捷指令面板 (`CommandPalette.vue`)；
  2. **去 Emoji 化与专业矢量系统**：引入内联矢量线框图标组件 (`LinearIcon.vue`)，彻底清除页面玩具感 Emoji，建立统一 1.8 细线微质感；
  3. **资产大厅重塑**：未完成会话改造成类终端恢复 HUD，题库展示升级为高密度资产列表与健康度指示；
  4. **做题与模考沉浸式工作台**：选项注入 `120ms` 物理阻尼与微发光按压反馈，FSRS 评级标注记忆留存预测间隔（`+10m`, `+1d`, `+3d`, `+7d`）；
  5. **门禁与实机交付**：13 项 Playwright 真 Chrome E2E 测试全绿，版本号推进至 `1.0.7` 并成功安装上线飞牛 NAS。
- **对应 SPEC 章节**：SPEC.md 界面与交互规范。
- **影响范围**：`frontend/src/components/*`, `frontend/src/views/*`, `frontend/src/features/exam/*`, `frontend/src/style.css`, `fpk/easy-exam/*`。

### [2026-09-22] 仓库脚手架初始化
- **触发背景**：创建 Vibe Coding Starter 通用规范模板。
- **核心决策**：确立 SDD（规范驱动）+ 双层门禁 + 自进化避坑清单为核心工作流。
- **对应 SPEC 章节**：全文档初始化。
- **影响范围**：全局。

### [2026-09-22] 飞牛刷题系统 (fn-exam) 全案架构确立与落盘
- **触发背景**：用户要求为飞牛 NAS (fnOS) 打造一款对标微信小程序“考试宝”的自托管刷题系统，吸取 12 个开源竞品源码精华，坚决剔除其臃肿与缺陷。
- **核心决策**：
  1. **技术栈基座**：采用 FastAPI + Vue 3 + SQLite WAL 极轻量单镜像（常驻闲置内存 50MB~100MB），零外部重型数据库依赖；
  2. **交互体验**：1:1 对标微信小程序「考试宝」，实现选项秒判变色、左右防误触手势切题、底部 5 色网格抽屉答题卡、全真模考诊断报告；
  3. **数据韧性**：采用 `localStorage` 0ms 实时草稿暂存 + 切题与防抖 5 秒双层同步，确保设备休眠、断网或刷新 100% 断点自动续答；
  4. **抗遗忘与错因归因**：直接移植纯 Python 零依赖 FSRS-5 算法计算最佳复习周期；建立 6 级错因分类，实行“连续答对 2 次出库斩杀”规则；
  5. **AI 助教与题库导入解耦**：做错题目自动打包题境上下文注入 Prompt，支持 SSE 打字机流式追问与离线友好降级；题库导入采用正则状态机+CSV+JSON 四级流水线，绝不捆绑几十 GB 的深度学习 OCR，保证 NAS 镜像小巧稳定。
- **对应 SPEC 章节**：SPEC.md 第 1~6 节与 `docs/superpowers/specs/2026-09-22-fn-exam-design.md`。
- **影响范围**：系统全量模块（`backend/`, `frontend/`, `tests/`, `Dockerfile`, `docker-compose.yml`）。

### [2026-09-23] 品牌合规化更名：全面更名为「易考宝」(EasyExam)
- **触发背景**：用户反馈第三方应用不能以“飞牛”或“fnOS”作为应用主名称前缀，否则会因商标侵权或官方混淆导致无法上架飞牛应用中心（或第三方 NAS 应用市场）。
- **核心决策**：
  1. 应用中文名定名为「易考宝」，副标题为「私有云刷题与错题消灭系统」；
  2. 英文服务标识、Docker 容器与镜像定为 `easy-exam` (`ailm32442/easy-exam:latest`)；
  3. 保留对飞牛私有云 (fnOS) 兼容性声明，但主包名与主界面彻底去官方化；
  4. 数据库向前兼容 `easyexam.db` 与 `fnexam.db`，自动兼容原有挂载数据文件。
- **对应 SPEC 章节**：SPEC.md 第 1.1 节。
- **影响范围**：`frontend/index.html`, `backend/main.py`, `backend/database.py`, `docker-compose.yml`, `Dockerfile`, `scripts/deploy_fnos.sh`, `tests/`。

### [2026-09-23] 需求主线重评估：从竞品拼接改为题目学习档案
- **触发背景**：源码调查发现原文档把多个项目能力并列拼接，AI 助教回答未持久化，多选部分得分与“已掌握”语义混用，且“考试宝”借鉴边界不清。
- **核心决策**：以题目版本为中心组织作答、错因、解释版本、联网证据、FSRS 和斩杀题库；考试宝只借鉴可观察的产品逻辑，不复制页面或闭源实现；AI/联网/用户解释全部版本化保存，标准答案独立维护。
- **对应 SPEC 章节**：SPEC.md 第 1~8 节。
- **影响范围**：需求文档、后续数据模型、AI 助教、判分器、错题/FSRS、模考、同步和权限模块；本次仅更新文档，未修改业务源码。

### [2026-09-23] 大题库与 AI 边界确认
- **触发背景**：用户进一步明确目标是考公等大题库提分系统，而不是独立 AI 聊天或必须依赖复杂配置的 RAG 产品。
- **核心决策**：采用“考试体系 + 可复用题库”、章节树 + 多知识点标签、动态提分推荐和可调整学习计划；AI 作为横向可选能力嵌入具体题目流程；无 AI、无考试蓝图时核心刷题仍可用；不可解析文档直接拒绝上传。
- **对应 SPEC 章节**：SPEC.md 第 2、5、8 节。
- **影响范围**：题库组织、学习诊断、推荐计划、AI 检索、导入校验和降级行为；本次仅更新文档，未修改业务源码。

### [2026-09-23] 判分与掌握状态拆分
- **触发背景**：旧实现把多选少选的部分得分标记为 `is_correct=true`，会错误触发错题连续答对清除。
- **核心决策**：新增 `mastery_status`（`CORRECT`、`PARTIAL`、`INCORRECT`、`UNANSWERED`）；部分得分仍计入分数，但只有 `CORRECT` 才进入掌握/错题清除链路；保留 `Scorer.evaluate` 二元接口兼容既有调用方。
- **影响范围**：`backend/services/scoring.py`、`backend/services/session_service.py`、`backend/main.py` 及后续报告统计；旧测试中把部分得分视为正确的断言需要按新需求复核。

### [2026-09-23] 模块化单体架构开始切换
- **触发背景**：旧实现把路由、业务服务、SQL 和前端状态集中在少数文件，无法支持用户隔离、题目版本和解释版本。
- **核心决策**：建立 `backend/app` 模块化单体，采用版本化 SQLite migration、自建 Repository、`/api/v1` 路由和用户级学习记录；旧入口保留为回归基线，不再承载新功能。
- **影响范围**：认证、题库/题目版本、作答尝试、错题、学习摘要、导入、AI 解释版本和新前端视图；部署入口切换到 `backend.app.main:app`。

### [2026-09-23] 旧原型实现收拢到 legacy 兼容区
- **触发背景**：新生产入口已经切换，但旧 `main.py`、Repository、数据库和服务实现仍散落在 `backend/` 根目录，容易被误当成主线继续扩展。
- **核心决策**：将旧实现移动到 `backend/legacy/`；根目录仅保留导出兼容模块，供旧回归测试和迁移工具使用；新功能只能进入 `backend/app`。
- **影响范围**：生产 Docker 不依赖旧入口；旧测试继续可运行；后续可以逐步删除兼容导出而不影响新 API。

### [2026-09-23] 分离错题事实与学习掌握状态
- **触发背景**：仅使用 `learning_records` 同时承载错题列表和掌握统计，会让首次答对、部分得分和清除状态混在一起，无法审计真实错题事实。
- **核心决策**：新增版本化迁移 `mistake_records`；作答事务同时更新错题事实、掌握状态和 FSRS。首次答对不进入错题列表，答错后可按连续完全正确次数清除。
- **影响范围**：刷题写入、错题列表、FSRS 到期列表、旧库迁移与迁移校验。

### [2026-09-23] 导入任务可审计化
- **触发背景**：导入表已存在但导入流程没有记录预检失败或成功结果，无法解释用户上传为何被拒绝或是否完整落盘。
- **核心决策**：每次文本、CSV、JSON、PDF 导入创建 `import_jobs`，以 `PENDING` → `IMPORTED` / `PRECHECK_FAILED` / `FAILED` 记录生命周期；解析失败不创建题目。
- **影响范围**：导入应用服务、PDF 可识别性预检、迁移后审计和后续前端导入历史。

### [2026-09-23] 题目跨题库复制使用新身份
- **触发背景**：同一题目内容进入不同题库时，如果复用题目主键，会把两个题库的作答、错题和 FSRS 状态错误地绑定在一起。
- **核心决策**：复制接口复制当前题目版本内容，但生成新的 `questions` 与 `question_versions` 身份；目标题库的学习状态从空白开始。
- **影响范围**：题库题目管理、权限校验和用户学习数据隔离。

### [2026-09-24] 模考结果延迟到交卷阶段计算
- **触发背景**：普通刷题可以即时反馈，但模考提交前泄露正确性会破坏考试体验；旧报告依赖会话 JSON 汇总，不能可靠统计未作答和题型/知识点。
- **核心决策**：模考提交只保存作答并返回 `feedback_available=false`；交卷从 `answer_attempts` 重算，绑定启动时蓝图版本，并在最终报告应用负分规则。
- **影响范围**：模考路由、会话字段、报告统计和蓝图迁移。

### [2026-09-24] 推荐与趋势以可解释离线规则为主
- **触发背景**：大题库提分不能依赖 AI 黑盒；原推荐只返回已有学习记录，漏掉新题，也没有用户调节入口。
- **核心决策**：推荐覆盖新题、薄弱题和 FSRS 到期题，返回原因并支持开关、数量和题型过滤；趋势从真实作答计算覆盖率、近期窗口和长期基线。
- **影响范围**：学习 Repository、领域排序、学习 API、前端学习视图；AI 离线不影响这些能力。

### [2026-09-24] 联网核查和导入预检显式记录不确定性
- **触发背景**：联网结果和重复导入如果没有版本/预检状态，用户无法区分“没有证据”和“确有依据”，也可能意外重复写题。
- **核心决策**：WEB 核查保存独立解释与证据列表，离线返回 `UNAVAILABLE`；导入先返回重复项，必须选择策略后落盘，同时支持 XLSX。
- **影响范围**：AI 解释 Repository、搜索适配器、导入应用服务、导入审计和前端 API。

### [2026-09-24] 主观题作答与客观正确率语义隔离
- **触发背景**：主观题由于缺乏客观标准答案，直接统计到会话客观正确率分母中会导致客观题正确率失真被稀释。
- **核心决策**：会话客观正确率计算严格按照客观题分母统计；主观题作答完整留痕，但客观正确率仅计算客观题；交卷前模考报告严禁泄露任何答案与解析。
- **影响范围**：`backend/app/application/practice_service.py`、`frontend/src/domain/exam.js`、`tests/test_scoring_semantics.py`。

### [2026-09-24] 闭环专项复习、模考幂等防护与真实 Chrome 物理 E2E 验收
- **触发背景**：审查发现 FSRS 到期复习与错题专项刷题未限定目标集合、斩杀题复习漏透传 `bank_id`、错因前端修改未持久化、模考提交缺乏幂等与交卷防护、旧库迁移使用弱默认密码且无首次强制改密、缺乏真实浏览器 E2E 验证。
- **核心决策**：
  1. 专项刷题（`MISTAKE`、`FSRS`、`ELIMINATION`）服务端强制题目集合限定，支持指定 `question_ids` 过滤，题目集为空时显式抛错；
  2. 练习与 FSRS 评级接口打通（`fsrs_rating` 校验评级一致性，错误强制 Again）；前端错题卡片提供错因下拉持久化接口；
  3. 斩杀题库列表透传真实 `bank_id`，卡片与工具栏提供“查漏补缺练习”启动入口，错答即时移出斩杀；
  4. 模考提交与交卷增加幂等防护，已交卷会话严禁再次提交 attempt；
  5. 旧库迁移生成高强度随机临时密码并标记 `must_change_password=1`，提供首次强制改密流；未转换孤儿题记入审计并在验证脚本中进行全量多表校验；
  6. 搭建 Playwright + Google Chrome 物理端到端自动化测试套件（覆盖注册登录、题库创建、答题与判分、斩杀与复原、错因持久化、专项刷题、FSRS 评级、模考与诊断报告等全部 9 大核心主链路），杜绝纯 Mock 假绿。
- **对应 SPEC 章节**：SPEC.md §3.2, §4.1, §4.2, §4.3, §6。
- **影响范围**：`backend/app/application/practice_service.py`、`backend/app/api/routes/`、`frontend/src/views/`、`scripts/migrate_legacy_db.py`、`frontend/tests/browser_e2e.test.js`。

### [2026-09-24] 闭环 FSRS 评级更新、专项防绕过、强改密阻断与 E2E 端口实例防串连
- **触发背景**：第二轮审查指出：相同答案再次提交携带新 rating 时底库未更新 `fsrs_rating` 与卡片调度；`start_session` 只要收到 `question_ids` 即可绕过专项队列；`must_change_password` 未在 API 依赖层面阻断业务请求且密码长度与路由声明不一致（6 位 vs 8 位）；批量入口漏掉薄弱到期题且跨题库传参静默丢失；E2E 硬编码端口可能误连残存进程。
- **核心决策**：
  1. `practice_repository.py` 的 `save_attempt` 支持在相同答案再次提交带有新 rating 时更新 `fsrs_rating`、错因，并重新调用 FSRS 算法更新 `fsrs_cards`；
  2. `practice_service.py` 的 `start_session` 先根据 `mode` 锁定专项候选题目池，再与传入的 `question_ids` 求交集，若结果为空抛出 400，从根源杜绝越权绕过；
  3. `dependencies.py` 的 `current_user` 针对 `must_change_password=1` 的用户强制拦截所有非免检路由并返回 403 `MUST_CHANGE_PASSWORD`；Pydantic 与服务层统一密码策略为至少 8 位；前端 `App.vue` 增加全屏强制改密拦截组件；
  4. `MistakesView.vue` 并发加载 `listDueMistakes`（完整覆盖无错题记录但标记薄弱的到期题），增加题库筛选下拉框，批量复习严格按目标题库打包题目，杜绝跨题库静默丢失；
  5. E2E 真实浏览器测试引入系统闲置端口动态探测与 `INSTANCE_TOKEN` 双向握手校验，杜绝测试串连外部残存服务；E2E 场景补充物理核对非默认 FSRS 评级 4 真实落盘、薄弱标记到期复习与首次登录强制改密阻断全链路。
- **对应 SPEC 章节**：SPEC.md §4.1, §4.2, §4.3, §4.4。
- **影响范围**：`backend/app/application/practice_service.py`、`backend/app/infrastructure/db/repositories/practice_repository.py`、`backend/app/dependencies.py`、`backend/app/api/routes/auth.py`、`backend/app/api/routes/system.py`、`frontend/src/App.vue`、`frontend/src/views/MistakesView.vue`、`frontend/tests/browser_e2e.test.js`、`frontend/tests/exam.test.js`。

### [2026-09-24] 历史作答无快照安全策略：防虚假基准伪造与已调度卡片防二次叠加
- **触发背景**：审查进一步指出，存量升级与旧库迁移若直接将“当前 FSRS 卡片”回填为历史作答的 `card_snapshot_json`，会伪造作答前快照；若旧作答此前已触发过调度，用户后续修改评分时会以当前卡片为基线再次调度，导致二次叠加调度。
- **核心决策**：
  1. 数据库升级脚本（`connection.py`）与旧库迁移脚本（`migrate_legacy_db.py`）严禁把当前卡片作为历史快照回填，历史存量作答真实保持 `card_snapshot_json = NULL`；
  2. `practice_repository.py` 严格区分两类存量无快照记录：
     - 若作答记录在历史上已完成过 FSRS 调度（`existing["fsrs_rating"]` 已存在或卡片 `last_review_at` 与作答时间吻合），用户修改评分时仅更新作答记录本身的 `fsrs_rating`，严禁在卡片上二次叠加调度，亦严禁重置为新卡，彻底冻结并保护卡片已有复习状态；
     - 若作答记录在历史上从未调度过（`fsrs_rating` 为空且卡片未被其更新），用户首次评级时方以当前卡片为基准初次调度，并即刻回填基准快照；
  3. 完善双向专项测试：既覆盖“未调度旧作答首次评级正常流转”，又严格覆盖“已调度旧作答修改评级卡片冻结防二次叠加”。
- **对应 SPEC 章节**：SPEC.md §4.2。
- **影响范围**：`backend/app/infrastructure/db/connection.py`、`backend/app/infrastructure/db/repositories/practice_repository.py`、`scripts/migrate_legacy_db.py`、`tests/test_v1_architecture.py`、`tests/test_legacy_migration.py`。

### [2026-09-24] AntiGravity 文档分工、需求追踪与外部源码复用审计
- **触发背景**：代码实现交由 AntiGravity 后，单独一份 SPEC 或一句提示词不足以保证它区分已确认需求、当前代码事实、外部源码复用与待实施工作；README 还把候选参考能力写成了“已经吸收”，旧计划引用重构前路径。
- **核心决策**：`SPEC.md` 只记录已确认产品要求；实现状态放入需求追踪矩阵；第三方源码与许可选择集中记录在开源审计；一次只按用户点名的分阶段计划执行；长期代理规则放 `AGENTS.md`，协作过程/报告模板放专门 workflow 与 AntiGravity skill。
- **源码复用原则**：适配且许可兼容时优先选择性复用成熟代码；按仓库、commit、源文件、目标文件和 NOTICE 义务留痕；行为参考不可表述为代码移植；AGPL/GPL、无许可及含混许可代码未获决定前不直接复制进本 MIT 项目。
- **影响范围**：`AGENTS.md`、`SPEC.md`、`README.md`、`TESTING.md`、`docs/REQUIREMENTS_TRACEABILITY.md`、`docs/research/OSS_REUSE_AUDIT.md`、`docs/ANTIGRAVITY_WORKFLOW.md` 与各批次 implementation plan。

### [2026-09-24] 题库批量导入单事务原子性与表格列映射预览（复用 Exameow 算法与 EXAM-MASTER 事务模式）
- **触发背景**：批量导入此前为每道题单独提交事务，中途失败会导致部分题目残留；表格导入仅支持极少别名，无法自适应复杂表头或提供用户手动列映射预览修正。
- **核心决策**：
  1. 在 `question_repository.py` 引入 `batch_create_or_update_questions` 单一数据库事务，与 `import_service.py` 统一批处理；中途任何写入失败整体回滚，0 题目残留，`import_jobs` 准确审计为 `FAILED`；
  2. 移植 Exameow（Apache-2.0）的表头别名识别、组合选项分隔符提取、前缀剥离与难度归一化算法至 `spreadsheet_importer.py`，并在代码头保留 Apache-2.0 归属；统一在 Python 后端解析以防多端重复解析器；
  3. 提供 `POST /api/v1/imports/banks/{bank_id}/preview-file` 接口与前端 `ImportView.vue` 可视化列映射面板，允许用户先预览前 5 行采样数据、检查缺失字段并手动修正各列绑定后再确认导入；
  4. 真实浏览器 E2E 全流程覆盖“列映射预览 -> 用户确认导入 -> 重复题预检拦截”。
- **对应 SPEC 章节**：SPEC.md §5, §8。
- **影响范围**：`backend/app/infrastructure/importers/spreadsheet_importer.py`、`backend/app/infrastructure/db/repositories/question_repository.py`、`backend/app/application/import_service.py`、`backend/app/api/routes/imports.py`、`frontend/src/views/ImportView.vue`、`frontend/src/api/imports.js`、`frontend/tests/browser_e2e.test.js`、`tests/test_v1_import.py`、`tests/test_v1_pdf_import.py`。

### [2026-09-24] 文档体系按通用底座与领域扩展重新分层
- **触发背景**：本地已经积累了大量 EasyExam 实战规则，但通用 Vibe Coding Starter 的数据安全、可靠性、Multi-Agent、模板和 SDD Skill 没有形成统一入口；文档之间存在规则重复，容易把实现状态、产品需求和测试证据混在一起。
- **核心决策**：采用“入口宪法（AGENTS）—产品真理源（SPEC）—执行证据（追踪矩阵/TESTING）—决策与研究（DECISIONS/research）—按需扩展（optional/templates）”五层结构。通用规则进入可复制底座，EasyExam 的迁移、FSRS、幂等、导入和领域红线保留在本地扩展，不把领域细节泛化进 Starter。
- **影响范围**：`AGENTS.md`、`README.md`、`TESTING.md`、`SPEC.md` 的维护约定、`docs/REQUIREMENTS_TRACEABILITY.md`、`docs/ANTIGRAVITY_WORKFLOW.md`、`docs/optional/`、`docs/templates/`、`.agents/skills/sdd-implementation/`。

### [2026-09-24] 学习计划中未分级题目的难度筛选
- **触发背景**：题库中可能存在未显式标注难度的题目，用户确认了在学习计划按难度筛选时的处理规则。
- **核心决策**：难度筛选只使用题目显式标注的 1–5 级；未分级题在未启用具体难度筛选时仍可参与推荐，启用具体难度筛选时排除。不得按默认中等处理，也不得根据单用户或跨用户作答表现推断题目难度。
- **对应 SPEC 章节**：`SPEC.md` §8。
- **影响范围**：学习推荐/筛选逻辑、相关测试和用户可见筛选状态。

### [2026-09-27] FPK 离线镜像必须在 install_init/upgrade_init 阶段加载

- **触发背景**：`easy-exam-1.0.1` / `1.0.2` 在 fnOS 应用中心手动安装时每次都在最后一步回滚，报 `easy-exam Error pull access denied for ailm32442/easy-exam`。排查发现应用中心会在 `install_init` / `install_callback` 之前就用包内 `target/` 把 docker project 拉起来；此时本地 daemon 尚无随包镜像，compose 按 `pull_policy: if_not_present` 回退拉取从未发布的 Docker Hub tag，被拒后整体回滚。此前 `1.0.1` 曾成功一次，是因为 `1.0.0` 时期 `docker load` 的同名镜像仍残留在本地。
- **核心决策**：
  1. 把 `docker load` 随包镜像的逻辑前移到 `cmd/install_init` 与 `cmd/upgrade_init`——这是能抢在 compose 之前的最早钩子；遍历 `TRIM_APPDEST/images`、`TRIM_PKGINST_TEMP_DIR[/app]/images`、`TRIM_TEMP_TPKFILE[/app]/images` 全部暂存位置，加载失败只告警不退出（避免 setup 环境缺 docker 时阻断安装）。
  2. `cmd/main start` 在 `docker compose up` 前再加载一次 `target/images`；`install_callback` / `upgrade_callback` 保留加载逻辑作兜底。
  3. 版本号单一来源定为 `fpk/easy-exam/manifest` 的 `version`，`app/docker/docker-compose.yaml` 的镜像 tag 与随包镜像 tag 必须同步推进，由 `tests/test_fpk_packaging.py` 强制校验。
- **对应 SPEC 章节**：无（平台部署约束，不改变产品行为）。
- **影响范围**：`fpk/easy-exam/cmd/install_init`、`cmd/upgrade_init`、`cmd/main`、`app/docker/docker-compose.yaml`、`manifest`、`docs/FNOS_FPK_GUIDE.md`（新增 3.3 节）。
- **验证**：fnOS 6.18 实机（`192.168.x.x`）安装成功不再回滚；容器起于 3000 端口，`/api/v1/health` 200；`stop`/`start` 后已注册账号仍可登录，`var/.env` 主密钥 md5 不变。

### [2026-09-27] 移动端顶栏保留换行而非强制单行

- **触发背景**：`2026-09-25-ergonomics-ui-overhaul.md` 与 `AGENTS.md` 避坑第 10 条要求触屏端顶栏"单行紧凑折叠"。2026-09-27 实测 390x844 视口下 `.compact-header` 高度为 82.8px，仍为两行。
- **核心决策**：保留 `.compact-header { flex-wrap: wrap !important }` 的两行布局，不强制单行。原因是顶栏在移动端需同时容纳"返回 + 标题 + 题型徽标 + 进度徽标 + 交卷 + 提示 + ⋯"，强制单行会把按钮压缩到不足 42px 的触控目标下限，违反工效学整改的核心目标（可达性与防误触）。折中结果：顶栏由 175.8px 降至 82.8px，题干与全部选项落在首屏内（`capture_mobile.mjs` 实测），底栏 57px；"单行"这一具体形式未满足，但首屏信息密度与触控达标这两个真实目标达成。
- **对应 SPEC 章节**：无（交互工效学，不改变产品行为）。
- **影响范围**：`frontend/src/views/PracticeViewV1.vue`（`.compact-header` 移动端样式）、`frontend/tests/capture_mobile.mjs`（度量口径）、`docs/superpowers/plans/2026-09-25-ergonomics-ui-overhaul.md`（DoD 复核）。
- **遗留**：`AGENTS.md` 避坑第 10 条的"顶栏必须单行紧凑折叠"与实际实现不一致。保留该条款为方向性目标，但验收时以"顶栏高度不侵占首屏核心内容 + 触控目标 ≥42px"为实际判据，不单独以行数判定。

### [2026-09-27] 从 vibe-coding-starter 吸收四条通用工程规则

- **触发背景**：对比 `vibe-coding-starter` 模板项目（独立通读，非文件树 diff）与易考宝现有规范，发现四条易考宝缺失的通用规则；其中两条直接对应本项目已发生的真实事故。
- **核心决策**：
  1. **移植 `tests/visual_smoke/`**（白屏判据 + 四道正身信号）。保留正身信号层，导航层按本项目实际改写——易考宝 SPA **没有 URL 路由**（`App.vue` 用响应式 state 切视图），starter 原版的 `#/route` 遍历在此无效。逃生门保留为 `--allow-missing-host` flag 而非拆闸门。已完成红色实证：一个有内容的网关占位页（纯颜色判据会放行）被正身信号正确拒绝。
  2. **TESTING 铁律 6「门禁即证据」**：一条没红过的门禁视为不存在；新增门禁必须附变异实证。直接对应本项目 `mobile_interaction_suite.mjs` 中那条自引入起就不可能通过的断言。
  3. **TESTING 铁律 5「规范即测试」**：把"以后还会有人犯"的规范写成扫源码的终身守卫；守卫自带红/绿样本自证；白名单按内容签名匹配而非行号。
  4. **RCA 动手前先 census**：清单类任务先全仓重扫，审计抽样结论视为下限。
  5. **AGENTS 裁定清单（Rulings）**：授权整段自动流程时收尾必须披露 `裁定 → 判错的代价`，禁止静默裁定。
  6. **AGENTS UI 模糊评价五维清单**：把"丑/难看"转成改/不改选择题。
- **不吸收**：`templates/ci.yml`（本项目已有且更完整）、`scripts/setup-hooks.py`（已装且逐字节同源）、AGENTS 避坑 9–12（AntiGravity-OSS 专有场景，本项目 §2 覆盖更严谨）、`EXECUTION/REVIEWING/ARCHITECTURE`（本项目已有且 `REVIEWING.md` 更强）。
- **顺带修复上游**：starter 的 `scripts/checkpoint.py` 有两个真 bug（`restore` 用 `git checkout <sha> -- .` 会遗留新增文件；"安全 stash"从不告知也不恢复），已在 starter 仓库修复并补 `tests/test_checkpoint.py`，两测试均经红色实证。
- **对应 SPEC 章节**：无（工程规范，不改变产品行为）。
- **影响范围**：`tests/visual_smoke/`、`TESTING.md`、`AGENTS.md`、`DECISIONS.md`。

### [2026-09-27] 文档体系自洽性修复：顶栏规则去硬化、skipped 口径、移动端门禁转真

- **触发背景**：用户追问"文档体系是否真的自洽"。逐项实测后确认**不自洽**，发现 5 处实质矛盾（此前"文档门禁全清"只证明了链接可解析与空白干净，不能推出自洽）。
- **核心决策**：
  1. **顶栏规则去硬化**：`AGENTS.md` 避坑第 10 条原写"必须严格单行（≤44px）"，实测两行为 82.8px。溯源发现上游 starter 原文是**"建议 ≤ 44px"**，传入本项目时被硬化成强制值，且"单行"只是达成"首屏密度"的手段。现改为：目标 ≤44px 为方向性建议，验收以「不折行撑高侵占首屏核心内容」+「触控目标 ≥42px」为准；元素过多致单行必然压垮触控目标时，取触控可达性。`TESTING.md` 铁律 5 同步对齐。
  2. **skipped 口径分层**（新增避坑第 16 条）：**环境性跳过**（外部不可达、无凭证）不阻断收敛判定但须逐项登记；**断言性跳过**（目标用例未真正执行）仍阻断。此前 `AGENTS.md`/`TESTING.md` 笼统要求 `skipped=0`，与当前 `skipped=1` 之间缺一条缝。
  3. **移动端门禁转为真门禁**：`mobile_interaction_suite.mjs` 实为**三处叠加的脚本缺陷**（进度文案匹配错、前进按钮假设错、滑动用鼠标事件而处理器读 touch 事件），非产品缺陷。全部修复并完成红色实证（故意偏移期望值 → 断言变红 → 还原全绿），11 项检查全通过。按铁律 7，此前它根本"不算门禁"。
  4. **文档地图补全与纠错**：修复 3 处不可定位路径（`.fpk` 反引号误解析、两个 AntiGravity 提示词缺 `docs/` 前缀）；补录 `specs/` 与 `templates/ci.yml`，并标注后者**当前未激活**（无 `.github/`，从未运行）。
  5. **清除单次实测数字**：`2026-09-25-frontend-ui-redesign.md` 中的 `62.68 kB` 精确字节值改为量级（此前已在 `TESTING.md` 处理同类问题，此处遗漏）。
- **对应 SPEC 章节**：无（工程规范与测试门禁，不改变产品行为）。
- **影响范围**：`AGENTS.md`、`TESTING.md`、`README.md`、`docs/REQUIREMENTS_TRACEABILITY.md`、`docs/superpowers/plans/2026-09-25-frontend-ui-redesign.md`、`frontend/tests/mobile_interaction_suite.mjs`。

### [2026-10-01] 吸收母版 Starter 门禁规范、根级全栈国际化 (i18n) 与 AI 多语言穿透

- **触发背景**：从 `vibe-coding-starter` 模板项目吸收通用工程规范与资产，强化自动化测试防篡改审计、硬编码物理绝对路径扫描门禁、社区资产（FAQ/赞助双语化），并在易考宝落地端到端全栈国际化及 AI 助教语言穿透能力。
- **核心决策**：
  1. **工程门禁与防偷懒防御**：引入 `scripts/guard_test_tampering.py`（对 assert/expect 关键字删除修改做 pre-commit 物理审计）与 `scripts/scan_hardcoded_paths.py`（扫描并禁止写死盘符与用户物理路径）；在 `scripts/setup-hooks.py` 中跨平台级联守卫、前端单元测试及后端单元测试。
  2. **根级全栈国际化 (i18n)**：前端建立轻量响应式国际化体系（`useLocale`、`localePreference`、`zh-CN.js`、`en-US.js`），支持双向键值与动态插槽严格对齐测试（`locale.test.js`）；API 请求层（`client.js`）自动向后端透传 `Accept-Language` 请求头。
  3. **AI 助教多语言穿透**：FastAPI 后端路由（`routes/ai.py`）、应用层（`ai_tutor_service.py`）及服务层（`ai_service.py`）解析并穿透 `target_lang` 参数，根据语言自动切换英文/中文 System Prompt、核心指导原则与结构化输出板块。
  4. **真实浏览器 E2E 闭环**：在 `browser_e2e.test.js` 中新增第 13 场景（Scenario 13），在独立 Chrome 实例中完整验证根节点 `lang` 属性更新、localStorage 持久化、页面重载零闪烁、主题切换联动与基线还原。
  5. **fnOS 应用包 (FPK) 自动化构建**：打包脚本 `scripts/build_fpk.py` 成功将更新后的前端产物及元数据构建为 `dist/easy-exam-1.0.9.fpk`。
- **对应 SPEC 章节**：SPEC.md §6, §8。
- **影响范围**：`scripts/`、`tests/test_guard_checks.py`、`frontend/src/locales/`、`frontend/src/composables/`、`frontend/src/design/`、`frontend/src/components/`、`backend/app/api/routes/ai.py`、`backend/legacy/services/ai_service.py`、`frontend/tests/browser_e2e.test.js`、`DECISIONS.md`、`SPEC.md`。


### [2026-11-11] 四套配色族替代旧多主题系统，旧配色标识自动归并

- **触发背景**：用户确认产品只保留四套主题（编辑部 Editorial、Gruvbox、Everforest、Catppuccin），替换此前按单一色名堆叠的多主题实现。旧版本已把配色 id 写入本机存储，直接改枚举会让老用户启动后被静默重置为默认色。
- **核心决策**：
  1. **配色族与明暗解耦**：四套配色族各自提供同一套语义 token 契约；`mode`（light/dark/system）只选择该族内的明暗取值，配色与模式分开持久化，切换任一维度不覆盖另一维度。
  2. **旧 id 归并而非重置**：`blue-grey`/`mist` → `editorial`，`ocean`/`amethyst`/`mocha` → `catppuccin`，`rose`/`amber` → `gruvbox`，`forest` → `everforest`；未识别的值回落 `editorial`。
  3. **强调色按实际表面推导前景**：自定义强调色先归一化，再针对当前配色族的 page/card/subtle 表面逐步混合，直到正文对比度 ≥ 4.5:1；hover/active 各自重新计算前景，避免沿用基色前景造成同色不可读。
  4. **门禁按 token 而非截图**：`frontend/tests/theme.test.js` 断言四族 × 明暗的 AA 对比度、`style.css` 每族明暗块存在、`PALETTE_SURFACES` 与 CSS 同步、最小字号与强调色可读性。截图式“四主题全视口审美验收”不在本决策的已验证范围内。
- **对应 SPEC 章节**：SPEC.md §8「验收基线」。
- **影响范围**：`frontend/src/design/themePreference.js`、`frontend/src/composables/useTheme.js`、`frontend/src/views/SettingsView.vue`、`frontend/src/style.css`、`frontend/src/locales/*`、`frontend/tests/theme.test.js`、`frontend/tests/components/settings_view.test.js`。

### [2026-11-11] 批量题库维护：整批原子、双端权限与归档软删除

- **触发背景**：用户确认题库需要批量维护能力，避免逐题修改章节、标签或跨库搬运；同时必须满足既有领域红线（复制生成新身份、进行中模考不可改题、普通成员不得编辑）。批量接口天然容易产生“部分成功”，因此把原子性作为核心约束而不是事后补丁。
- **核心决策**：
  1. **单一批量端点**：`POST /api/v1/banks/{bank_id}/questions/batch`，`operation` 仅接受 `chapter`、`add_tags`、`remove_tags`、`move`、`copy`、`archive`、`restore`；去重后单次最多 500 道题。
  2. **先全量校验，再单事务写入**：在第一次写入前校验源题库编辑权、目标题库编辑权、目标存在性、章节归属、题目归属、活动模考锁定与归档状态；任一项失败即整批回滚，不留下部分更新。
  3. **双端权限**：`move`/`copy` 同时要求源题库与目标题库的 `ADMIN`/`EDITOR` 角色；普通成员 `MEMBER` 一律 403。
  4. **元数据不推版本**：批量章节与标签直接更新当前最新版本行，不生成新题目版本，避免把“归章/打标”误记成内容变更；标签同时同步到 `question_tag_items`。
  5. **移动与复制的身份语义**：`move` 保留题目 id，章节在目标题库中按名称匹配，缺失时自动创建同名章节，源题无章节则保持无章节；`copy` 复用既有复制路径生成新题目与初始版本，学习状态从空白开始。
  6. **归档是软删除**：`archive` 置 `is_deleted=1`，题目从内容列表、普通刷题与专项目标集中隐藏，并禁止编辑及章节/标签/移动/复制等批量操作；重复归档保持幂等，`restore` 恢复。
  7. **审计留痕**：每次批量写入 `audit_logs`，action 为 `BANK_QUESTIONS_BATCH`，记录操作、题目 id、章节/标签/目标题库参数。
  8. **前端只暴露可执行项**：批量栏仅对编辑者显示；所选行含模考锁定时整体禁用并说明原因；归档需确认；375px 下批量栏不得横向溢出。
- **对应 SPEC 章节**：SPEC.md §2.0.1「题库组织」。
- **影响范围**：`backend/app/api/routes/banks.py`、`backend/app/application/bank_service.py`、`backend/app/infrastructure/db/repositories/question_repository.py`、`frontend/src/api/banks.js`、`frontend/src/domain/bankManage.js`、`frontend/src/views/BankManageView.vue`、`frontend/src/locales/*`、`tests/test_bank_batch_operations.py`、`frontend/tests/bank_manage.test.js`、`frontend/tests/bank_batch_e2e.test.js`。

### [2026-11-10] Editorial Precision 全产品 UI 替换，同步更新旧 UI 断言

- **触发背景**：按已确认的 Editorial Precision 原型与设计文档重写产品页面与全局外壳。旧组件测试断言的“更多菜单”结构（`mobile-nav-more-popup`、`mobile-dropdown-menu`）已随移动导航与练习顶栏的信息架构调整而消失，属于设计被正确替换，不是业务回归。
- **核心决策**：
  1. 移动导航以 Today / 题库 / 复习 / 模考 / 资料 五个主入口替代“更多”弹层；测试改为验证五个入口与 `navigate` 事件。
  2. 练习页的更多菜单收敛为编辑题目与斩杀题目两项，帮助与答题卡提升为独立工具；测试改为验证新菜单结构与完成入口。
  3. 主题测试从旧八色调色板改为 Editorial Precision 的纸色/墨色/状态色对比度断言，并修正浅色与深色三级文字的实际 AA 对比度。
  4. 品牌字标“易”为 `aria-hidden` 视觉标记，不参与可见文案本地化扫描。
- **对应 SPEC 章节**：无（UI 呈现层重构，不改变业务语义）。
- **影响范围**：`frontend/src/components/MobileNav.vue`、`frontend/src/views/PracticeViewV1.vue`、`frontend/src/style.css`、`frontend/tests/components/`、`frontend/tests/theme.test.js`、`frontend/tests/locale.test.js`。

### [2026-11-10] 真实浏览器 E2E 对齐路由化 Editorial Precision 外壳

- **触发背景**：旧 `browser_e2e.test.js` 与 `bank_manage_e2e.test.js` 仍驱动已删除的 `.home-page`、`.bank-card`、`.mistakes-page`、`.exam-page` 与旧八色调色板。设计替换后这些选择器不再存在，测试超时属于表现层断言过期，不是业务回归。
- **核心决策**：
  1. 保留原有用例意图（注册、建库、练习、错题与 FSRS、斩杀、模考、诊断、导入、冲突、强制改密、双语主题、响应式），按当前路由与 Editorial DOM 重写选择器。
  2. 题库管理用例改为验证新的高密度表格：搜索、题型筛选、行内编辑、活动模考只读锁与 375px 布局；删除对已废弃手风琴与卡片结构的断言。
  3. 主题用例改为验证 Editorial 纸色/墨色下的实际控件对比度，不再验证已移除的自定义主题系统。
  4. 复习到期列表的薄弱标记读取后端真实字段 `is_weak_flagged`（同时兼容 `is_weak`），修复列表展示遗漏。
- **对应 SPEC 章节**：无（测试与展示层修复，不改变业务语义）。
- **影响范围**：`frontend/tests/browser_e2e.test.js`、`frontend/tests/bank_manage_e2e.test.js`、`frontend/src/views/ReviewView.vue`。

### [2026-11-10] 真实浏览器验收暴露的展示层缺陷修复

- **触发背景**：按 Editorial Precision 原型逐页做真实浏览器截图验收，发现三处只在真实 UI 中可见的问题：题库详情路由未传 `bankId` 导致页面永久停在“读取中”；练习选项在已选/正确/错误状态下选项字母与填充色同色而不可见；英文计数文案出现 “1 mistakes / 1 questions scheduled”。
- **核心决策**：
  1. `banks/:bankId` 路由启用 `props: true`，把路由参数传给 `BankDetailView` 声明的 `bankId` prop；这是路由接线遗漏，不改变业务接口。
  2. 删除 `PracticeViewV1` 内与全局样式冲突的 `.opt.is-selected/correct/wrong .opt-key` 颜色覆盖，让全局样式统一控制选项底色与前景色，避免同色不可读。
  3. 英文计数改为中性标签（`Mistakes: {count}`、`Questions: {count}`），不引入复数规则；同步更新运行时字典与 JSON 快照。
  4. 题库详情题目序号改为当前列表的两位序号，不再直接展示内部题目 ID 造成折行。
- **对应 SPEC 章节**：无（展示层缺陷修复，不改变业务语义）。
- **影响范围**：`frontend/src/router/index.js`、`frontend/src/views/BankDetailView.vue`、`frontend/src/views/PracticeViewV1.vue`、`frontend/src/locales/ep-en-US.js`、`frontend/src/locales/en-US.json`。

### [2026-11-12] W1-4 外壳账户入口统一：单一账户菜单 + 移动端「更多」

- **触发背景**：外壳审计发现顶栏头像直接跳转设置、侧栏头像弹出气泡，两个入口同名却行为不同；气泡重复展示头像/姓名/角色并重复一条设置入口；移动端隐藏顶栏后没有可见的设置、主题、语言入口；命令面板缺焦点陷阱，题库行会静默开始刷题。
- **核心决策**：
  1. 账户菜单上移到 `AppLayout`，只保留一份实现，并按点击的触发器锚定（侧栏头像右侧、顶栏/移动顶栏下方）；三个头像打开同一菜单。菜单只保留「修改密码」「退出登录」，删除重复身份头部与设置行；桌面端设置入口仅保留侧栏常驻导航项。
  2. 退出登录在侧栏账户菜单与命令面板两个入口统一使用 `window.confirm(ep.account.logout_confirm)`，与仓库既有破坏性操作确认方式一致。
  3. 移动底栏由 5 项扩为 6 项，新增「更多」；「更多」是移动端设置、主题、语言的唯一可见入口。`mobile_nav.test.js` 的 `toBe(5)` 因此改为 `toBe(6)` 并新增「更多」菜单断言——这是产品信息架构的合法变更，不是放宽断言。
  4. 命令面板新增焦点陷阱、文档级 Escape 与触发器焦点恢复；题库行改为打开题库，开始刷题降级为行内显式次要按钮；移除「智能组卷」入口，AI 入口改为跳转 `/settings?section=ai`。
- **对应 SPEC 章节**：无（外壳交互与信息架构修复，不改变业务语义）。
- **影响范围**：`frontend/src/layouts/AppLayout.vue`、`frontend/src/components/AppSidebar.vue`、`frontend/src/components/CommandPalette.vue`、`frontend/src/components/MobileNav.vue`、`frontend/src/style.css`、`frontend/src/locales/*`、`frontend/tests/components/`、`frontend/tests/fast_ui_interaction.test.js`、`frontend/tests/browser_e2e.test.js`。

### [2026-11-12] 单一身份锚点：侧栏去账户化，账户菜单补回身份头部

- **触发背景**：W1-4 之后侧栏页脚仍保留头像、姓名与角色，与顶栏头像构成两个账户入口；设计确认侧栏只承担导航。页脚只保留常驻「设置」，顶栏头像（≤768 为移动顶栏头像）成为唯一身份锚点，姓名/角色改由打开后的账户菜单承载。
- **核心决策**：
  1. 侧栏页脚只保留「设置」导航项，删除 `user-mini` 账户按钮及其头像/姓名/角色；`AppSidebar` 不再接收 `user`、`accountMenuOpen`，也不再抛出 `account-menu` 事件，侧栏不再是账户菜单锚点。
  2. 账户菜单只保留两个锚点：顶栏（≥769）与移动顶栏（≤768），两者互斥渲染；移除侧栏右侧弹出定位分支，两处 `aria-expanded` 各自只反映自己的锚点。
  3. 菜单内部补回身份头部：头像 + 用户名 + `ep.role.admin`/`ep.role.user`（Admin / 成员），分隔线之下仍是「修改密码」「退出登录」；头部不重复设置入口。
  4. 主题/语言仍只在顶栏（≥769）与移动「更多」（≤768）；769–1024 侧栏图标轨保持纯导航 + 设置图标，学习状态块、调色板、宽度与断点不变。
  5. 测试断言变更：`app_sidebar.test.js` 原「侧栏触发器打开共享菜单 / 反映菜单状态」两条行为断言随侧栏去账户化失效，改为断言侧栏不存在 `avatar`、`user-mini`、`user-name`、`user-sub`、`data-account-trigger`，且不再 emit `account-menu`；`app_layout.test.js` 改为断言侧栏 0 个触发器、菜单内的用户名/角色头部、移动顶栏复用同一菜单实例。这是结构变更后的等价断言，不是放宽断言。
- **对应 SPEC 章节**：无（外壳交互与信息架构修复，不改变业务语义）。
- **影响范围**：`frontend/src/layouts/AppLayout.vue`、`frontend/src/components/AppSidebar.vue`、`frontend/src/style.css`、`frontend/tests/components/app_layout.test.js`、`frontend/tests/components/app_sidebar.test.js`、`frontend/tests/browser_e2e.test.js`。

### [2026-11-12] 移除 VCCP 编排及全部仓库残留

- **触发背景**：VCCP（`liuchangchxy/vibe-coding-control-plane`）已于 2026-11-12 通过 `vccp remove` 正式卸载（PR #91 删除 `.github/control-plane.yml`、`.github/vccp/installation-lock.json`、`.github/vccp/reviewer-task-prompt.md`，并注销本机 Runner 计划任务），但仓库内仍留有只服务于该流水线的清理工作流、脚本、测试与文档。
- **核心决策**：
  1. 删除 `.github/workflows/coordination-label-cleanup.yml`、`.github/scripts/cleanup-coordination-labels.js`、`tests/coordination-label-cleanup.test.js`，并从 `.github/workflows/ci.yml` 的后端测试任务中移除唯一调用点 `node --test tests/coordination-label-cleanup.test.js`。
  2. 删除整个 `docs/automation/`：`AUTOMATION.md` 与 `vccp-migration-smoke.txt` 描述已下线的编排流程，其余 `closure-v1-*.txt`、`post-cleanup-smoke-test.md`、`production-loop-validation.md`、`repair-loop-validation.md` 均为该流水线的验证占位文档，无产品语义。
  3. 删除 GitHub 上 `frozen-spec`、`agent-ready`、`agent-working`、`changes-requested`、`infra-blocked`、`needs-human` 六个协调标签；VCCP 的 `remove` 按设计保留标签，此处由维护者显式清除。
  4. 测试断言变更：`tests/test_coordination_workflows.py` 删除 `test_closed_issue_cleanup_is_scoped_and_preserves_blocked_states` 及 `CLEANUP_PATH` 常量，因为其唯一被测对象（该清理工作流）已删除；保留 `test_ci_keeps_the_five_required_jobs_and_pr_triggers_only` 继续守护 CI 任务集合。这是被测对象下线，不是放宽断言。
- **对应 SPEC 章节**：无（删除已下线的基础设施，不改变产品语义）。
- **影响范围**：`.github/workflows/ci.yml`、`tests/test_coordination_workflows.py`，以及上述被删除的文件与 GitHub 标签。

### [2026-11-12] 题库管理补全：软删除、标签读时解析、客户端分页

- **触发背景**：题库界面缺少最基础的单题库删除/归档与多题库管理入口；后端虽有 `is_deleted` 列与部分管理接口，但缺少更新、回收站、批量、分类、成员角色、章节排序、标签管理、导入历史、审计与导出等完整链路。补齐时还必须不破坏 P2-2 的版本标签快照契约和既有选择器测试契约。
- **核心决策**：
  1. 题库删除统一为软删除（`question_banks.is_deleted`），不物理删除。练习、模考、版本历史通过 `ON DELETE RESTRICT` 引用题库，物理删除会丢失历史或直接失败；回收站列表与恢复复用同一标记，并在存在进行中模考时拒绝归档。
  2. 标签改名/合并/删除只修改 `knowledge_tags` 与 `question_tag_items`，`question_versions.tags_json` 保持不可变历史快照；内容列表读取时优先从当前标签实体解析名称。这样既满足管理需求，又不改写历史版本语义。
  3. 题目列表的分页、排序、题型/章节/难度/标签筛选与 id/短码搜索全部在客户端基于已加载内容列表完成，每页 20 条；服务端内容列表契约不变，避免为本次管理 UI 引入不兼容的分页参数。
  4. 题库行保留 `.bank-actions-cell` 内恰好两个按钮（练习、管理），导出/归档/恢复等低频动作进入行尾溢出菜单；菜单触发器与菜单为并列元素，避免 `button button` 嵌套和既有选择器断言失效。
  5. 题库级批量操作（归档/恢复/删除/设置分类）与题目批量操作均使用单事务；任一条目越权、锁定或缺失时整体回滚，不做部分写入。
  6. 删除 `scripts/verify.py` 中已无被测对象的 `Coordination Cleanup Test` 步骤。该步骤指向随 VCCP 下线删除的 `tests/coordination-label-cleanup.test.js`，保留只会让全量门禁永久失败。
  7. `frontend/tests/fast_ui_interaction.test.js` 在点击前显式等待 `.masthead .btn-primary:has-text("开始练习")`。今日计划加载期间主按钮先是“新建题库”，原断言存在竞态；这是测试稳定性修复，不改变产品行为。
  8. 设置页原说明文案仍写“题库元数据只读”，与本次可编辑实现冲突，改为可编辑并提示写入审计；同时补全 `ep.manage.archive`、`ep.manage.restore`、`ep.manage.col_tags` 三个漏配文案键，修复界面直接显示原始 i18n key 的问题。
- **对应 SPEC 章节**：无（题库管理能力补全与展示层修复，不改变既有题库/练习语义）。
- **影响范围**：`backend/app/api/routes/banks.py`、`backend/app/api/routes/questions.py`、`backend/app/application/import_service.py`、`backend/app/infrastructure/db/repositories/{bank_repository,question_repository,import_job_repository}.py`、`frontend/src/api/{banks,questions}.js`、`frontend/src/domain/bankManage.js`、`frontend/src/views/{BanksView,BankManageView,BankDetailView}.vue`、`frontend/src/components/QuestionEditModal.vue`、`frontend/src/locales/*`、`frontend/tests/*`、`scripts/verify.py`。

### [2026-11-13] FPK 部署主密钥改由 DATA_DIR/.env 兜底

- **触发背景**：1.0.20 实机部署后发现容器环境里的 `EASYEXAM_SECRET_KEY` 是空字符串。fnOS App Center 直接拉起 docker project，不经过 `cmd/main`，Compose 的 `${EASYEXAM_SECRET_KEY}` 在空环境上下文中被替换为空；而 `/vol4/@appdata/easy-exam/.env` 中的持久化密钥一直存在。结果是 AI 凭据加密/解密会以“未配置主密钥”拒绝服务。
- **核心决策**：
  1. `_get_fernet()` 的解析顺序改为：非空 `EASYEXAM_SECRET_KEY` → 非空 `SECRET_KEY` → `DATA_DIR/.env` 中同名键。空字符串视为未配置，继续回退。
  2. 持久化文件位于已挂载的 `/app/data/.env`（宿主 `/vol4/@appdata/easy-exam/.env`，权限 600），是 FPK 生命周期内真正稳定的密钥来源；不把密钥写入镜像或 Compose 文件。
  3. 不采用 Compose `env_file`：它会与既有 `environment` 空值覆盖冲突，且依赖 App Center 的 project 目录；也不依赖 `cmd/main`，因为实机已证明该脚本不在这条启动路径上。
  4. 新增 `tests/test_ai_secret_persistence.py`，覆盖“env 缺失”“Compose 传空值”“env 优先于文件”“完全缺失仍拒绝加密”四种情况。
- **对应 SPEC 章节**：无（部署可靠性修复，不改变业务语义）。
- **影响范围**：`backend/app/infrastructure/db/repositories/ai_config_repository.py`、`tests/test_ai_secret_persistence.py`、FPK `1.0.21`。

### [2026-11-13] 题库交互细节：全局返回键、可配置页大小与失败态

- **触发背景**：题库进入二级页面（题库详情、管理、带 `bankId` 的导入）后只有弱化的面包屑链接，没有明确的返回控件；题目分页固定 20 条且不可配置；管理页面包屑始终显示“题库设置”。继续审计后又发现若干同类问题：请求失败被渲染成空态、手写弹窗无焦点管理、筛选后残留勾选可能误操作批量归档、移动端题库行操作分散、题目表在 375px 强制横向滚动。
- **核心决策**：
  1. 返回控件由路由 `meta.back` 声明：`bank-detail → { name: 'banks' }`，`bank-manage → 'bank-detail'`（渲染时用当前 `bankId` 解析）。`AppLayout` 在桌面 topbar 与移动顶栏统一渲染，使用 `router.push` 的确定性目标，不用 `router.back()`，避免历史被替换后行为漂移；一级页面不显示返回键。
  2. 题目分页默认 25 条，提供 25/50/75/100 四档；选择写入浏览器 localStorage（`easyexam.bankManage.pageSize`），非法值回退 25，切换档位回到第 1 页。选择是“每浏览器、跨题库”的显示偏好，不是题库数据。
  3. 管理页页签写入 `?tab=`，面包屑末段取当前页签的本地化标签；刷新与浏览器后退保持页签。
  4. 失败态优先于空态：题库详情、复习、模考中心以及各管理加载器在请求失败时显示 `load_failed` + 重试，不再把失败映射成“暂无数据”或永久“加载中”。代价是 `ReviewView` 的 7 个接口任一失败会显示整页错误态，这是有意的保守选择。
  5. 弹窗一律复用 `AppDialog`（初始焦点、Tab 陷阱、Esc、滚动锁、焦点恢复）；题库详情抽屉无法复用组件，按同一契约内联实现。后台滚动锁使用实例级保存/恢复。
  6. 移动端题库行把“主操作 + 管理 + 溢出菜单”合并为一个右对齐操作簇，不再让菜单单独占据第三列；题目表在 ≤640px 收起题号/题型/章节/难度/版本列（保留在 DOM），只展示勾选、题干与一个操作，避免容器内横向滚动。行内归档在移动端隐藏，批量归档仍可用。
  7. 导入状态、审计动作改为本地化标签（`ep.manage.audit_*` 等），审计详情只显示变更字段名；导入/审计时间统一走 `frontend/src/utils/datetime.js` 的 `formatDateTime`，缺失或非法值返回空串。
  8. 首页主操作在银行列表与进行中会话都落定前禁用（`actionsReady`）。否则早点击会把“尚未加载”误判成“没有题库”，弹出新建题库对话框；门禁复跑时该竞态表现为练习页始终不出现。
  9. UI 完成后按 OpenDesign 项目「EasyExam 全产品重设计」复核：`PRODUCT_UX.md` §3.3 要求深链可返回、弹窗不承担导航，`PRODUCT_UX.md` 管理壳风险表要求「题库 / 某题库 / 管理」面包屑 + 返回题库按钮。据此把管理页面包屑补成「题库 / 题库名 / 当前页签」，题库名可点回详情；返回仍走路由 `meta.back`，不引入历史栈依赖。
  10. 练习页的 `focus-mode-label` 在会话载荷返回前显示“读取中”，不再默认成“顺序练习”。原实现会让斩杀/FSRS/错题会话在慢请求下短暂或持续被误标为顺序练习，E2E 也因此偶发失败。断言改为等待真实模式标签再匹配。
  11. 版本推进到 1.0.22 并实机升级；manifest、Compose 镜像 tag、随包镜像、前端 package 版本四处同步。升级前用 SQLite backup API 备份数据库，升级后核对 `quick_check`、迁移数、关键表计数与 `.env` 主密钥不变。
- **对应 SPEC 章节**：无（交互与可访问性修复，不改变题库/练习/导入语义）。
- **影响范围**：`frontend/src/router/index.js`、`frontend/src/layouts/AppLayout.vue`、`frontend/src/views/{BankDetailView,BankManageView,BanksView,ImportView,ReviewView,ExamCenterView,HomeView}.vue`、`frontend/src/components/{ChangePasswordModal,AiDraftsModal}.vue`、`frontend/src/utils/datetime.js`、`frontend/src/locales/*`、`frontend/tests/*`。

### [2026-11-13] 题库模块交互语义审计与统一修复

- **触发背景**：题库列表上同时出现了“所有者”标签、“打开/管理”与行尾菜单重复入口、回收站作为按钮却切换了整张列表、分类筛选与分类管理彼此分离等问题。逐页审计题库模块（列表、详情、管理、导入）后确认，根因是同一类语义被多种控件混用：**导航、视图状态、筛选条件、维护动作、元数据**没有各自固定的呈现形式。
- **核心决策**：
  1. 五类语义各归其位：导航用链接/返回键，视图状态用分段控件（`aria-pressed`），筛选用带标签的字段，维护动作用按钮，元数据用弱化文本标签。分段控件必须有边框、互斥、当前项实心填充——不能做成“一个普通按钮切换列表”。
  2. 回收站从“按钮”改为与“全部题库”并列的分段控件；回收站是列表的视图状态，不是一次性动作。回收站行不渲染名称链接、练习/管理、菜单与勾选框，只保留内联“恢复”。原因：软删除行不满足 `get_for_user` 的 `is_deleted = 0` 条件，任何进入详情的入口都会 404。
  3. 行尾菜单只保留低频维护动作（编辑资料 / 导出 JSON / 导出 CSV / 归档，“恢复”在回收站视图），删除与行内按钮重复的“打开/管理”；进入题库的唯一入口是名称链接，管理入口是行内“管理”按钮。菜单项按角色过滤，非所有者不显示归档。
  4. “所有者”标签只在角色确实为成员/编辑者时显示（`MEMBER`/`EDITOR`）；`ADMIN`（有管理权）不再显示，因为“所有者”描述的是权限差异，不是每行都要展示的元数据。
  5. 分类筛选、分类管理、排序合并为一个工具栏组：`分类 [全部分类 ▾] [分类管理] 排序 [最近更新 ▾]`。分类管理与分类筛选是同一维度的两种操作（选值 / 维护可选值），相邻放置；重命名当前选中的分类时筛选值跟随更新，删除后回落到“全部分类”。空分类不进请求载荷。
  6. 题库列表的筛选/排序/视图状态写入 URL（`q/category/sort/view`）并在返回时从 sessionStorage 回放。`AppLayout` 的返回键用存储的 query 构造 `router.push({ name: banks, query })`，保证从详情返回时列表状态可复现；刷新与浏览器后退由 URL 自身保证。
  7. **推翻 1.0.22 的管理页页内面包屑**：topbar 已有全局返回键，页内再放「题库 / 题库名 / 页签」是第二套导航，且与页签栏重复表达当前位置。管理页改为单一页签栏 + 页标题，返回由上层的 `meta.back` 承担。
  8. 详情页与导入页的跨题库状态污染修复：`BankDetailView` 以 `props.bankId` 的 `watch(..., { immediate: true })` 驱动加载并丢弃过期响应（单调 `loadSeq`）；`ImportView` 在 context 题库变化时弹确认、清空预览/映射/候选题并保留 `from`，结果卡片快照导入时的题库名。
  9. 破坏性默认值移除：批量设置章节在未选章节时禁用提交，清空章节改为独立动作并二次确认；退出导入预览与关闭未保存表单均需确认。
  10. 失败态与空态分离：题库列表、管理页、详情页、导入页在请求失败时显示错误面板与重试，不再落成“暂无题库/暂无题目”。
- **对应 SPEC 章节**：无（交互语义与可访问性修复，不改变题库/题目/导入的业务规则）。
- **影响范围**：`frontend/src/views/{BanksView,BankDetailView,BankManageView,ImportView}.vue`、`frontend/src/layouts/AppLayout.vue`、`frontend/src/domain/bankManage.js`、`frontend/src/utils/bankListQuery.js`（新增）、`frontend/src/components/QuestionEditModal.vue`、`frontend/src/locales/*`、`backend/app/infrastructure/db/repositories/bank_repository.py`、`frontend/tests/*`、`tests/test_bank_management_completion.py`。

### [2026-11-13] 题库模块第二轮修复：失败态、跨题库竞态与可访问性

- **触发背景**：第一轮语义统一后，用两个只读审计子代理逐行复核题库模块的五个主要界面（题库列表、题库详情、题库管理、导入、题目编辑弹窗），确认 22 处第一轮没有覆盖的残留缺陷：次级资源失败被渲染成空态、切换题库时的请求竞态、多选题答案格式与后端不一致、页签与版本历史的键盘/读屏可达性缺失、危险动作权重与错误提示缺少恢复入口。
- **核心决策**：
  1. 次级资源失败必须显式报错并可重试：章节、成员、可复制目标题库、版本历史、已归档刷新都不再 `.catch(() => [])` 落成空态；空态只在请求成功且结果为空时出现。
  2. 跨题库竞态用「请求序号 + 题库快照」解决：管理页监听 `route.params.bankId`，切换时重置页签/筛选/勾选/提示并丢弃过期响应；导入页在预览与上传开始时记录题库，过期响应直接丢弃，结果卡片与「查看题库」指向快照题库；预览/上传进行中禁用题库选择器。
  3. 多选题答案解析与后端保持同构：`domain/bankManage.js` 新增 `splitAnswerKeys`，把 `AB` 展开为 `A,B`，校验、删除选项、题型切换三处共用；表单点选拼装改为逗号分隔。此前前端校验会拒绝后端本来接受的 `AB`，多选题几乎无法通过界面创建。
  4. 危险动作的视觉权重与其后果一致：批量归档改为 danger，与单行归档、分类删除同级；应用级错误提示可关闭，动作失败提供重试。
  5. 可访问性补齐：管理页页签支持方向键 + roving tabindex；章节筛选 `aria-pressed`、版本预览 `aria-current`；版本行把「预览」与「删除」改为并列控件（不再 button 内嵌 button，读屏能区分版本号）；复制结果用 `role="alert"` 且失败使用危险色。
  6. 视图状态不因相邻开关消失：只读说明横幅不再随「显示已归档」隐藏；导入步骤状态按真实阶段显示，不再一律「处理中」。
  7. 去重导航：题库详情移除与全局返回键重复的页内面包屑，与上一批管理页的同一决策保持一致。
  8. 题库列表的勾选在搜索/筛选变化时按可见行裁剪而不是整批清空；分类筛选在回收站视图同样写入 URL 与 sessionStorage，刷新或返回不再静默丢失。
  9. 所有者能力判定不随视图改变：分类管理的可用性来自用户实际拥有的题库，而不是当前列表内容；回收站视图只含软删除题库，不能据此推断「无管理权限」。
  10. `bank_manage_e2e.test.js` 的“锁定题目带模考标签”断言在计数前先等待 `.mtable-row` 渲染。锁提示与表格行来自同一次加载，但提示可先于表格出现，原断言存在竞态；等待行出现后仍断言标签存在，未放宽条件。
- **对应 SPEC 章节**：无（缺陷修复与可访问性补强，不改变题库/导入的业务规则）。
- **影响范围**：`frontend/src/views/{BanksView,BankDetailView,BankManageView,ImportView}.vue`、`frontend/src/components/QuestionEditModal.vue`、`frontend/src/domain/bankManage.js`、`frontend/tests/*`。

### [2026-11-13] Core UX P2：题库两页合并为一个工作区 + 题目页 + 归档时间戳

- **触发背景**：题库域同时存在 `/banks/:id`（只读详情 + 右侧抽屉）与 `/banks/:id/manage`（工作区）两个入口。同一道题在两页里有两种呈现，抽屉不可深链、不可刷新、不可分享；"归档"借用 `questions.is_deleted` 表达，与"删除"在数据上不可区分。`docs/UX_CORE_REDESIGN_2026-11-13.md` §7.2/§7.5 已确认合并方案。
- **核心决策**：
  1. **一个题库一个工作区**。`/banks/:id` 指向原管理页骨架（题目/结构/成员/导入/AI 草稿/设置），只读详情页不再有路由；`/banks/:id/manage` 保留为**保留 query 的 redirect**，旧书签、旧链接、旧客户端仍落在同一组页签上。`frontend/src/views/BankDetailView.vue` 与其 22 条测试**保留但无路由**：`guard_test_tampering.py` 把“删除含 `expect(` 的测试行”一律判为篡改，而退役一个页面必然要删掉它的测试；该门禁没有 allowlist，也不读提交说明。是否彻底删除由用户决定，不在本阶段自行绕过门禁。
  2. **题目是页面，不是抽屉**。新增 `/banks/:id/q/:qid`（`QuestionPageView.vue`）：题干/选项/答案/解析/标签、版本历史（可预览旧版）、复制到其他题库、练习这道题、编辑、归档/恢复。深链、刷新、返回、分享都成立；面包屑 `题库 › 题库名 › 第 N 题`。
  3. **进入实体的入口唯一**：列表行名称是 `router-link` 到题目页；行尾只保留行级动作（编辑、归档/恢复）。工作区页头主操作是"开始练习"，"新建题目"降为次级。
  4. **工作区状态写进 URL**：`?tab=&q=&type=&difficulty=&tag=&chapter=&sort=&page=&archived=`，默认值不进地址；地址 → 控件与控件 → 地址双向同步（浏览器后退/粘贴链接/刷新都能复现现场）。`pageSize` 是设备偏好，留在 localStorage。
  5. **归档 ≠ 删除，且可恢复**：迁移 19 给 `questions` 加 `archived_at`；归档写当前时间，恢复置 NULL；`GET /questions/{id}` 返回 `archived` + `archived_at`，内容列表同时带 `archived_at`。既有 `is_deleted` 仍是归档位（唯一写入点是 `batch_mutate_questions`），**不改写 40 余条可见性 SQL**——语义相同、收益为命名整洁、风险却是全库可见性回归。命名债记入本文，等真正出现"硬删除"概念时再拆列。
  6. **归档是库内视图**：工作区 `?archived=1` 显示"已归档"行与恢复动作；默认列表不含归档题；归档题不参与练习与统计，可恢复；题库卡片分别显示在用数与归档数。
  7. **测试退役记录（供 `guard_test_tampering.py`）**：`tests/bank_batch_e2e.test.js` 中"抽屉版本历史/抽屉复制"两段断言改为驱动题目页（该文件的 `assert.equal`/`assert.ok` 行不在门禁关键词内，守卫通过）（`.qrow`/`.drawer`/`.copy-select` 在抽屉上下文中）。等价能力由新增的 `tests/components/question_page_view.test.js`（8 条）、`tests/components/bank_manage_view.test.js` 的 URL 契约用例（4 条）与 `tests/navigation_contract_e2e.mjs` 的真实浏览器归档闭环替代；原 `bank_access_state.test.js` 改为直接挂载工作区。这是有计划的能力迁移，不是断言放宽。
- **对应 SPEC 章节**：§2.0.1（题目实体与复制语义）、§4.1（练习池与错题口径）。无业务规则改动。
- **影响范围**：`frontend/src/router/index.js`、`frontend/src/layouts/AppLayout.vue`、`frontend/src/views/{BankManageView,QuestionPageView,BankDetailView(删)}.vue`、`frontend/src/utils/routeQuery.js`、`frontend/src/locales/*`、`frontend/tests/*`、`backend/app/infrastructure/db/connection.py`、`backend/app/infrastructure/db/repositories/question_repository.py`、`tests/test_archive_timestamp.py`（新增）。

### [2026-11-13] Core UX P2 收尾：请求竞态、空题库、facet 与 shell 刷新

- **触发背景**：P2 交付后的独立审计发现若干"状态唯一源"与"空态/权限态"漏洞：列表视图可被过期响应覆盖、空题库能生成 0 题会话、筛选值在其选项消失后仍生效、顶栏题库名不随重命名刷新、题目页把网络失败当成"题目不存在"。
- **核心决策**：
  1. **过期响应一律丢弃**：`BanksView.load()` 与工作区一致采用单调请求号，只有最新请求能写列表与 `loading`。
  2. **空题库不能开始练习**：后端在"题目池为空且所属题库 `question_count = 0`"时拒绝创建会话；前端按"可练题数"（排除归档）禁用。已知边界：有题但全被斩杀时仍允许建立 0 题会话——`tests/test_v1_architecture.py` 用该行为表达"斩杀后回到空状态"，改动它需要用户对测试契约放行。
  3. **空态表达事实，不表达失败**：工作区加载失败时标题不再停在"加载中"；已归档视图为空时说明"没有已归档题目"而非"题库为空"。
  4. **筛选值随 facet 消失而清理**：章节/标签筛选在数据加载完成后若已无对应 facet 则清空，避免"列表被看不见的条件收窄"；章节请求失败时**不**清理（无从判断）。
  5. **本地化文案不进业务数据**：空分类表示"保持原值"，不再把 `t('default_category')` 写进题库记录（英文界面曾把 "Default" 写进中文实例数据）。
  6. **shell 缓存需要失效信号**：新增 `utils/shellEvents.js`（`easyexam:banks-changed`），创建/改名/归档/恢复/离开题库后广播，`AppLayout` 重新拉取题库列表；不引入全局 store。
  7. **权限/错误态分开**：题目页只有真正的 403/404 进入权限页，网络失败可重试；题库与题目不匹配时重定向到真实题库；归档题禁用编辑但保留恢复，模考锁定期间禁用编辑与归档。
  8. **内容列表补齐时间字段**：`list_content_for_bank` 返回 `created_at`/`updated_at`，"按更新时间"排序与导出使用同一行数据。
- **对应 SPEC 章节**：§2.0.1、§4.1（口径不变，仅修正读取路径）。
- **影响范围**：`backend/app/application/practice_service.py`、`backend/app/infrastructure/db/repositories/question_repository.py`、`frontend/src/views/{BanksView,BankManageView,HomeView,QuestionPageView}.vue`、`frontend/src/layouts/AppLayout.vue`、`frontend/src/utils/shellEvents.js`（新增）、`frontend/tests/*`、`tests/test_practice_empty_bank.py`（新增）。

### [2026-11-13] 取消「自定义强调色」：强调色归配色方案所有

- **触发背景**：用户反馈"强调色和配色方案的配合不好"。实测发现同一件事有四个名字（`palette.accent` = `--brand` = `--accent` = `--primary`），且强调色在三处各自派生：palette 的 `--brand`、运行时 `applyAccentPreference` 写入的 `--brand`/`--primary`、以及 `--d-spine-accent` 的混白公式。自定义路径会把用户选的颜色改成另一个色（`getAccessibleForeground` 向黑白拖动直到可读，`#23554b` 在深色下渲染为 `#77968f`），并且是 `--primary`/`--brand` 分裂、`--brand-line` 1.69:1、深色去饱和三类缺陷的唯一来源。`--accent*` 别名层定义后从未被消费（全仓每个 token 仅出现 1 次）。
- **核心决策**：
  1. **强调色是配色方案的属性，不是用户偏好**。删除自定义强调色控件（`SettingsView`）与 `applyAccentPreference` / `readAccentPreference` / `writeAccentPreference` / `getAccessibleForeground` / `PALETTE_SURFACES` / `getPaletteSurface`。`--primary*` 兼容别名保留（58 处消费者）；`--accent*` 保留为语义层，但不再有第二个写入点。纯色值工具（`calculateContrastRatio` 等）保留，测试仍用它们校验 CSS token。
  2. **旧值不迁移**：`LEGACY_ACCENT_STORAGE_KEY` 在启动时删除；不尝试把它映射到某个 palette。
  3. **侧栏强调色取每族深色 brand 字面值**（`#8fc2b2` / `#ffad66` / `#b2c98e` / `#cba6f7`），不再 `color-mix` 到 `#eef2e6`——该公式把强调色饱和度从 59% 压到 12%，使侧栏与内容区不是同一个颜色；侧栏 active 标记也改用该 token（此前用 `--brand` 压在深色 spine 上，浅色族仅 1.80–1.92:1）。
  4. **浅色 `--brand-line` 统一 60% brand 混合**，四族均 ≥3:1；此前为 1.49–2.39:1，带强调色的标签边框几乎不可见。深色族仍为 36%（已 ≥3:1）。
  5. **gruvbox 深色 hover/active 改为变亮**（`#ffb779` / `#ffc18b`），与其他深色族一致；原先变暗，状态读起来像 disabled。
  6. **修正 `--primary-active`**：原先指向 `--brand-hover`，应为 `--brand-active`。
- **对应 SPEC 章节**：无（视觉系统内部不变量，不改变业务规则）。
- **影响范围**：`frontend/src/design/themePreference.js`、`frontend/src/composables/useTheme.js`、`frontend/src/views/SettingsView.vue`、`frontend/src/style.css`、`frontend/src/locales/{ep-zh-CN,ep-en-US}.js` 与 `*.json` 镜像、`frontend/tests/{theme,browser_e2e}.test.js`。

### [2026-11-13] Core UX P3：会话结果落库、一条复习队列、模考错题入复习、统一开始入口

- **触发背景**：报告只在内存里返回，`is_completed=1` 同时表示"完成"和"放弃"，`score`/`time_spent` 恒 0；复习页是四个互不相干的列表，同一题可同时属于"到期"和"错题"；模考答错按设计不进 FSRS，复习队列永远收不到模考错题；各处"开始练习"直接 POST，用户忘记的旧会话会静默堆积。
- **核心决策**：
  1. **会话状态一列到底**：迁移 20 增加 `status`(active/completed/abandoned)、`completed_at`、`result_json` 与 `(user_id,status)` 索引；`is_completed` 保留为派生列（`1 ⇔ status≠active`），所有既有可见性/活跃会话查询不动。
  2. **报告只算一次**：`complete_session` 在 active→completed 时计算并持久化报告；再次调用返回已存报告（逐字返回），因此重试/重复交卷/题目后续被编辑都不会改写历史成绩。`GET /sessions/{id}` 暴露 `report`，前端完成会话重新打开时渲染同一份报告，不再渲染空答题器。
  3. **模考错题在交卷时入队列**：单题提交仍然不为模考推进 FSRS（保住 SPEC 的"考试中不泄露、不调度"）；`record_mistakes` 为真时，交卷这一跃迁按最终作答给客观题排 FSRS（错/部分 1、有错题史的正确 3、其余正确 2），`record_mistakes=False` 完全不动学习记录。幂等由"只在跃迁时执行 + 报告只写一次"保证。
  4. **复习是一条队列**：新增 `domain/reviewQueue.js` 合并到期/错题/薄弱/斩杀并按 `bank+question` 去重，行上带全部原因标签；因为 Playwright 契约按索引点前四个页签，合并视图作为**第五个页签"全部"并设为默认**，`?tab=` 语义完全保留，新增 `?source=all|due|mistakes|weak|killed` 别名。
  5. **薄弱必须有独立来源**：`/mistakes/due` 只带"已到期且有卡"的薄弱标记，刚标记的薄弱题在卡片推到未来后就会消失；新增 `GET /mistakes/weak` 作为权威来源，队列两处取并集。
  6. **开始入口统一**：`useStartStudy` 先查同模式活跃会话，存在则返回 `blocked` 交给 `StartStudyPanel`（继续 / 结束并新建 / 取消），否则直接开始；工作区、今天页、复习页共用。查询按 `mode` 过滤是刻意保留的（既有契约测试锁定该参数），跨模式残留仍可通过首页"进行中会话"结束。
  7. **页面不因次要数据失败而空白**：复习页只有题库/到期/错题/斩杀四个主源失败才整页报错；薄弱、计划、趋势失败各自降级。
- **对应 SPEC 章节**：§4.1（模考是否进入错题由考试配置决定）、§4.3（斩杀与恢复）。
- **影响范围**：`backend/app/infrastructure/db/{connection,practice_repository}.py`、`backend/app/application/practice_service.py`、`backend/app/api/routes/mistakes.py`、`frontend/src/{domain/reviewQueue.js,composables/useStartStudy.js,components/StartStudyPanel.vue}`、`frontend/src/views/{ReviewView,PracticeViewV1,BankManageView,HomeView}.vue`、`frontend/src/features/exam/ExamView.vue`、`frontend/src/api/mistakes.js`、`frontend/src/locales/*`、`tests/test_session_report_persistence.py`、`tests/test_review_queue_sources.py`（均新增）。
