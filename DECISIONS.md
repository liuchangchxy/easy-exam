# 决策与演进时间线 (DECISIONS.md)

> 本文档用于以微日志（Lightweight ADR）的形式记录项目的重大架构调整、需求变更及背后的原因。
> **目的**：防止数周或数月后遗忘“当初为什么把那个逻辑改成这样”，杜绝需求反复横跳。

---

## 变更记录模板格式
```markdown
### [YYYY-MM-DD] [变更标题]
- **触发背景**：用户反馈 / 性能瓶颈 / 测试异常
- **核心决策**：将原本的 XXX 规则改为 YYY
- **对应 SPEC 章节**：SPEC.md 第 X.X 节
- **影响范围**：[列出涉及的模块或文件]
```

---

## 历史决策流

### [2026-09-30] 第二轮对抗性审查与安全漏洞加固 (ADV2-001 ~ ADV2-007)
- **触发背景**：对全项目进行第二轮深度对抗性审查（涵盖模考旁路版本泄露、只读成员越权写入/重判/解冲突、FSRS 僵尸会话泄漏、多租户题目斩杀嗅探、刷题摘要统计口径以及跨平台与版本对齐）。
- **核心决策**：
  1. **版本列表模考动态脱敏**：在 `QuestionRepository.list_versions` 中接入 `_get_active_exam_question_ids`，杜绝考生通过历史版本列表端点窃取正在进行的模考题目标准答案与官方解析；
  2. **严格收紧题目版本与历史重判权限**：`create_next_version`、`regrade_question_history` 和 `resolve_conflict` 统一要求题库角色为 `ADMIN` 或 `EDITOR`，杜绝只读普通成员 `MEMBER` 越权修改题目、重判全库作答或解决冲突；
  3. **单题复习会话闭环完结**：`PracticeService.review_answer` 在单题作答提交后立即调用 `complete_session` 关闭会话，杜绝产生未关闭的僵尸会话；
  4. **斩杀多租户鉴权与信息隔离**：`kill` 必须校验当前用户对目标题目所属题库的成员资格，`list_killed` 限定仅列出当前用户有权访问的题库内的题目，杜绝非授权租户嗅探私有题目的题干和题型；
  5. **刷题摘要剥离主观题**：`summary` 查询显式排除主观题型 `UPPER(qv.type) NOT IN ('ESSAY', 'SHORT_ANSWER', 'SUBJECTIVE')` 并限定租户所属题库，防止非客观作答稀释正确率；
  6. **Windows 平台子进程 UTF-8 声明**：`system.py` 与 `setup-hooks.py` 中的 `subprocess.run(text=True)` 统一补齐 `encoding="utf-8", errors="replace"`；
  7. **前端包版本同步**：`frontend/package.json` 中的版本号由 `1.0.0` 推进同步至 `1.0.8`，彻底消除交付清单间的版本漂移。
- **对应 SPEC 章节**：SPEC.md 第 2.1、2.2、3.1、3.2、5 节。
- **影响范围**：`backend/app/infrastructure/db/repositories/question_repository.py`, `backend/app/infrastructure/db/repositories/practice_repository.py`, `backend/app/application/practice_service.py`, `backend/app/api/routes/system.py`, `scripts/setup-hooks.py`, `frontend/package.json`。

### [2026-09-30] 全面修复对抗性审查 14 处规范不一致与安全/数据完整性缺陷
- **触发背景**：对需求文档（SPEC.md）与既有代码进行深度对抗性静态与动态审计，审查出模考防泄题、会话超时硬判定、FSRS/错题开关语义隔离、导入难度与置信度归一化、学习指标计算口径、题库元数据完整性与草稿防篡改等 14 处不一致与缺口。
- **核心决策**：
  1. **模考防作弊动态脱敏**：在 `QuestionRepository` 查询层检查当前用户是否存在活跃未完成模考会话，若是则动态清空标准答案与官方解析，防止通过普通题目详情或列表接口泄题；
  2. **模考 FSRS 与错题隔离**：模考会话单题提交禁止推进 `fsrs_cards` 复习调度，并严格遵循会话 `record_mistakes` 开关；
  3. **服务端硬限时**：`PracticeService` 引入 `_check_exam_timeout` 校验（限时 + 60s 宽限），超时严格拒绝作答与草稿同步（HTTP 409），终结纯前端倒计时漏洞；
  4. **导入健壮性**：表格导入修复 1~5 难度离散映射，缺失/无法识别规范映射为 0（未分级）；PDF 导入对 `UNCERTAIN` 置信度题目强制拒绝直接批量入库，收敛至校对草稿箱；
  5. **学习趋势指标科学收敛**：弱项统计限定题目最新版本号 `MAX(version_number)`；到期复习统计排除已斩杀题目；学习完成率仅统计 `s.mode = 'FSRS'`；客观正确率基线完全剥离主观题；
  6. **题库元数据安全与完整性**：章节与标签补全修改与删除 REST 路由，施加 ADMIN/EDITOR 权限校验与循环父级检查；
  7. **草稿防篡改**：会话草稿严格校验只接受会话快照内题目 ID，并限制 `current_index` 与 `time_spent` 合法范围。
- **对应 SPEC 章节**：SPEC.md 第 2.2、3.2、4.1、5、8 节。
- **影响范围**：`backend/app/infrastructure/db/repositories/*`, `backend/app/application/practice_service.py`, `backend/app/infrastructure/importers/*`, `backend/app/api/routes/banks.py`, `backend/legacy/services/__init__.py`。

### [2026-09-28] 前端全站视觉与交互深度重构：落地工作台侧边栏、Cmd+K 指令面板、全仓去 Emoji (v1.0.7)
- **触发背景**：用户反馈单纯的 CSS 颜色替换仅是“换了个主题”，要求深入底层 DOM、宏观信息架构与组件触感进行真正的结构性重新设计。
- **核心决策**：
  1. **全局工作台 Shell**：新增左侧高密度工作台侧边栏 (`AppSidebar.vue`) 与移动端底部沉浸条 (`MobileNav.vue`)，集成全局 `Ctrl/Cmd + K` 快捷指令面板 (`CommandPalette.vue`)；
  2. **去 Emoji 化与专业矢量系统**：引入内联矢量线框图标组件 (`LinearIcon.vue`)，彻底清除页面玩具感 Emoji，建立统一 1.8 细线微质感；
  3. **资产大厅重塑**：未完成会话改造成类终端恢复 HUD，题库展示升级为高密度资产列表与健康度指示；
  4. **做题与模考沉浸式工作台**：选项注入 `120ms` 物理阻尼与微发光按压反馈，FSRS 评级标注记忆留存预测间隔（`+10m`, `+1d`, `+3d`, `+7d`）；
  5. **门禁与实机交付**：13 项 Playwright 真 Chrome E2E 测试全绿，版本号推进至 `1.0.7` 并成功安装上线飞牛 NAS。
- **对应 SPEC 章节**：SPEC.md 界面与交互规范。
- **影响范围**：`frontend/src/components/*`, `frontend/src/views/*`, `frontend/src/features/exam/*`, `frontend/src/style.css`, `fpk/easy-exam/*`。

### [2026-09-22] 仓库脚手架初始化
- **触发背景**：创建 Vibe Coding Starter 通用规范模板。
- **核心决策**：确立 SDD（规范驱动）+ 双层门禁 + 自进化避坑清单为核心工作流。
- **对应 SPEC 章节**：全文档初始化。
- **影响范围**：全局。

### [2026-09-22] 飞牛刷题系统 (fn-exam) 全案架构确立与落盘
- **触发背景**：用户要求为飞牛 NAS (fnOS) 打造一款对标微信小程序“考试宝”的自托管刷题系统，吸取 12 个开源竞品源码精华，坚决剔除其臃肿与缺陷。
- **核心决策**：
  1. **技术栈基座**：采用 FastAPI + Vue 3 + SQLite WAL 极轻量单镜像（常驻闲置内存 50MB~100MB），零外部重型数据库依赖；
  2. **交互体验**：1:1 对标微信小程序「考试宝」，实现选项秒判变色、左右防误触手势切题、底部 5 色网格抽屉答题卡、全真模考诊断报告；
  3. **数据韧性**：采用 `localStorage` 0ms 实时草稿暂存 + 切题与防抖 5 秒双层同步，确保设备休眠、断网或刷新 100% 断点自动续答；
  4. **抗遗忘与错因归因**：直接移植纯 Python 零依赖 FSRS-5 算法计算最佳复习周期；建立 6 级错因分类，实行“连续答对 2 次出库斩杀”规则；
  5. **AI 助教与题库导入解耦**：做错题目自动打包题境上下文注入 Prompt，支持 SSE 打字机流式追问与离线友好降级；题库导入采用正则状态机+CSV+JSON 四级流水线，绝不捆绑几十 GB 的深度学习 OCR，保证 NAS 镜像小巧稳定。
- **对应 SPEC 章节**：SPEC.md 第 1~6 节与 `docs/superpowers/specs/2026-09-22-fn-exam-design.md`。
- **影响范围**：系统全量模块（`backend/`, `frontend/`, `tests/`, `Dockerfile`, `docker-compose.yml`）。

### [2026-09-23] 品牌合规化更名：全面更名为「易考宝」(EasyExam)
- **触发背景**：用户反馈第三方应用不能以“飞牛”或“fnOS”作为应用主名称前缀，否则会因商标侵权或官方混淆导致无法上架飞牛应用中心（或第三方 NAS 应用市场）。
- **核心决策**：
  1. 应用中文名定名为「易考宝」，副标题为「私有云刷题与错题消灭系统」；
  2. 英文服务标识、Docker 容器与镜像定为 `easy-exam` (`ailm32442/easy-exam:latest`)；
  3. 保留对飞牛私有云 (fnOS) 兼容性声明，但主包名与主界面彻底去官方化；
  4. 数据库向前兼容 `easyexam.db` 与 `fnexam.db`，自动兼容原有挂载数据文件。
- **对应 SPEC 章节**：SPEC.md 第 1.1 节。
- **影响范围**：`frontend/index.html`, `backend/main.py`, `backend/database.py`, `docker-compose.yml`, `Dockerfile`, `scripts/deploy_fnos.sh`, `tests/`。

### [2026-09-23] 需求主线重评估：从竞品拼接改为题目学习档案
- **触发背景**：源码调查发现原文档把多个项目能力并列拼接，AI 助教回答未持久化，多选部分得分与“已掌握”语义混用，且“考试宝”借鉴边界不清。
- **核心决策**：以题目版本为中心组织作答、错因、解释版本、联网证据、FSRS 和斩杀题库；考试宝只借鉴可观察的产品逻辑，不复制页面或闭源实现；AI/联网/用户解释全部版本化保存，标准答案独立维护。
- **对应 SPEC 章节**：SPEC.md 第 1~8 节。
- **影响范围**：需求文档、后续数据模型、AI 助教、判分器、错题/FSRS、模考、同步和权限模块；本次仅更新文档，未修改业务源码。

### [2026-09-23] 大题库与 AI 边界确认
- **触发背景**：用户进一步明确目标是考公等大题库提分系统，而不是独立 AI 聊天或必须依赖复杂配置的 RAG 产品。
- **核心决策**：采用“考试体系 + 可复用题库”、章节树 + 多知识点标签、动态提分推荐和可调整学习计划；AI 作为横向可选能力嵌入具体题目流程；无 AI、无考试蓝图时核心刷题仍可用；不可解析文档直接拒绝上传。
- **对应 SPEC 章节**：SPEC.md 第 2、5、8 节。
- **影响范围**：题库组织、学习诊断、推荐计划、AI 检索、导入校验和降级行为；本次仅更新文档，未修改业务源码。

### [2026-09-23] 判分与掌握状态拆分
- **触发背景**：旧实现把多选少选的部分得分标记为 `is_correct=true`，会错误触发错题连续答对清除。
- **核心决策**：新增 `mastery_status`（`CORRECT`、`PARTIAL`、`INCORRECT`、`UNANSWERED`）；部分得分仍计入分数，但只有 `CORRECT` 才进入掌握/错题清除链路；保留 `Scorer.evaluate` 二元接口兼容既有调用方。
- **影响范围**：`backend/services/scoring.py`、`backend/services/session_service.py`、`backend/main.py` 及后续报告统计；旧测试中把部分得分视为正确的断言需要按新需求复核。

### [2026-09-23] 模块化单体架构开始切换
- **触发背景**：旧实现把路由、业务服务、SQL 和前端状态集中在少数文件，无法支持用户隔离、题目版本和解释版本。
- **核心决策**：建立 `backend/app` 模块化单体，采用版本化 SQLite migration、自建 Repository、`/api/v1` 路由和用户级学习记录；旧入口保留为回归基线，不再承载新功能。
- **影响范围**：认证、题库/题目版本、作答尝试、错题、学习摘要、导入、AI 解释版本和新前端视图；部署入口切换到 `backend.app.main:app`。

### [2026-09-23] 旧原型实现收拢到 legacy 兼容区
- **触发背景**：新生产入口已经切换，但旧 `main.py`、Repository、数据库和服务实现仍散落在 `backend/` 根目录，容易被误当成主线继续扩展。
- **核心决策**：将旧实现移动到 `backend/legacy/`；根目录仅保留导出兼容模块，供旧回归测试和迁移工具使用；新功能只能进入 `backend/app`。
- **影响范围**：生产 Docker 不依赖旧入口；旧测试继续可运行；后续可以逐步删除兼容导出而不影响新 API。

### [2026-09-23] 分离错题事实与学习掌握状态
- **触发背景**：仅使用 `learning_records` 同时承载错题列表和掌握统计，会让首次答对、部分得分和清除状态混在一起，无法审计真实错题事实。
- **核心决策**：新增版本化迁移 `mistake_records`；作答事务同时更新错题事实、掌握状态和 FSRS。首次答对不进入错题列表，答错后可按连续完全正确次数清除。
- **影响范围**：刷题写入、错题列表、FSRS 到期列表、旧库迁移与迁移校验。

### [2026-09-23] 导入任务可审计化
- **触发背景**：导入表已存在但导入流程没有记录预检失败或成功结果，无法解释用户上传为何被拒绝或是否完整落盘。
- **核心决策**：每次文本、CSV、JSON、PDF 导入创建 `import_jobs`，以 `PENDING` → `IMPORTED` / `PRECHECK_FAILED` / `FAILED` 记录生命周期；解析失败不创建题目。
- **影响范围**：导入应用服务、PDF 可识别性预检、迁移后审计和后续前端导入历史。

### [2026-09-23] 题目跨题库复制使用新身份
- **触发背景**：同一题目内容进入不同题库时，如果复用题目主键，会把两个题库的作答、错题和 FSRS 状态错误地绑定在一起。
- **核心决策**：复制接口复制当前题目版本内容，但生成新的 `questions` 与 `question_versions` 身份；目标题库的学习状态从空白开始。
- **影响范围**：题库题目管理、权限校验和用户学习数据隔离。

### [2026-09-24] 模考结果延迟到交卷阶段计算
- **触发背景**：普通刷题可以即时反馈，但模考提交前泄露正确性会破坏考试体验；旧报告依赖会话 JSON 汇总，不能可靠统计未作答和题型/知识点。
- **核心决策**：模考提交只保存作答并返回 `feedback_available=false`；交卷从 `answer_attempts` 重算，绑定启动时蓝图版本，并在最终报告应用负分规则。
- **影响范围**：模考路由、会话字段、报告统计和蓝图迁移。

### [2026-09-24] 推荐与趋势以可解释离线规则为主
- **触发背景**：大题库提分不能依赖 AI 黑盒；原推荐只返回已有学习记录，漏掉新题，也没有用户调节入口。
- **核心决策**：推荐覆盖新题、薄弱题和 FSRS 到期题，返回原因并支持开关、数量和题型过滤；趋势从真实作答计算覆盖率、近期窗口和长期基线。
- **影响范围**：学习 Repository、领域排序、学习 API、前端学习视图；AI 离线不影响这些能力。

### [2026-09-24] 联网核查和导入预检显式记录不确定性
- **触发背景**：联网结果和重复导入如果没有版本/预检状态，用户无法区分“没有证据”和“确有依据”，也可能意外重复写题。
- **核心决策**：WEB 核查保存独立解释与证据列表，离线返回 `UNAVAILABLE`；导入先返回重复项，必须选择策略后落盘，同时支持 XLSX。
- **影响范围**：AI 解释 Repository、搜索适配器、导入应用服务、导入审计和前端 API。

### [2026-09-24] 主观题作答与客观正确率语义隔离
- **触发背景**：主观题由于缺乏客观标准答案，直接统计到会话客观正确率分母中会导致客观题正确率失真被稀释。
- **核心决策**：会话客观正确率计算严格按照客观题分母统计；主观题作答完整留痕，但客观正确率仅计算客观题；交卷前模考报告严禁泄露任何答案与解析。
- **影响范围**：`backend/app/application/practice_service.py`、`frontend/src/domain/exam.js`、`tests/test_scoring_semantics.py`。

### [2026-09-24] 闭环专项复习、模考幂等防护与真实 Chrome 物理 E2E 验收
- **触发背景**：审查发现 FSRS 到期复习与错题专项刷题未限定目标集合、斩杀题复习漏透传 `bank_id`、错因前端修改未持久化、模考提交缺乏幂等与交卷防护、旧库迁移使用弱默认密码且无首次强制改密、缺乏真实浏览器 E2E 验证。
- **核心决策**：
  1. 专项刷题（`MISTAKE`、`FSRS`、`ELIMINATION`）服务端强制题目集合限定，支持指定 `question_ids` 过滤，题目集为空时显式抛错；
  2. 练习与 FSRS 评级接口打通（`fsrs_rating` 校验评级一致性，错误强制 Again）；前端错题卡片提供错因下拉持久化接口；
  3. 斩杀题库列表透传真实 `bank_id`，卡片与工具栏提供“查漏补缺练习”启动入口，错答即时移出斩杀；
  4. 模考提交与交卷增加幂等防护，已交卷会话严禁再次提交 attempt；
  5. 旧库迁移生成高强度随机临时密码并标记 `must_change_password=1`，提供首次强制改密流；未转换孤儿题记入审计并在验证脚本中进行全量多表校验；
  6. 搭建 Playwright + Google Chrome 物理端到端自动化测试套件（覆盖注册登录、题库创建、答题与判分、斩杀与复原、错因持久化、专项刷题、FSRS 评级、模考与诊断报告等全部 9 大核心主链路），杜绝纯 Mock 假绿。
- **对应 SPEC 章节**：SPEC.md §3.2, §4.1, §4.2, §4.3, §6。
- **影响范围**：`backend/app/application/practice_service.py`、`backend/app/api/routes/`、`frontend/src/views/`、`scripts/migrate_legacy_db.py`、`frontend/tests/browser_e2e.test.js`。

### [2026-09-24] 闭环 FSRS 评级更新、专项防绕过、强改密阻断与 E2E 端口实例防串连
- **触发背景**：第二轮审查指出：相同答案再次提交携带新 rating 时底库未更新 `fsrs_rating` 与卡片调度；`start_session` 只要收到 `question_ids` 即可绕过专项队列；`must_change_password` 未在 API 依赖层面阻断业务请求且密码长度与路由声明不一致（6 位 vs 8 位）；批量入口漏掉薄弱到期题且跨题库传参静默丢失；E2E 硬编码端口可能误连残存进程。
- **核心决策**：
  1. `practice_repository.py` 的 `save_attempt` 支持在相同答案再次提交带有新 rating 时更新 `fsrs_rating`、错因，并重新调用 FSRS 算法更新 `fsrs_cards`；
  2. `practice_service.py` 的 `start_session` 先根据 `mode` 锁定专项候选题目池，再与传入的 `question_ids` 求交集，若结果为空抛出 400，从根源杜绝越权绕过；
  3. `dependencies.py` 的 `current_user` 针对 `must_change_password=1` 的用户强制拦截所有非免检路由并返回 403 `MUST_CHANGE_PASSWORD`；Pydantic 与服务层统一密码策略为至少 8 位；前端 `App.vue` 增加全屏强制改密拦截组件；
  4. `MistakesView.vue` 并发加载 `listDueMistakes`（完整覆盖无错题记录但标记薄弱的到期题），增加题库筛选下拉框，批量复习严格按目标题库打包题目，杜绝跨题库静默丢失；
  5. E2E 真实浏览器测试引入系统闲置端口动态探测与 `INSTANCE_TOKEN` 双向握手校验，杜绝测试串连外部残存服务；E2E 场景补充物理核对非默认 FSRS 评级 4 真实落盘、薄弱标记到期复习与首次登录强制改密阻断全链路。
- **对应 SPEC 章节**：SPEC.md §4.1, §4.2, §4.3, §4.4。
- **影响范围**：`backend/app/application/practice_service.py`、`backend/app/infrastructure/db/repositories/practice_repository.py`、`backend/app/dependencies.py`、`backend/app/api/routes/auth.py`、`backend/app/api/routes/system.py`、`frontend/src/App.vue`、`frontend/src/views/MistakesView.vue`、`frontend/tests/browser_e2e.test.js`、`frontend/tests/exam.test.js`。

### [2026-09-24] 历史作答无快照安全策略：防虚假基准伪造与已调度卡片防二次叠加
- **触发背景**：审查进一步指出，存量升级与旧库迁移若直接将“当前 FSRS 卡片”回填为历史作答的 `card_snapshot_json`，会伪造作答前快照；若旧作答此前已触发过调度，用户后续修改评分时会以当前卡片为基线再次调度，导致二次叠加调度。
- **核心决策**：
  1. 数据库升级脚本（`connection.py`）与旧库迁移脚本（`migrate_legacy_db.py`）严禁把当前卡片作为历史快照回填，历史存量作答真实保持 `card_snapshot_json = NULL`；
  2. `practice_repository.py` 严格区分两类存量无快照记录：
     - 若作答记录在历史上已完成过 FSRS 调度（`existing["fsrs_rating"]` 已存在或卡片 `last_review_at` 与作答时间吻合），用户修改评分时仅更新作答记录本身的 `fsrs_rating`，严禁在卡片上二次叠加调度，亦严禁重置为新卡，彻底冻结并保护卡片已有复习状态；
     - 若作答记录在历史上从未调度过（`fsrs_rating` 为空且卡片未被其更新），用户首次评级时方以当前卡片为基准初次调度，并即刻回填基准快照；
  3. 完善双向专项测试：既覆盖“未调度旧作答首次评级正常流转”，又严格覆盖“已调度旧作答修改评级卡片冻结防二次叠加”。
- **对应 SPEC 章节**：SPEC.md §4.2。
- **影响范围**：`backend/app/infrastructure/db/connection.py`、`backend/app/infrastructure/db/repositories/practice_repository.py`、`scripts/migrate_legacy_db.py`、`tests/test_v1_architecture.py`、`tests/test_legacy_migration.py`。

### [2026-09-24] AntiGravity 文档分工、需求追踪与外部源码复用审计
- **触发背景**：代码实现交由 AntiGravity 后，单独一份 SPEC 或一句提示词不足以保证它区分已确认需求、当前代码事实、外部源码复用与待实施工作；README 还把候选参考能力写成了“已经吸收”，旧计划引用重构前路径。
- **核心决策**：`SPEC.md` 只记录已确认产品要求；实现状态放入需求追踪矩阵；第三方源码与许可选择集中记录在开源审计；一次只按用户点名的分阶段计划执行；长期代理规则放 `AGENTS.md`，协作过程/报告模板放专门 workflow 与 AntiGravity skill。
- **源码复用原则**：适配且许可兼容时优先选择性复用成熟代码；按仓库、commit、源文件、目标文件和 NOTICE 义务留痕；行为参考不可表述为代码移植；AGPL/GPL、无许可及含混许可代码未获决定前不直接复制进本 MIT 项目。
- **影响范围**：`AGENTS.md`、`SPEC.md`、`README.md`、`TESTING.md`、`docs/REQUIREMENTS_TRACEABILITY.md`、`docs/research/OSS_REUSE_AUDIT.md`、`docs/ANTIGRAVITY_WORKFLOW.md` 与各批次 implementation plan。

### [2026-09-24] 题库批量导入单事务原子性与表格列映射预览（复用 Exameow 算法与 EXAM-MASTER 事务模式）
- **触发背景**：批量导入此前为每道题单独提交事务，中途失败会导致部分题目残留；表格导入仅支持极少别名，无法自适应复杂表头或提供用户手动列映射预览修正。
- **核心决策**：
  1. 在 `question_repository.py` 引入 `batch_create_or_update_questions` 单一数据库事务，与 `import_service.py` 统一批处理；中途任何写入失败整体回滚，0 题目残留，`import_jobs` 准确审计为 `FAILED`；
  2. 移植 Exameow（Apache-2.0）的表头别名识别、组合选项分隔符提取、前缀剥离与难度归一化算法至 `spreadsheet_importer.py`，并在代码头保留 Apache-2.0 归属；统一在 Python 后端解析以防多端重复解析器；
  3. 提供 `POST /api/v1/imports/banks/{bank_id}/preview-file` 接口与前端 `ImportView.vue` 可视化列映射面板，允许用户先预览前 5 行采样数据、检查缺失字段并手动修正各列绑定后再确认导入；
  4. 真实浏览器 E2E 全流程覆盖“列映射预览 -> 用户确认导入 -> 重复题预检拦截”。
- **对应 SPEC 章节**：SPEC.md §5, §8。
- **影响范围**：`backend/app/infrastructure/importers/spreadsheet_importer.py`、`backend/app/infrastructure/db/repositories/question_repository.py`、`backend/app/application/import_service.py`、`backend/app/api/routes/imports.py`、`frontend/src/views/ImportView.vue`、`frontend/src/api/imports.js`、`frontend/tests/browser_e2e.test.js`、`tests/test_v1_import.py`、`tests/test_v1_pdf_import.py`。

### [2026-09-24] 文档体系按通用底座与领域扩展重新分层
- **触发背景**：本地已经积累了大量 EasyExam 实战规则，但通用 Vibe Coding Starter 的数据安全、可靠性、Multi-Agent、模板和 SDD Skill 没有形成统一入口；文档之间存在规则重复，容易把实现状态、产品需求和测试证据混在一起。
- **核心决策**：采用“入口宪法（AGENTS）—产品真理源（SPEC）—执行证据（追踪矩阵/TESTING）—决策与研究（DECISIONS/research）—按需扩展（optional/templates）”五层结构。通用规则进入可复制底座，EasyExam 的迁移、FSRS、幂等、导入和领域红线保留在本地扩展，不把领域细节泛化进 Starter。
- **影响范围**：`AGENTS.md`、`README.md`、`TESTING.md`、`SPEC.md` 的维护约定、`docs/REQUIREMENTS_TRACEABILITY.md`、`docs/ANTIGRAVITY_WORKFLOW.md`、`docs/optional/`、`docs/templates/`、`.agents/skills/sdd-implementation/`。

### [2026-09-24] 学习计划中未分级题目的难度筛选
- **触发背景**：题库中可能存在未显式标注难度的题目，用户确认了在学习计划按难度筛选时的处理规则。
- **核心决策**：难度筛选只使用题目显式标注的 1–5 级；未分级题在未启用具体难度筛选时仍可参与推荐，启用具体难度筛选时排除。不得按默认中等处理，也不得根据单用户或跨用户作答表现推断题目难度。
- **对应 SPEC 章节**：`SPEC.md` §8。
- **影响范围**：学习推荐/筛选逻辑、相关测试和用户可见筛选状态。

### [2026-09-27] FPK 离线镜像必须在 install_init/upgrade_init 阶段加载

- **触发背景**：`easy-exam-1.0.1` / `1.0.2` 在 fnOS 应用中心手动安装时每次都在最后一步回滚，报 `easy-exam Error pull access denied for ailm32442/easy-exam`。排查发现应用中心会在 `install_init` / `install_callback` 之前就用包内 `target/` 把 docker project 拉起来；此时本地 daemon 尚无随包镜像，compose 按 `pull_policy: if_not_present` 回退拉取从未发布的 Docker Hub tag，被拒后整体回滚。此前 `1.0.1` 曾成功一次，是因为 `1.0.0` 时期 `docker load` 的同名镜像仍残留在本地。
- **核心决策**：
  1. 把 `docker load` 随包镜像的逻辑前移到 `cmd/install_init` 与 `cmd/upgrade_init`——这是能抢在 compose 之前的最早钩子；遍历 `TRIM_APPDEST/images`、`TRIM_PKGINST_TEMP_DIR[/app]/images`、`TRIM_TEMP_TPKFILE[/app]/images` 全部暂存位置，加载失败只告警不退出（避免 setup 环境缺 docker 时阻断安装）。
  2. `cmd/main start` 在 `docker compose up` 前再加载一次 `target/images`；`install_callback` / `upgrade_callback` 保留加载逻辑作兜底。
  3. 版本号单一来源定为 `fpk/easy-exam/manifest` 的 `version`，`app/docker/docker-compose.yaml` 的镜像 tag 与随包镜像 tag 必须同步推进，由 `tests/test_fpk_packaging.py` 强制校验。
- **对应 SPEC 章节**：无（平台部署约束，不改变产品行为）。
- **影响范围**：`fpk/easy-exam/cmd/install_init`、`cmd/upgrade_init`、`cmd/main`、`app/docker/docker-compose.yaml`、`manifest`、`docs/FNOS_FPK_GUIDE.md`（新增 3.3 节）。
- **验证**：fnOS 6.18 实机（`192.168.x.x`）安装成功不再回滚；容器起于 3000 端口，`/api/v1/health` 200；`stop`/`start` 后已注册账号仍可登录，`var/.env` 主密钥 md5 不变。

### [2026-09-27] 移动端顶栏保留换行而非强制单行

- **触发背景**：`2026-09-25-ergonomics-ui-overhaul.md` 与 `AGENTS.md` 避坑第 10 条要求触屏端顶栏"单行紧凑折叠"。2026-09-27 实测 390x844 视口下 `.compact-header` 高度为 82.8px，仍为两行。
- **核心决策**：保留 `.compact-header { flex-wrap: wrap !important }` 的两行布局，不强制单行。原因是顶栏在移动端需同时容纳"返回 + 标题 + 题型徽标 + 进度徽标 + 交卷 + 提示 + ⋯"，强制单行会把按钮压缩到不足 42px 的触控目标下限，违反工效学整改的核心目标（可达性与防误触）。折中结果：顶栏由 175.8px 降至 82.8px，题干与全部选项落在首屏内（`capture_mobile.mjs` 实测），底栏 57px；"单行"这一具体形式未满足，但首屏信息密度与触控达标这两个真实目标达成。
- **对应 SPEC 章节**：无（交互工效学，不改变产品行为）。
- **影响范围**：`frontend/src/views/PracticeViewV1.vue`（`.compact-header` 移动端样式）、`frontend/tests/capture_mobile.mjs`（度量口径）、`docs/superpowers/plans/2026-09-25-ergonomics-ui-overhaul.md`（DoD 复核）。
- **遗留**：`AGENTS.md` 避坑第 10 条的"顶栏必须单行紧凑折叠"与实际实现不一致。保留该条款为方向性目标，但验收时以"顶栏高度不侵占首屏核心内容 + 触控目标 ≥42px"为实际判据，不单独以行数判定。

### [2026-09-27] 从 vibe-coding-starter 吸收四条通用工程规则

- **触发背景**：对比 `vibe-coding-starter` 模板项目（独立通读，非文件树 diff）与易考宝现有规范，发现四条易考宝缺失的通用规则；其中两条直接对应本项目已发生的真实事故。
- **核心决策**：
  1. **移植 `tests/visual_smoke/`**（白屏判据 + 四道正身信号）。保留正身信号层，导航层按本项目实际改写——易考宝 SPA **没有 URL 路由**（`App.vue` 用响应式 state 切视图），starter 原版的 `#/route` 遍历在此无效。逃生门保留为 `--allow-missing-host` flag 而非拆闸门。已完成红色实证：一个有内容的网关占位页（纯颜色判据会放行）被正身信号正确拒绝。
  2. **TESTING 铁律 6「门禁即证据」**：一条没红过的门禁视为不存在；新增门禁必须附变异实证。直接对应本项目 `mobile_interaction_suite.mjs` 中那条自引入起就不可能通过的断言。
  3. **TESTING 铁律 5「规范即测试」**：把"以后还会有人犯"的规范写成扫源码的终身守卫；守卫自带红/绿样本自证；白名单按内容签名匹配而非行号。
  4. **RCA 动手前先 census**：清单类任务先全仓重扫，审计抽样结论视为下限。
  5. **AGENTS 裁定清单（Rulings）**：授权整段自动流程时收尾必须披露 `裁定 → 判错的代价`，禁止静默裁定。
  6. **AGENTS UI 模糊评价五维清单**：把"丑/难看"转成改/不改选择题。
- **不吸收**：`templates/ci.yml`（本项目已有且更完整）、`scripts/setup-hooks.py`（已装且逐字节同源）、AGENTS 避坑 9–12（AntiGravity-OSS 专有场景，本项目 §2 覆盖更严谨）、`EXECUTION/REVIEWING/ARCHITECTURE`（本项目已有且 `REVIEWING.md` 更强）。
- **顺带修复上游**：starter 的 `scripts/checkpoint.py` 有两个真 bug（`restore` 用 `git checkout <sha> -- .` 会遗留新增文件；"安全 stash"从不告知也不恢复），已在 starter 仓库修复并补 `tests/test_checkpoint.py`，两测试均经红色实证。
- **对应 SPEC 章节**：无（工程规范，不改变产品行为）。
- **影响范围**：`tests/visual_smoke/`、`TESTING.md`、`AGENTS.md`、`DECISIONS.md`。

### [2026-09-27] 文档体系自洽性修复：顶栏规则去硬化、skipped 口径、移动端门禁转真

- **触发背景**：用户追问"文档体系是否真的自洽"。逐项实测后确认**不自洽**，发现 5 处实质矛盾（此前"文档门禁全清"只证明了链接可解析与空白干净，不能推出自洽）。
- **核心决策**：
  1. **顶栏规则去硬化**：`AGENTS.md` 避坑第 10 条原写"必须严格单行（≤44px）"，实测两行为 82.8px。溯源发现上游 starter 原文是**"建议 ≤ 44px"**，传入本项目时被硬化成强制值，且"单行"只是达成"首屏密度"的手段。现改为：目标 ≤44px 为方向性建议，验收以「不折行撑高侵占首屏核心内容」+「触控目标 ≥42px」为准；元素过多致单行必然压垮触控目标时，取触控可达性。`TESTING.md` 铁律 5 同步对齐。
  2. **skipped 口径分层**（新增避坑第 16 条）：**环境性跳过**（外部不可达、无凭证）不阻断收敛判定但须逐项登记；**断言性跳过**（目标用例未真正执行）仍阻断。此前 `AGENTS.md`/`TESTING.md` 笼统要求 `skipped=0`，与当前 `skipped=1` 之间缺一条缝。
  3. **移动端门禁转为真门禁**：`mobile_interaction_suite.mjs` 实为**三处叠加的脚本缺陷**（进度文案匹配错、前进按钮假设错、滑动用鼠标事件而处理器读 touch 事件），非产品缺陷。全部修复并完成红色实证（故意偏移期望值 → 断言变红 → 还原全绿），11 项检查全通过。按铁律 7，此前它根本"不算门禁"。
  4. **文档地图补全与纠错**：修复 3 处不可定位路径（`.fpk` 反引号误解析、两个 AntiGravity 提示词缺 `docs/` 前缀）；补录 `specs/` 与 `templates/ci.yml`，并标注后者**当前未激活**（无 `.github/`，从未运行）。
  5. **清除单次实测数字**：`2026-09-25-frontend-ui-redesign.md` 中的 `62.68 kB` 精确字节值改为量级（此前已在 `TESTING.md` 处理同类问题，此处遗漏）。
- **对应 SPEC 章节**：无（工程规范与测试门禁，不改变产品行为）。
- **影响范围**：`AGENTS.md`、`TESTING.md`、`README.md`、`docs/REQUIREMENTS_TRACEABILITY.md`、`docs/superpowers/plans/2026-09-25-frontend-ui-redesign.md`、`frontend/tests/mobile_interaction_suite.mjs`。

### [2026-10-01] 吸收母版 Starter 门禁规范、根级全栈国际化 (i18n) 与 AI 多语言穿透

- **触发背景**：从 `vibe-coding-starter` 模板项目吸收通用工程规范与资产，强化自动化测试防篡改审计、硬编码物理绝对路径扫描门禁、社区资产（FAQ/赞助双语化），并在易考宝落地端到端全栈国际化及 AI 助教语言穿透能力。
- **核心决策**：
  1. **工程门禁与防偷懒防御**：引入 `scripts/guard_test_tampering.py`（对 assert/expect 关键字删除修改做 pre-commit 物理审计）与 `scripts/scan_hardcoded_paths.py`（扫描并禁止写死盘符与用户物理路径）；在 `scripts/setup-hooks.py` 中跨平台级联守卫、前端单元测试及后端单元测试。
  2. **根级全栈国际化 (i18n)**：前端建立轻量响应式国际化体系（`useLocale`、`localePreference`、`zh-CN.js`、`en-US.js`），支持双向键值与动态插槽严格对齐测试（`locale.test.js`）；API 请求层（`client.js`）自动向后端透传 `Accept-Language` 请求头。
  3. **AI 助教多语言穿透**：FastAPI 后端路由（`routes/ai.py`）、应用层（`ai_tutor_service.py`）及服务层（`ai_service.py`）解析并穿透 `target_lang` 参数，根据语言自动切换英文/中文 System Prompt、核心指导原则与结构化输出板块。
  4. **真实浏览器 E2E 闭环**：在 `browser_e2e.test.js` 中新增第 13 场景（Scenario 13），在独立 Chrome 实例中完整验证根节点 `lang` 属性更新、localStorage 持久化、页面重载零闪烁、主题切换联动与基线还原。
  5. **fnOS 应用包 (FPK) 自动化构建**：打包脚本 `scripts/build_fpk.py` 成功将更新后的前端产物及元数据构建为 `dist/easy-exam-1.0.9.fpk`。
- **对应 SPEC 章节**：SPEC.md §6, §8。
- **影响范围**：`scripts/`、`tests/test_guard_checks.py`、`frontend/src/locales/`、`frontend/src/composables/`、`frontend/src/design/`、`frontend/src/components/`、`backend/app/api/routes/ai.py`、`backend/legacy/services/ai_service.py`、`frontend/tests/browser_e2e.test.js`、`DECISIONS.md`、`SPEC.md`。

