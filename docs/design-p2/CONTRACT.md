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
- 移动顶 `.mobile-top`：返回 `.page-back` 或 `.brand-mark` + `.mt-title` + 搜索 + 头像。
- 底部导 `.bottomnav`：6 项（今天/题库/复习/模考/资料/更多），当前项 `.is-active`。
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

## 3.3 越权表达（FN-421，全产品唯一）

入口**禁用而非隐藏**，禁用控件旁必须给出可读原因。403 两种变体都要设计：
- **看不到**（对象不存在或无访问权）→ 整页 `.empty`，403 语义；
- **看得到但不能操作**（有读权限无写权限）→ 控件禁用 + `.hint` 原因。

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
11. **越权禁用不隐藏**，403 两变体都设计（FN-421）。
12. **没有 AI 也要完整可用**，每个 AI 入口有非 AI 替代路径（P-8 / FN-518）。
13. 面包屑表达真实层级，不与页签重复。
14. 已用浏览器真实渲染并**实际看过图**，不是只读源码。
