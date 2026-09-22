# 飞牛刷题系统 (fn-exam) 架构与需求规约设计书

- **创建日期**: 2026-09-22
- **设计主题**: 飞牛私有云 (fnOS) 自托管轻量刷题与全真模考系统 (fn-exam)
- **流程分类**: Superpowers Architectural Design
- **真理源映射**: 本文档与项目根目录 `SPEC.md` 严格同步并互为佐证。

---

## 1. 目标画像与核心价值 (Goals & Boundaries)

### 1.1 核心诉求与终极体验标杆
为飞牛 NAS (fnOS) 用户打造一款免受商业软件广告骚扰、数据 100% 本地自主可控的现代化刷题 Web 应用。
**交互体验全面对标并超越微信小程序「考试宝」**：
1. **背题秒判变色**：单选/判断点选瞬间给出正确（浅绿）/错误（浅红）视觉反馈并同步展示解析；
2. **移动触控手势**：手机端丝滑左右滑动手势切题，防误触横竖轴分离；
3. **底部抽屉答题卡**：随时向上滑出网格式答题卡（直观呈现已做、未做、存疑、正误）；
4. **断点自动续答**：客户端毫秒级本地缓存草稿，意外断电、锁屏、切屏无感 100% 恢复；
5. **智能助教互动**：做错题目无需复制题干，一键直呼 AI 针对错选逻辑一针见血剖析；
6. **科学抗遗忘复习**：集成现代 FSRS-5 遗忘曲线调度算法，杜绝“刷过即忘”。

### 1.2 资源与部署硬约束
1. **轻量常驻**：单容器极简部署，采用 FastAPI + Vue 3 静态编译 + 单文件 SQLite WAL 模式，整机常驻内存控制在 50MB~100MB，NAS 7×24 开机无感知。
2. **主仆解耦**：核心刷题系统严禁集成庞大的深度学习 OCR 运行环境；外部复杂 PDF/扫描件的重型版面解析作为独立微服务或通过 LLM API 异步完成。
3. **数据完全私有**：所有题库、进度、错因、笔记存放在挂载目录的 `fnexam.db`，备份迁移只需拷贝该单文件。

---

## 2. 12 大开源竞品全量源码吸收矩阵

本项目架构严禁闭门造车，各模块均已在本地真实克隆的代码中完成代码级验证与取舍：

| 序号 | 竞品仓库名 | 核心源码查验路径 | 🌟 吸收的精华 (Virtues Extracted) | 🗑️ 扬弃的糟粕 (Discards) |
| :--- | :--- | :--- | :--- | :--- |
| 1 | **heshengtao/exameow** | `frontend/src/views/Exam.vue` | **轻量容器架构**、手机端触控切题动效、单选题即选即判。 | 剔除其无多轮 AI、无记忆算法、解析只认死板 Markdown 的缺陷。 |
| 2 | **EXAM-MASTER** | `static/app.js:52` | **`localStorage` 自动草稿持久化**（选选项毫秒级落盘防丢）、底部抽屉答题卡。 | 剔除其全页白屏刷新与无现代化响应式组件的问题。 |
| 3 | **pdf-exam-bank** | `parser/pdf_parser_v2.py` | 正则状态机结构化拆题机制；**AI 解析在 SQLite 的缓存设计**。 | 剔除其纯正则在遇到复杂排版时的脆弱断裂缺陷。 |
| 4 | **MiaowTest** | `Express-node/llm/prompts/` | **上下文深度提示词工程**：题干+错选+正解+解析一键打包直送 LLM 追问。 | 剔除其无复习记忆逻辑与前端未针对移动端优化的缺陷。 |
| 5 | **gongkao** | `prisma/schema.prisma` | **6 级错因深度归因体系**；**“连续答对 2 次彻底消灭出库”** 机制。 | 剔除其臃肿的 Next.js 服务端渲染与 PostgreSQL 重度依赖。 |
| 6 | **OpenTutor** | `apps/api/services/spaced_repetition/fsrs.py` | **零依赖纯 Python FSRS-5 算法实现**（300 行纯函数，精准预测复习间隔）。 | 剔除其侧重教学大纲排课、缺乏高频刷题流的复杂框架。 |
| 7 | **xzs-mysql (学之思)** | `sql/xzs-mysql.sql` | **工业级标准试卷与题目 Schema**（涵盖复合题型、标准卷 vs 练习卷编排）。 | 剔除沉重庞大的 Java 依赖与陈旧的 PC 端页面。 |
| 8 | **anki** | `rslib/src/scheduler/` | **卡片四态生命周期状态机**（New, Learning, Review, Relearning）。 | 剔除其缺乏试卷答题卡、多选题与全真模考的 Flashcard 局限。 |
| 9 | **openedx-platform** | `common/lib/xmodule/` | **渲染与判分逻辑解耦 (XModule)**：客户端速判与服务端统分完全解耦。 | 剔除几十万行重型代码，仅吸取其评分判定器模式。 |
| 10 | **moodle** | `question/type/` | **题目/选项随机乱序 (Shuffle) 防死记**；多级题库标签体系。 | 剔除传统 PHP 服务端模板，采用现代前后端分离。 |
| 11 | **frappe-lms** | `frontend/src/components/Quiz.vue` | **现代高质感 UI**：自适应暗黑模式、环形进度指示器、答题计时组件。 | 剔除与 ERPNext 巨石框架的强耦合。 |
| 12 | **Razzia** | `packages/web/` | **正向游戏化激励**：答对连击 Combo 飘字、阶段性连胜徽章反馈。 | 剔除纯派对游戏化逻辑，服务于严肃备考场景。 |

---

## 3. 详细分层架构设计

### 3.1 总体分层架构
```
+-------------------------------------------------------------------+
|                        Vue 3 前端应用 (PWA)                         |
|  - 答题手势容器 (Touch/Swipe)      - 底部抽屉答题卡 (Bottom Drawer)   |
|  - localStorage 毫秒草稿保护      - AI 助教多轮对话抽屉 (SSE 流式)   |
|  - 实时判分变色反馈                - 连对 Combo 动效与暗黑主题        |
+-------------------------------------------------------------------+
                                  | REST / SSE API
+-------------------------------------------------------------------+
|                      FastAPI 后端服务 (Python 3.11)                 |
|  - /api/banks & /api/questions   : 题库与试卷元数据服务           |
|  - /api/sessions                 : 刷题会话与草稿增量同步服务     |
|  - /api/reviews                  : FSRS-5 调度与错题消灭引擎       |
|  - /api/ai/tutor                 : 题境打包与流式大模型代理       |
|  - /api/import                   : Excel/CSV/Markdown/LLM 导入管道 |
+-------------------------------------------------------------------+
                                  | SQLite Driver (WAL Mode)
+-------------------------------------------------------------------+
|                     持久化存储层 (SQLite WAL)                     |
|  - data/fnexam.db (单文件随拷随走，WAL 并发读写不锁库)            |
+-------------------------------------------------------------------+
```

---

## 4. 数据模型与存储架构设计 (Data & Persistence)

采用 SQLite 单文件存储，启动时执行 `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`。

### 4.1 核心表结构定义

#### 1. 题库大纲表 (`banks`)
```sql
CREATE TABLE banks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT DEFAULT '默认分类',
    question_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. 试题表 (`questions`)
```sql
CREATE TABLE questions (
    id TEXT PRIMARY KEY,
    bank_id TEXT NOT NULL,
    type TEXT NOT NULL,          -- 'SINGLE', 'MULTI', 'JUDGE', 'ESSAY'
    stem TEXT NOT NULL,          -- 题干 (支持 Markdown, LaTeX 公式, 本地图片)
    options_json TEXT NOT NULL,  -- JSON 数组: [{"key":"A","content":"..."}, ...]
    answer TEXT NOT NULL,        -- 正确答案，如 'A', 'ABCD', 'TRUE'
    explanation TEXT,            -- 题目解析 (Markdown)
    difficulty INTEGER DEFAULT 3,-- 难度星级 (1~5)
    tags_json TEXT,              -- 知识点标签 JSON: ["刑法", "侵占罪"]
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(bank_id) REFERENCES banks(id) ON DELETE CASCADE
);
```

#### 3. 做题会话与草稿表 (`sessions`)
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    bank_id TEXT NOT NULL,
    mode TEXT NOT NULL,          -- 'PRACTICE', 'EXAM', 'ELIMINATION', 'FSRS'
    total_questions INTEGER NOT NULL,
    current_index INTEGER DEFAULT 0,
    answers_json TEXT DEFAULT '{}',  -- JSON: {"q_id_1": {"answer": "A", "is_correct": true, "time": 12}}
    flags_json TEXT DEFAULT '[]',    -- 存疑标记题目 ID 数组
    time_spent INTEGER DEFAULT 0,    -- 累计耗时 (秒)
    time_limit INTEGER DEFAULT 0,    -- 限时 (秒, 0 为不限时)
    is_completed BOOLEAN DEFAULT 0,
    score REAL DEFAULT 0.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(bank_id) REFERENCES banks(id) ON DELETE CASCADE
);
```

#### 4. 错题与 FSRS 记忆档案表 (`mistake_records`)
```sql
CREATE TABLE mistake_records (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL UNIQUE,
    bank_id TEXT NOT NULL,
    mistake_count INTEGER DEFAULT 1,
    consecutive_correct INTEGER DEFAULT 0, -- 连对次数 (达到 2 自动消灭)
    is_cleared BOOLEAN DEFAULT 0,          -- 是否已消灭出库
    mistake_cause TEXT,                    -- 6 级错因: 'READING_MISS', 'CONCEPT_GAP' 等
    fsrs_state INTEGER DEFAULT 0,          -- 0=New, 1=Learning, 2=Review, 3=Relearning
    fsrs_stability REAL DEFAULT 0.0,       -- 稳定性 S (天)
    fsrs_difficulty REAL DEFAULT 5.0,      -- 难度 D (1.0~10.0)
    fsrs_due DATETIME,                     -- 下次到期复习时间
    last_review_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
);
```

---

## 5. 刷题与考试交互架构 (UX & Engine)

### 5.1 三大核心模式
1. **背题模式 (Practice Mode - 考试宝标杆体验)**：
   - **点选即判**：单选题、判断题点击选项时立即变色：用户所选若正确显浅绿背景，若错误显浅红背景并同步将正确选项标注浅绿。
   - **秒出解析**：选毕下方平滑滑出解析卡片，包含正确答案、官方解析、6 级错因打标入口、以及“向 AI 助教提问”快捷入口。
   - **自动跳题设置**：用户可随时切换“答对后 0.6s 自动跳下一题 / 保持停留在当前题”。
2. **全真模考模式 (Exam Mode)**：
   - **严格盲答**：点击选项仅呈现普通选中高亮，绝不透露正误与解析；
   - **计时控制**：顶部常驻倒计时悬浮条，耗尽自动交卷；
   - **存疑标记**：每题右上角提供“标记待查 (Flag)”图标，在答题卡上以醒目黄色书签角标显示；
   - **交卷多维诊断**：弹出包含未做题预警的二次确认窗口；交卷后生成全卷得分率、耗时统计与错题重盘清单。
3. **错题消灭模式 (Elimination Mode)**：
   - 专注打磨薄弱环节，仅拉取 `is_cleared = 0` 的错题。
   - 每次答对 `consecutive_correct` 累加 1；累加至 2 时弹出金色“彻底斩杀”轻动效，并从待消灭队列移除。

### 5.2 移动端手势与答题卡交互
- **左右滑动手势**：采用防误触判定算法（横向位移 $|\Delta x| \ge 40px$ 且纵横比 $|\Delta x / \Delta y| \ge 1.73$），确保垂直翻阅长题干时绝不误触发切题。
- **底部抽屉答题卡**：
  - 底部吸底条实时展示当前进度（例如 `18/100 答题卡`）；
  - 点击或向上轻扫唤出底部抽屉（支持半屏与全屏查看）；
  - 网格圆圈颜色编码：绿色（已对）、红色（已错）、蓝色（考试模式已答）、黄色（存疑标记）、灰色（未答）；
  - 点击任意圆圈 0 延迟锚定至目标题目并平滑回退抽屉。

### 5.3 数据零丢失草稿机制 (借鉴 EXAM-MASTER)
- 每次用户触碰选项，立即以 `fnexam_draft_{sessionId}` 存入浏览器 `localStorage`；
- 前端建立 5 秒防抖队列或切题触发，批量向后端 `/api/sessions/{id}/sync` 发送增量。
- 刷新页面、意外关机或移动端清理后台，再次进入同一会话时毫秒级自动读取草稿无感复原现场。

---

## 6. 错题归因体系与 FSRS 抗遗忘算法

### 6.1 六级靶向错因归因
做错题目后，解析卡片底部提供直观的单选胶囊标签：
1. `READING_MISS`：粗心审题 / 遗漏关键字（如“不属于”、“错误的是”）
2. `CONCEPT_GAP`：概念盲区 / 知识点未学过
3. `METHOD_GAP`：解法不熟 / 题型思路受阻
4. `OPTION_TRAP`：陷阱诱导 / 易混淆项蒙蔽
5. `CALCULATION_ERROR`：计算失误 / 手抖误点
6. `CARELESSNESS`：其他手滑

用户随时可在错题本中通过胶囊标签一键筛选（例如“考前集中突击【概念盲区】题”）。

### 6.2 原生 FSRS-5 算法集成
直接提取自 `OpenTutor` 的纯 Python `fsrs.py`：
- **四大评级响应**：
  - `Again` (彻底遗忘 / 做错): 稳定性置零重学，进入短周期复习；
  - `Hard` (勉强选对): 稳定性小幅递增；
  - `Good` (熟练做对): 按照标准艾宾浩斯与 FSRS 公式延展间隔；
  - `Easy` (秒杀掌握): 大幅跳升复习天数。
- **自适应最佳复习日**：根据设定的目标记忆保留率（默认 90%），精准计算 `fsrs_due` 日期，每天主页自动汇聚“今日待复习任务”。

---

## 7. 上下文 AI 智能助教与导入解耦架构

### 7.1 上下文直通 AI 助教 (MiaowTest 进化版)
- 点击“问 AI 助教”即唤出侧边抽屉；
- 前端自动将结构化上下文构造成系统消息：
  ```json
  {
    "stem": "关于刑法中侵占罪的表述，下列哪一选项是正确的？",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "user_answer": "B",
    "correct_answer": "D",
    "official_explanation": "...",
    "mistake_cause": "OPTION_TRAP"
  }
  ```
- **首轮点拨**：AI 自动聚焦“为什么选 B 是典型的偷换概念，而 D 才是正解”，免去用户反复打字陈述背景。
- **多轮流式对话**：支持基于 SSE 的打字机交互，内置快捷预设指令（“通俗解释”、“生成同类变式题”、“考点记忆口诀”）。
- **模型路由**：完全兼容 OpenAI API 规范，支持配置飞牛 NAS 本地 Ollama（如 `qwen2.5:7b`）或外网 API。

### 7.2 四级题库摄取流水线 (解耦设计)
1. **Tier 1 (标准模板导入)**：Excel / CSV 一键导入，带容错表头映射器。
2. **Tier 2 (纯文本/Markdown 状态机解析)**：借鉴 `pdf-exam-bank`，状态机智能解析标准序号（`1.`、`A.`、`【答案】`、`【解析】`）。
3. **Tier 3 (LLM 语义结构化清洗)**：对于格式错乱的纯文本考卷，一键调用 LLM 严格按照 JSON Schema 格式化输出题库。
4. **Tier 4 (复杂扫描件/PDF)**：解耦为外部 HTTP 导入钩子，系统提供标准开放 REST API，便于外挂本地 MinerU 或云端多模态进行预清洗后投递，保障核心应用镜像极致轻盈。

---

## 8. 规范自检与验收标准 (DoD)

1. **无占位符扫描**：全文无任何 TBD/TODO，所有表结构与业务流均具备完备定义。
2. **架构一致性**：SQLite WAL + FastAPI + Vue 3 贯穿始终，无隐藏重型依赖。
3. **单单交付验收**：
   - 单元测试：涵盖 FSRS-5 状态计算、题目判分器、Excel/Markdown 状态机解析器；
   - 端到端测试 (E2E)：覆盖“创建题库 -> 做题秒判变色 -> 断点续答恢复 -> 错题连续 2 次答对斩杀出库 -> AI 助教流式追问”完整链路，`skipped=0`。
