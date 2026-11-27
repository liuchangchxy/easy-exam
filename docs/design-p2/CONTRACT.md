# EasyExam 设计规范 · 屏幕构建合同（Frozen Contract v2 · P2）

所有屏幕与流程页面必须遵守本合同。合同的文件基础：

- `assets/ee.css` — 设计系统唯一来源（令牌 + 控件 + 外壳 + 学习域组件）
- `assets/icons.js` — 图标符号表（`<svg class="od-icon"><use href="#i-name"/></svg>`）
- `assets/spec-boot.js` — 规格引导（应用 URL 主题参数、iframe 自动高度、对话框/菜单/分段/toast 助手）
- **`docs/IA-AND-OWNERSHIP.md` — 信息架构与 FN 归属矩阵（页面树、载体规则、八态矩阵）。本合同的语义上层，先读它再写屏。**

## 1. 文件骨架（每个屏幕页必须如此开头）

```html
<!DOCTYPE html>
<html lang="zh-CN" data-theme="light" data-theme-palette="editorial">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>屏幕名 · EasyExam 设计规范</title>
<link rel="stylesheet" href="../../assets/ee.css">
<style>
  /* 仅允许：本屏特有的、ee.css 未覆盖的布局微调；禁止重新定义令牌与控件 */
</style>
</head>
<body>
<a class="skip-link" href="#main-content">跳到主内容</a>
<div class="app-shell">
  <aside class="sidebar">…侧栏（按屏幕宽度规则渲染，见 §4）…</aside>
  <div class="app-main">
    <header class="topbar">…顶栏（桌面）…</header>
    <header class="mobile-top">…移动顶栏…</header>
    <main class="content" id="main-content">…屏幕主体…</main>
  </div>
</div>
<nav class="bottomnav">…底部导航（仅 ≤768 显示，CSS 已处理）…</nav>
<script src="../../assets/icons.js"></script>
<script src="../../assets/spec-boot.js"></script>
<script>
  /* 本屏交互：tab 用 data-panel/data-tab-panel；对话框用 eeDialog.open/close */
</script>
</body>
</html>
```

注意：`screens/*.html` 与 `flows/*.html` 的相对路径是 `../../assets/`。`data-theme` / `data-theme-palette` 的初始值由 spec-boot 按 URL 参数覆盖，写上初始值只是防闪烁。

## 2. 外壳渲染规则（同一套 DOM，CSS 负责三档）

- 侧栏 `.sidebar`：品牌区（`.side-brand` → `.brand-mark`「易」+ `.brand-text`）+ 分组标签「学习」+ `.side-nav` 五项（今天/题库/复习/模考/资料，当前项 `aria-current="page"` 与 `.is-active`）+ `.side-study` 学习状态块 + `.side-foot`（设置）。≤1024 CSS 自动收成仅图标。
- 顶栏 `.topbar`：`.crumb` 面包屑（父级/当前，父级为 `button.link`）+ spacer + 搜索/主题/语言 `.icon-btn` + `.user-mini` 头像按钮。
- 移动顶 `.mobile-top`：返回 `.page-back` 或 `.brand-mark` + `.mt-title` + 搜索 + `.user-mini` 头像按钮（`data-menu-trigger` + `.menu-anchor` 账户菜单，全产品同一形态：可点击、有可访问名称「账户菜单」）。
- 底部导 `.bottomnav`：5 项（今天/题库/复习/模考/资料），当前项 `.is-active`。**没有第六格**——原「更多」是只开不动的死按钮，已删除。
- **「设置」在手机端的唯一入口是账户菜单**（移动顶栏与桌面顶栏的头像按钮）：侧栏在 ≤768 整块隐藏，账户菜单里必须有「设置」项。桌面端侧栏 `.side-foot` 仍保留「设置」。
- **面包屑必须表达真实层级**：`题库 / 题库名 / 第 12 题`；`题库 / 设置` 这种与页签重复的说明不要。
- 全屏 runner（练习/模考）不用 `.app-shell`，用 `.focus-shell` 结构（见 ee.css §12）。

## 3. 控件使用规则（唯一实现）

| 需求 | 只用 |
|---|---|
| 按钮 | `.btn` + `.btn-primary` / `.btn-quiet` / `.btn-danger` / `.btn-sm` / `.btn-block` |
| 图标按钮 | `.icon-btn`（+`.sm`），图标 `<svg class="od-icon"><use href="#i-x"/></svg>` |
| 文字链 | `.link-btn` |
| 输入 | `.field > .label(+.req) + .input/.textarea/.select + .hint/.field-err` |
| 搜索 | `.search-box > svg + .input` |
| 复选 | `.check > input[type=checkbox] + 文字` |
| 标签/徽章 | `.tag`（+`.brand/.ok/.warn/.bad/.plain`） |
| 分段 | `.segmented[role=radiogroup] > .segment[role=radio][aria-checked]` |
| 视图页签 | `.tabs[role=tablist] > .tab[role=tab][aria-selected][data-panel]` + `[data-tab-scope]` 容器内 `[data-tab-panel]` |
| 面板 | `.panel > .panel-head(.panel-title) + .panel-body` |
| 页头 | `.page-head > (.page-eyebrow + .page-title + .page-sub) + .page-actions` |
| 列表行 | `.list-row`（+`.dense/.is-active/.static`）> `.list-main(.list-title+.list-meta) + .list-side` |
| 统计 | `.stat-row > .stat(.stat-num + .stat-cap)` |
| 空态 | `.empty > .empty-mark + .empty-title + .empty-desc + .empty-actions` |
| 骨架 | `.skeleton` + `.sk-line`/`.sk-block` |
| 进度 | `.progress > .progress-fill[style=width:%]` |
| 通知 | `.notice`（+`.info/.ok/.warn/.bad`）> svg + `.notice-body` |
| 瞬态提示 | `eeToast('文案')`（不要手写 toast DOM） |
| 对话框 | `<dialog class="dlg [wide|narrow|danger]"> .dlg-head(.dlg-eyebrow+.dlg-title) + .dlg-body + .dlg-foot`；开：`eeDialog.open('id', trigger)`；关：按钮加 `data-dlg-close` |
| 抽屉 | `.drawer-scrim + .drawer(.drawer-head+.drawer-body+.drawer-foot)` |
| 菜单 | `.menu > .menu-item`（挂 `[data-menu-trigger]` 的按钮切换 `menu.hidden`） |
| 表格 | `.dtable-wrap > table.dtable`；每个 `<td data-label="列名">`（640 转卡片用） |
| 步骤条 | `.steps > .step(.step-n) + .step-line` |
| 批量条 | `.bulkbar` |
| 答题选项 | `.opt(.opt-key + 文本 + .opt-mark)` + `.is-selected/.is-correct/.is-wrong` |
| 作答卡 | `.sheet-grid > .sheet-cell` + `.is-answered/.is-current` |
| 计划行 | `.plan-row(.plan-index + .plan-title/.plan-meta + .plan-arrow)` |
| 计时 | `.timer`（+`.low`） |
| 键帽 | `.kbd` |
| 筛选 chip | `.chip-row > .chip(.count)` |

**禁止**：发明新控件形态、渐变、玻璃拟态、霓虹、大圆角（>4px）、卡片套卡片、每标题配图标、hover 变灰、内联 style 做布局（除 `.progress-fill` 宽度与 `.sheet-cell` 等必要动态值）。

## 3.1 批量结果口径（CR-27，全产品唯一）

- 整批拒绝：零写入，必须给出**可读的拒绝原因**（`.notice.bad`）。
- 整批执行：只报「**成功 X · 无须变更 Y**」两项，`X + Y = 已选 N`。
- **不存在「跳过 Z」**。「已经处于目标状态」是无须变更，不是校验失败。
- 归档/恢复四种情形：归档+未归档→执行；归档+已归档→无须变更；恢复+已归档→执行；恢复+未归档→无须变更。

## 3.2 考试会话三段式（CR-31，全产品唯一）

作答窗口 → **宽限 60 秒**（仅同步，网络恢复后补交）→ 服务端收卷。
「作答窗口结束」**不是**会话终止；宽限期内用户仍看到「已收卷/宽限中」状态，不得显示成失败。

## 3.3 权限表达（CR-12 两向规则，全产品唯一）

权限**改变能力，不改变结构**；表达方式按「相关性」分流。判据只有一句：**这个入口说的事，对这个用户有意义吗。**

- **与当前用户相关、但此刻不可用 → 禁用并解释**（置灰 + 可读原因，`.hint`）。
  例：成员看到「编辑题目」「批量维护」「导入」；可练量为 0 时的「开始练习」；编辑者看到「归档题库」。
- **与当前用户完全无关的管理入口 → 不渲染**。
  例：普通用户看不到实例管理入口；普通成员看不到「题库设置 / 归档题库 / 删除空库」。
- 成员名单对所有人可见（能看到谁在协作、自己的角色是什么），但增/改/移除/转移所有权对所有非所有者禁用并解释。
- 403 两种变体都要设计：
  - **看不到**（对象不存在或无访问权）→ 整页 `.empty`，403 语义；
  - **看得到但不能操作**（有读权限无写权限）→ 控件禁用 + `.hint` 原因。
- **不得**用顶部英文 banner 或错误码当作唯一反馈；后端 403 的 `detail` 必须转成中文可读呈现。

> P2 曾把本条简化为「入口一律禁用而非隐藏」，导致普通成员满屏与自己无关的管理控件，属产品语义退化，已按 P1 CR-12 恢复。
> 实现：`assets/store.js` 的 `can(action)`（能不能做）与 `relevant(action)`（跟这个用户有没有关系）分工，页面按两者分别渲染。

## 3.3b 统一纸面构图（P2 收口）

全产品普通页面共用**同一张纸**：同一个宽度（`--d-max` 1120px）、同一条左边界、同一份外边距、同一套基础内容网格。
页面之间的功能差异一律在纸面**内部**用排版解决（分栏、密度、宽表自滚、次要信息下沉），**不得改纸张规格**；
切换页面时空间秩序保持稳定。`.wide` 只作语义标记，不再改变纸面宽度（原 P2 曾让三个页面宽 44px 且整张左移 22px，已收敛）。
**例外**（确有特殊需求，可不套用本纸面）：登录页、全屏练习与模考 runner（`.focus-shell`）。
不强制固定纸张高度或 A4 比例。窄幅 `.content.narrow` 与 `--d-max-wide` 已废除。

## 3.3c 本期不提供的功能不得进入产品界面

已裁定「本期不做」的能力（FN-113 历史作答重判、FN-509 AI 建议标签与蓝图等）**不得**在最终产品界面出现占位入口、
未实现说明或设计阶段解释文字。规格记录留在 `docs/product-spec/`。
判据看**产品模式渲染后的可见文本**（`data-spec` 包裹的内容在产品模式不可见，不算违规）。
确有告知必要的，只保留产品语义本身需要的部分：FN-113 保留的是「报告按题目版本判分，永久不可变」这一事实陈述与
「查看该题当前版本」入口，而不是「本期不提供重判」的免责声明。
规格编号（`FN-xxx / CR-xx / BR-xxx`）同样属于设计阶段解释文字：流程页脚注、规则标签、面板副标题里出现的，
一律改写成产品语言。判据必须**逐步走查流程的每一步**再扫可见文本——只加载首页会漏掉后段步骤的页脚注。

## 3.4 复习四视图（CR-29，唯一）

`/review` 只有四个视图：**待复习 / 错题 / 薄弱 / 斩杀**。
「全部」与「到期」是同一集合，**不是两个页签**。「学习档案」是独立路由 `/review/diagnosis`，在 `/review` 页头给入口，不做第五个页签。

## 4. 三档与八态要求

- 同一 DOM 三档自适应；不得出现横向滚动（宽表用 `.dtable-wrap` 自滚，≤640 自动转卡片）。**断点四宽实测：1440 / 1024 / 768 / 375**。
- 每个屏幕必须呈现的"状态格"——**八态**：
  | 状态 | 表达 |
  |---|---|
  | 空 | `.empty`（说明**为什么**空 + 下一步 CTA） |
  | 加载 | `.skeleton`（与真实内容同构） |
  | 错误 | `.notice.bad` + 重试按钮 |
  | 禁用 | 禁用控件 + `.hint` 可读原因（入口不隐藏） |
  | 无权限 | `.notice.warn` 或整页 `.empty` + 403 语义（两变体） |
  | 冲突 | `.notice.warn` + 「查看我的版本 / 使用对方版本」 |
  | 未配置 | `.notice.info` + 去配置的链接 |
  | 离线 | 持久标识 + 队列计数 + 重试 |
  用同一屏幕内的不同面板/切换呈现，或用小号"状态"面板并列展示。
- 点击目标 ≥44px（`pointer:coarse` 已由 CSS 兜底大部分）；焦点态用 `:focus-visible`（已全局）。
- 对比度：正文 ≥4.5:1；大字号/图标 ≥3:1。明暗两套都成立（CSS 令牌已保证，不要用十六进制绕过）。

## 5. 内容规则

- 文案用产品真实措辞（参考 `frontend/src/locales/ep-zh-CN.js` 的键与中文值；术语如「到期复习 / 错题重做 / 斩杀题库 / 模考 / 题库工作区」须与产品一致）。
- 题目内容用 `assets/sample-questions.json` 中的真实软考真题（可直接内联为 HTML，不必 fetch——file:// 下 fetch 被禁）。
- 数字、日期、用户名用真实感样例（如 `accept_admin_1794570360969`、`验收题库 1794570360969`、2026-11-13 第 46 周），不虚构指标。
- 中文为主；登录与设置两屏附英文规格段（`lang="en-US"` 的容器，文案用产品 en-US 词典的同键译法）。

## 6. 交互规则

- tab 切换：`.tab[data-panel]` + `[data-tab-scope]` 祖先 + `[data-tab-panel]` 面板；spec-boot 已实现切换逻辑，**不要自己写 tab JS**。
- 分段：`.segmented > .segment` 点击切 `aria-checked`，spec-boot 已实现。
- 对话框：`<button data-dlg-open="id">` 不对——用 `onclick="eeDialog.open('id',this)"` 或等价的 addEventListener；关闭按钮加 `data-dlg-close`。
- 菜单：触发器加 `data-menu-trigger`，菜单 `.menu[hidden]`；spec-boot 处理 Escape/外部点击/方向键。
- 反馈：保存成功 `eeToast('已保存')`；持久结论用 `.notice`。
- 演示性交互只允许：tab、分段、菜单开闭、对话框开闭、抽屉开闭、选项选中态切换、toast。**不模拟网络请求**。

## 7. 每屏必备内容（来自域勘察，逐项落实）

见各屏任务书。通用必备：
- 面包屑/页头层级正确；`document.title` 由 `<title>` 表达。
- 该屏全部弹窗/抽屉/菜单至少各出现一次（可在"浮层"状态格中并列展示）。
-  runner 屏（练习/模考）必须含：顶栏（退出/模式/计时/交卷）、纸张区（题干/选项/反馈）、右栏或抽屉（进度/作答卡/快捷键）、底部操作条、以及"进行中 / 已交卷报告 / 空 / 加载失败"四态。

## 8. 交付前自检（写完后逐条过）

1. 无横向滚动（**1440 / 1024 / 768 / 375** 四宽）。
2. 无十六进制颜色、无 px 间距/字号硬编码（令牌之外）；无渐变、玻璃拟态、霓虹、>4px 圆角。
3. 图标全部来自符号表；语义名正确（import=入、export=出、archive=归档、restore=撤销、trash=删除）。
4. **八态齐备**：空/加载/错误/禁用/无权限/冲突/未配置/离线；空态说明「为什么空」。
5. 对话框只有 `.dlg` 一种形态；确认按钮次序统一。
6. 焦点可见；Escape 可关所有浮层；对话框关闭回焦。
7. 中文文案与产品术语一致；无虚构指标。
8. **批量结果只有「成功 X · 无须变更 Y」**，`X+Y=已选 N`，无「跳过 Z」；整批拒绝零写入 + 可读原因（CR-27）。
9. **考试三段式**：作答窗口 → 宽限 60 秒 → 服务端收卷；「作答窗口结束」不画成失败（CR-31）。
10. **复习只有四视图**：待复习/错题/薄弱/斩杀；「全部」与「到期」不同时出现；学习档案是独立路由（CR-29）。
11. **权限表达按相关性分流**：相关但不可用 → 禁用 + 可读原因；完全无关的管理入口 → 不渲染；403 两变体都设计（CR-12 / FN-421）。
12. **普通页面同一张纸**：宽度、左边界、外边距、基础网格一致，功能差异只在纸面内部解决；例外仅登录与全屏 runner（§3.3b）。
13. **本期不提供的功能不出现在产品界面**：产品模式可见文本里没有「本期不提供 / 未实现 / FN 编号 / P3」之类（§3.3c）。
14. **历史报告与交卷当次报告内容一致**：逐题明细、作答结果、解析、评级、判分版本、回看入口都有，且明确区分历史快照与当前版本。三处报告（练习交卷态、模考交卷态、模考归档回看）共用 `assets/report.js` 的同一套 `.rep-*` 渲染与展开交互，不得各写一份；交卷时把 `total` 与 `items` 一并写进报告。报告里没有逐题快照时（老数据，CR-25 不可重算）**不得用演示数据冒充用户的作答**，明说没有明细可回看。列表行与详情对话框对同一指标给同一个值，早期报告缺分母时两边都显示「—」，不允许一边算一边不算（CR-06 / BR-109 / CR-25）。
15. **没有 AI 也要完整可用**，每个 AI 入口有非 AI 替代路径（P-8 / FN-518）。
16. 面包屑表达真实层级，不与页签重复。
17. 已用浏览器真实渲染并**实际看过图**，不是只读源码。
18. **表格不得被自身内容顶出容器**：表头与单元格必须可折行/可断词（`overflow-wrap`），否则长表头或长 token 的 min-content 宽度会成为表格最小宽度，把行内操作裁到横向滚动里。列数多于纸面放得下时（步骤条同理）必须留可发现的滚动，不许静默裁掉。
19. **对话框结构必须完整闭合**：`.dlg-head > .dlg-head-text` + 关闭按钮，再 `.dlg-body`、`.dlg-foot`。少一个 `</div>` 会让 body/foot 沦为 head 的子元素——head 是 flex row，内容会被横排成不可读的窄列。
20. **文字层级靠六维组合，不只靠加粗**：页面标题 / 章节标题 / 次级标题 / 正文 / 辅助信息五级，每一级在 字号 × 字重 × 字体 × 颜色 × 行高 × 留白 上至少有三维不同。只用 `font-weight` 区分的标题算不达标。衬线只给长文阅读位（页面标题、章节标题、题干、解析、资料正文），控件与界面 chrome 用无衬线；等宽只给数字与编号。
21. **细分隔线必须承担结构意义**：新增每一条线都要能说出它分开了什么。能靠留白、对齐、字重替代的一律不加。已删除的重复线不要加回来：面板外框、表格外框、统计带下边线、通知四边框、报告列表上沿线。保留的是页签基线、章节标题下沿线、表头下沿线、列表行间线、列间竖线、列分线。
22. **纸内布局用既定模式，不各写网格**：`.lay-stack` / `.lay-main-side` / `.lay-side-main` / `.lay-two` / `.lay-three` / `.lay-four` / `.lay-read` / `.lay-toolbar`。页面按任务选模式；确需新形态先在评审里说明理由。不得用统一 CSS 数值代替真正的视觉设计。
23. **文案是产品语言，不是规格说明**：界面能表达的信息不用文字重复；短句能表达的不写长段；只在用户要做决定时才给规则 / 风险 / 影响说明。不解释为什么某个功能没被设计出来。不暴露规格编号、实现细节、演示说明、开发限制。按钮命名、状态名称、反馈文案全产品统一，同义不同词算不达标。
24. **桌面与手机各自为自己的输入方式设计**：手机不是桌面缩窄——底部导航五个主入口、移动顶栏不与正文重复标题、高频操作单手可触、专用移动列表、筛选用底部弹层、软键盘不遮主操作（`--kb-inset` / `data-kb`）。桌面要发挥键盘鼠标：快捷键按题型动态适配且不拦截系统快捷键与输入法组合、浮层按可用空间展开、批量与选择范围表达完整。平板只做响应式过渡，不建第三套界面。
25. **高频路径操作成本最低**：答题、下一题、解析、评级四步的点击次数与视觉权重必须明显优于同屏其他操作；一屏至多一颗 `.btn-hero` 主操作；判分后不再弹重复结果的 Toast；开始学习、继续学习、切换题库一步可达。
26. **每个页面与每个状态分支都必须实际渲染出内容**：`#q-body` / `#q-state` 这类「二选一显隐」的容器，
    任何分支都必须落到「看得见的那一个」上——不允许两边都 `hidden`，那会只剩一个空框，而它**不报错**。
    键名对不上、兜底分支漏写，都会造成这种静默空白。验证必须逐变体打开（含无参数、参数无效、
    深链指向不存在对象）并确认有内容，不能只查横向溢出与控制台错误。

## 9. P2 成品级打磨轮的全局规则

本轮在 Direction D 与四条全局规则之上追加五条，全部为跨页面共性问题：

1. **字号阶梯 v4**：全站字号整体上移一档（辅助 12.5 / 控件与表格 13.5 / 正文 14.5 / 阅读正文 16.5 / 小节标题 18.5 / 题干与抽屉标题 21 / 区块标题 25 / 页面标题 30）。长时间阅读题干、解析、资料的舒适度是硬指标。
2. **控件高度 v4**：`--ctl-h 36`（按钮 / 输入 / 菜单项）、`--ctl-h-sm 32`、`--ctl-h-lg 42`。`pointer:coarse` 兜底仍为 44。
3. **细分隔线治理**：见自查 21。
4. **纸内布局模式**：见自查 22。
5. **产品模式只见产品**：设计阶段工具（角色切换、覆盖范围清单、重置数据、规范入口、状态格）一律用 `data-spec` 包裹，产品模式不可见；`?spec=1` 仍可查看。

P2 与 P3 的边界、15 项源码问题的逐项归属见 `review/P3-HANDOFF.md`。
