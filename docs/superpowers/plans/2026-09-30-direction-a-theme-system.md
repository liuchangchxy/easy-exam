# 方向 A 全站主题与界面统一实施计划

> **For agentic workers:** 本计划由当前执行者按任务顺序原生执行。每项按 checkbox 留痕；不提交或暂存工作区已有改动。

**Goal:** 将已确认的“温润书房”方向落实为 EasyExam 的浅色默认主题、可持久切换的深色主题，以及跨核心页面一致的颜色、表面和状态。

**Architecture:** 用无 Vue 依赖的主题偏好函数承载存储、解析和 DOM 属性应用，Vue composable 持有单一响应状态，复用 `ThemeToggle` 暴露切换。全局 CSS 变量作为唯一色板接口；导航、登录、练习、模考和各内容页复用语义变量，保留现有功能、信息结构和 SPEC 判分规则。

**Tech Stack:** Vue 3 `<script setup>`、CSS custom properties、Node.js `node:test`、现有 Playwright 浏览器 E2E。

**Spec:** `SPEC.md` 第 1、2、3、4、8 节；视觉方向来自用户确认的 Figma 提案 A。主题存储为设备本地偏好，不写入产品行为真理源。

## Global Constraints

- 普通单选练习选择后即时判定；完整模考在交卷前不展示正确性。
- AI、联网、题库蓝图缺失时，核心刷题必须可用。
- 不回滚、覆盖或暂存当前工作区既有改动；不改后端、数据库、版本号或交付包。
- 默认主题为浅色；用户切换后在同一浏览器持久保存；无有效偏好或存储不可用时回退到浅色。
- 亮暗两套主题使用相同的松绿品牌语义色、文本层级、边框和状态语义；不将语义成功/错误颜色与品牌色混用。

## Review Focus

- localStorage 缺失、损坏或抛异常：首次加载仍可显示浅色，切换仍能在当前页面生效。
- 刷题与模考独立于主 Shell 渲染：沉浸式顶栏也必须能切换主题。
- 手机端底部导航空间有限：主题控件可触达，主导航触控目标不被压缩到 42px 以下。
- 浏览器自动深色偏好：首次访问仍显示方向 A 的浅色默认，显式选择后以已保存偏好为准。
- 普通练习答对/答错与模考未交卷：颜色主题变化不能改变判分信息时序。

## File map

- `frontend/src/design/themePreference.js`：主题值校验、读取/写入容错、根节点应用。
- `frontend/src/composables/useTheme.js`：Vue 响应状态与切换入口。
- `frontend/src/components/ThemeToggle.vue`：统一可访问的切换控件。
- `frontend/src/style.css`：方向 A 的 light/dark 语义令牌、基础控件和表面颜色。
- `frontend/src/App.vue`、`AppSidebar.vue`、`MobileNav.vue`：桌面/移动主壳与密码重设页。
- `frontend/src/views/LoginView.vue`、`HomeView.vue`、`PracticeViewV1.vue`、`LearningView.vue`、`MistakesView.vue`、`ImportView.vue`、`frontend/src/features/exam/ExamView.vue`：登录、主页、练习、诊断、错题、导入、模考页面的主题控制和硬编码中性色归一。
- `frontend/tests/theme.test.js`、`frontend/package.json`：偏好行为的真实纯函数测试和测试入口。
- `docs/REQUIREMENTS_TRACEABILITY.md`：登记本批设计实现范围与实测证据。

## Tasks

### Task 1: 持久主题偏好

- [x] 先在 `frontend/tests/theme.test.js` 写出浅色回退、深色读回、非法值回退、存储异常不阻断和根节点主题属性五项测试。
- [x] 运行 `node --test frontend/tests/theme.test.js`，确认因主题模块不存在而按预期失败。
- [x] 实现 `themePreference.js` 和 `useTheme.js`，每项测试只覆盖一个外部可观察结果。
- [x] 重跑上述定向测试并确认全通过；然后将该测试文件加入 `frontend/package.json` 的 `test` 与 `test:unit` 脚本。

### Task 2: 主题控件与方向 A 色板

- [x] 在 AppSidebar 和 MobileNav 中接入 ThemeToggle；在 LoginView、PracticeViewV1、ExamView 的页面顶栏加入同一控件。
- [x] 用方向 A 的浅色变量作为 `:root` 默认值；用 `:root[data-theme="dark"]` 定义深色松绿变量，并统一导航、弹层、表单、按钮和焦点态。
- [x] 用项目搜索结果逐项处理固定深色外壳颜色和浅色内联颜色；保留危险、警告、成功状态的可读语义。
- [x] 手工检查 375px / 390px 手机宽度下底部导航目标宽高均至少 42px，沉浸式练习/模考操作不会与主题控件相撞。

### Task 3: 视觉核验与证据

- [x] 运行 `npm --prefix frontend run test:unit`、`npm --prefix frontend run build` 与 `npm --prefix frontend run test:e2e`；逐项记录 pass/fail/skipped。
- [x] 用仓库现有真实浏览器截图脚本分别抓取浅色桌面、深色桌面、浅色手机、深色手机和答题反馈/模考状态。
- [x] 检查截图的断行、遮挡、对比度、空/加载/错误/成功状态；修复本计划内的视觉缺陷后复跑对应门禁。
- [x] 在追踪矩阵登记本批文件、命令与可复核证据；不把构建通过写成真实浏览器验证。
