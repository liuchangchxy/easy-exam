# 🐮 飞牛刷题系统 (fn-exam)

<p align="center">
  <strong>专为飞牛私有云 (fnOS) NAS 量身定制的高颜值、自托管、微信「考试宝」交互体验、现代 AI 智能刷题系统</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Workflow-Spec--Driven%20Development-blue?style=flat-square" alt="SDD Workflow">
  <img src="https://img.shields.io/badge/UI-Exam--Bao%20Touch%20Parity-brightgreen?style=flat-square" alt="Exam-Bao UX">
  <img src="https://img.shields.io/badge/Algorithm-FSRS--5%20Spaced%20Repetition-purple?style=flat-square" alt="FSRS-5">
  <img src="https://img.shields.io/badge/Storage-SQLite%20WAL%20Single--File-orange?style=flat-square" alt="SQLite WAL">
  <img src="https://img.shields.io/badge/Memory-50MB~100MB%20Ultra--Light-success?style=flat-square" alt="Memory">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
</p>

---

## 🌟 核心价值与产品标杆

飞牛刷题系统 (`fn-exam`) 旨在解决公考、考研、教资、软考、驾考等备考用户在私有 NAS 上的自托管刷题需求。**交互体验全面对标并超越微信小程序「考试宝」**：

1. **背题秒判变色**：单选/判断点选瞬间给出正确（浅绿）/错误（浅红）视觉反馈，秒展官方解析与错因归因；
2. **移动端手势切题**：具备三角几何防误触（$|\Delta x| \ge 40\text{px}, |\Delta x / \Delta y| \ge 1.73$）的左右滑动手势切题，长屏纵向滚动绝不冲突；
3. **底部抽屉答题卡**：随手滑出半屏/全屏网格答题卡（绿对、红错、蓝已答、黄存疑、灰未答），0 延时瞬移锚定；
4. **断点零丢失保护**：客户端 `localStorage` 毫秒级草稿自动落盘，切题或防抖 5 秒增量同步，意外断电、锁屏、刷新 100% 原样恢复；
5. **科学抗遗忘 (FSRS-5)**：内嵌纯 Python 零依赖 FSRS-5 算法，动态计算遗忘临界点，提供精准的“每日到期复习”；
6. **靶向错题本与 6 级归因**：支持按 6 类错因归类（审题粗心、概念盲区、思路不熟、陷阱诱导、计算失误、其他手滑），**连续答对 2 次彻底出库斩杀**；
7. **题境感知 AI 智能助教**：做错题目一键直呼 AI，后台自动打包【题干+选项+错选项+正解+解析+错因标签】System Prompt，SSE 流式打字机解答，直通飞牛宿主机本地 Ollama 或云端 API；
8. **题库多格式极速摄取**：内置基于正则状态机的纯文本/Markdown 智能切题器、容错 CSV 映射器与标准 JSON 导入器。

---

## 🏗️ 架构全貌与 12 开源竞品萃取

本项目拒绝凭空自嗨与大模型幻觉，核心架构 100% 依托本地物理实测审查的 12 个顶级开源项目源码精华：

```
+-------------------------------------------------------------------+
|                        Vue 3 前端应用 (PWA)                         |
|  - 微信考试宝级触控切题手势       - 底部半屏抽屉答题卡 (5 色网格)       |
|  - localStorage 0ms 草稿保护      - AI 助教多轮 SSE 流式抽屉          |
|  - 即点即判秒变色反馈             - 连对 Combo 激励动画与暗黑主题      |
+-------------------------------------------------------------------+
                                  | REST / SSE API
+-------------------------------------------------------------------+
|                      FastAPI 后端服务 (Python 3.11)                 |
|  - 题库/题目服务 (Bank / Question) - 刷题会话与草稿同步 (Session)     |
|  - 纯 Python FSRS-5 调度引擎      - 6 级错因与 2 次连对斩杀引擎       |
|  - 题境 Prompt 装配与流式代理     - 正则状态机多格式导入管道          |
+-------------------------------------------------------------------+
                                  | SQLite WAL Driver
+-------------------------------------------------------------------+
|                     持久化存储层 (SQLite WAL)                     |
|  - /app/data/fnexam.db (单文件随拷随走，WAL 模式高并发读写不锁库)    |
+-------------------------------------------------------------------+
```

### 12 开源项目源码萃取矩阵

| 竞品项目 | 吸收源码精华 | 坚决剔除的糟粕 |
| :--- | :--- | :--- |
| **heshengtao/exameow** | **轻量容器架构**、手机端触控切题动效、单选题即选即判 | 剔除其无多轮 AI、无记忆算法、解析只认死板 Markdown 的缺陷 |
| **EXAM-MASTER** | **`localStorage` 自动草稿持久化**、底部抽屉答题卡 | 剔除其传统白屏刷新与无响应式组件的问题 |
| **OpenTutor** | **零依赖纯 Python FSRS-5 算法实现**（300 行纯函数，精准预测复习间隔） | 剔除其侧重排课大纲、缺乏高频做题流的复杂框架 |
| **gongkao** | **6 级错因深度归因体系**；**“连续答对 2 次彻底消灭出库”** 机制 | 剔除其臃肿的 Next.js 服务端渲染与 PostgreSQL 重度依赖 |
| **MiaowTest** | **上下文深度提示词工程**：题干+错选+正解+解析一键打包直送 LLM 追问 | 剔除其无复习记忆逻辑与前端未针对移动端优化的缺陷 |
| **pdf-exam-bank** | 正则状态机结构化拆题机制；**AI 解析在 SQLite 的缓存设计** | 剔除其纯正则在遇到跨页复杂排版时的脆弱断裂缺陷 |
| **xzs-mysql (学之思)** | **工业级标准试卷与题目 Schema**（涵盖复合题型、标准卷 vs 练习卷编排） | 剔除沉重庞大的 Java 依赖与陈旧的 PC 端页面 |
| **anki** | **卡片四态生命周期状态机**（New, Learning, Review, Relearning） | 剔除其缺乏试卷答题卡、多选题与全真模考的 Flashcard 局限 |
| **openedx-platform** | **渲染与判分逻辑解耦 (XModule)**：客户端速判与服务端统分完全解耦 | 剔除几十万行重型代码，仅吸取其评分判定器模式 |
| **moodle** | **题目/选项随机乱序 (Shuffle) 防死记**；多级题库标签体系 | 剔除传统 PHP 服务端模板，采用现代前后端分离 |
| **frappe-lms** | **现代高质感 UI**：自适应暗黑模式、环形进度指示器、答题计时组件 | 剔除与 ERPNext 巨石框架的强耦合 |
| **Razzia** | **正向游戏化激励**：答对连击 Combo 飘字、阶段性连胜徽章反馈 | 剔除纯派对游戏化逻辑，服务于严肃备考场景 |

---

## 🚀 极速部署指南 (fnOS / Docker)

### 方式 1：Docker Compose 一键启动（推荐）

在飞牛 NAS 的 Docker 应用管理或本地终端中：

```bash
# 1. 启动服务
docker compose up -d

# 2. 检查日志与运行状态
docker compose logs -f
```

- **访问地址**：`http://<你的NAS_IP>:3000`
- **数据目录**：宿主机 `./data/fnexam.db`，备份迁移只需拷贝该单文件。
- **直通本地 Ollama**：默认自动配置 `http://host.docker.internal:11434/v1` 直通宿主机上的 Ollama 实例。

### 方式 2：使用一键自动化脚本
- **Linux / fnOS**: `bash scripts/deploy_fnos.sh`
- **Windows / 本地**: `powershell -ExecutionPolicy Bypass -File scripts/deploy_fnos.ps1`

### 方式 3：本地源码调试运行
```bash
# 安装轻量生产依赖
pip install -r requirements.txt

# 本地启动后端（自动托管 frontend/dist 静态资源）
python -m uvicorn backend.main:app --host 0.0.0.0 --port 3000
```

---

## 🤖 AI Agent 协作开发守则 (针对接手的新 Agent)

如果你是新接入本项目进行开发、修复 Bug 或添加新特性的 AI Agent，**请务必首先强制遵循以下四项原则**：

1. **唯一业务真理源 (SSOT)**：
   - 任何业务行为以 [SPEC.md](SPEC.md) 与 [docs/superpowers/specs/2026-09-22-fn-exam-design.md](docs/superpowers/specs/2026-09-22-fn-exam-design.md) 为准；
   - 收到用户的新需求或改动指示，**严禁直接修改业务代码**，必须第一时间调用工具同步更新 `SPEC.md`。
2. **测试驱动防退化 (TDD)**：
   - 遵循 [TESTING.md](TESTING.md) 守则：修改代码前必须先写失败测试，严禁反向篡改旧测试判定标准；
   - 本地 Git 配置了物理 pre-commit 钩子，**严禁使用 `--no-verify`**，提交前必须保证所有测试 100% 全绿（`skipped=0`）。
3. **避坑经验自学习**：
   - 查阅 [AGENTS.md](AGENTS.md) 底部的【历史教训与避坑清单】，严格遵守其中的 12 条红线（特别是 Windows UTF-8 编码、主系统与重型 OCR 深度学习环境解耦、防自嗨跑偏等）。
4. **决策留痕**：
   - 涉及破坏性变更或重要架构调整，在 [DECISIONS.md](DECISIONS.md) 中追加 ADR 记录。

---

## 📁 项目工程目录索引

```text
飞牛刷题软件/
├── AGENTS.md                  # AI 行为宪法与自进化避坑清单
├── SPEC.md                    # 业务规约唯一真理源 (SSOT)
├── TESTING.md                 # 自动化测试与质量防线守则
├── DECISIONS.md               # 架构决策记录簿 (ADR)
├── Dockerfile                 # Alpine 多阶段轻量镜像构建文件
├── docker-compose.yml         # 飞牛 NAS / 生产部署编排配方
├── requirements.txt           # 极简生产依赖 (fastapi, uvicorn, pydantic)
├── backend/                   # 后端 FastAPI 核心模块
│   ├── config.py              # 配置中心 (支持环境变量覆盖)
│   ├── database.py            # SQLite WAL 底座与并发防锁
│   ├── models.py              # 领域数据模型与枚举
│   ├── repositories.py        # 事务安全数据访问仓储层
│   ├── main.py                # 应用装配与 REST/SSE 路由接入
│   └── services/              # 核心业务引擎
│       ├── fsrs.py            # 纯 Python FSRS-5 记忆算法
│       ├── mistake_service.py # 6 级错因与 2 次连对斩杀引擎
│       ├── scoring.py         # 秒判评分器 (支持多选部分分)
│       ├── session_service.py # 会话调度与断点草稿同步
│       ├── importer.py        # 题库正则状态机与多格式导入器
│       └── ai_service.py      # 题境感知 AI 助教与 SSE 流
├── frontend/                  # Vue 3 前端工程
│   ├── index.html             # 移动端 PWA 壳与元标签
│   ├── vite.config.js         # Vite 构建配置
│   ├── src/
│   │   ├── App.vue            # 仪表盘主页与草稿复原提示
│   │   ├── views/
│   │   │   └── PracticeView.vue # 考试宝级触控刷题核心视图
│   │   ├── components/
│   │   │   ├── AnswerDrawer.vue # 5 色网格抽屉答题卡
│   │   │   └── AiTutorDrawer.vue# SSE 流式 AI 助教抽屉
│   │   └── composables/
│   │       ├── useSwipe.js    # 防误触切题手势 hook
│   │       └── useDraftStorage.js # localStorage 毫秒断点草稿 hook
│   └── dist/                  # 预编译静态资源产物
├── docs/                      # 架构设计与工程规约
│   └── superpowers/
│       ├── specs/             # 2026-09-22-fn-exam-design.md
│       └── plans/             # 2026-09-22-fn-exam-implementation.md
├── scripts/                   # 运维、快照与部署脚本
│   ├── deploy_fnos.sh         # fnOS 一键启动脚本
│   ├── deploy_fnos.ps1        # 本地 PowerShell 启动脚本
│   └── checkpoint.py          # 秒级影子微快照工具
└── tests/                     # 自动化物理测试套件 (82 用例全绿)
    ├── test_database.py       # 数据库与仓储层测试
    ├── test_fsrs_engine.py    # FSRS 算法与错题消灭测试
    ├── test_session_sync.py   # 评分器与草稿同步测试
    ├── test_importer.py       # 多格式导入器测试
    ├── test_ai_service.py     # AI 助教服务测试
    ├── test_e2e_flow.py       # 物理端到端全链路集成测试
    ├── test_frontend_integration.py # 前端集成与静态托管测试
    └── test_deployment_config.py    # 部署配方与容器规范测试
```

---

## 📄 开源协议
本项目采用 [MIT License](LICENSE) 开源协议。
