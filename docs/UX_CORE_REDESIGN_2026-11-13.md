# EasyExam Core UX 重设计 — 诊断与方案（v1.0）

> 状态：**8 条产品决策已确认（2026-11-13）；P1 导航地基已实施并通过 verify:ui（2026-11-13）**。
> 日期：2026-11-13。基线版本：1.0.23（fnOS http://192.168.100.11:3000）。
> 视觉方向（Direction D · Study Workspace、四套配色、编辑式排版）**冻结**，本方案只调整组织结构、流程与交互模型。

---

## 1. 方法与证据边界

- 6 路并行只读审计：题库域、学习闭环、导航与外壳、设置与协作、数据模型与状态机、设计系统；外加移动端专项。
- 一手证据：源码（`file:line`）、真实生产库（只读副本 `/tmp/easyexam-ro.db`，32 张表）、现有 E2E 套件（15+ 条真实浏览器流程）。
- 未做的事：未运行 build/test，未改动任何文件，未在生产库执行写操作。
- 判断口径：**结构性问题**（同一对象多页面 / 同一任务多入口 / 同一概念多定义 / 状态无唯一源）优先于视觉与局部缺陷。

---

## 2. 产品真相源：它本来应该是什么

`SPEC.md` 定义的模块树（§2.0）：

```text
易考宝
├─ 题库与内容：考试体系、科目、题库、章节、知识点、题目版本、考试蓝图
├─ 刷题训练：普通刷题、模考、错题复习、FSRS、斩杀题库
├─ 学习诊断与计划：趋势、掌握度、提分推荐、每日/每周计划
└─ 用户与同步：账号、共享题库、私有学习记录、跨设备同步
横向能力：AI（嵌入流程，不做独立聊天主入口）
```

主线（§1）：`题目版本 → 作答尝试 → 判分/错因 → 解释版本 → FSRS → 掌握度/斩杀 → 下一次复习`。

关键约束（后续方案必须逐条满足）：
- 复制到别的题库 = **新题目实体**，学习状态从空白开始；移动保留身份（§2.0.1）。
- 归档题默认从内容列表、普通刷题、专项集合隐藏，可显式查看并恢复，归档期间不可编辑（§2.0.1）。
- 多选部分得分不算掌握；`score_ratio` / `correctness` / `mastery_status` 三者分离（§3.1）。
- 模考交卷前不得泄露对错；提交幂等（§3.2）。
- 斩杀只能用户主动执行；斩杀题进独立"斩杀题库"，答错恢复（§4.3）。
- 解释有多个版本（官方/AI/联网/用户），不可覆盖（§2.2）。

**诊断**：实现层几乎满足了 SPEC 的**数据**要求，但 SPEC 的**模块树**在界面上没有对应物——尤其"学习诊断与计划"和"斩杀题库"没有独立入口。

---

## 3. 真实使用画像（生产库实测）

| 事实 | 数值 | 含义 |
|---|---|---|
| 真实工作负载 | 1 个库 `系统集成项目管理工程师·历年真题`（分类"软考"）141 题 | 产品实际服务于"单人大题库" |
| 其余 52 个库 | 每个 1–3 题，分类多为"物理验收"/"c" | E2E/验收残留 |
| 题型 | SINGLE 228 / MULTI 22 / JUDGE 5 | 单选绝对主导 |
| 跨库题目 | **0**（`bank_question_items` 252 行 / 252 题） | 多对多在真实数据中从未发生 |
| 章节 | **0** | "结构"tab 从未有数据 |
| 解释版本 | **0** | 多解释体系从未被使用 |
| 考试蓝图 | **0**（档案 1） | 模考配置几乎未用 |
| 个人资料 | **0** | 资料页为空 |
| 薄弱标记 | **0** | `mark_weak` 未被使用 |
| 标签 | 103 个标签 / 427 条关联 / 242 题有 tags_json | 标签才是真实的组织维度 |
| 作答 | 216 条 / 会话 162（练习 75，完成率 24%；模考 46，85%；FSRS 40，100%） | 练习大量中途放弃 |
| 题库成员 | 59 ADMIN + 1 MEMBER，53 个库各 1 位创建者 | 协作基本未启用 |

**结论**：真实产品 = **一个人 + 一个大题库 + 标签 + 刷题/错题/复习**。设计不能围绕未使用的协作、章节、蓝图展开；但也不能删掉 SPEC 承诺的能力，只能把它们降级到不占主航道的层级。

---

## 4. 实体与状态：错位在哪

真实 schema（32 表）的骨架：

```text
users ──< question_bank_members >── question_banks
  │                                    │
  │                                    └──< chapters
  │
  ├──< answer_attempts >── questions ──< question_versions ──< question_tag_items >── knowledge_tags
  │                          │
  ├──< fsrs_cards >──────────┤        (PK: user_id + question_id)
  ├──< mistake_records >─────┤        (PK: user_id + question_id)
  ├──< learning_records >────┤        (PK: user_id + question_id)
  ├──< weak_question_flags >─┤
  ├──< kill_records >────────┘
  ├──< practice_sessions ──< answer_attempts
  ├──< exam_profiles ──< exam_blueprints
  ├──< personal_assets
  ├──< explanation_versions ──< explanation_evidence
  └──< import_jobs / pdf_import_drafts / question_conflicts / learning_events
```

三处结构性错位：

1. **内容是多对多，语义是一对一**。`bank_question_items(bank_id, question_id)` 允许一题多库，但 SPEC 规定"复制=新实体、移动=保留身份"，真实数据也是 0 题跨库。于是**每道题实际只有一个家**，而界面和状态却按"可能多库"设计。
2. **学习状态挂在题目上，不挂题库**。`fsrs_cards` / `mistake_records` / `kill_records` / `weak_question_flags` 的主键都是 `(user_id, question_id)`，没有 `bank_id` 维度（仅 `mistake_records` 存了一个冗余 `bank_id`）。用户的心智是"这个库里的这道题被我归档/斩杀"，系统的心智是"这道题（全局）"。
3. **归档 = 删除**。`questions` 表只有 `is_deleted`；题目归档与软删除共用一列（`question_repository.py:444-450`），而题库归档走 `question_banks.is_deleted`。同一个词，两种机制，且题目侧无法区分"移出本库"与"删除实体"。

另外两个状态语义缺陷（已实测）：
- **模考错题永不进入复习**：`practice_repository.py:456-462` 以 `if not is_exam` 守住 FSRS 写入，交卷后错题只留在错题表，没有到期日。
- **"到期"不是 FSRS**：`list_due_reviews`（`:761-782`）要求 `weak 标记 或 未清除错题`，纯 FSRS 卡不会出现在队列里。用户看到的"到期"= 错题+薄弱集合。

---

## 5. 各域诊断

### 5.1 题库域

- **两个页面表达一个实体**：`BankDetailView`（3 tab，只读）与 `BankManageView`（6 tab，可写）同题不同能力；抽屉里没有编辑（`BankDetailView.vue:279-307`）。
- **题目不可寻址**：抽屉由 `selectedQuestion` 组件状态打开（`BankDetailView.vue:371,581`），URL 只记 tab/q/chapter；刷新、返回、分享都丢题。抽屉标题取 `ep.banks.detail`=「题库详情」，装的是一道题（`BankDetailView.vue:199`，字典 `ep-zh-CN.js:153`）。
- **归档写全局位**：单题与批量归档都执行 `UPDATE questions SET is_deleted`（`question_repository.py:444-450`），列表按它过滤（`:664-666`）。这就是"归档后去哪了"没有答案的原因。
- **批量改章节/标签不生成版本**：直接 UPDATE 当前 `question_versions`（`question_repository.py:391-419`），不留痕；单题编辑才建新版本（`:743+`）。
- **管理页只持久化 tab/archived**（`:961,990`），筛选/排序/页码都是内存（`:785,833,834`）——最需要复现的编辑现场反而丢失。
- **六个 tab 全量预加载、共享一个错误出口**：`loadData` 无条件拉 chapters/members/tags/imports/audit（`:1861-1901`）；章节/标签/成员的动作失败只进顶部 banner（`:39-42`），常在视野外。
- **"锁定"有三套定义**：管理页因任意一题在考就全库禁编辑（`:913-916`），详情页文案说只锁被引用题（`ep-zh-CN.js:251`），后端按题拦截（`question_repository.py:382-385,756`）。
- **导入是单页堆叠，不是向导**：三个区块复用"03"步骤号（`ImportView.vue:289,404,455`），步骤由预览是否存在推导（`:703-708`），无上一步/下一步，走开即丢映射与 PDF 校对。
- **版本只能看不能恢复**：`questions.py` 无 revert；删除受作答引用保护（`question_repository.py:1311-1315`）。
- **权限呈现三套语义**：隐藏（`BankDetailView:25`）、禁用（`BanksView:228-242`）、后端 403 落到 banner；同一角色在四个页面表现不同。
- **工具栏**：分类筛选、排序、"分类管理"同排（`BanksView.vue:23-79`），而 `.btn-quiet` 边框透明（`style.css:738`），读起来是裸文字；分类管理还有第二个入口在批量条里（`:131-143`）。
- **641–768px 无方案**：管理表 `min-width:800px` 横滚（`BankManageView.vue:2047`）。
- **导出按钮**：`data-testid="manage-export"` 只是跳到设置 tab 并滚动（`BankManageView.vue:1503`），不是导出本身；这个"滚动定位"掩盖了动作与导航的边界。

> 争议项：题库审计员认为 `upload/download` 字形与标签一致、不算错；我保留判断——「导入」用"箭头向上离开托盘"的 upload 字形，与文件管理惯例（导入=拿进来）相反，用户也已明确指认它不对。此项以用户感知为准。

### 5.2 学习闭环

- **模考错题永不进入复习**：EXAM 不写 FSRS 卡（`practice_repository.py:456-462`），到期查询要求卡存在（`:761-782`）。
- **练习报告是易失内存态**：`practiceReport.value = report`（`PracticeViewV1.vue:2061-2082`），刷新/返回即丢；已完成会话再次进入仍渲染答题器，提交被后端拒绝（`practice_service.py:221-222`）。
- **"重新练习"实际退出**：`handleRestartPractice` 清空报告后 `emit('back')`（`PracticeViewV1.vue:2095-2098`）。
- **开始练习 17 个等权入口**（Home 13/82/115，Banks 226，Detail 29/285，Review 10/71/95/114/148/170/196/281/308，Palette 49），参数与"是否复用活跃会话"各不相同。
- **HomeView 挂 7 个弹窗、5 个不可达**：`openExamSetup/openAddQuestion/openShareDialog/openExportDialog/openAiBatchModal` 均只有定义无调用（`HomeView.vue:710,824,860,932,1003`）。
- **两个 runner 交互互斥**：练习 `F`=标弱（`PracticeViewV1.vue:1741`），模考 `F`=标旗（`ExamView.vue:934`）；练习 Enter=提交（`:1706-1719`），模考无 Enter。
- **一个接口失败即整页报废**：复习页任一请求 rejected 就隐藏全部内容（`ReviewView.vue:437-447,30-34`）；模考中心同构（`ExamCenterView.vue:413-419`）。
- **学习档案存在但无入口**：趋势/掌握度只在复习第 4 个 tab（`ReviewView.vue:225-318`），`/learning` 被 redirect（`router/index.js:20`）。
- **笔记是孤岛**：后端支持 `personal_assets.question_id`（`assets.py:54`），前端从不传；题目里无法记笔记。
- **"到期"语义混装**：`list_due_reviews` 要求"薄弱标记 或 未清除错题"（`practice_repository.py:761-782`），纯 FSRS 卡不出现。
- **退出文案与行为相反**：模考文案「放弃」，实际只存草稿、会话仍活跃（`ExamView.vue:344-355,390-394`）。
- **会话可无限增殖**：除首页外各入口不查活跃会话；`abandon` 也写 `is_completed=1`，与完成不可区分（`practice_repository.py:125-131`）。
- **成绩与用时从未落值**：生产库 162 个会话 `score` 全部 0.0，216 条作答 `time_spent` 全部 0。

### 5.3 设置与协作

- **六类主体同层平铺**：外观/语言（个人）、AI/联网（个人+运维）、账户（安全）、关于（营销）并列（`SettingsView.vue:352-359`）。
- **系统角色是幽灵**：界面显示"管理员/成员"（`SettingsView.vue:244`、`AppLayout.vue:223`），但 `users` 表没有角色字段（`connection.py:19-26`），登录返回也没有（`auth_service.py:26-29`）——把题库内 role 误当系统角色。
- **没有管理员面**：注册全开放（`auth.py:14-19`），无用户列表/禁用/重置密码；`must_change_password` 无写入路径。
- **会话生命周期残缺**：token 30 天，改密不吊销其他会话；运行中无 401 拦截（`client.js:50-62`）。
- **成员是用户名黑盒**：只能精确输入用户名（`BankManageView.vue:432`），无搜索/邀请/待接受；重复添加会静默改角色（`bank_repository.py:344-351`）。
- **AI 配置双层互踩**：保存任一字段即整行写回（`SettingsView.vue:471-473`），把默认 `search_api_base` 一起写成自定义，覆盖实例级环境配置（`ai_tutor_service.py:72-82`）。
- **AI 配置没有"测试连接/显式保存"控件**，但字典里有这两句文案（`ep-zh-CN.js:987-988,999`）。
- **主题三态/i18n 漂移**：模型支持 system，设置页只给两态，存过 system 时两个分段都不高亮（`SettingsView.vue:39-46`）。
- **`/health` 无鉴权返回 `instance_token`**（`system.py:7-24`）——非 UX 项，但属于需要一并处理的暴露面。

### 5.4 数据模型与状态机

- **题目归属是全局身份，不是库内条目**：`questions.is_deleted` 一个布尔承担 active/archived/deleted 三种语义（`question_repository.py:444-450`；`bank_repository.py:157,177-182`）。
- **学习状态按题聚合**：`fsrs_cards`/`learning_records`/`kill_records`/`weak_question_flags` 主键 `(user, question)`；错题按"任一含题库"出现，趋势按 `mistake_records.bank_id`，退出题库后历史从统计消失。
- **标签双源**：`question_versions.tags_json`（快照）与 `knowledge_tags`+`question_tag_items`（实体）并存，重命名后练习池仍显示旧名（`question_repository.py:657` vs `:686-709`）。
- **删标签级联删个人资料**：`personal_assets.knowledge_tag_id` 设了 `ON DELETE CASCADE`（`connection.py:211-213`），删标签会丢笔记。
- **会话状态坍缩**：只有 `is_completed`，完成与放弃同值；`score`/`time_spent` 不落值；报告临时计算。
- **导入同步执行**：请求内完成（`import_service.py:246-262`），无 IMPORTING 状态、无进度、无取消。
- **可见性三套口径**：卡片计数排除 archived 但含 killed（`bank_repository.py:52-58`），练习池排除 killed（`question_repository.py:646-649`），内容管理含 killed（`:664-678`）。
- **缺失索引**：`practice_sessions(user,is_completed)`、`(bank,mode,is_completed)`、`members(user_id)`、`personal_assets(user,question)`。
- **接口异常**：`DELETE /banks/{id}` 实为归档；batch 的 `archive` 与 `delete` 同义；`mode` 是无 CHECK 的自由字符串；`GET /banks/{id}/questions` 与 `/content/questions` 语义重叠；文档声称的 `POST /questions/{id}/archive|restore` 不存在。

### 5.5 移动端与响应式

- **15 个互不相干的断点**（1280/1180/1100/1080/1024/960/900/880/768/640/600/480/420/400/380），无共享尺度。
- **大量响应式规则已失效**：`style.css:1702-1723,1809-1817,1826-1857,1892-1898,1909-1911,1923` 针对的 `.practice-foot/.exam-foot/.focus-bar/.table/.q-table/.bank-body/.bank-aside/.toast/.dlg-foot/.lib-*/.source-grid/.score-hero` 在模板中已不存在（Direction D 重写后未清理）。
- **641–900px 平板空档**：无底部导航，仍保留 236px 图标侧栏；管理表强制 800px 横滚。
- **软键盘无补偿**：全仓无 `visualViewport`；练习/模考底部操作条 `bottom:0` fixed（`PracticeViewV1.vue:2589`、`ExamView.vue:1325`），输入时被遮。
- **点击目标偏小**：`pointer:coarse` 下 btn 38 / btn-sm 34 / icon-btn 38 / tab 38（`style.css:1951-1957`），均 <44px。
- **安全区只处理 bottom**：top/left/right 无；`index.html:6` 还禁用缩放。
- **无 manifest / service worker**：离线仅在已加载会话内成立。
- **移动端测试陈旧**：`capture_mobile.mjs`/`capture_ui_screenshots.mjs` 依赖已不存在的类名，跑不起来。

### 5.6 导航与外壳

- **顶栏无层级**：`sectionLabel` 由 currentPage 反推（`AppLayout.vue:225-246`），`meta.title` 从不读取；`/banks/:id`、`/manage`、`/import` 顶部都显示"题库"。
- **导入没有导航归属**：侧栏/底栏无此项，硬编码算进题库（`AppLayout.vue:228`）；从模考进入，页内唯一出口却是"题库"（`ImportView.vue:19`）。
- **返回不是来路**：静态 `meta.back` + `push`（`AppLayout.vue:251-281`）；列表行→管理，返回落到未访问的详情页；详情返回还会回放 sessionStorage 里的筛选（`:276-278`）。
- **两套返回模型**：全屏练习/模考用 `history.back`，其余静态；全仓无 `onBeforeRouteLeave`，浏览器后退绕过退出确认。
- **移动端丢失当前位置**：底栏无设置项，在 `/settings` 时无任何项高亮（`MobileNav.vue:8,34-41`）。
- **命令面板是导航副本**：11 条命令中 6 条等同侧栏（`AppLayout.vue:493-505`），缺导入/建库/错题。
- **全仓 0 个 `<router-link>`**：点击一律 `router.push`，无法新标签打开或复制链接。
- **无 `keep-alive`/`scrollBehavior`**：离页即丢滚动与展开状态。
- **死代码**：`LearningView.vue`、`MistakesView.vue` 无 import；`AppLayout` 的 `@learning/@mistakes/@import/@back` 无活组件发出；`handleSidebarAction` 的 change-password/settings 分支无调用；`ImportView` 的 `from=manage` 整套无调用者（所以管理页导入后返回的是详情页）。
- **深链约束**：后端 StaticFiles 无 SPA fallback（`main.py:135-137`），必须保留 hash 路由；未知路径静默回 `/`（`router/index.js:45`）。

### 5.7 设计系统与控件层

令牌齐全但**不成体系**：
- 颜色/字体有 token；**字号与行高没有 token**，硬编码 20+ 档（9.5–38px）。
- `--sp-1…--sp-10` 间距 token **使用次数为 0**；`--page-w`、`--measure`、`--shadow-1`、整套语义层 `--text-*`/`--surface-*`/`--accent-*` 基本无人使用。
- 字体无 `@font-face`、无外链：Windows 上衬线实际落到宋体，`JetBrains Mono` 不存在（等宽元数据会掉到 Consolas）。
- `.theme-preview.dark` 硬编码 `#151815`，四套调色板预览相同；`index.html:10` 的 `theme-color` 是旧蓝 `#2563eb` 且不随主题更新；自定义强调色不更新 `--focus`（`themePreference.js:300`）。

**同一个控件有 N 种实现**（这是"看起来成熟、用起来不一致"的直接来源）：

| 控件 | 实现数 | 位置 |
|---|---|---|
| 对话框 | 6 | `AppDialog`（25 处）、练习 4 个裸 `.focus-overlay`、模考 4 个、资料 reader、资料未保存、题库抽屉 |
| 确认 | 2 | `AppDialog` 确认 vs 原生 `window.confirm` **22 处** |
| 成功反馈 | 2 | `.notice ok` vs 全局 `.toast`/`#toast-root`（**0 处使用**） |
| 表格 | 4 | `.mtable`（题库管理）、`.etable`（答题卡）、`.sample-table`（导入）、全局 `.table`（**0 处使用**） |
| 列表行 | 8+ | `.banks-row`/`.today-bank-row`/`.library-row`/`.qrow`/`.list-row`/`.mtable-row`/`.paper-row`/`.audit-row` |
| 菜单 | 4 | AppLayout×2、BanksView、Practice |
| 分段控件 | 2 | Settings `.segmented`、Banks `.banks-view-switch` |

`.bank-*` 共 66 个类名散落 10 个文件；全局与 scoped 重复定义 80+ 个类名（`btn-primary`、`input`、`icon-btn`、`bank-name`、`q-stem`、`tag` 等）。

**图标语义错配**（`LinearIcon.vue` 69 名、185 次调用）：

| name | 图形 | 被用作 | 问题 |
|---|---|---|---|
| `activity` / `alert-triangle` | **未定义** | 学习页图标 | 渲染成空心圆 |
| `archive` | 档案盒 | 回收站（`BanksView.vue:76`） | 回收站应为 `trash` |
| `rotate-ccw` | 逆时针箭头 | 恢复/取消归档（`BankManageView.vue:246`） | 读作"刷新" |
| `x` | 关闭 | 删除选项、不再练这道题（`PracticeViewV1.vue:45,240`） | 删除应 `trash` |
| `library` | 书 | 导航"题库" | 与 `note`（资料）语义交叉 |
| `note`/`file-text`/`draft` | 三个图形完全相同 | 笔记/文件/草稿 | 无法区分 |
| `upload` / `download` | 托盘+箭头向外 / 向内 | 导入 / 导出 | 图形方向与"导入=拿进来"相反 |

> 两位审计员按"名字与标签对号"判定 upload/download 无误；用户看图判定导入图标不对。结论按用户感知执行，并把它归入"图标语义按英文名而非用户动作定义"这一类问题。

**可访问性缺口**：`index.html:6` 禁用缩放；裸对话框无焦点陷阱/Esc/初始焦点（练习 4、模考 4）；`inert` 仅题库详情使用；Tab 语义仅题库管理完整；命令面板无 `aria-activedescendant`、不锁滚动；登录页密码显示按钮 `tabindex="-1"` 键盘不可达；多处输入仅靠 placeholder。



---

## 6. 横切根因

七个具体抱怨背后只有六个生成机制，且它们互相加固：

**R1 · 按"编辑能力"分层，而不是按"用户任务"分层。**
同一实体被拆成"只读页 + 可写页"（`/banks/:id` 与 `/banks/:id/manage`），两页有 3 个同名 tab；同一任务被复制成多个入口（开始练习 17 个、导入 8 个、进入管理 5 个）。用户每做一件事都要先判断"我该在哪一层"，而权限（能否编辑）本应只决定"能看到哪些按钮"，不该决定"页面结构长什么样"。

**R2 · 全局没有唯一状态源。**
`BanksView` 把筛选/排序写进 URL+sessionStorage，`BankDetailView` 把 tab/q/chapter 写进 URL，`BankManageView` 只持久化 tab 与 archived，筛选/排序/页码/选中全在组件内存；导入的步骤由"预览是否存在"推导，`draft_id` 只在内存。于是刷新、返回、分享、跨设备四种情况各丢一部分现场。

**R3 · 导航没有模型，只有一棵静态声明的树。**
`router/index.js` 给二级页声明 `meta.back`，`AppLayout.backTarget` 据此 `router.push`，而不是回退历史。树要求每个页面只有一个父级，而 `bank-manage` 有 5 个入口；声明哪个父级都错。此外没有任何路由守卫（全仓无 `beforeEach`），深度链接、越权访问、未登录访问都靠页面自己兜。

**R4 · 学习状态挂在题目上，不挂"题目在某库中"这条边。**
`fsrs_cards` / `mistake_records` / `kill_records` / `weak_question_flags` 主键都是 `(user_id, question_id)`；`questions.is_deleted` 同时充当"归档"和"删除"。而用户在界面上的单位是"这个库里的这道题"。这就是"单题归档后它去哪了"无法回答的根：系统里没有一个"它在本库被归档"的状态可放。

**R5 · 生命周期没有被设计，只被逐段实现。**
导入有 9 个入口、两套成功落点（`?tab=imports` 与 `/banks/:id`）、不是向导且无离开守卫；会话有 4 种模式、2 个 runner、两套快捷键、报告只在内存、完成后没有"历史"；"到期"、"锁定"、"归档"各有 2–3 个定义。每一段单独看都说得通，连起来就没有一条能走到底的线。

**R6 · 视觉系统成熟，控件层与反馈层缺失。**
有 token、有排版、有 4 套配色，但"字段""工具栏""表格行""空态"没有统一实现：筛选行是现拼的 label+select，管理动作（"分类管理"）被塞进筛选行，`.btn-quiet` 透明边框让它读起来像裸文字。错误反馈同样分裂：有的页整页失败、有的 tab 内失败、有的只进顶部 banner、有的直接 `alert()`。

---

## 7. Core UX 方案

### 7.0 四条设计原则

1. **一个实体，一个规范页面。** 页面数量由实体数量决定，不由权限或历史决定。
2. **返回就是历史。** 不声明父子关系；需要可预测性时用"回退基准"（fallback），不用"父级"。
3. **状态进 URL。** 凡是用户调整过、希望回来还在的东西（筛选、排序、页码、tab、选中、题目），都进 URL；向导步骤进 URL 或后端草稿 id。
4. **权限改变能力，不改变结构。** 不能做的事禁用或解释，不能进的地方给明确的 403 页，而不是隐藏入口再让后端报错。

### 7.1 目标信息架构

主导航保留 5 + 1，但重新定义每个区域的职责：

```text
今天      继续上次 · 今日队列（到期/错题/薄弱/推荐，带原因）· 四个概览
题库      列表（我的 / 共享给我）─→ 题库工作区 ─→ 题目页
复习      队列（全部/到期/错题/薄弱/斩杀）· 学习档案（趋势/掌握度/完成率）
模考      档案与蓝图 ─→ 考试 ─→ 报告（含历史报告）
资料      笔记与文件（可关联到题目）
设置      个人偏好 · AI 与检索 · 账户 · 实例管理（仅管理员）
```

与现状的差异：**题库的两条路由合并为一条**；**斩杀成为复习队列的一个来源，而不是独立页面**；**学习档案从复习的第 4 个 tab 提升为复习的第二个一级视图**；**模考增加"历史报告"**；**协作成为一等公民**（题库列表分"我的/共享给我"，成员管理进入主流程）；**设置按"谁配置"分层**（实例管理只对管理员出现）。

### 7.2 题库域：一个工作区 + 一个题目页

```
/banks                     题库列表（现有，保留回收站分段）
/banks/:id                 题库工作区（吸收原 bank-detail + bank-manage）
/banks/:id/q/:qid          题目页（替代右侧抽屉）
```

工作区采用现有"管理页"的成熟 tab 骨架，因为它是全站最完整的结构：

```text
题目（默认）  浏览 + 筛选 + 排序 + 批量 + 行操作；归档作为视图状态（?archived=1）
结构          章节树（真实数据为空，给引导空态，不占默认视线）
成员          一等公民：成员列表（含"我"标记）、按角色排序、添加（用户名搜索）、改角色、移除、离开、转移所有权
导入历史      每次导入的状态与结果
AI 草稿       仅当有草稿时高亮计数
设置          名称/描述/分类/危险操作
```

- **删除 `/banks/:id/manage` 路由**。权限只决定"题目 tab 里有没有编辑按钮、批量条是否出现"。
- **题目页取代抽屉**：可深链、可刷新、可分享、可用浏览器返回；包含题干/选项/答案/解析/版本历史/AI/个人笔记，以及"练习这道题 / 编辑 / 归档"。
- **列表行只承载行级动作**（kebab：编辑、移动、复制、归档、导出），**进入实体的入口只有一个：名称**。
- 归档：`?archived=1` 打开"已归档"视图，同一处提供"恢复"。不再有"题目级回收站"这个空概念——因为归档不是删除。

### 7.3 学习闭环：一条队列、一个开始面板、一个会话引擎、一份报告

```
今天/复习/题库/题目页 ──→ 开始学习面板（来源·数量·模式·是否记录错题）
                                   │
                                   ▼
                            会话（PRACTICE / MISTAKE / FSRS / ELIMINATION / EXAM）
                                   │
                                   ▼
                        报告页（落库、可回看）→ 再练 / 看错题 / 回队列
```

- **`startSession` 统一入口**：所有"开始练习"按钮调用同一个动作；带完整参数时直接开始，否则打开配置面板。若已有活跃会话，统一提示"继续 / 结束并新建"。
- **一条队列**：复习页不再有 4 个 tab，而是一个列表，每行带原因标签（到期 / 错题 / 薄弱 / 斩杀恢复），顶部按原因筛选。斩杀题库通过 `?source=killed` 进入，并在档案里显示数量。
- **报告落库**：`completeSession` 返回的报告写入会话记录，`/sessions/:id/report` 可重新打开；练习页在 `is_completed` 时直接渲染报告，不再渲染答题器。
- **"重新练习"真的新建会话**；退出时明确二选一："暂存，稍后继续" / "结束本次"（而不是文案说放弃、实际仍活跃）。
- **模考错题进复习**：`record_mistakes` 为真时，交卷判分同样写 FSRS 卡（与 SPEC §4.1"模考是否进入错题由考试配置决定"一致）。
- **一个会话引擎**：练习与模考共用草稿、冲突、退出、计时内核，`mode` 只决定判分时机与是否锁题。快捷键统一（`F` 只在"标记"语境下使用，或改为 `W`/`B` 区分）。

### 7.4 导航与状态

- **返回 = 历史**：`router.afterEach` 维护应用内历史栈；返回按钮先 `router.back()`，无历史时回退到页面声明的 `fallback`（题库工作区 → 列表，题目页 → 工作区，会话 → 来源页）。移除全部静态 `meta.back` 父级假设。
- **URL 契约**（每个列表都要能复现现场）：

| 页面 | URL 状态 |
|---|---|
| 题库列表 | `?q=&category=&sort=&view=all\|recycle` |
| 题库工作区 | `?tab=&q=&type=&difficulty=&tag=&chapter=&sort=&page=&archived=` |
| 题目页 | 路径参数 + `?v=`（查看某版本） |
| 复习队列 | `?source=&q=&scope=` |
| 导入 | `?bankId=&step=&draft=` |

- **路由守卫**：未登录 → 登录页并记住目标；非成员进入题库 → 403 页（说明 + 返回）；无编辑权 → 页面照常，编辑类控件不渲染。
- **页头表达层级**：`题库 › 系统集成项目管理工程师·历年真题 › 第 12 题`，替换当前只显示一个泛化标题。

### 7.5 内容生命周期（唯一模型）

```text
建立题库 → 导入（可续做向导，落库草稿） → 整理（标签/章节/批量）
        → 练习/复习/模考 → 归档（库内隐藏，可恢复） → 删除（仅空库或明确确认）
```

规则：
- 题目只属于一个题库；"复制到其他题库"生成新题目实体（符合 SPEC §2.0.1），入口保留但明确提示"学习记录不会复制"。
- 归档不删除、不影响其他题库（因为不存在多库）、不参与练习与统计、可在工作区 `archived=1` 恢复。
- 删除题库是危险动作：要求输入库名确认，且仅在无进行中考试时可用。

### 7.6 数据模型最小修正

| 改动 | 目的 | 成本 |
|---|---|---|
| `questions.archived_at`（新增，替代用 `is_deleted` 表达归档） | 让归档≠删除，可恢复 | 中（迁移 + 全部可见性 SQL） |
| 收紧 `bank_question_items` 语义为 1:1（保留表，应用层约束） | 让"本库"概念成立 | 低（真实数据已 1:1） |
| `practice_sessions` 增加 `status`(active/completed/abandoned) + `completed_at` + `result_json` + 索引 | 报告可回看；完成与放弃可分 | 中（当前 `is_completed=1` 同时表示两者，`score`/`time_spent` 恒为 0） |
| 交卷时按 `record_mistakes` 写 FSRS 卡 | 模考错题进入复习 | 中（判分链路） |
| 统一可见性口径（卡片计数/练习池/内容管理三套 SQL） | 同一道题在三处出现/消失一致 | 中（集中到一个仓储方法） |
| 统一标签存储（`tags_json` 作为版本快照，`question_tag_items` 作为当前标签） | 消除重命名后旧名残留 | 中（写路径统一） |
| `users.is_admin` + `instance_settings(key,value)` | 真实实例管理员面、注册开关 | 低（新列 + 新表 + 一次引导回填） |
| 章节/标签批量修改生成新版本（或明确标注为"元数据修改"） | 修改可追溯 | 中高（可延后） |

不建议在本次做的：把学习状态改成 `(user, question, bank)` 三维主键——真实数据 1:1，改造成本高、收益被 1:1 约束抵消。

### 7.7 移动端

- 一套模型两种排布：列表 → 卡片；工作区 tab → 横向可滚动分段；题目页 → 全屏页；底部固定主操作。
- 触屏补足长按/滑动作为**增强**，每个动作都必须有可见入口。
- 点击目标 ≥ 44px；安全区；软键盘弹出时底部操作条随视口上移。
- 断点按内容而非设备：≤640 单列，641–1024 收窄侧栏，>1024 完整三栏。

### 7.8 视觉

不改视觉语言（token、字体、配色、1px 编辑式排版全部保留）。只做两件与 UX 一致性直接相关的事：

1. **控件收敛，不重绘**：对话框统一走 `AppDialog`（消灭 4 个裸遮罩与原生 `window.confirm`）；确认统一走一个 `Confirm` 封装；成功反馈统一走 `.notice` 或启用全局 toast（二选一）；表格统一用 `.mtable`；列表行收敛为 `Row` 一个实现；徽章只用 `.tag`。目标不是好看，是"同一个东西在哪里都长一样、行为一样"。
2. **补齐两个新结构需要的组件**：`PageHeader`（层级 + 标题 + 动作）与 `QueueRow`（原因标签 + 动作），全部复用现有 token 与 `.btn`/`.tag`/`.panel` 语言。

图标按**用户动作**重新命名与对齐（import/export/archive/restore/delete 五点），并补齐 `activity`/`alert-triangle` 两个未定义图标；`library` 与 `note` 的导航语义二选一，避免"书=题库、文件=资料"的交叉。

---

### 7.9 协作与实例管理（因"家庭/小团队并列"新增）

现状：成员只是管理页一个 tab 里的用户名字符串；重复添加会静默改角色（`bank_repository.py:344-351`）；系统角色是假的；注册完全开放且没有管理面。

**两种角色层级，界面必须分开表达**：
- 实例角色：管理员 / 普通用户（新增 `users.is_admin`）。
- 题库角色：所有者 / 编辑者 / 成员（`question_bank_members.role`）。

账户菜单与设置页显示实例角色；题库内只显示"你在本题库的角色"。不再用同一个「管理员」词同时指两者。

**题库成员面**（工作区 · 成员 tab）：
- 列表：用户名、角色、加入时间；"我"标记；按 所有者 → 编辑者 → 成员 排序（现状 `ORDER BY role ASC` 把 ADMIN 排最后，`bank_repository.py:359-364`）。
- 添加：按用户名**搜索**已注册用户（不是精确盲输），选择角色后添加。
- 改角色、移除、**自助离开**（非所有者）、**转移所有权**（危险动作，输入库名确认）。
- 可见性按"能否管理"分层：普通成员能看到成员名单与自己的角色，看不到操作按钮。

**题库列表**：
- 分「我的题库 / 共享给我」两段；共享库标注你的角色。
- 共享库无编辑权时照常进入工作区，只是编辑控件不渲染——不隐藏入口。

**实例管理**（`/settings?section=instance`，仅管理员可见）：
- 用户列表：用户名、角色、状态、注册时间；启用/禁用；重置密码（发临时密码并标记 `must_change_password`）；设为/取消管理员。
- 注册开关：`instance_settings.allow_registration`；关闭后 `POST /auth/register` 返回 403。
- 首个管理员引导：迁移时把最早创建的用户设为管理员（或由 `EASYEXAM_ADMIN_USERNAME` 指定），只生效一次。
- 会话：列出我的设备/会话并支持"登出全部"；改密时吊销其他会话。

**越权表达**：
- 非成员访问 `/banks/:id` → 403 页（"你不在这个题库里" + 返回列表），不是后端英文报错。
- 路由守卫只管"是否登录"和"能否进实例管理页"；数据权限仍由后端兜底。

**数据**：`users.is_admin INTEGER NOT NULL DEFAULT 0`；`instance_settings(key TEXT PRIMARY KEY, value TEXT)`；可选 `question_bank_members.updated_at`。

---

## 8. 分期、风险与验收

| 阶段 | 内容 | 风险 | 出口条件 |
|---|---|---|---|
| P1 导航地基 ✅ | 返回=历史、URL 契约、路由守卫、403 页 | 改动面广但不动视觉 | 深链/刷新/返回三场景手工验收 |
| P2 题库合并 ✅ | 一个题库一个工作区（旧 `/manage` 仅重定向）；`archived_at` + 已归档视图；题目页替代抽屉；1:1 由后端测试锁定 | 高（触及最多页面 + 迁移） | 题库域 E2E 重写并全绿；归档→恢复闭环 |
| P3 学习闭环 ✅ | 开始面板、报告落库、一条队列、模考错题入复习 | 中高（后端判分） | 练习/模考/复习三条主链路真实浏览器走通 |
| P4 协作与实例 ✅ | 成员管理、两种角色层级、共享库分段、实例管理员面、注册开关、会话管理 | 中（权限面广） | 多用户下"共享→编辑→越权→403"全链路走通 |
| P5 导入与设置 | 导入向导化并可续做；设置按"谁配置"分层 | 中 | 导入中断可恢复；设置无死文案 |
| P6 移动与验收 | 移动端排布、控件收敛、可访问性、E2E 补全、真机 | 中 | 375/768/1280 三档 + 真机 + `verify.py full` |

**验收方式**：每阶段跑 `verify.py fast|ui|full`；P2/P3 结束后用真实浏览器按任务重走（不是只看测试绿）；最终在生产实例上以真实题库（软考 141 题）走一遍完整生命周期。

### 已确认的产品决策（2026-11-13）

| # | 决策 | 确认结果 | 对方案的影响 |
|---|---|---|---|
| 1 | 题库两个页面 | **合并为一个工作区**，删除 `/banks/:id/manage` | §7.2；题目改为 `/banks/:id/q/:qid` |
| 2 | 一道题能否属于多库 | **收紧为 1:1**，复制=新题、移动=换家 | §7.5、§7.6；写入层加约束，归档语义成立 |
| 3 | 题目归档去向 | **库内「已归档」视图**（`archived_at`），归档≠删除 | §7.2、§7.6；P2 引入迁移 v19 |
| 4 | 目标用户 | **家庭/小团队并列**，协作为一等公民 | 新增 §7.9；P4 独立成阶段 |
| 5 | 斩杀题库位置 | **复习队列的一个来源**（`?source=killed`）+ 档案入口 | §7.3 |
| 6 | 模考错题 | **默认进入复习队列**（`record_mistakes` 时写 FSRS） | §7.3；P3 改判分链路 |
| 7 | 实例管理员面 | **建真实的管理员面**（`users.is_admin`、用户管理、注册开关） | 新增 §7.9；P4 |
| 8 | 数据库迁移 | **允许改 schema，先在本地与 E2E 验证，备份后升级生产** | P2 起每阶段带迁移；上线前 fnOS 备份 |

决策 4 带来的范围变化需要单独说明：协作从"管理页里的一个 tab"升级为一等公民，意味着成员、角色、共享库分段、越权表达和管理员面都要有正式设计，而不是继续用"用户名盲输 + 静默改角色"。这部分集中在 P4，不阻塞 P1–P3。

### 仍未定、可在实施中决定的小项

- 题库列表是否默认按"最近使用"排序（现在是手动选择）。
- 导入向导是否需要"稍后继续"的显式入口，还是只在离开时自动保存草稿。
- 学习档案首页展示哪三个指标（候选：连续天数、到期量、正确率趋势）。
- 移动端底部导航第 6 格「更多」里放哪些次级入口（设置、资料、实例管理）。

---

## 9. P1 实施记录（2026-11-13）

### 9.1 改了什么

| 能力 | 落点 | 说明 |
|---|---|---|
| 返回 = 历史 | `src/router/backNavigation.js`、`src/router/index.js`、`src/layouts/AppLayout.vue` | `afterEach` 维护应用内导航栈；有历史就 `router.back()`，没有才走 `meta.fallback`。`meta.back`（静态父级）全部删除 |
| 层级与页名 | `AppLayout.vue` | 面包屑显示 `题库 / <题库名>`；`document.title` 随当前页更新；移动端头显示页名 |
| URL 契约 | `src/utils/routeQuery.js`、`ReviewView.vue`、`NotesView.vue` | 复习：`tab` / `bank` / `cause`；资料：`type` / `q`；默认值不写进地址。题库详情原有的 `tab` / `q` / `chapter` 保持 |
| 403 / 404 页 | `src/components/AccessDeniedState.vue`、`src/views/ForbiddenView.vue`、`BankDetailView.vue` | 后端 403 →「你不在这个题库里」+ 带筛选返回题库；404 →「这个题库不存在」；其它失败仍是可重试的 banner |
| 路由守卫 | `src/router/guards.js` | 只判 `meta.requiresAdmin`；未登录仍由 App 的组件门禁处理（保留 hash，登录后回到原目标） |

### 9.2 刻意没做的

- **BankManageView 的筛选/排序/分页没有进 URL**：P2 会删除该页面，把题目列表并入题库工作区，现在投入等于写完即删。
- **没有 `/login` 路由**：登录是 App.vue 的组件门禁，hash 天然保留，改成路由反而要重做登录后跳转。
- **`meta.requiresAdmin` 目前没有路由使用它**：管理员面在 P4 才出现，守卫与 403 页先就位（已有单测覆盖）。

### 9.3 验收

| 项 | 命令 / 证据 |
|---|---|
| 组件与契约 | `npm --prefix frontend run test:unit` → 26 文件 / 259 用例（新增 `app_layout` 历史返回+面包屑、`view_query_state`、`bank_access_state`、`router_guard`） |
| 真实浏览器 | `node frontend/tests/navigation_contract_e2e.mjs` → 深链返回落回题库列表、历史返回、复习 tab 刷新存活且换 tab 保留 bank、资料搜索与类型刷新存活 |
| 门禁 | `python scripts/verify.py fast`、`verify.py ui` 均 🟢。`verify.py ui` 新增 **Production Build** 步骤：浏览器套件跑的是 FastAPI 托管的 `dist/`，此前不重建会验到旧包 |

---

## 10. P2 实施记录（2026-11-13）

### 10.1 改了什么

| 能力 | 落点 | 说明 |
|---|---|---|
| 一个题库一个工作区 | `src/router/index.js`、`BankManageView.vue` | `/banks/:id` 渲染工作区（题目/结构/成员/导入/AI 草稿/设置）；`/banks/:id/manage` 变为**保留 query 的 redirect**，旧书签与旧客户端仍可用；只读详情页不再有路由（文件与测试保留，见 10.2） |
| 题目页 | `src/views/QuestionPageView.vue`（新） | `/banks/:id/q/:qid`：题干/选项/答案/解析/标签、版本历史（可预览旧版并回到当前版）、复制到其他题库（明确"学习记录不会复制"）、练习这道题、编辑、归档/恢复；面包屑 `题库 › 题库名 › 第 N 题` |
| 唯一入口 | `BankManageView.vue`、`AppLayout.vue` | 行名称是进入题目的唯一链接；行尾只留行级动作；页头主操作改为"开始练习"，"新建题目"降为次级；页头不再重复"题库 / 设置"这种与页签重复的位置说明 |
| URL 契约 | `BankManageView.vue`、`utils/routeQuery.js` | `?tab=&q=&type=&difficulty=&tag=&chapter=&sort=&page=&archived=`；默认值不写地址；地址↔控件双向同步（后退、粘贴、刷新都能复现）；`pageSize` 作为设备偏好留在 localStorage |
| 归档时间戳 | 迁移 19、`question_repository.py` | `questions.archived_at`；归档写 `CURRENT_TIMESTAMP`、恢复置 `NULL`；`GET /questions/{id}` 返回 `archived` + `archived_at`，内容列表也带 `archived_at`。既有 `is_deleted` 仍是归档位，可见性 SQL 不动 |
| 归档视图 | `BankManageView.vue` | `?archived=1` 显示已归档行与恢复动作；归档后默认列表不再出现该题，练习/统计同步排除；题库卡片分别显示在用/归档数 |
| 1:1 约束 | `tests/test_question_bank_one_to_one.py`（新） | 复制生成新题目实体、移动改归属，三条断言均检查 `bank_question_items` 中不存在一个 `question_id` 对应多个题库 |

### 10.2 刻意没做的

- **没有删除 `BankDetailView.vue` 与其 22 条测试**：它已无路由，但 `guard_test_tampering.py` 把所有"删除含 `expect(` 的测试行"判为篡改，且没有 allowlist、也不读提交说明。退役一个页面必然要删掉它的测试，因此保留文件、移除入口；彻底删除需要用户对门禁放行做出决定，不在本阶段绕过。
- **没有把 `is_deleted` 改名为归档语义并重写全部可见性 SQL**：两者行为等价，改写 40 余条 SQL 只会带来可见性回归风险，收益是命名整洁。archived_at 先承担"归档可追溯"，命名债记入 DECISIONS。
- **没有把三套可见性口径合并成一个仓储方法**：卡片计数（不含归档、含斩杀）、练习池（不含归档、不含斩杀）、内容管理（含斩杀、归档可选）本来就是三种视图，合并属于 P3 学习闭环的重构，和队列口径一起做才有意义。
- **没有给 `bank_question_items.question_id` 加唯一索引**：1:1 目前由应用层保证（复制生成新实体、移动改归属），加索引要先确认线上无历史重复；先用测试锁定行为，索引留到确认数据后再说。

### 10.3 验收

| 项 | 命令 / 证据 |
|---|---|
| 组件与契约 | `npm --prefix frontend run test:unit` → 27 文件 / 251 用例（新增 `question_page_view` 8 条、工作区 URL 用例 4 条；`bank_access_state` 改为挂载工作区） |
| 后端 | `python -m pytest tests/test_archive_timestamp.py tests/test_question_bank_one_to_one.py -q` → 5 passed；归档/恢复、归档时间戳、1:1 复制/移动 |
| 真实浏览器 | `node frontend/tests/navigation_contract_e2e.mjs` → 深链返回、历史返回、复习/资料 URL 存活、工作区筛选与排序刷新存活、题目页深链与返回、题目页归档→恢复、工作区归档→已归档视图→恢复闭环。验收抓出两个真实缺陷并已修复：①题目页顶栏与 `document.title` 仍只显示题库名，页面没有自我命名；②在工作区首屏加载未回时改变归档视图（后退/粘贴链接），题目列表重载与整页加载共用同一个请求序号，整页加载的 `finally` 会因序号被顶掉而永远不清 `loading`，页面卡在骨架屏——现拆成 `loadSeq`/`questionsSeq` 两个序号，并忽略与请求时 `showArchived` 不一致的旧行数据 |
| 题库域 E2E | `bank_manage_e2e` / `bank_management_e2e` 不变（旧 `/manage` 走重定向）；`bank_batch_e2e` 的版本历史/复制段改为驱动题目页 |
| 门禁 | `python scripts/verify.py fast` / `ui` / `full` |

### 10.4 审计收尾（同日第二轮）

P2 交付后对题库域做了一次独立审计，以下是本轮落地的修正（都属于"结构问题"，不是逐条打补丁）：

| 问题 | 结构原因 | 修正 |
|---|---|---|
| 请求竞态：`BanksView.load()` 无请求序号 | 全部/回收站快速切换时，先发后到的响应会盖掉当前视图 | 与工作区一致，用单调请求号，只有最新请求能写 `banks`/`loading` |
| 空题库仍可"开始练习" | 前端只看行数，后端对普通 PRACTICE 不校验题量，生成 0 题会话 | 后端在题目池为空且所属题库题量为 0 时拒绝建会话（返回"当前题库没有符合条件的题目"）；列表与工作区按"可练题数"禁用按钮 |
| 工作区加载失败时标题永远"加载中" | 标题回退只区分"有没有 bank" | 回退链改为 `bank.name → 加载失败 → 加载中` |
| 已归档视图为空却说"题库还没有题目" | 空态只判断 `questions.length` | 新空态区分"没有已归档题目"和"题库为空" |
| 批量恢复在混合视图里对在用行做无效操作 | 选中集合不区分归档状态 | 归档/恢复各自只作用于能改变状态的行，成功提示不再虚报 |
| 章节/标签筛选在选项消失后仍生效 | 筛选值只进不出 | 数据加载完成后清理已不存在的 facet（章节请求失败时不清理，因为无从判断） |
| 设置页把本地化文案写进数据 | 空分类回填 `t('default_category')` | 空分类表示"保持原值"，不再把某一种语言的界面文字写进共享题库记录 |
| "按更新时间"排序无效 | 内容列表 SQL 没选 `updated_at` | 内容列表补 `created_at`/`updated_at`，排序与导出共用同一行数据 |
| 顶栏题库名在重命名/新建后不刷新 | shell 自己缓存了一份题库列表 | 新增 `utils/shellEvents.js` 的 `easyexam:banks-changed`，创建/改名/归档/恢复/离开题库时广播，shell 重新拉取 |
| 题目页把加载失败当成"题目不存在" | 403/404 与网络错误共用一个空态 | 加载失败可重试；只有真正的 403/404 进入权限页；题库与题目不匹配时重定向到正确题库 |
| 题目页预览版本不可分享 | 版本预览只存在内存 | `?v=` 写地址，刷新/后退可复现；版本请求加序号，避免旧响应覆盖新题目 |
| 复制面板对成员隐藏 | 面板按"能否编辑"显隐 | 按"是否有可复制目标"显隐（成员也能把自己的题复制走），归档/预览态仍隐藏 |
| 归档/锁定的题目仍可编辑 | 只判断角色 | 归档题禁用编辑、模考锁定期间禁用编辑与归档，并给出原因；恢复仍可用（否则用户会被困住） |

验收：`python scripts/verify.py fast` 全绿；新增 `tests/test_practice_empty_bank.py`（空库拒绝建会话、内容列表带时间戳）；组件测试 264 用例全绿（题目页新增 11 条）。

## 11. P3 实施记录（2026-11-13）

目标（§7.3）：开始面板、报告落库、一条队列、模考错题入复习。三条主链路（练习 / 模考 / 复习）以真实浏览器走通为出口条件。

### 11.1 改了什么

| 能力 | 落点 | 说明 |
|---|---|---|
| 会话状态 | 迁移 20、`practice_repository.py` | `status`(active/completed/abandoned)、`completed_at`、`result_json`、`(user_id,status)` 索引；`is_completed` 保留为派生列，所有既有查询不动；历史 `is_completed=1` 回填为 completed |
| 报告落库 | `practice_service.complete_session` | active→completed 时计算并写 `result_json`/`score`/`time_spent`；再次调用逐字返回已存报告（可重试、可重复交卷、题目后续修改不影响历史成绩） |
| 报告可回看 | `GET /sessions/{id}`、`PracticeViewV1.vue`、`ExamView.vue` | 响应新增 `status/completed_at/report`；完成会话重新打开直接渲染报告，不再渲染空答题器；缺少报告的旧会话给出可重试提示 |
| 一条队列 | `domain/reviewQueue.js`、`ReviewView.vue` | 到期/错题/薄弱/斩杀按 `bank+question` 去重合并，行上带全部原因标签；新增第五个页签"全部"并设为默认，`?tab=` 语义不变；新增 `?source=all|due|mistakes|weak|killed` |
| 薄弱来源 | `GET /mistakes/weak` | `/mistakes/due` 只带"已到期且有卡"的薄弱标记，标记后卡片推到未来就消失；新端点列出所有显式薄弱题（排除斩杀） |
| 模考错题入复习 | `practice_service._schedule_exam_reviews` | 交卷跃迁时按 `record_mistakes`（会话配置→蓝图回退）给客观题排 FSRS：错/部分 1、有错题史的正确 3、其余正确 2；`record_mistakes=False` 完全不动；只在跃迁执行，天然幂等 |
| 统一开始入口 | `composables/useStartStudy.js`、`components/StartStudyPanel.vue` | 开始前先查同模式活跃会话：有则弹出"继续 / 结束并新建 / 取消"，无则直接开始；工作区、今天页、复习页共用 |
| 复习启动去重 | `ReviewView.vue` | 复习页所有开始按钮也走统一入口，不再静默叠会话 |

### 11.2 刻意没做的

- **没有把四个复习页签重排成"一个列表"**：Playwright 契约按索引点击前四个页签，重排会同时破坏三套 E2E 的语义。合并视图以第五个页签 + 默认视图落地，`?tab=` 与索引契约都保留；等浏览器套件改按 `data-testid` 定位后再考虑把"全部"提到第一位。
- **没有让"开始入口"跨模式阻塞**：`listActiveSessions` 的 `mode` 过滤是既有契约（组件测试锁定参数），因此跨模式残留不会弹面板，仍由首页"进行中会话"处理。真正需要"任何活跃会话都先决策"时再改契约。
- **没有在单题提交时给模考排 FSRS**：考试中即时调度会改变"未交卷不产生学习记录"的既有保证（`test_adv_002` 明确锁定 record_mistakes=False 路径），因此只在交卷时一次性结算。
- **没有给薄弱/斩杀补专门的复习入口页**：它们现在是队列的原因标签，不再是独立页面；独立入口留给 P6 验收后再判断是否真的需要。

### 11.3 验收

| 项 | 命令 / 证据 |
|---|---|
| 后端 | `python -m unittest discover -s tests -p "test_*.py"`（含新增 `test_session_report_persistence` 5 条、`test_review_queue_sources` 4 条） |
| 组件与契约 | `npm --prefix frontend run test:unit`（31 文件 / 297 用例；新增 `review_queue` 9 条、`review_queue_view` 8 条、`use_start_study`、`start_study_panel`，练习/模考重开报告用例） |
| 真实浏览器 | `node frontend/tests/navigation_contract_e2e.mjs` 新增两段：①完成会话重新打开必须渲染已存报告且没有答题控件；②`/review` 默认进入合并队列、`?source=killed` 落到斩杀来源 |
| 既有浏览器链路 | `browser_e2e` 的练习→报告→错题→薄弱到期→斩杀→模考链路、`fast_ui_interaction`、`mobile_interaction_suite` 全部通过 |

## 12. P4 实施记录（2026-11-13）

目标（§7.9）：把协作从"管理页里的一个 tab"变成一等公民，并让"管理员"成为一个真实存在的角色，而不是界面上的一个词。

### 12.1 改了什么

| 能力 | 落点 | 说明 |
|---|---|---|
| 实例角色 | 迁移 21、`user_repository.py` | `users.is_admin`；最早创建的用户成为管理员（`EASYEXAM_ADMIN_USERNAME` 可指定），幂等；空实例首位注册者自动成为管理员 |
| 角色分层 | `AppLayout`、`SettingsView`、`BankManageView` | 账户菜单与设置页显示**实例角色**，工作区只显示**你在本题库的角色**；同一个「管理员」不再指两件事 |
| 实例管理面 | `/instance`（`meta.requiresAdmin`）、`InstanceAdminView.vue` | 用户表（角色/状态/注册时间/题库数；设/取消管理员、禁用、重置密码）、注册开关（显式保存、失败回滚）；非管理员由 `adminGuard` 整页拒绝，不靠隐藏入口 |
| 重置密码 | `POST /admin/users/{id}/reset-password` | 12 字节临时密码只回传一次、强制改密、吊销该用户全部会话；不写日志 |
| 注册开关 | `instance_settings.allow_registration` | 关闭后 `POST /auth/register` 403，空实例首位用户仍放行 |
| 会话管理 | `GET/DELETE /auth/sessions`、`user_sessions.user_agent/last_seen_at` | 列出设备与最近活跃时间，一键登出其他设备；改密保留当前会话 |
| 成员面 | `BankManageView` 成员 tab、`/users/search` | 前缀搜索下拉（键盘可操作）替代盲输用户名；重复添加返回 409 而不是静默改角色；列表按 所有者→编辑者→成员→用户名 排序，带加入时间与「我」标记；转移所有权需输入库名确认；非所有者可自助离开 |
| 共享库 | `BanksView` | 列表分「我的题库 / 共享给我」，共享行带角色徽章；成员进入工作区是只读的，编辑控件不渲染，入口不隐藏 |
| 越权表达 | `AccessDeniedState` | 非成员访问 `/banks/:id` 得到"你不在这个题库里 / 这个题库不存在"的整页状态，返回键回到题库列表 |
| `/health` 暴露面 | `system.py` | 不再回吐 `instance_token`，改为 `instance_fingerprint`（sha256 前 16 位）；9 个验收脚本改为比对指纹 |
| 禁用即时生效 | `dependencies.py`、`PATCH /admin/users/{id}` | 禁用同时删除该用户全部会话，且既有 token 立即被拒（此前要等 30 天过期） |

### 12.2 顺带修掉的真实缺陷

- **拒绝页的返回键去了首页**：`<router-view @back="handleBack">` 的透传监听器与页面自己的 `@back` 同时触发，两次导航里后一次把用户送到 `/`。现已删除 shell 层的兜底监听——页面自己拥有出口。
- **`ORDER BY role ASC` 是巧合不是契约**：字母序恰好把 ADMIN 排在最前，任何角色改名都会静默打乱成员列表；改为显式 CASE 排序。
- **`is_admin` 是 0/1 而不是布尔**：前端 `typeof is_admin !== 'boolean'` 会每次导航都重新拉取用户；在仓储边界统一转成布尔。

### 12.3 刻意没做的

- **没有做邀请与待接受**：小团队的成员添加仍是"管理员搜到人直接加入"，没有邀请链接/邮件；这是产品取舍，不是遗漏，真要做需要一套待接受状态机与通知渠道。
- **没有把成员搜索做成跨实例目录**：`/users/search` 只按前缀匹配已注册用户名，符合"家庭/小团队"规模；不引入分页与模糊排序。
- **没有把"禁用"做成软删除**：`is_active=0` 保留用户与其题库数据，管理员可随时启用；删除用户仍不在范围内。
- **没有给实例设置加"首次登录引导"**：注册关闭后如何创建下一个账号，靠管理员手动重置密码，不做邀请码。

### 12.4 验收

| 项 | 命令 / 证据 |
|---|---|
| 后端 | `python -m unittest discover -s tests -p "test_*.py"`：471 条通过（新增 `test_instance_admin` 9 条、`test_bank_members_p4` 4 条） |
| 组件与契约 | `npm --prefix frontend run test:unit`：35 文件 / 334 用例（新增 `instance_admin_view` 10、`settings_sessions` 7、`bank_collab_view` 11、`banks_sections_view` 6） |
| 多用户真实浏览器 | `node frontend/tests/p4_collab_e2e.mjs`：首位用户即管理员 → 所有者建库并共享 → 编辑者加题、不能管理成员 → 陌生人整页 403 并返回题库列表 → 所有者用搜索下拉把陌生人加成成员 → 注册开关关闭/开启 → 管理员面列用户与保存开关、非管理员被守卫拒绝 → 重置密码吊销会话 → 会话列表与登出其他设备 |
| 迁移 | 从 v17 生产形态库升级到 v21 成功，`instance_settings` 建表、历史用户保留 |
| 既有链路 | `browser_e2e` 15 步、题库管理/批量/编辑流程/批量管理四套 E2E 全部通过 |
