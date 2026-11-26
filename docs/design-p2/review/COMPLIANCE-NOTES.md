# P2 合规核实记录（人工逐条）

静态脚本 `review/staticcheck.py` 的 CR-27 正则对「跳过」一词有误报。
已对全项目每一处「跳过」逐条人工核实，结论如下。

## 两类合法出现

### A. CR-27 的禁令表述（不是违规）
出现在：`index.html`、`pages/states.html`、`pages/screens/banks.html`、
`pages/screens/review.html`、`pages/screens/workspace.html`、`pages/components.html`

原文形态：「**不存在「跳过 Z」这一项**」「清除一切「跳过 Z」残留表述」。
这是把规则写进设计文档，属于要求而非违反。

### B. 导入重复题处理策略（FN-127，另一个域）
出现在：`pages/screens/import.html`、`pages/flows/import.html`、
`pages/components.html`（导入策略下拉的控件示例）

原文形态：重复题处理策略的三个选项 `跳过重复 / 新建为新题 / 合并`，
以及导入作业结果的「跳过（重复）」计数列。

**这不属于 CR-27 管辖范围。** CR-27 管的是「题库 / 题目的批量操作结果」，
即归档、恢复这类动作的成败计数；FN-127 管的是「导入时遇到重复题怎么办」，
是规格明确承诺的去重策略，删掉它等于删减已承诺能力。

### 待办的表述澄清（不改变语义，只消除误读）
导入作业结果的列头由裸「跳过」改为「跳过重复」，作业汇总由「跳过 N」
改为「跳过重复 N」。语义不变，只是让读者不会误以为是 CR-27 的批量结果。
执行时机：题库域代理交付后由主 Agent 统一改（避免与代理写同一文件冲突）。

## 已修复的真实缺陷

| # | 缺陷 | 位置 | 修复 |
|---|---|---|---|
| 1 | 玻璃拟态 `backdrop-filter: blur(10px)`（合同禁止） | `pages/screens/practice.html` `.focus-topbar` | 改为实色 `background: var(--d-gasket)` |
| 2 | 同上 | `pages/screens/exam.html` `.exam-topbar` | 同上 |
| 3 | 死链 `pages/palette.html` | `index.html` | 改为 `pages/screens/palette.html` |
| 4 | `.notice-actions` 不换行，窄宽度按钮溢出 | `assets/ee.css`（设计系统源头） | 加 `flex-wrap: wrap` |

## 已知且有理由的例外

| 项 | 说明 |
|---|---|
| `pages/screens/login.html` 无 `.skeleton` | 登录页的加载态是「提交中」，正确表达是提交按钮 spinner + disabled，整页骨架对登录没有意义 |
| `pages/tokens.html` 含十六进制 | 该页是令牌规范页，十六进制是它要展示的内容本身，不是用来着色的内联值 |
| `pages/flows/*.html` 八态不全 | 流程页展示的是某条路径的关键状态，不是全状态矩阵；全状态矩阵在 `pages/states.html` |

---

## P2 组件提升（消除跨屏复制）

问题：`.state-note` 在 **14 个文件**里各写一遍（6 种变体）、`.state-grid` 在 **10 个文件**里各写一遍（4 种变体，minmax 分别是 300/320/280/260px），`.flow-*` 流程布局在 5 个流程页各写一遍，`.mt-4`/`.mt-5`/`.mb-4`/`.menu-anchor`/`.sheet-legend` 同样多份。这违反 CONTRACT「禁止重新定义控件」。

处置：新增 `assets/ee.css §15 共享模式（唯一实现）`，收录 23 条，并从 18 个屏/流程页剥离本地副本（共剥离 89 处）。两条漂移规则先统一再剥离：
- `.state-grid` → `repeat(auto-fit, minmax(min(300px, 100%), 1fr))`（加 `min()` 兜底，容器窄于 300px 也不再溢出）
- `.state-note` → 统一为 `font-size/text-xs; color/ink-3; line-height/xs-lh; margin: sp-3 0 0`
- `.doc-page` 原为硬编码 `max-width:1100px; padding:28px 24px 60px`，改为令牌 `var(--page-w)` / `var(--sp-7) var(--sp-6) var(--sp-10)`

复验：14 个产品屏 + 5 个流程页 × 4 宽度（1440/1024/768/375），全部无横向滚动、无控制台错误；`.state-grid` 与 `.state-note` 的计算值已确认来自 ee.css。

## P2 store.js 修正（共享数据层，主 Agent 拥有）

| # | 缺陷 | 修复 |
|---|---|---|
| 1 | `can('instance.manage')` 用**题库角色** OWNER 判定，把实例角色与题库角色混为一谈（PI-01/GAP-413） | 新增独立 `state.instanceRole`（admin/user）；`instance.manage` 只按它判定，并新增 `isInstanceAdmin()` / `instanceRole()`；`denyReason` 补充「实例管理员身份不会自动给你任何题库的访问权」 |
| 2 | 复习队列种子只有 5 行，且没有一行同时「到期 ∧ 薄弱」，导致待复习视图的「薄弱」原因 chip 恒为 0 | 补 rq6（due+weak+mistakes 三因叠加）、rq7（due+weak）、rq8（due）；今日待复习从 2 变 5、复习总计数从 5 变 8，四视图的理由分布有了代表性 |
| 3 | `reflowRow()` 的到期时间是写死的 `2026-11-13/14/16`（相对当前日期已成过去），与界面按稳定度实时推算不是同一套模型 | 改为与界面同一模型：稳定度表 `{1:1.2, 2:1.8, 3:2.4, 4:3.1}` × 基准 `{1:0.5, 2:1.2, 3:2.6, 4:5.0}`，按今天起算，新增 `datePlusDays()` 助手 |

---

# P2 独立视觉审查 · 发现与处置

两位未参与设计的独立审查员（一位管产品语义与 IA，一位管视觉质量与跨端）真实渲染后交回清单。两人总体判断一致：**可进入 P3**，结构性规则全部落地，问题集中在成片的系统性小项。逐条处置如下。

## 已在主 Agent 层修掉（`assets/ee.css`，一次修好多屏）

| # | 审查发现 | 处置 |
|---|---|---|
| V1 | `exams.html` 375/768 考试档案行：`.list-side`（250px）把 `.list-main` 压到 77px，标题折成 5 行每行 6 字 | `≤640` 增加 `.list-row{flex-wrap:wrap}` + `.list-main/.list-side{flex:1 1 100%}`，提升进 ee.css。**这是唯一被标为阻塞的可见破损** |
| V2 | `.topbar` / `.mobile-top` 仍带 `backdrop-filter: blur(10px)`（CONTRACT §3 禁玻璃拟态；自查记录说已修但只修了 runner 两个） | 两处删除，改纯色 `background: var(--d-gasket)`。全项目 `backdrop-filter` 现为 0 |
| V6 | 长文行宽未收口：`.notice-body` 实测 142–148ch、`.explain-body` 700px / 56 汉字一行，`--measure: 68ch` 令牌存在却只有 notes 阅读器用 | `.notice-body`、`.explain-body`、`.doc-rule`、`.tsec-desc` 加 `max-width: var(--measure)` |
| V9 | 亮色主题侧栏次级文字 4.16:1（`--d-spine-ink-3` #7b8377，12px），`.nav-count` 个别 3.44:1，`.crumb .sep` 4.11:1 | `--d-spine-ink-3` → `#8a9186`（实测 5.03:1）；`.crumb .sep` 由 `--ink-4` 改 `--ink-3` |
| V11 | `pointer:coarse` 触屏白名单漏 `.link-btn`（19–21px）、`.user-mini`（30px）、`.set-item`（37px）、flow `.step`（28px） | 白名单补 `.link-btn, .user-mini, .set-item, .step, .plan-row, .link, .check` |
| M3 | `.steps .step` 按钮 reset 在 `exams.html` 与 `flows/exam.html` 重复定义 | 提升进 ee.css，5 个流程页本地副本已剥离 |
| S24 | 侧栏「复习」角标跨屏不一致（home 5 / settings 8 / exams 21）：`nav.js` 用 `reviewQueue().length`（全部行），home 用 CR-05 可执行集合 | store.js 新增 `executableReview()`（CR-05：到期 ∧ 未斩杀 ∧ 未归档 ∧ 有访问权），`nav.js` 改用它，全产品一个口径 |

## 已在主 Agent 层修掉（文档）

| # | 审查发现 | 处置 |
|---|---|---|
| S2 | `states.html` 断点表写「641–768 小平板｜侧栏图标轨 + 底栏同时可用」，直接违反 CR-28「底部导航与侧栏不得并存」，且与 70 册 §6 的 641–1024 分段冲突 | 该行改为「侧栏隐藏，底部导航 6 项」，并补一段裁定：**断点取 768 为唯一判据**（>768 侧栏可见，≤768 侧栏隐藏由底导接管），文档以 `ee.css` 的实现为准 |
| S8 | 资料类型用 tabs 表达过滤条件，踩 IA 自己的禁令；IA §五 却又给 FN-501 标 `P+T`，设计权威文件自相矛盾 | IA 文档 FN-501 载体改 `P+S`，并把这条载入 §六 变更记录；屏幕改造由资料域代理执行 |

## 已在主 Agent 层修掉（术语与 typo，共 44 处）

00 册 §7 术语表禁用词清剿：**错题本→错题**（19 处 / 8 文件）、**正确答案→标准答案**（14 处）、**题库管理员→题库所有者**（3 处）、**含附件→有上传文件**、**场次→考试**、**对错标记→判分结果**、**填写参考答案→填写标准答案**；typo **留在境中→留在屏中**（4 处）；重写 home 403 空态那句不通的「历史作答与错题仍归你回看」。

## 派回域代理执行（文件归属在其域）

| # | 审查发现 | 归属 |
|---|---|---|
| S1 | **FN-203 开始面板缺「本次学习参数」上段**（只有活跃会话决策下半段 + 三个只读 kv，用户无法在开始前调范围/数量/题型/章节标签/模式）——规格自己把它列为必须补齐项，且是产品最高频控制的半成品 | 学习域 |
| S6 | `diagnosis.html` 学习记录表有死复选框 + 「回看」只 toast（P-7 有控件无出口） | 学习域 |
| S9 | home 侧栏「学习状态」四项是死数字，FN-201 理想态 ③ 要求可点 | 学习域 |
| V7 | `practice.html` ≤768 把答题卡整段 inline 堆到纸面下方，而 `exam.html` 正确地用底部抽屉——同一产品两个 runner 两种交互 | 学习域 |
| S7 | 不限时会话缺 CR-31 末段的「连续 30 天无活动失效并告知」 | 模考域 |
| S10 | `banks.html` 批量条缺「M 项当前不可见」标注，而 workspace/review 都有 | 题库域 |
| S8' | `notes.html` 资料类型 tabs → segmented；`settings.html` 窄屏左轨横向滚动且激活项不可见、无标签 skeleton | 资料设置域 |
| V8 | 规格文案漏进产品屏（notes/review/diagnosis/instance/forbidden），12px 满宽长行把产品屏拉成文档页 | 各域（包进 `data-spec` 或翻成用户语言；**注意 FN-421 的控件旁可读原因必须留在产品里**，只有设计理由说明才进 data-spec） |
| S2' | `instance.html` 两处实例权限门禁仍用 `?denied=1` 绕过，未接主 Agent 新加的 `eeStore.isInstanceAdmin()` | 协作域 |

## 核实后不成立 / 有理由保留

| # | 审查发现 | 结论 |
|---|---|---|
| V10 | `tokens.html` 深色色板「hex 标签印在色块上（2.54–2.92:1）」 | **不可复现**。`.sw-hex` / `.sw-name` 在 CSS 里是 `.sw-chip` **下方**的独立元素（`pages/tokens.html:85-88`），不是压在色块上。用 `review/contrast.py` 对四套配色 × 明暗的 `--ink-3`/`--ink-4` on `--surface` 逐组实测，最低 5.16:1，**全部通过 AA**。审查员很可能测到了色块边框或相邻元素 |
| V9' | 同上，侧栏次级文字 | **成立，已修**（见上表） |
| S14 | 演示数据跨屏自相矛盾（侧栏角标 5/8/21 等） | 角标部分已由 `executableReview()` 统一；其余演示值是各域屏内样例，`docs/IA-AND-OWNERSHIP.md` §5 已要求「数字日期用真实感样例」，跨屏完全一致需要真实数据源，属 P3 事项 |
| S17 | `.select` caret 用两个 4px `linear-gradient` 画三角 | 是画图标不是装饰渐变，属探测误报，不改 |
| S15/16/18 | flow `.step` 28px、flow stage 375 下 327px、home crumb 与 H1 重复、exam 底部按钮与答题卡统计数字不一致 | 均为演示层细节，其中 flow stage 宽度与 `.doc-page` 令牌化有关，已由 ee.css §15 统一；不影响 P3 |

---

# P2 最终轮 · 域代理修正结果

五位域代理按审查清单各自修完自有文件，主 Agent 复核。

## 各域完成项

| 域 | 修正 |
|---|---|
| 学习 | **FN-203 开始面板补上「本次学习参数」上段**（来源范围/数量/题型/章节标签/模式），默认只显示一行摘要 + 「调整参数」，**参数完整时一键开始，不完整才自动展开**（P-1 三击可达未被破坏）；「纳入学习记录」只对模考暴露；顺带修掉 `openStart` 形参顺序写反导致入口参数从未生效的 bug |
| 学习 | `diagnosis.html` 删掉学习记录表的死复选框列（8 列回 7 列），「回看」改成真实链接（进行中→会话、练习报告→`practice.html?rid=`、模考→`exams.html` 成绩报告区）；为此在 `practice.html` 新增归档报告只读视图，并明确「归档报告只保留汇总计数，逐题明细不重建，缺的就不显示」 |
| 学习 | home 侧栏「学习状态」四项做成可点：今日待复习→`/review`、未完成会话→CR-14 会话选择器、覆盖率与正确率→学习档案（这两项是跨窗口聚合值，唯一能拆开看的地方就是档案页） |
| 学习 | `practice.html` ≤768 统一为 exam 的做法：右栏整段隐藏、底部固定操作区加「移动作答卡」触发、抽屉从底部弹出（scrim/Esc/焦点归还同一套）、快捷键留在纸上。实测 375：`rail=none / trigger=flex / keys=block`，点击后抽屉打开 |
| 学习 | review / practice / diagnosis 三处纯规格句翻成用户语言，原规格句包进 `data-spec`（产品模式自动隐藏） |
| 题库 | `banks.html` 批量条补 CR-27 ②「含当前不可见项 N 项」，三处口径统一；复核批量结果仍只有「成功 X · 无须变更 Y」且 `X+Y=已选 N` |
| 题库 | 修掉 `question.html` 单题归档条件写反（`already === wasArchived` 导致每次都报「无须变更」且从不归档）；修掉冲突对象形状不统一渲染出 undefined；修掉知识点添加按钮有数据后消失；修掉 import 第 1 步 PDF 路径跳错步、`?step=imp-5` 深链渲染静止骨架 |
| 模考 | **不限时会话补上 CR-31 末段「连续 30 天无活动失效并告知」**：开始前确认条件化一行、宽限态 rail 对照块、退出/多设备态整块「已失效」+ 通知位置 + 四行 kv、模考中心 `isExpired()` 行徽标与「去交卷」主动作、流程页同步 |
| 模考 | 修掉 exam.html 宽限/已收卷态静态题目与会话实际停靠题号不符、静态答题卡待复查标记与 `DEMO_FLAGS` 不符、交卷确认「已答 23」与实际 10 不符、报告未答行与 runner 脚本作答矛盾 |
| 协作 | `instance.html` 修掉两个真实缺陷：**768 下 7 列表格超出容器 122px、操作列被无声裁切且无滚动条**（加 ≤1024 压缩块）；375 下 `.lock-inline` 继承 `nowrap` 把禁用原因从词中间截断 |
| 协作 | 删掉/收编产品屏里的规格说明（表下三段行级规则、forbidden 的 URL 参数说明）；实例级 403 门禁改读真实的 `eeStore.isInstanceAdmin()`；`?denied=1` 退化为审查用覆盖 |
| 资料设置 | `notes.html` 资料类型 tabs → segmented（与 IA §三 载体表对齐） |
| 资料设置 | `settings.html` 窄屏左轨收起为分段行（768/375 实测无裁切、「关于」分组独立成行）、「设备与会话」的无标签 skeleton 移入带标签的状态格 |

## 主 Agent 补充提升（本轮新增）

| 类 | 文件数 | 说明 |
|---|---|---|
| `.mt-2` / `.mt-3` / `.mt-8` | 4 / 8 / 3 | 间距档收敛进 ee.css §15，剥离 14 处本地副本 |
| `.step.is-skip` | 1 | 步骤条第三态（`.is-active` / `.is-done` 之外的「不适用」），PDF 路径步骤划掉降色而非假完成 |

## 最终全量验证

**26 个页面 × 4 档宽度 × 明暗两套 = 208 个渲染组合，全部零问题**：无横向滚动、无控制台错误、无未捕获异常。
页面集合：16 个产品屏 + 5 个流程页 + tokens/components/states 三份规范页 + index 入口。

专项实测：
- FN-203 开始面板：`来源范围 / 未做过 / 数量 / 题型 / 章节或标签 / 模式 / 调整参数 / 开始` 八项齐备，「纳入学习记录」元素存在且仅模考暴露
- practice 375：`focus-rail=none`、`sheet-trigger=flex`、`keys-paper=block`，点击「移动作答卡」后 `.drawer` 正常打开
- 令牌对比度：四套配色 × 明暗的 `--ink-3`/`--ink-4` on `--surface` 逐组实测，最低 5.16:1，全部通过 AA；侧栏次级文字修后 5.03:1
- 禁用词：全项目 0 残留（错题本/正确答案/题库管理员/库管理员/留在境中/含附件/场次/对错标记/填写参考答案/附件）
- `backdrop-filter`：全项目 0 处

## 仍未解决（移交 P3，均非设计缺陷）

1. `store.js` 的 `finishSession` 报告只带汇总计数，无逐题明细与评级 → 归档报告页无法重建逐题表格。**数据形状问题，需 store owner 补字段。**
2. 模考报告深链 `/exams/:id/report` 归考试域，练习域只能落到模考中心成绩报告区。
3. `localStorage` 在 `file://` 下按文档隔离，`?rid=` 深链只能读同一份持久化 state；接真实后端后走服务端路由。
4. 注册开关的跨屏一致性是原型层 `localStorage['eeInstance.allowRegistration']` 直连；产品实现应为服务端 `instance_settings` 单源。
5. 实例用户表 ≤1024 省去注册时间同年份、「题库数（含所有）」省去括注（完整语义在表上方说明句里）；跨多年实例需把 `.yr` 加回，一行 media query 即可。
6. 学习档案的历史趋势用明确标注的本地样本载荷，等学习记录接口落地后替换。
7. 演示数据在各屏是屏内样例（侧栏角标已由 `executableReview()` 统一，其余跨屏完全一致需真实数据源）。
