# 深度对抗性 UI/UX 缺陷系统性整改计划

## 背景与问题描述
在执行真正的破坏性对抗测试（含 76 字长题库名、15 标签、1200 字长题干、150 字符无空格长代码块、8 个长选项、320px 极限极窄屏）后，自动化检测与实测视觉截图曝出了 4 大系统性缺陷：
1. **[P1] 全端横向撑破滚动（Horizontal Scroll Blowout）**：长代码块与未断词长文本导致 320px/375px 文档宽度达 1110px，1280px 桌面达 1369px；
2. **[P1] 长题库标题撑爆 `<select>` 下拉框**：`LearningView` 与 `MistakesView` 下拉框被撑至 707px~735px，严重穿透视口；
3. **[P1] 操作栏悬浮漂移遮挡核心内容（Layout Occlusion）**：`PracticeViewV1` 操作条浮在选项正上方遮挡 Option C；`MobileNav` 盖住 `LearningView` 看板指标；
4. **[P2] 移动端触控目标矮化（<40px Touch Target 灾难）**：全仓 `btn-back` 仅 30px 高，关闭与工具按钮仅 26~32px。

## 变更文件范围
1. `frontend/src/style.css`：全局排版与表单基础防撑破规则、全局触控热区保证；
2. `frontend/src/views/PracticeViewV1.vue`：题干 `.stem-box` 排版断词、代码块防溢出、底部操作条 Sticky 定位与层叠；
3. `frontend/src/layouts/AppLayout.vue`：移动端底部安全内边距（padding-bottom），彻底防止 `MobileNav` 遮挡内容；
4. `frontend/src/views/LearningView.vue`：题库下拉框与过滤条容器宽度限制与截断；触控尺寸达标；
5. `frontend/src/views/MistakesView.vue`：题库筛选下拉框宽度限制与截断；触控尺寸达标；
6. `frontend/src/views/ImportView.vue`：`btn-back` 及表单元素触控达标；
7. `frontend/src/views/HomeView.vue`：题库卡片长标题截断与微型链接触控达标。

## 验收标准
1. 再次执行 `run_adversarial_ui_audit.mjs`，所有视口（320px, 375px, 1280px）下：
   - `HORIZONTAL_OVERFLOW` (P1) 归零（`scrollWidth <= window.innerWidth + 1`）；
   - `select` 控件最大宽度不超过父容器；
   - 底部操作条不再遮挡选项或正文；
   - `btn-back` 及核心交互控件触控高度 ≥42px；
2. 单测套件全绿：`npm test` 通过；
3. 本地化配置检查通过：`npm run check:localization` 通过；
4. 后端测试通过：`python -m unittest discover -s tests` 通过；
5. 门禁审计通过：`scan_hardcoded_paths.py` 与 `guard_test_tampering.py` 通过。
