# 工程规范与防退化（Regression）防线守则 (TESTING.md)

本项目为保证 Vibe Coding 过程中的系统稳定与需求准确对齐，杜绝“代码改来改去、修复了 A 破坏了 B”的现象，全体开发与 AI 协作必须严格遵守以下工程红线：

---

## 一、四大铁律（Engineering Gates）

### 1. 缺陷即测试（Defect-Driven Testing）
* **原则**：任何被确认的 Bug 或需求调整，**严禁直接修改业务代码**。
* **标准流程**：
  1. **先写失败测试**：在测试套件中编写针对该 Bug 或新规则的测试用例；
  2. **验证必报错**：确保该测试在现有代码下**必定红灯报错**；
  3. **修改业务代码**：调整实现逻辑，直至该测试变绿；
  4. **终身防退化**：**该测试用例永久保留**，纳入日常全量自动化回归跑道。

### 2. 契约防线与禁止静默容错（Contract & Fail-Fast）
* **原则**：拒绝“宽松容错导致的静默死锁或数据漂移”。
* **契约断言**：前后端字段、配置键名、函数返回结构必须通过测试强校验对齐。

### 3. 根因全局治理与防头痛医头 (Root Cause Analysis - RCA)
* **原则**：排查并修复缺陷时，必须顺藤摸瓜对项目中所有同类逻辑进行全局检索，一次性彻底清除同类隐患，严禁只改孤立单行。

### 4. 双层自动化门禁（CI Gates）
* **本地门禁（Pre-Commit Hook）**：位于 `.git/hooks/pre-commit`。每次在执行 `git commit` 前自动运行全量测试，测试未全绿则本地直接拒绝提交。
* **远端门禁（GitHub Actions CI）**：位于 `templates/ci.yml`。每次向主分支推送或提交 PR 时，在干净 runner 环境上自动执行全量测试，红灯严禁合入。

---

## 二、收敛交付标准 (Definition of Done - DoD)

为防止“无限对抗审查导致精神内耗、修不彻底”，确立科学的交付收敛判定准则：

1. **Bug 严重度台阶分级**：
   - **P0 致命级**：数据丢失损坏、主流程死锁崩溃 ➔ **必须清零**；
   - **P1 严重级**：核心业务功能与 SPEC 不符、乱码 ➔ **必须修复**；
   - **P2 次要级**：极端网络抖动容错、文案优化 ➔ **记入待办，不阻断交付**；
   - **P3 洁癖级**：理论假想风险、微小代码格式 ➔ **直接忽略，严禁内耗**。
2. **交付绿灯条件**：
   - 所有 P0 / P1 问题已清零；
   - 自动化测试套件（含端到端测试）100% 通过且 `skipped=0`；
   - 达到上述条件即可果断确认验收通过并上线交付！

---

## 三、本地测试运行命令

```bash
# 运行全量测试套件 (82 个用例)
python -m unittest discover -s tests -p "test_*.py" -v

# 运行特定模块测试
python -m unittest tests/test_database.py
python -m unittest tests/test_fsrs_engine.py
python -m unittest tests/test_session_sync.py
python -m unittest tests/test_importer.py
python -m unittest tests/test_ai_service.py
python -m unittest tests/test_e2e_flow.py
python -m unittest tests/test_frontend_integration.py
python -m unittest tests/test_deployment_config.py
```

## 四、全量测试套件清单 (Test Manifest)

| 测试文件 | 覆盖领域与测试要点 |
| :--- | :--- |
| `tests/test_database.py` | SQLite WAL 模式、忙超时、级联外键、四大仓储 CRUD、并发读写安全 |
| `tests/test_fsrs_engine.py` | 纯 Python FSRS-5 算法状态流转、6 级错因分类、连续 2 次答对斩杀出库 |
| `tests/test_session_sync.py` | 单选/多选/判断评分器（支持多选部分分 0.5）、localStorage 草稿合并与会话生命周期 |
| `tests/test_importer.py` | 正则状态机纯文本/Markdown 试题切分、容错 CSV 别名映射、标准 JSON 导入器 |
| `tests/test_ai_service.py` | 题境感知 System Prompt 装配、OpenAI/Ollama 流式与非流式调用、网络离线优雅降级 |
| `tests/test_e2e_flow.py` | 真实物理 SQLite 单文件全生命周期集成测试（10 个复杂端到端场景） |
| `tests/test_frontend_integration.py` | FastAPI 根路径静态托管 Vue 3 编译产物 (`frontend/dist`) 与 PWA 元标签检验 |
| `tests/test_deployment_config.py` | Dockerfile 多阶段构建语法、Compose 编排有效性、生产无冗余臃肿依赖断言 |

