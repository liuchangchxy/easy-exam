# 易考宝 (EasyExam) 核心业务规约与需求规约 (SPEC.md)

> **文档性质**：本项目唯一业务规范真理源（Single Source of Truth, SSOT）。
> **核心原则**：所有业务逻辑改动、新功能扩展或缺陷修复，必须**先修订本文档**，再编写测试用例，最后调整实现代码。任何偏离本文档定义的行为均视为 Bug。

---

## 1. 系统定位与核心价值

- **项目名称**：易考宝 (`easy-exam`)
- **副标题**：私有云刷题与错题消灭系统
- **一句话定位**：专为飞牛私有云 (fnOS) 等自托管环境深度优化的现代高颜值、自托管、现代 AI 智能刷题系统。
- **商店上架合规规范 (Store Compliance)**：
  - **正式中文名称**：易考宝 (EasyExam)
  - **英文服务标识 / 包名**：`easy-exam`
  - **Docker 镜像与容器**：`easy-exam` (镜像 `ailm32442/easy-exam:latest`)
  - **合规红线**：为彻底符合飞牛应用中心（及第三方 NAS 应用商店）官方上架审核要求，严禁在主名称中使用“飞牛”、“fnOS”作为前缀，规避官方商标冲突风险；在兼容性描述中说明支持飞牛私有云。
- **终极产品体验标杆**：**全面对标并超越微信小程序「考试宝」的极致刷题手感**：
  1. 背题模式点选即判（绿对红错，秒展解析与考点）；
  2. 全真模考支持限时计时、悬浮抽屉答题卡与交卷多维诊断；
  3. 移动端丝滑触屏左右滑动手势切题；
  4. `localStorage` 级毫秒断点自动续答，意外断电、锁屏、刷新 100% 无损恢复。
- **运行环境与约束**：
  - 飞牛 OS (fnOS) 单 Docker 容器一键部署，数据持久化于本地 SQLite 单文件 (`easyexam.db` / `fnexam.db` 自动兼容兼容)；
  - 闲置内存严格控制在 **30MB~50MB**，CPU 占用接近 0，私有云 NAS 7×24 小时开机零负担；
  - 手机、iPad 平板、电脑浏览器多端响应式自适应，手机端支持 PWA 添加到主屏幕全屏无边框运行。

---

## 2. 12 大开源项目精华吸取契约 (Sourced Architecture Matrix)

本项目拒绝闭门造车，核心架构与算法 100% 依托本地已审查的 12 个顶级开源项目源码精华：

| 系统维度 | 纯源码吸收来源 (已实证文件) | 坚决剔除的糟粕 | 本项目中具体落地实现规范 |
| :--- | :--- | :--- | :--- |
| **刷题交互手感** | **Exameow** (`QuestionCard.vue`)<br>+ **EXAM-MASTER** (`app.js:52`) | 剔除 EXAM-MASTER 的整页白屏刷新与 Exameow 无法追问的缺陷 | **背题即判 + 抽屉答题卡 + 断点秒恢复**：单选/判断点选即判变色；原生抽屉答题卡；`input` 监听秒级存入 `localStorage` 恢复。 |
| **错题消灭机制** | **gongkao** (`schema.prisma:88`)<br>+ **Exameow** | 剔除 gongkao 绑定的 MySQL 商业 VIP 会员付费代码 | **靶向错题本**：6 维错因打标（概念混淆/选项陷阱/审题粗心等），支持单类错因定向重练，连续答对 2 次彻底消灭。 |
| **智能讲题助教** | **MiaowTest** (`Express-node/llm/`) | 剔除其强依赖的大型 MongoDB 容器 | **带题上下文追问**：做错后一键后台打包【题干+错选+正解+错因】，支持向飞牛本地 Ollama 或云端 API 连续追问。 |
| **抗遗忘复习算法** | **OpenTutor** (`fsrs.py`)<br>+ **Anki** (`rslib/scheduler/`) | 剔除纯卡片翻牌形态与大型微服务包体积 | **原生 FSRS 调度**：直接移植无第三方依赖的纯 Python `fsrs.py`，根据做题掌握度动态计算下一次复习周期。 |
| **真题摄取切片** | **pdf-exam-bank** (`pdf_parser_v2.py`) | 剔除纯正则死板脆弱容易漏题的缺陷 | **状态机切片 + AI 容错**：正则状态机识别题号与选项，结合大模型缝合卷末分离答案，左右分栏核验入库。 |
| **题型与评分规则** | **学之思** (`xzs-mysql.sql`)<br>+ **Moodle** + **Open edX** | 剔除学校教务管理、年级班级、排课防作弊几十万行代码 | **标准题库模型**：解耦题型判定器，支持单选/多选/判断，支持选项随机打乱（防死记）与多选题部分得分。 |
| **视觉美学与正反馈** | **Frappe LMS** (`Quiz.vue`)<br>+ **Razzia** | 剔除 Frappe 框架强绑定与 Razzia 纯派对游戏化 | **现代 UI 审美与连对动效**：Tailwind CSS 精致暗黑模式、做题连对 Combo 微动效激励。 |
| **NAS 容器底座** | **Exameow** (`Dockerfile`) | 剔除 Java(xzs)、MongoDB(Miaow)、MySQL(gongkao) 等重型服务 | **极简 Alpine 单容器**：FastAPI + Vue 3 静态托管 + SQLite，整机常驻内存 < 50MB。 |

---

## 3. 核心功能清单与业务规则契约 (Feature Matrix)

### 3.1 第一核心：对标微信小程序「考试宝」的刷题引擎 (Practice Engine)

#### 1. 背题模式 (Learning Mode)
- **业务规则**：
  - **单选/判断即点即判**：用户点击选项瞬间，已选项给出颜色反馈（选对变绿，选错当前项变红且高亮绿色正确项）；下方平滑无损展开“正确答案”、“官方解析”与“问 AI 助教”按钮；
  - **多选题确认提交**：支持多选勾选，选中后点击底部浮动“确认提交”进行判定，支持按 Moodle 规则计算部分得分；
  - **自动跳转**：用户可开启“答对后 0.8s 自动切到下一题”；若答错则强制停留在当前题，供复盘解析；
  - **移动端手势切题**：屏幕支持左右滑动手势（Swipe）上一题/下一题，手感与小程序无异。

#### 2. 全真模考模式 (Exam Mode)
- **业务规则**：
  - **限时与不限时**：支持设置倒计时（如 60 分钟 / 120 分钟），倒计时结束自动强制交卷；交卷前绝不提前透露任何答案和对错；
  - **悬浮答题卡抽屉**：点击底部工具栏随时呼出全局答题卡（蓝色已答、灰色未答、黄色待查标记），点击题号毫秒级无损跳转；
  - **全方位断点续答**：采用 EXAM-MASTER 机制，每次作答实时更新 `localStorage` 和后端 Session，无论刷新、误关网页或设备休眠，重新进入 100% 恢复进度。

#### 3. 模考交卷诊断分析
- **业务规则**：交卷后立即生成成绩单：包含总得分、答题耗时、正确率，以及按题型/知识点的错题雷达图。

---

### 3.2 第二核心：靶向错题本与 FSRS 抗遗忘闭环 (Review & Mastery)

#### 1. 错题自动收录与消灭机制
- **业务规则**：
  - 任何练习或模考中做错的题目，自动归档进入该题库的专属“错题本”；
  - **做题会话模式联动**：在 `PRACTICE`、`ELIMINATION` 与 `FSRS` 模式下，提交作答均实时驱动错题记录、连对状态与 FSRS 记忆调度更新（全真模考 `EXAM` 模式除外）；
  - **错题消灭（移出）规则**：在错题攻坚 (`ELIMINATION`) 模式下，仅装载活跃未消灭的错题，题目被“连续答对 2 次”或被用户手动标记为“已完全掌握”，系统自动将其移出活跃错题集；若当前题库没有待消灭错题，界面展示友好横幅：“🎉 恭喜！当前题库没有待消灭的错题！”。

#### 2. 六维错因打标（吸收 gongkao 优点）
- **业务规则**：
  - 答错题目时，界面提供一键错因归类选项：
    1. `READING_MISS`（审题遗漏 / 粗心看错）
    2. `CONCEPT_GAP`（概念欠缺 / 知识未掌握）
    3. `METHOD_GAP`（解法未掌握 / 逻辑断层）
    4. `OPTION_TRAP`（掉入出题人陷阱）
    5. `CALCULATION_ERROR`（计算错误）
    6. `CARELESSNESS`（手滑手误）
  - **靶向复习**：在错题本中支持筛选“只看掉入陷阱的题”或“只看概念欠缺的题”，实现有的放矢。

#### 3. 科学抗遗忘调度（吸收 OpenTutor / Anki 原生 FSRS 算法）
- **业务规则**：
  - 后端直接集成无外部依赖的纯 Python `fsrs.py` 算法模块；
  - 根据用户历史做题的稳定度（Stability）与难度（Difficulty），动态预测记忆遗忘临界点，在第 1 天、第 3 天、第 7 天推送到“每日抗遗忘复习任务”中。

---

### 3.3 第三核心：上下文关联的 AI 智能讲题助教 (AI Tutor)

#### 1. 自动上下文打包（吸收 MiaowTest 优点）
- **业务规则**：
  - 用户在做题或复盘错题时，点击“问 AI 助教”，无需用户手动复制题干；
  - 系统在后台自动将以下要素组装成系统 Prompt：
    - `【题干】` + `【各选项内容】` + `【正确答案】` + `【用户选错项】` + `【官方题库解析】` + `【用户标记的错因】`；
  - 前端以右侧抽屉（桌面端）或底部半屏抽屉（移动端）滑出聊天面板，首句由 AI 直接针对用户的错选进行一针见血点拨：“你选择了 B，但本题的陷阱在于……”。

#### 2. 多轮连续追问与启发式教学
- **业务规则**：
  - 用户可在抽屉中继续打字：“请通俗解释一下这个概念”、“能不能出一道同类变式题考考我”；
  - 后端采用 Server-Sent Events (SSE) 流式打字机输出，响应迅速不卡顿。

#### 3. 飞牛私有云模型路由
- **业务规则**：
  - 后端采用标准 OpenAI 协议客户端：
    - 本地优先：直连飞牛 NAS 内部运行的 Ollama / vLLM（如 `http://localhost:11434/v1`，运行 Qwen2.5 / DeepSeek-R1-Distill，完全离线且零费用）；
    - 在线补充：支持用户配置云端 API Key（DeepSeek、硅基流动、OpenAI、Gemini 等）。

---

### 3.4 第四核心：题库管理与真题灵活摄取 (Bank & Ingestion)

#### 1. 题库分类管理
- **业务规则**：支持创建多个独立科目（如“计算机软考”、“公考行测”、“自考英语”、“驾考科目一”），每个题库拥有独立的练习进度、错题本与 FSRS 记忆曲线。

#### 2. 标准格式极速导入导出
- **业务规则**：
  - 支持标准 Excel (.xlsx/.xls) 与 CSV 文件上传；
  - 内置智能列映射器（Column Mapper），自动匹配“题干、选项A~D、答案、解析”等表头。

#### 3. 辅助摄取：已有试卷文本/PDF 规范化清洗
- **业务规则**：
  - 针对市面上下载的网盘真题文档，采用 `pdf-exam-bank` 的题号与选项状态机切分初筛；
  - 遇到双栏排版错乱或答案分离在文末附录的考卷，调用大模型做 Structured Output (JSON Schema) 后置校准修复，用户在左右分栏工作台中核对无误后一键入库。

---

## 4. 核心数据结构契约 (Data Contracts)

本系统采用单文件 SQLite 数据库，核心表定义规范如下：

### 4.1 题库表 (`banks`)
```sql
CREATE TABLE banks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    subject TEXT,
    question_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 试题表 (`questions`)
```sql
CREATE TABLE questions (
    id TEXT PRIMARY KEY,
    bank_id TEXT NOT NULL,
    type TEXT NOT NULL,          -- 'single_choice', 'multi_choice', 'true_false', 'fill_blank'
    stem TEXT NOT NULL,          -- 题干内容，支持 Markdown 与本地图片路径
    options_json TEXT NOT NULL,  -- JSON: [{"key":"A","content":"..."}, ...]
    answer TEXT NOT NULL,        -- 正确答案，如 'A', 'BC', 'T'
    analysis TEXT,               -- 官方或 AI 题目解析
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(bank_id) REFERENCES banks(id) ON DELETE CASCADE
);
```

### 4.3 做题会话与断点草稿表 (`sessions`)
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    bank_id TEXT NOT NULL,
    mode TEXT NOT NULL,          -- 'PRACTICE', 'EXAM', 'ELIMINATION', 'FSRS'
    total_questions INTEGER NOT NULL,
    current_index INTEGER DEFAULT 0,
    answers_json TEXT DEFAULT '{}',  -- JSON: {"q_id": {"answer": "A", "is_correct": true, "time": 12}}
    flags_json TEXT DEFAULT '[]',    -- 标记待查题目 ID 列表
    time_spent INTEGER DEFAULT 0,    -- 耗时 (秒)
    time_limit INTEGER DEFAULT 0,    -- 考试限时 (秒)
    is_completed BOOLEAN DEFAULT 0,
    score REAL DEFAULT 0.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(bank_id) REFERENCES banks(id) ON DELETE CASCADE
);
```

### 4.4 做题记录与错题追踪表 (`practice_records` / `mistake_records`)
```sql
CREATE TABLE practice_records (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    bank_id TEXT NOT NULL,
    user_answer TEXT,
    is_correct BOOLEAN NOT NULL,
    wrong_reason TEXT,           -- 吸收 gongkao: 'READING_MISS', 'CONCEPT_GAP', 'OPTION_TRAP' 等
    consecutive_correct INT DEFAULT 0, -- 连续答对次数，>=2 自动消灭移出错题本
    is_cleared BOOLEAN DEFAULT 0,      -- 是否已从错题本消灭
    fsrs_state INTEGER DEFAULT 0,      -- 0=New, 1=Learning, 2=Review, 3=Relearning
    fsrs_difficulty REAL DEFAULT 5.0,  -- FSRS 难度值 (1.0 - 10.0)
    fsrs_stability REAL DEFAULT 0.0,   -- FSRS 稳定性 (天数)
    fsrs_due DATETIME,                 -- 下次复习到期时间
    reps INT DEFAULT 0,                -- 重复复习次数
    last_practiced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
);
```

---

## 5. 飞牛 OS (fnOS) 部署与容器契约

- **交付方式**：单一 Docker 镜像 (`ailm32442/fn-exam:latest`)；
- **极简部署命令**：
  ```bash
  docker run -d \
    --name fn-exam \
    -p 3000:3000 \
    -v /vol1/1000/docker/fnexam/data:/app/data \
    -e PORT=3000 \
    ailm32442/fn-exam:latest
  ```
- **数据完全自主可控**：所有题库、错题、做题记录均保存在本地宿主机挂载目录的 `data/fnexam.db`，备份或重装 NAS 仅需拷走该单文件；
- **健康检查探针契约**：容器通过 `HEALTHCHECK` 探针动态读取环境变量 `PORT`（默认 3000）请求 `/api/health` 探活，确保自定义端口部署时健康状态精准上报。

---

## 6. 边缘情况与容错防御 (Edge Cases)

1. **断网与纯离线防御**：在没有配置 AI API 或 NAS 处于局域网断网状态时，所有做题、背题、模考、答题卡、错题消灭、FSRS 算法全部 100% 在本地正常运行，仅在点击“问 AI”时优雅降级提示。
2. **移动端手势冲突防御**：滑动手势切题仅在横向位移绝对值 $> 50px$ 且纵向滑动偏角 $< 30^\circ$ 时触发，绝不干扰用户垂直浏览长题干时的正常上下滚动。
3. **高频点击防抖**：单选题点选即判瞬间增加 300ms 交互锁，防止用户快速双击或误触导致跳过题目。
