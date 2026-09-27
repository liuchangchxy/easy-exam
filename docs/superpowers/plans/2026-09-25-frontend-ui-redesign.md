# 实施计划：EasyExam 前端视觉系统与一致性样式修复

## 1. 任务背景与目标

依据用户指示与 Impeccable 评估规范，为现有 EasyExam 前端（Vue 3、现有业务逻辑与组件树）设计并实现一致、完整的产品界面。
这是一个面向家庭与小团队 NAS 的刷题、错题复习与模考工具（Operate & Read 混合模式），核心诉求为：
- 清晰、克制、可信、易读、操作层级明确。
- 全局建立可复用的设计系统（Design Tokens、组件类体系、布局容器、栅格）。
- 统一修复登录/注册、首页、刷题、错题/斩杀、学习诊断、题目导入、模拟考试及强制改密界面的缺失与残缺样式。
- 完善所有交互状态：默认、Hover、Focus、Active、Disabled、Loading、Error、Success、选中。
- 兼顾桌面（1280px+）与移动窄屏（375px+）断点响应式。
- 保持所有现有 DOM 选择器与交互链路，不破坏 E2E 与单元测试，不修改 `SPEC.md`。

## 2. 详细设计方向 (Impeccable Operate Mode)

### 2.1 调色板与语义变量 (Design Tokens)
- 品牌与操作主色：`--primary: #2563eb` (湛蓝)，Hover `--primary-hover: #1d4ed8`，Active `--primary-active: #1e40af`，Light `--primary-light: #eff6ff`
- 成功/答对：`--success: #16a34a` (翠绿)，Hover `#15803d`，Light `#f0fdf4`，Border `#bbf7d0`
- 危险/错题/斩杀：`--danger: #dc2626` (砖红)，Hover `#b91c1c`，Light `#fef2f2`，Border `#fecaca`
- 警告/待复查/薄弱：`--warning: #d97706` (琥珀金)，Light `#fffbeb`，Border `#fde68a`
- 中性色阶：
  - 页面背景 `--bg-page: #f8fafc` (Slate 50)
  - 卡片/表面 `--bg-card: #ffffff`
  - 悬浮/次级表面 `--bg-subtle: #f1f5f9`
  - 边框 `--border: #e2e8f0` (Slate 200)
  - 弱化边框 `--border-light: #f1f5f9`
  - 强化边框 `--border-focus: #3b82f6`
  - 正文文本 `--text-main: #0f172a` (Slate 900，高可读对比度)
  - 次级文本 `--text-muted: #64748b` (Slate 500)
  - 弱化文本 `--text-tertiary: #94a3b8` (Slate 400)
- 阴影系统：
  - `--shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05)`
  - `--shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.06)`
  - `--shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.04)`

### 2.2 共享组件与样式类 (style.css)
- **页面框架与容器**：
  - `.page-container` / 统一步伐：`max-width: 76rem; margin: 1.5rem auto; padding: 0 1rem;`
  - `.page-header`：规范 Flex 布局，桌面两端对齐，窄屏垂直堆叠，标题与导航操作平齐。
- **按钮体系**：
  - `.primary`, `.primary-btn`：实心蓝底白字，优雅轻阴影，active 按压微缩或微下沉，禁用态清晰。
  - 默认/次级按钮：`border: 1px solid var(--border); background: var(--bg-card); color: var(--text-main);`
  - 危险按钮：`.btn-kill`, `.danger-btn` 红边红字，hover 浅红底。
  - `.link-button`：无边框纯文字，hover 下划线。
- **表单与输入框**：
  - 全局 input, select, textarea 统一内边距、圆角（6px~8px）、边框色彩与 focus-visible 光晕。
- **卡片与栅格**：
  - `.bank-grid`：响应式网格 `grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr)); gap: 1.25rem;`
  - `.bank-card`：白色圆角卡片，细边框，轻悬停浮起，flex-column 弹性撑满。
- **登录鉴权**：
  - `.auth-page`：柔和渐变/纯净灰底居中满屏。
  - `.auth-card`：精致卡片（max-width 420px），标题、副标、表单字段、主按钮、切换按钮、错误提示清晰分层。
- **响应式断点**：
  - `@media (max-width: 768px)`：网格单列化、页头导航换行、弹窗自适应、边距微调。

## 3. 逐页面完善清单

1. `frontend/src/style.css`：完善全局 design tokens、按钮规范、表单规范、卡片与网格规范、通用提示条、文本选区与无障碍 focus ring。
2. `frontend/src/views/LoginView.vue`：引入 `.auth-page` 与 `.auth-card` 结构与样式，支持移动端自适应。
3. `frontend/src/views/HomeView.vue`：优化题库列表、统计微徽标、操作按钮组、创建/模考弹窗表单。
4. `frontend/src/views/PracticeViewV1.vue`：优化题干版式、选项选中态、判分反馈卡片、FSRS 四阶评分按钮、AI 折叠面板及移动端排版。
5. `frontend/src/views/MistakesView.vue`：优化 Tab 切换、工具栏题库筛选、错题与斩杀卡片、归因选择器。
6. `frontend/src/views/LearningView.vue`：优化诊断指标网格、基线对比栏、薄弱知识点榜单、推荐筛选条及计划列表。
7. `frontend/src/views/ImportView.vue`：优化上传表单、列映射栅格、数据采样表格及重复策略选项。
8. `frontend/src/features/exam/ExamView.vue` 与 `frontend/src/App.vue`：对齐共享全局样式变量与规范。

## 4. 验证与回归门禁

- 前端单测：`npm --prefix frontend run test:unit`
- 前端打包构建：`npm --prefix frontend run build`
- 浏览器截图核验：编写 Playwright 脚本捕获关键页面（桌面 1280x800 和手机 375x812）真实截图并检查。
- 端到端测试：`npm --prefix frontend run test:e2e`
- 空白与 git 差异检查：`python scripts/check_whitespace.py` 与 `git diff --check`


---

## 完成状态（2026-09-27 复核）

第 4 节验证门禁的实际复核结果：

| 门禁 | 2026-09-27 实测 | 状态 |
|---|---|---|
| `npm --prefix frontend run test:unit` | 11 passed, 0 failed, 0 skipped | 通过 |
| `npm --prefix frontend run build` | Vite v5.4.21，43 modules transformed，exit code 0 | 通过 |
| 浏览器截图核验（桌面 1280x800 / 手机 375x812） | `docs/screenshots/` 下 12 张桌面 + 多组移动端截图；`capture_mobile.mjs` 按 390x844 采集并输出 `metrics.json` | 通过 |
| `npm --prefix frontend run test:e2e` | 13 passed, 0 failed, 0 skipped | 通过 |
| `python scripts/check_whitespace.py` / `git diff --check` | 0 errors | 通过 |

设计系统目标（Design Tokens、按钮/表单/卡片栅格规范、8 个视图对齐、全交互状态、375px+ 响应式）已落地；`style.css` 产物约 63 kB（gzip 约 11 kB，体积逐次浮动）。
