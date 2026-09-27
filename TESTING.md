# 测试与交付证据规范

本文规定如何证明代码行为，不能替代 [SPEC.md](SPEC.md) 的产品规则，也不能把未运行的测试写成已通过。

## 1. 五条硬门禁

1. **缺陷即测试**：修复缺陷前先增加或定位能复现它的回归测试。
2. **契约优先**：输入、权限、状态转换和失败原因必须明确；不能用静默容错掩盖数据错误。
3. **根因全局治理**：修一处后搜索同类实现，检查事务、用户隔离、幂等、离线降级和前端使用链路。
4. **证据分层**：测试报告必须写明测试层级、命令、pass/fail/skipped/未运行；低层证据不能冒充高层验收。
5. **端侧物理可用**：移动端/受限视口适配必须剔除无物理外设支撑的特性（如键盘快捷键指南）；顶栏必须单行收拢（避免多行换行侵占视口）；核心交互触发源与即时反馈必须在首屏内零滚动可见，不能以“允许页面滚动”替代信息密度治理。

## 2. 测试层级

| 层级 | 证明什么 | 不能证明什么 |
|---|---|---|
| 纯函数/领域单测 | 算法、判分、状态转换 | API、数据库、真实用户流程 |
| API/Repository 集成测试 | 服务端路由、持久化和事务 | 浏览器交互、真实部署链路 |
| 前端 Node/契约测试 | 前端领域模型、组件契约 | 浏览器渲染、真实后端 |
| 真实浏览器 E2E | 用户界面到真实后端的物理链路 | 生产环境全部规模与网络条件 |
| 构建/静态检查 | 编译、打包、格式和空白 | 业务行为正确 |

涉及前端交互、持久化、迁移、导入、登录或关键学习状态时，必须显式执行对应的真实链路测试；不能把 Mock 测试称为 E2E。

## 3. 当前命令

```bash
# 后端全量测试
python -m unittest discover -s tests -v

# 前端单元/契约测试
npm --prefix frontend run test:unit

# 真实浏览器 E2E
npm --prefix frontend run test:e2e

# 生产构建
npm --prefix frontend run build

# 文档/补丁空白检查
python scripts/check_whitespace.py
git diff --check
```

如果命令因环境未执行，报告为“未运行”；如果存在 skipped，报告实际数量并说明原因，不得宣称全绿。

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
- 相关测试命令实际运行，失败和 skipped 数量已报告。
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
| `frontend/tests/browser_e2e.test.js` | Playwright 真实浏览器链路 |

## 7. 最终交付验收运行证据（2026-09-25）

| 测试层级与环节 | 执行命令 | 实际运行结果 | 状态 |
|---|---|---|---|
| 后端全量测试 | `python -m unittest discover -s tests` | 182 passed, 0 failed, 0 errors, 0 skipped (78.9s) | 通过 |
| 前端单元测试 | `npm --prefix frontend run test:unit` | 5 passed, 0 failed, 0 skipped (10.2ms) | 通过 |
| 前端生产构建 | `npm --prefix frontend run build` | Vite 打包成功 (dist/index.html, dist/assets/*)，exit code 0 | 通过 |
| 代码格式与补丁检查 | `git diff --check` | 0 errors (仅 CRLF 正常警告)，exit code 0 | 通过 |
| Chrome 真实端到端 E2E | `for ($i = 1; $i -le 10; $i++) { npm --prefix frontend run test:e2e }` | 连续 10 轮测试全部通过；每轮均严格为 13 passed, 0 failed, 0 skipped，总耗时 ~14s/轮，连续 10 次 exit code 0 | 通过 |
| 容器构建与真实运行 | `docker build -t easy-exam:delivery-check .` 及临时容器端口启动 | 镜像构建成功；临时目录挂载启动成功；`/api/v1/health` HTTP 200；`/` HTTP 200 (HTML)；Docker Healthcheck 探针正常返回 healthy；容器日志无报错；验证后已清理临时容器和数据 | 通过 |
| 外部真实商业搜索服务 | N/A | 本地未配置商业搜索引擎生产 API Key，代码已验证 `UNAVAILABLE` 优雅降级行为，真实外部在线搜索标记为【未验证（外部依赖）】 | 未验证 |
| 真实 fnOS 物理机部署 | N/A | 已验证 Docker 容器 Alpine 运行时与数据持久卷挂载，但未在真实物理 NAS (fnOS) 机器上安装实测，标记为【未验证（物理环境）】 | 未验证 |

