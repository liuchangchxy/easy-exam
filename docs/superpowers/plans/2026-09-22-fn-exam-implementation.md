# 飞牛刷题系统 (fn-exam) 核心工程实施计划 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于已审定的架构规范，构建轻量自托管、微信“考试宝”级交互体验的飞牛 NAS 刷题与全真模考系统。

**Architecture:** 采用单容器极简分层架构：前端 Vue 3 + Tailwind CSS 提供触屏手势切题、秒判变色与抽屉答题卡；后端 FastAPI 提供轻量 REST/SSE API；本地 SQLite 数据库启用 WAL 模式提供并发无锁持久化；集成纯 Python FSRS-5 算法与上下文打包 AI 助教。

**Tech Stack:** Python 3.11/FastAPI, SQLite 3 (WAL mode), Vue 3 + Vite + Tailwind CSS, OpenAI SDK (兼容 Ollama/Cloud LLM), openpyxl/csv.

**Spec:** [docs/superpowers/specs/2026-09-22-fn-exam-design.md](../../../docs/superpowers/specs/2026-09-22-fn-exam-design.md) 及 [SPEC.md](../../../SPEC.md)

---

## Global Constraints

- **资源上限**: 单 Docker 镜像常驻闲置内存必须严格控制在 50MB~100MB 范围内，禁止引入重量级服务依赖。
- **数据库规范**: 必须使用单文件 SQLite 并显式开启 `PRAGMA journal_mode=WAL;` 与 `PRAGMA busy_timeout=5000;`。
- **编码与平台规范**: 所有文件读写与子进程调用必须显式声明 `encoding="utf-8", errors="replace"`。
- **测试防倒退红线**: 所有功能必须先写测试再写实现，代码提交前测试套件必须 100% 通过且 `skipped=0`。
- **断点防丢失**: 答题数据必须在客户端 `localStorage` 毫秒暂存并在切题或防抖 5s 同步服务端。

---

## Review Focus

1. **并发写入防锁死**: SQLite 在客户端高频答题同步时的并发锁库风险，必须通过 WAL 模式与独立短事务保障。
2. **手势与滚动冲突**: 移动端手势左右切题不能误拦截用户浏览长题干时的垂直滚动（必须满足 $|\Delta x| \ge 40$ 且 $|\Delta x / \Delta y| \ge 1.73$）。
3. **多选题计分歧义**: 多选题漏选应判定为部分得分（如 0.5 分），但错选一项即全题 0 分。
4. **错题消灭时序**: 必须严格在连对次数达到 2 次时才将 `is_cleared` 置为 1，且一旦在后续复习答错，立即清零连对数并重新激活。
5. **AI 助教离线降级**: 当未配置 API Key 或 NAS 离线时，调用 AI 助教必须优雅返回友好提示，绝不抛出 500 导致界面死锁。

---

## Task Breakdown

### Task 1: 数据库核心底座与数据模型 (Database & Repositories)

**Files:**
- Create: `backend/database.py`, `backend/models.py`, `backend/repositories.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Consumes: 标准 SQLite3 模块与 Python 内置类型
- Produces: `init_db(db_path: str)`, `BankRepository`, `QuestionRepository`, `SessionRepository`, `MistakeRepository`

- [ ] **Step 1: 编写数据库底座的失败测试**

```python
# tests/test_database.py
import os
import tempfile
import unittest
from backend.database import init_db, get_connection
from backend.repositories import BankRepository, QuestionRepository

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_exam.db")
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_wal_mode_enabled(self):
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(mode.lower(), "wal")

    def test_bank_crud(self):
        repo = BankRepository(self.db_path)
        bank_id = repo.create_bank("公考行测", "行测真题库", "公务员")
        bank = repo.get_bank(bank_id)
        self.assertIsNotNone(bank)
        self.assertEqual(bank["name"], "公考行测")
        self.assertEqual(bank["question_count"], 0)

    def test_question_crud(self):
        b_repo = BankRepository(self.db_path)
        bank_id = b_repo.create_bank("测试题库", "描述", "科目")
        q_repo = QuestionRepository(self.db_path)
        q_id = q_repo.create_question(
            bank_id=bank_id,
            q_type="SINGLE",
            stem="1+1=?",
            options=[{"key": "A", "content": "1"}, {"key": "B", "content": "2"}],
            answer="B",
            explanation="基础算术",
            difficulty=1,
            tags=["数学", "初级"]
        )
        q = q_repo.get_question(q_id)
        self.assertIsNotNone(q)
        self.assertEqual(q["answer"], "B")
        self.assertEqual(len(q["options"]), 2)
```

- [ ] **Step 2: 运行测试验证其物理失败**

Run: `python -m unittest tests/test_database.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend'`

- [ ] **Step 3: 编写数据库与仓储层极简实现**

创建 `backend/database.py` 与 `backend/repositories.py`，实现 `init_db` 执行建表 SQL（包括 `banks`, `questions`, `sessions`, `mistake_records` 并开启 WAL 模式），实现 `BankRepository` 与 `QuestionRepository`。

- [ ] **Step 4: 重新运行测试确保 100% 通过**

Run: `python -m unittest tests/test_database.py`
Expected: PASS (Ran 3 tests, OK)

- [ ] **Step 5: 提交代码**

```bash
git add backend/database.py backend/repositories.py tests/test_database.py
git commit -m "feat: implement sqlite wal database layer and core repositories"
```

---

### Task 2: FSRS-5 复习调度与 6 级错因消灭引擎 (FSRS & Mistake Engine)

**Files:**
- Create: `backend/services/fsrs.py`, `backend/services/mistake_service.py`
- Test: `tests/test_fsrs_engine.py`

**Interfaces:**
- Consumes: `MistakeRepository`, `backend/models.py`
- Produces: `FSRSEngine.next_interval(rating, s, d) -> (new_s, new_d, due_date)`, `MistakeService.record_answer(q_id, is_correct, cause) -> result`

- [ ] **Step 1: 编写 FSRS 算法与错题消灭的失败测试**

```python
# tests/test_fsrs_engine.py
import unittest
from datetime import datetime, timedelta
from backend.services.fsrs import FSRS5
from backend.services.mistake_service import MistakeService

class TestFSRSEngine(unittest.TestCase):
    def test_fsrs_initial_state(self):
        fsrs = FSRS5()
        # Rating: 1=Again, 2=Hard, 3=Good, 4=Easy
        res_good = fsrs.schedule(rating=3, stability=0.0, difficulty=5.0)
        self.assertGreater(res_good.stability, 0.0)
        self.assertGreaterEqual(res_good.scheduled_days, 1)

    def test_mistake_two_consecutive_correct_kills_error(self):
        service = MistakeService()
        record = {"consecutive_correct": 0, "is_cleared": False}

        # 第一次答对
        rec1 = service.evaluate_answer(record, is_correct=True)
        self.assertEqual(rec1["consecutive_correct"], 1)
        self.assertFalse(rec1["is_cleared"])

        # 第二次连对 -> 自动消灭出库
        rec2 = service.evaluate_answer(rec1, is_correct=True)
        self.assertEqual(rec2["consecutive_correct"], 2)
        self.assertTrue(rec2["is_cleared"])

        # 后续一旦答错 -> 连对清零并重新激活
        rec3 = service.evaluate_answer(rec2, is_correct=False, cause="CONCEPT_GAP")
        self.assertEqual(rec3["consecutive_correct"], 0)
        self.assertFalse(rec3["is_cleared"])
        self.assertEqual(rec3["mistake_cause"], "CONCEPT_GAP")
```

- [ ] **Step 2: 运行测试验证其物理失败**

Run: `python -m unittest tests/test_fsrs_engine.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 提取并实现纯 Python FSRS-5 算法与错题消灭逻辑**

实现 `backend/services/fsrs.py`（无第三方依赖 FSRS 算法计算类）与 `backend/services/mistake_service.py`（封装 6 级错因与连对斩杀状态机）。

- [ ] **Step 4: 运行测试确保 100% 通过**

Run: `python -m unittest tests/test_fsrs_engine.py`
Expected: PASS (Ran 2 tests, OK)

- [ ] **Step 5: 提交代码**

```bash
git add backend/services/fsrs.py backend/services/mistake_service.py tests/test_fsrs_engine.py
git commit -m "feat: implement fsrs-5 memory algorithm and 2-consecutive mistake kill engine"
```

---

### Task 3: 答题评分器与会话草稿同步服务 (Scoring & Session Sync)

**Files:**
- Create: `backend/services/scoring.py`, `backend/services/session_service.py`
- Test: `tests/test_session_sync.py`

**Interfaces:**
- Consumes: `SessionRepository`, `QuestionRepository`
- Produces: `Scorer.evaluate(q_type, user_ans, correct_ans) -> (is_correct, score_ratio)`, `SessionService.sync_progress(session_id, draft_data) -> session`

- [ ] **Step 1: 编写多题型判分与会话同步失败测试**

```python
# tests/test_session_sync.py
import unittest
from backend.services.scoring import Scorer

class TestScoringAndSession(unittest.TestCase):
    def test_single_choice_scoring(self):
        is_cor, ratio = Scorer.evaluate("SINGLE", "A", "A")
        self.assertTrue(is_cor)
        self.assertEqual(ratio, 1.0)

        is_cor, ratio = Scorer.evaluate("SINGLE", "B", "A")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)

    def test_multi_choice_fractional_scoring(self):
        # 标准答案 ABCD
        # 完全正确
        is_cor, ratio = Scorer.evaluate("MULTI", "ABCD", "ABCD")
        self.assertTrue(is_cor)
        self.assertEqual(ratio, 1.0)

        # 漏选给部分分 (0.5)
        is_cor, ratio = Scorer.evaluate("MULTI", "AB", "ABCD")
        self.assertTrue(is_cor)
        self.assertEqual(ratio, 0.5)

        # 错选一项即 0 分
        is_cor, ratio = Scorer.evaluate("MULTI", "ABCE", "ABCD")
        self.assertFalse(is_cor)
        self.assertEqual(ratio, 0.0)
```

- [ ] **Step 2: 运行测试验证其失败**

Run: `python -m unittest tests/test_session_sync.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 编写 Scorer 与 SessionService 核心实现**

实现 `backend/services/scoring.py`，支持 SINGLE, MULTI, JUDGE 的快速秒判与部分得分。

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m unittest tests/test_session_sync.py`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add backend/services/scoring.py tests/test_session_sync.py
git commit -m "feat: implement instant answer scorer with multi-choice fractional support"
```

---

### Task 4: 题库解析与多格式导入流水线 (Bank Ingestion Pipeline)

**Files:**
- Create: `backend/services/importer.py`
- Test: `tests/test_importer.py`

**Interfaces:**
- Consumes: 纯文本 / CSV / Excel 数据
- Produces: `parse_markdown_text(text: str) -> list[QuestionDict]`, `parse_csv_content(csv_str: str) -> list[QuestionDict]`

- [ ] **Step 1: 编写题库导入解析器的失败测试**

```python
# tests/test_importer.py
import unittest
from backend.services.importer import TextExamParser

class TestImporter(unittest.TestCase):
    def test_parse_markdown_questions(self):
        content = """
1. 刑法中关于正当防卫的规定，下列说法正确的是？
A. 必须针对不法侵害人本人实行
B. 可以针对不法侵害人的亲友实行
C. 防卫过当不负刑事责任
D. 事后防卫也属于正当防卫
【答案】A
【解析】正当防卫只能针对不法侵害人本人。
        """
        questions = TextExamParser.parse(content)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["answer"], "A")
        self.assertEqual(len(questions[0]["options"]), 4)
        self.assertIn("正当防卫只能针对", questions[0]["explanation"])
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m unittest tests/test_importer.py`
Expected: FAIL

- [ ] **Step 3: 实现正则状态机题库解析器**

汲取 `pdf-exam-bank` 的分词状态机思路，编写稳定健壮的题干、选项、答案与解析提取器。

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m unittest tests/test_importer.py`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add backend/services/importer.py tests/test_importer.py
git commit -m "feat: implement robust regex state-machine question parser"
```

---

### Task 5: 题境感知 AI 助教与 SSE 流式输出服务 (Contextual AI Tutor)

**Files:**
- Create: `backend/services/ai_service.py`
- Test: `tests/test_ai_service.py`

**Interfaces:**
- Consumes: `question_context: dict`, `history: list`, `api_config: dict`
- Produces: `build_tutor_prompt(ctx: dict) -> list[dict]`, `stream_chat_completion(messages: list) -> Generator`

- [ ] **Step 1: 编写上下文打包与 Prompt 组装的失败测试**

```python
# tests/test_ai_service.py
import unittest
from backend.services.ai_service import build_tutor_prompt

class TestAIService(unittest.TestCase):
    def test_build_tutor_prompt_contains_all_context(self):
        ctx = {
            "stem": "我国现行宪法是哪一年颁布的？",
            "options": [{"key": "A", "content": "1954"}, {"key": "B", "content": "1982"}],
            "user_answer": "A",
            "correct_answer": "B",
            "explanation": "现行宪法为1982年宪法。",
            "mistake_cause": "CONCEPT_GAP"
        }
        messages = build_tutor_prompt(ctx, user_query="为什么我选 A 不对？")
        system_msg = messages[0]["content"]
        self.assertIn("1982", system_msg)
        self.assertIn("选错项：A", system_msg)
        self.assertIn("错因标签：CONCEPT_GAP", system_msg)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m unittest tests/test_ai_service.py`
Expected: FAIL

- [ ] **Step 3: 实现上下文组装器与 OpenAI/Ollama 适配器**

编写 `backend/services/ai_service.py`，实现优雅 Prompt 打包与离线优雅降级处理。

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m unittest tests/test_ai_service.py`
Expected: PASS

- [ ] **Step 5: 提交代码**

```bash
git add backend/services/ai_service.py tests/test_ai_service.py
git commit -m "feat: implement ai tutor context packager and prompt builder"
```

---

### Task 6: FastAPI 应用装配与端到端物理验收测试 (API & E2E Verification)

**Files:**
- Create: `backend/main.py`
- Test: `tests/test_e2e_flow.py`

**Interfaces:**
- FastAPI REST/SSE 路由接入所有核心服务
- 物理集成测试验证“创建题库 -> 做题秒判 -> 断点恢复 -> 错题连对 2 次消灭 -> AI 助教响应”完整流程

- [ ] **Step 1: 编写全链路真实物理 E2E 失败测试**

```python
# tests/test_e2e_flow.py
import unittest
import os
import tempfile
from fastapi.testclient import TestClient
from backend.main import create_app

class TestE2EFlow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "e2e_exam.db")
        self.app = create_app(db_path=self.db_path)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_practice_and_mistake_lifecycle(self):
        # 1. 创建题库
        r = self.client.post("/api/banks", json={"name": "全链路测试", "category": "测试"})
        self.assertEqual(r.status_code, 200)
        bank_id = r.json()["id"]

        # 2. 导入题目
        r = self.client.post(f"/api/banks/{bank_id}/questions", json={
            "stem": "地球是圆的吗？",
            "type": "SINGLE",
            "options": [{"key": "A", "content": "是"}, {"key": "B", "content": "否"}],
            "answer": "A",
            "explanation": "常识"
        })
        self.assertEqual(r.status_code, 200)
        q_id = r.json()["id"]

        # 3. 创建刷题会话
        r = self.client.post("/api/sessions", json={"bank_id": bank_id, "mode": "PRACTICE"})
        self.assertEqual(r.status_code, 200)
        session_id = r.json()["id"]

        # 4. 提交错误答案 -> 触发错题收录
        r = self.client.post(f"/api/sessions/{session_id}/answer", json={
            "question_id": q_id,
            "user_answer": "B",
            "mistake_cause": "READING_MISS"
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["is_correct"])

        # 5. 错题消灭模式：第一次答对
        r = self.client.post(f"/api/mistakes/{q_id}/practice", json={"user_answer": "A"})
        self.assertTrue(r.json()["is_correct"])
        self.assertFalse(r.json()["is_cleared"])

        # 6. 第二次连对 -> 彻底斩杀出库
        r = self.client.post(f"/api/mistakes/{q_id}/practice", json={"user_answer": "A"})
        self.assertTrue(r.json()["is_correct"])
        self.assertTrue(r.json()["is_cleared"])
```

- [ ] **Step 2: 运行 E2E 测试验证失败**

Run: `python -m unittest tests/test_e2e_flow.py`
Expected: FAIL

- [ ] **Step 3: 实现 FastAPI 主应用与路由调度**

编写 `backend/main.py` 整合所有 REST 接口并注册错误处理中间件。

- [ ] **Step 4: 运行全量测试套件验证全绿 (0 skipped)**

Run: `python -m unittest discover -s tests`
Expected: PASS (All tests passing, 0 skipped)

- [ ] **Step 5: 提交代码**

```bash
git add backend/main.py tests/test_e2e_flow.py
git commit -m "feat: assemble fastapi application and pass full physical e2e verification"
```

---

### Task 7: Vue 3 前端现代触控刷题交互与断点草稿 (Frontend UI & PWA)

**Files:**
- Create: `frontend/src/views/PracticeView.vue`, `frontend/src/components/AnswerSheet.vue`, `frontend/src/components/AiTutorDrawer.vue`, `frontend/src/composables/useSwipe.ts`
- Modify: `frontend/src/App.vue`

**Interfaces:**
- 消费后端 `/api/sessions`, `/api/banks`, `/api/ai/tutor`
- 提供考试宝级背题即判、滑动切题、底部答题卡抽屉与 `localStorage` 毫秒级断点草稿。

- [ ] **Step 1: 编写手势判定与本地草稿存储核心逻辑测试**
- [ ] **Step 2: 实现 Vue 3 核心组件与 Tailwind 样式**
- [ ] **Step 3: 本地构建与静态资源产物集成验证**
- [ ] **Step 4: 提交代码**

---

### Task 8: 单 Docker 镜像构建与飞牛 NAS 部署配方 (Containerization & fnOS Deploy)

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`
- Test: 本地 Docker 构建与内存基准验证

**Interfaces:**
- 制作 Alpine Linux + Python 3.11 极致轻量单镜像（常驻内存 < 100MB），挂载本地 SQLite 数据库。

- [ ] **Step 1: 编写轻量多阶段 Dockerfile**
- [ ] **Step 2: 构建测试镜像并验证内存占用**
- [ ] **Step 3: 提交部署配置文件**
