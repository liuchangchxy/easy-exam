# P2 第五轮 · 共享规则（五个域共同遵守）

基线 `6c4c7e4`。本轮目标不是重做视觉，而是把**交互一致性、可供性、空间连续性、
完整国际化、连续任务**这五件事收敛到一套共享实现上。视觉方向（Direction D）、
P1 冻结规格、已完成的成果全部保留。

## 0. 硬约束

- 只改 `docs/design-p2/`。不改生产代码、不改 P1、不合并 main、不进入 P3。
- 不新增产品功能。所有改动是「让已有设计真的成立」。
- 每个域只改自己名下的文件。**跨域需要的共享层改动写在报告里交回主 Agent**，
  不要直接改别人的文件（并行编辑会互相覆盖）。
- 新增的用户可见文案，在报告里单独列一张「新增文案」表（中文原文 + 英文），
  主 Agent 汇总进词典。不在报告里的新增文案视为未完成。

## 1. 文件归属

| 域 | 独占文件 |
|---|---|
| A 全局组件与可供性 | `assets/nav.js`、`assets/spec-boot.js`、`pages/components.html`、`pages/states.html` |
| B 空间连续性与导航 | `pages/screens/settings.html`、`pages/screens/notes.html` |
| C 国际化与全局机制 | `assets/i18n.js`、`assets/ee.css` |
| D 学习与模考任务链 | `assets/store.js`、`assets/report.js`、`pages/screens/home.html`、`review.html`、`practice.html`、`exam.html`、`exams.html`、`diagnosis.html`、`pages/flows/*` |
| E 题库资料导入任务链 | `pages/screens/banks.html`、`workspace.html`、`question.html`、`import.html`、`instance.html`、`login.html`、`forbidden.html`、`palette.html`、`pages/tokens.html` |
| 主 Agent | `index.html`、`README.md`、`CONTRACT.md`、`IA-AND-OWNERSHIP.md`、`product.html`、`review/*`、跨域整合 |

`assets/icons.js` 谁都不改；需要新图标在报告里列出名称与路径。

## 2. 交互对象必须用行为属性标识

共享脚本不得凭视觉 class 绑定功能。所有可交互对象在 HTML 上写明行为：

```html
<div class="list-row" data-act="open-question" data-id="q_123" tabindex="0" role="button">
<button data-act="toggle-fav" data-id="...">
```

- `data-act` 的值是**稳定的功能 ID**（英文、kebab-case），不是显示文字。
- 路由、权限、计数、业务判断一律用 `id` / `mode` / `status` 等稳定值；
  禁止 `textContent === '中文'` 这类判断。已发现一处：`instance.html` 用
  `dlg-admin-title` 的文字判断是否设为管理员，本轮必须改成 `data-role-action`。
- 纯展示区域不得带 `cursor:pointer`、hover 位移/变色、或看起来可点的图标。

## 3. 导航选中态按功能域

一级导航的选中由**页面所属功能域**决定，不由文件名决定：

```html
<body data-nav-domain="review">   <!-- review / diagnosis 都属 review -->
```

`nav.js` 读 `data-nav-domain`（缺省回落到文件名映射）。子页面继承父域：
`workspace.html` / `question.html` / `import.html` → `banks`；
`practice.html` / `exam.html` → 分别 `review` / `exams`；
`diagnosis.html` → `review`；`instance.html` → `settings`。

## 4. 视图状态的键必须带作用域

`S.view.save(key, patch)` 的 key 一律写成 `页面:作用域`：

- 题库工作区：`workspace:<bankId>`
- 题库列表：`banks:<scope>`（我的 / 共享给我）
- 资料：`notes:<noteId 或 list>`
- 复习：`review:<tab>:<bankId>`

不同题库、题目、账户的视图状态不得互相污染。跨账户隔离属 P3（账户数据本身未拆分），
但键里必须预留 `:<userId>` 位，P3 接上时不用再改页面。

## 5. 滚动策略（四种进入方式）

| 进入方式 | 行为 |
|---|---|
| 首次进入（无历史） | 停在页首，不做任何滚动 |
| 返回原页面（有历史） | 恢复筛选、页签、选中项、浏览位置 |
| 打开新对象（列表 → 详情） | 详情从头开始；返回时列表回到原位置 |
| 精确深链（带 id） | 定位到对象并高亮，滚动到它 |

`nav.js` 现有的「按文件名存滚动」不满足这张表，由 B 提出键格式，A 在 `nav.js` 实现。
两域在报告里对齐，不要各自实现一份。

## 6. 国际化机制（C 定义，全产品遵守）

- `assets/i18n.js` 提供：词典 `window.eeI18N`、`window.eeT(zh)`、`window.eeApplyI18N(root)`。
- **按中文原文做键**（中文是源语言，稳定不变）。`data-i18n="key"` 优先，用于外壳。
- 覆盖范围：文本节点 + `title` / `aria-label` / `placeholder` / `alt`；
  动态插入的内容由 `MutationObserver` 覆盖。
- **不翻译**：题目原文、选项、解析、用户资料、笔记正文、已有解释内容
  （这些容器加 `data-no-i18n`）；`[data-spec]` 规格说明块（设计文档，非产品 UI）；
  `code` / `pre` / `.mono` 里的标识符。
- 切换语言后：当前页立即切换；随后打开的任何控件（菜单、弹窗、toast、空状态）
  都用目标语言。实现方式是「渲染后统一过一遍 + 观察新增节点」，不是逐处手写。
- 必须附一个覆盖率脚本（`docs/design-p2/review/i18n-coverage.mjs` 或等价物），
  输出「未翻译条目清单」，并在报告里给出中英双向实测结果。

## 7. 禁用与只读

- 禁用必须有可见原因，且原因**不能只在 hover 里**：行内说明、`aria-describedby`、
  或点击后给 toast。`title` 只能作为补充。
- 正常 / 选中 / 禁用 / 只读四态在视觉上必须可分：选中用 `aria-selected`/`is-on`，
  禁用用 `disabled` + 说明，只读用 `aria-readonly` + 只读标记，不用禁用样式冒充只读。

## 8. 空间稳定

- 局部操作不得引起无关区域跳动：切换设置分区、展开一行、切换页签，
  不得改变页面框架、左轨、面包屑的位置。
- 长内容（报告、阅读、复杂编辑）用与内容规模匹配的容器，不要把所有东西塞进一张窄纸。

## 9. 验证配方

静态原型，无构建。用 Playwright 直接跑：

```js
const { chromium } = require('C:/Users/chang/Desktop/code/飞牛刷题软件/frontend/node_modules/playwright');
const EXE = 'C:/Users/chang/AppData/Local/ms-playwright/chromium-1254/chrome-win64/chrome.exe';
```

本地预览已在 `http://127.0.0.1:8787/` 运行（根目录 = `docs/design-p2/`）。
每个域至少自测：自己的页面在 1440 / 1024 / 834 / 375 四档、明暗两主题下
零横向溢出、零控制台错误、零 pageerror，并实际点一遍自己负责的任务链。

## 10. 报告格式

```md
## 域 X 完成报告
### 改了什么（文件:行 + 一句话）
### 任务链实测（逐步：点了什么 → 看到什么）
### 新增文案（中文 → English）
### 需要的共享层改动（主 Agent 处理）
### 未解决 / 转 P3
```
