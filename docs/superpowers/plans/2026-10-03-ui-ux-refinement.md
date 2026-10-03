# EasyExam UI/UX 视觉精修与移动端触控优化实施计划

> **目标**：彻底清理 HomeView 和 PracticeView 中的内联样式，统一字阶与 4/8px 间距节奏，消除卡片嵌套（Card Soup），移动端补齐 >= 42px 触控热区并清理 !important 补丁债。

---

## 阶段划分

### 阶段 1：全局 CSS 变量与字阶间距统一
- 文件：`frontend/src/style.css`
- 规范字阶阶梯变量与工具类。
- 确保空状态组件规范化（`.empty-state-card`）。

### 阶段 2：HomeView 模板清理与视觉层级重构
- 文件：`frontend/src/views/HomeView.vue`
- 清理模态框和会话卡片的行内 `style="..."`，抽离为独立语义样式类。
- 题库网格与进行中会话条视觉层级精简，消除冗余边框与多层嵌套。
- 空状态视觉增强（图标 + 一键创建 / 导入）。

### 阶段 3：PracticeView 移动端触控与样式补丁治理
- 文件：`frontend/src/views/PracticeViewV1.vue`
- 顶栏触控热区提升至 >= 42px（满足触控标准且不折行）。
- 清理 `@media (max-width: 767px)` 中滥用的 `!important` 覆盖。
- 调整题干行高至 1.6，优化选项点击区域与视觉反馈。

### 阶段 4：回归测试与视觉验证
- 运行前端单元测试 `npm test`。
- 运行多语言静态扫描与检查 `npm run check:localization`。
- 验证暗色模式与不同视口下的渲染正常。
