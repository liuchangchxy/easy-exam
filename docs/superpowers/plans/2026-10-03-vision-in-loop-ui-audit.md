# EasyExam "视觉在环 (Vision-in-the-Loop)" UI/UX 审查与重构计划

> **核心原则**：
> 1. **代码诊断与视觉走查互为支撑**：代码诊断定位架构根因（内联样式、巨石组件、!important 补丁），真实视口截图负责发现视觉瑕疵（呼吸感、折行、触控挤压、层级扁平）。
> 2. **真实渲染基准**：采用真实 Chromium 在桌面端 (1280x800) 与移动端 (375x812) 双重视口下抓取核心页面真实渲染截图。
> 3. **根因治理，拒绝视觉补丁**：发现瑕疵后，修改底层 Design Tokens、语义化类与布局结构，不打临时 `!important` 补丁。

---

## 执行步骤

### 步骤 1：构建自动化真实视口截图套件
- 编写 `scripts/capture_ui_audit_snapshots.mjs`。
- 启动临时干净后端，注入示例题库（含单选、多选、长题干、代码块与解析）。
- 分别截取桌面端 (1280x800) 与移动端 (375x812) 核心页面截图：
  1. `01-login-desktop.png` / `01-login-mobile.png`
  2. `02-home-desktop.png` / `02-home-mobile.png`
  3. `03-practice-unanswered-desktop.png` / `03-practice-unanswered-mobile.png`
  4. `04-practice-answered-desktop.png` / `04-practice-answered-mobile.png`
  5. `05-practice-sheet-mobile.png`
  6. `06-mistakes-desktop.png` / `06-mistakes-mobile.png`

### 步骤 2：多模态视觉问题定位 + 代码根因印证
- 并排审查各截图与对应源码：
  - **移动端顶栏与物理预算**：是否折行撑高？触控热区是否满足 >= 42px？
  - **核心操作区**：做题主界面的主行动按钮（Primary CTA）是否恒定在拇指友好区？
  - **视觉层级与 Card Soup**：边框是否过度重叠？文字行高是否拥挤？
- 结合先前的代码诊断（内联样式、巨石文件），逐项形成具体重构清单。

### 步骤 3：高保真重构与落地治理
- 完善 `frontend/src/style.css` 设计系统规范。
- 重构 `HomeView.vue` 与 `PracticeViewV1.vue` 模板与样式结构。
- 彻底清除历史 `!important` 覆盖，建立自然响应式级联。

### 步骤 4：再次生成对比截图并运行全量测试验证
- 重新运行截图脚本，输出改进后的对比证据。
- 执行 `npm test`（前端 33 个单元测试）。
- 执行 `npm run check:localization`（多语言静态门禁）。
- 执行 `.venv/bin/python -m unittest discover -s tests`（后端全量回归）。
