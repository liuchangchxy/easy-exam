# 测试与交付证据规范

本文规定如何证明代码行为，不能替代 [SPEC.md](SPEC.md) 的产品规则，也不能把未运行的测试写成已通过。

## 1. 七条硬门禁

1. **缺陷即测试**：修复缺陷前先增加或定位能复现它的回归测试。
2. **契约优先**：输入、权限、状态转换和失败原因必须明确；不能用静默容错掩盖数据错误。
3. **根因全局治理**：修一处后搜索同类实现，检查事务、用户隔离、幂等、离线降级和前端使用链路。
   - **动手前先 census**：任何"按清单改 N 处"的任务，动手前先全仓重扫一遍同类项。**审计抽样结论默认视为下限**（报告说 15 处，实际可能 35 处）；不经 census 直接开改 = 假完成。
4. **证据分层**：测试报告必须写明测试层级、命令、pass/fail/skipped/未运行；低层证据不能冒充高层验收。
5. **端侧物理可用**：移动端/受限视口适配必须剔除无物理外设支撑的特性（如键盘快捷键指南）；核心交互触发源与即时反馈必须在首屏内零滚动可见，不能以“允许页面滚动”替代信息密度治理。
   - **顶栏判据**：目标 ≤44px（方向性建议，非硬阈值）。实际验收以「不折行撑高侵占首屏核心内容」+「触控目标 ≥42px」为准；当元素数量使单行必然压垮触控目标时，取触控可达性。测量口径见 `frontend/tests/capture_mobile.mjs`。
6. **规范即测试（源码自扫描守卫）**：凡是“以后还会有人犯”的代码规范，必须写成一条终身测试去扫描自己的源码，让规范从建议变门禁。
   - **三件套**：① 扫描对象是源码**文本**而非运行行为（禁止的 API、非法字面量）；② 守卫自带违规/合规样本自证——先证明它能红能绿，再信任它的全仓结论；③ 豁免走白名单且必须写 WHY，白名单按**内容签名**匹配而非行号（行号一改就漂移）。
   - **何时用**：同一规范第二次被违反时，就值得写成守卫，而不是第三次再修。
   - 本项目候选：`AGENTS.md` 避坑第 7 条（Windows `subprocess.run(text=True)` 必须声明 `encoding="utf-8"`）、第 8 条（SPA 入口 `no-cache`）、第 9 条（分步向导禁止阻断导航）。
7. **门禁即证据（新增门禁必须自带一次红色实证）**：**一条没红过的门禁视为不存在。**
   - 每新增一条门禁（守卫测试、冒烟断言、CI 步骤），交付时必须附一次「变异实证」：怎么把它打坏的 + 红的原文输出 + 还原后变绿。
   - **绿色只证明"这次没炸"，红色才证明"炸了会响"。**没经过变异实证的门禁，绝大多数是"不可能失败的仪式"（见 REVIEWING 攻击面 3）。
   - **红色控制必须署名**：文档里每个"已验证"必须指名是哪条控制验证的；引用错层（实际死在前一层却写成后一层拦下的）按证据链缺陷处理。

## 2. 测试层级

| 层级 | 证明什么 | 不能证明什么 |
|---|---|---|
| 纯函数/领域单测 | 算法、判分、状态转换 | API、数据库、真实用户流程 |
| API/Repository 集成测试 | 服务端路由、持久化和事务 | 浏览器交互、真实部署链路 |
| 前端 Node/契约测试 | 前端领域模型、组件契约 | 浏览器渲染、真实后端 |
| 真实浏览器 E2E | 用户界面到真实后端的物理链路 | 生产环境全部规模与网络条件 |
| 构建/静态检查 | 编译、打包、格式和空白 | 业务行为正确 |
| 视觉冒烟（仅 Web） | 路由不白屏、产物正身、宿主挂载 | 业务行为正确、可见内容是否**正确** |

涉及前端交互、持久化、迁移、导入、登录或关键学习状态时，必须显式执行对应的真实链路测试；不能把 Mock 测试称为 E2E。

**视觉冒烟是两层判据**：机器判白屏（颜色数/着墨比 + 四道正身信号），人眼或 AI 并排评审"好不好看"——后者机器测不了。见 `tests/visual_smoke/`。它是否定判据（不出错即过），**不能替代** `browser_e2e.test.js` 的肯定判据（真实链路必须跑通）。

## 3. 当前命令

```bash
# 代码与门禁安全检查
python scripts/scan_hardcoded_paths.py
python scripts/guard_test_tampering.py

# 后端全量测试
python -m unittest discover -s tests -v

# 前端单元/契约测试
npm --prefix frontend run test:unit

# 双语静态/词典完整性门禁（test:unit 和 pre-commit 也会强制执行）
npm --prefix frontend run check:localization

# 真实浏览器 E2E
npm --prefix frontend run test:e2e

# 双语真实浏览器门禁（localization.config.json 的 browser 阶段）
npm --prefix frontend run test:localization:e2e

# 生产构建
npm --prefix frontend run build

# 移动端物理度量与截图（390x844，输出到 screenshots/mobile/）
node frontend/tests/capture_mobile.mjs

# 移动端交互 E2E（11 项检查）
node frontend/tests/mobile_interaction_suite.mjs

# 视觉冒烟（需先 build；自动起服务与无头 Chrome，动态端口）
npm --prefix frontend run build
node tests/visual_smoke/run.mjs

# 文档/补丁空白检查
python scripts/check_whitespace.py
git diff --check
```

如果命令因环境未执行，报告为“未运行”；如果存在 skipped，报告实际数量并说明原因，不得宣称全绿。

双语交付门禁由根目录 `localization.config.json` 声明适用语言和词典、源码、契约、浏览器四类检查。EasyExam 必须保持 `applicable: true`；源码守卫还必须通过一个含裸英文文案的红例和一个目录翻译的绿例。双语浏览器门禁运行真实后端和 Chromium，验证页面中英文、`Accept-Language`、API 错误消息即时切换及刷新持久化；词典键数量、构建成功或 API Mock 均不能替代。

## 4. EasyExam 关键回归面

- 判分：多选部分得分不等于完全正确或已掌握；主观题不进入客观正确率。
- 会话：模考不提前泄露答案；提交和交卷可幂等重试；终结状态拒绝后续写入。
- 专项：错题、FSRS 到期、斩杀模式均由服务端限定目标题目集合。
- FSRS：Again/Hard/Good/Easy、作答前快照、两步交互等价性和历史无快照迁移保护。
- 导入：预检、重复策略、PDF 结构拒绝、单事务原子性、失败无半批数据。
- 迁移：强制改密、孤儿题目 `unconverted`、题库/题目/会话/作答/错题全量核对。
- 前端：登录、导入、刷题、错题、FSRS、斩杀、模考报告和离线降级的真实浏览器路径。

## 5. Definition of Done

只有同时满足以下条件，才能把一个批次报告为完成：

- 对应 SPEC 条目已在追踪矩阵中登记源码、测试和运行证据。
- 新增缺陷已有回归测试；既有测试未被删除或放宽。
- 相关测试命令实际运行，失败和 skipped 数量已报告，并区分**环境性跳过**（外部不可达，逐项登记即可）与**断言性跳过**（目标用例未真正执行，必须清零）。
- 关键用户链路按需求范围完成真实 E2E；若环境限制未运行，必须标记缺口。
- P0/P1 缺陷清零；P2/P3 已记录且没有被伪装成完成。
- `git diff --check` 和文档空白检查通过。

## 6. 测试清单索引

具体文件以当前工作树为准，常见入口包括：

| 文件 | 覆盖 |
|---|---|
| `tests/test_v1_architecture.py` | v1 API、认证、刷题/模考、学习状态和解释 |
| `tests/test_v1_import.py`、`tests/test_v1_pdf_import.py` | 表格/文本/PDF 导入和拒绝 |
| `tests/test_v1_learning.py` | 趋势、掌握、FSRS、推荐 |
| `tests/test_legacy_migration.py` | 旧库迁移和校验 |
| `tests/test_scoring_semantics.py` | 判分语义 |
| `frontend/tests/browser_e2e.test.js` | Playwright 真实浏览器链路（`npm run test:e2e`） |
| `frontend/tests/mobile_interaction_suite.mjs` | 移动端交互 E2E：判分文案、切题、跳题、答题卡抽屉、滑动切题 |
| `frontend/tests/capture_mobile.mjs` | 移动端物理度量与截图采集（非断言类） |
| `tests/test_fpk_packaging.py` | FPK manifest/权限/compose 镜像 tag 与版本一致性 |
| `tests/test_remote_fnos_e2e.py` | 远程 fnOS 实机 API E2E：`FNOS_BASE_URL` 必填，两阶段（`FNOS_E2E_PHASE=chain` / `post-restart`）验证核心链路与重启持久性 |
| `frontend/tests/physical_fnos_browser_e2e.mjs` | 远程 fnOS 真实浏览器 E2E：`FNOS_BASE_URL` 必填，`CHROME_PATH` 可选（缺省 bundled Chromium） |
| `tests/visual_smoke/run.mjs` + `shot.mjs` | 视觉冒烟：四道正身信号 + 白屏判据（否定判据，不替代 E2E） |

## 7. 当前工作区运行证据（2026-09-27）

**代码快照**：`48bfa856e9cd3d6f5a981589e1ffc2ef63453027`（`fix(fpk): load offline docker image before fnOS starts the docker project`）。

| 测试层级与环节 | 执行命令 | 实际运行结果 | 状态 |
|---|---|---|---|
| 后端全量测试 | `python -m unittest discover -s tests` | **205 passed, 0 failed, 0 errors, 1 skipped**（耗时 ~100s，逐次浮动） | 通过（含 1 skipped） |
| 前端单元/契约测试 | `npm --prefix frontend run test:unit` | **11 passed, 0 failed, 0 skipped**（毫秒级，逐次浮动） | 通过 |
| Chrome 真实端到端 E2E | `npm --prefix frontend run test:e2e` | **13 passed, 0 failed, 0 skipped**（耗时 ~14s，逐次浮动） | 通过 |
| 前端生产构建 | `npm --prefix frontend run build` | Vite v5.4.21，43 modules，CSS ~63 kB / JS ~225 kB（体积逐次浮动），exit code 0 | 通过 |
| 视觉冒烟（正身信号 + 白屏判据） | `node tests/visual_smoke/run.mjs` | 真实 `frontend/dist` 通过四道正身信号；另用"有内容的网关占位页"做红色实证，被正确拒绝 | 通过 |
| 移动端物理度量与截图 | `node frontend/tests/capture_mobile.mjs` | 采集成功并写入 `screenshots/mobile/metrics.json` | 通过（采集类，无断言） |
| 移动端交互 E2E | `node frontend/tests/mobile_interaction_suite.mjs` | **11 项检查全部通过**（判分文案、切题、跳题、状态保留、答题卡抽屉与跳转、真实触摸滑动） | 通过 |
| 文档/补丁空白检查 | `python scripts/check_whitespace.py`；`git diff --check` | 0 errors，exit code 0 | 通过 |

### 7.1 skipped 明细

唯一 skipped 项是 `tests/test_remote_fnos_e2e.py::TestRemoteFnOsE2E::setUpClass`，原因：`Cannot reach fnOS at http://192.168.x.x:3000: HTTP Error 404: Not Found`。这是**远程物理环境不可达**导致的环境性跳过，不是断言被放宽。按第 1 节硬门禁，此项不得计入"全绿"。

### 7.2 仍标记为未验证的边界

| 环节 | 状态 | 说明 |
|---|---|---|
| 真实外部商业搜索服务 | 未验证（外部依赖） | 本地未配置商业搜索生产 API Key；代码层已验证 `UNAVAILABLE` 优雅降级路径 |
| 远程 fnOS API 实机 E2E | 未运行（环境不可达） | 见 7.1。需 NAS 可达时另行执行并单独记录结果 |

### 7.3 历史证据

2026-09-25 的交付快照（后端 182 通过、前端单测 5 通过、连续 10 轮每轮 13 个 E2E 通过、Docker 健康检查通过）只代表当日固定代码快照，不覆盖当前工作区，保留为历史记录，不得用于声明当前状态。

### 7.4 移动端交互 E2E：三项缺陷已修复（2026-09-27）

该脚本此前无法通过，实为**三个叠加的缺陷**，全部属测试脚本自身，非产品缺陷：

1. **进度文案匹配错误**：断言用 `includes('2/')`，而 DOM 实际为 `"2 / 51"`（斜杠两侧有空格）。同一次提交同时引入断言与 DOM 文本，因此该断言**自引入起就不可能通过**。已改为正则解析 `(\d+)\s*/\s*(\d+)` 并断言数值。
2. **前进按钮假设错误**：脚本硬点 `.btn-next-question`，但该按钮仅在**已作答**时存在；未作答时操作栏渲染的是 `.btn-skip-unanswered`（"跳过 →"）。已改为 `advance()` 按实际状态选择。
3. **滑动用错事件类型**：脚本用 `page.mouse` 模拟滑动，而处理器读取的是 `e.touches` / `e.changedTouches`（`PracticeViewV1.vue` 的 `handleTouchStart`/`handleTouchEnd`），鼠标事件根本不会到达处理器。已改用 CDP `Input.dispatchTouchEvent` 派发**真实触摸事件**，并避开 25px iOS 返回手势保护区。

**红色实证**：将 `assertProgress` 的期望值故意偏移 1，重跑确认断言变红（`actual: 2, expected: 3`），还原后 11 项全绿。按第 1 节铁律 7，该门禁至此才真正"存在"。

### 7.5 交付验收仍然成立的核心项（2026-09-27 实机复核）

FPK 离线安装时序修复已在 fnOS 6.18 实机（`192.168.x.x`）验证：`appcenter-cli install-fpk` 安装成功且不再回滚；容器 `easy-exam-fpk` 起在 3000 端口，`/api/v1/health` 返回 200；`stop`/`start` 重启后已注册账号仍可登录，`var/.env` 主密钥 md5 不变。这部分证据由物理执行产生，不依赖本地测试套件。

### 7.6 Issue #11 fnOS 物理验收（2026-10-26 实机实跑，exact-head 构建）

目标：fnOS 6.18，`http://192.168.100.11:3000`（SSH `Host nas`），容器 `easy-exam-fpk`。

**版本核对（证据归属的前提）**：验收对象是 PR #81 的 exact HEAD，必须先确认实机运行的正是该 revision，否则结果不能证明本 PR。

| 项 | 值 |
|---|---|
| 目标 SHA（验收对象） | `dedea6c5dd926b9e46a75bbfd1b28b1b02a19885` |
| 构建来源 | `git archive dedea6c5dd926b9e46a75bbfd1b28b1b02a19885`（tar SHA-256 `d72d6caac20efbd7cd67a5ee8994427d55300bab1975e4f491e8a6bf432580d1`），在 fnOS 上 `docker build` |
| 构建产物 | `easyexam-exacthead:dedea6c5dd926b9e46a75bbfd1b28b1b02a19885`，label `org.opencontainers.image.revision=dedea6c…` |
| 产物与源码一致性 | 镜像内 `backend/**.py` 共 95 个文件逐个 SHA-256 与 exact-head 工作树**全部一致**（0 差异、0 缺失） |
| 前端产物一致性 | 镜像内 `frontend/dist/assets` 4 个文件与本地 exact-head `npm run build` 产物 SHA-256 **全部一致** |
| 实机运行 revision | `GET /api/v1/health` → `commit_sha` = `dedea6c5dd926b9e46a75bbfd1b28b1b02a19885` |
| 一致性判定 | **目标 SHA == 实际运行 revision**（相等） |

`commit_sha` 由 `EASYEXAM_BUILD_SHA` 注入（`backend/app/api/routes/system.py:9-23`），部署编排中已写入同一 SHA；两个测试入口现在都强制校验该值，不一致直接失败（见下方「revision 门禁红色实证」）。

| 层级 | 命令 | 实际结果 | 状态 |
|---|---|---|---|
| 实机 API 链路 | `FNOS_BASE_URL=... FNOS_E2E_EXPECTED_SHA=dedea6c… FNOS_E2E_PHASE=chain python -m pytest tests/test_remote_fnos_e2e.py -q -rs` | **2 passed, 1 skipped**（skip 为 phase 门控，非断言跳过） | 通过 |
| NAS 重启 | `cmd/main stop` → `cmd/main start`，等待 `/api/v1/health` 200 | 容器 `Up (healthy)`；健康响应 `{"status":"ok","app":"easy-exam","version":"v1","commit_sha":"dedea6c…"}` | 通过 |
| 重启持久性 | `FNOS_BASE_URL=... FNOS_E2E_PHASE=post-restart python -m pytest tests/test_remote_fnos_e2e.py -q -rs` | **1 passed, 2 skipped**（2 个 skip 为 chain 阶段用例被 phase 门控） | 通过 |
| 实机浏览器链路 | `FNOS_BASE_URL=... FNOS_E2E_EXPECTED_SHA=dedea6c… node frontend/tests/physical_fnos_browser_e2e.mjs` | 8 个步骤全部通过：注册登录 → 建题库 → 文件导入 2 题 → 键盘刷题与底部固定条 → 错题斩杀/恢复 → 模考交卷判分（2 题答题卡、得分 2）→ 复习中心 4 个指标卡 | 通过 |
| 既有数据未被替换破坏 | 部署前后统计 | 容器内 SQLite 计数 users 40 / question_banks 30 / questions 192 / practice_sessions 73 / answer_attempts 91 / mistake_records 37，部署前已备份 `easyexam-v1.db.backup-issue11-20261026-062502` | 通过 |

**revision 门禁红色实证**：新增的 `_assert_running_revision()` / `assertRunningRevision()` 在旧部署（`commit_sha="unknown"`）上实跑失败，原文为
`AssertionError: 'unknown' != 'dedea6c5dd926b9e46a75bbfd1b28b1b02a19885'`，pytest `exit 1`、浏览器脚本 `exit 1`；不设 `FNOS_E2E_EXPECTED_SHA` 时同样拒绝执行。切到 exact-head 构建后同一命令变绿。即：若再次用错版本实跑，证据会当场变红，而不是被记录成通过。

**跳过口径**：两阶段各出现的 skip 全部是 `_require_phase` 的主动门控（另一阶段用例不在本轮执行范围），不是断言被跳过，也不存在目标用例未真正执行的情况。两阶段合计 `3 passed, 3 skipped`，覆盖同一批实体在重启前后的读写。

**已解决的部署漂移（不再适用于本轮）**：上一轮记录中 `ailm32442/easy-exam:1.0.19`（分支提交 `1797a03`）存在 `/api/v1/auth/me` 返回 `password_hash` 与 JUDGE 选项未归一化两个问题。exact-head 代码中二者均已修复（`backend/app/api/routes/auth.py:40-44` 显式 `pop("password_hash")`；`backend/app/domain/content/validators.py:118-130` 与 `backend/app/domain/learning/scoring.py` 将 JUDGE 归一化为 T/F），且本轮运行的正是该 exact-head 构建。这两项因此是**旧镜像的事实，不是本 PR 的事实**；上一轮把它们写成"待重新部署验证项"并同时把旧镜像结果当作验收证据，属于证据归属错误，本轮已按 exact-head 重新实跑并替换。

