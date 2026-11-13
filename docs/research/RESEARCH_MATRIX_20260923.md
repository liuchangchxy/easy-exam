# 飞牛刷题软件：源码调查矩阵（临时研究稿）

> 状态：调查阶段，不是最终需求，不得直接替代 `SPEC.md` 或 `README.md`。
> 原则：代码事实优先；候选能力必须经过产品确认后才能落盘。

## 1. 当前项目的核心缺口（代码事实）

| 主题 | 代码证据 | 当前状态 | 初步风险 |
|---|---|---|---|
| AI 回答保存 | `backend/main.py` 只有 `/api/ai/tutor/chat` SSE；`frontend/src/components/AiTutorDrawer.vue` 使用内存 `messages` | 关闭抽屉/刷新后无法恢复 AI 回答 | AI 助教无法形成长期学习资产 |
| 多选题语义 | `backend/services/scoring.py` 漏选返回 `is_correct=True, score_ratio=0.5`；`session_service.py` 将 `is_correct` 传给错题服务 | 部分得分与“答对/掌握”共用一个布尔值 | 可能错误触发连续答对和错题出库 |
| 错题主线 | `mistake_records` 有计数、错因、FSRS 字段，但没有与 AI 对话/笔记形成统一对象 | 错题、解析、AI 对话分散 | 用户无法回到某道题的完整学习历史 |
| 复习语义 | 当前服务以答对/答错驱动 FSRS，尚未形成清晰的 Again/Hard/Good/Easy 用户评级界面 | 算法字段存在，产品语义未定 | FSRS 可能只是“换名字的错题重刷” |

## 2. 外部源码的实际能力

| 来源 | 代码事实 | 可借鉴候选 | 不能直接照搬的部分 |
|---|---|---|---|
| Exameow | `QuestionCard.vue` 做即时反馈；`wrongQuestions.ts` 用 localStorage 保存错题状态 | 题目卡片反馈、轻量本地草稿、移动端即时交互 | 仅靠 localStorage 不足以保存跨设备学习档案 |
| EXAM-MASTER | Flask + SQLite；`static/app.js` 保存 draft、分页答题、答题卡、倒计时自动交卷；`app.py` 有 history/favorites/exam_sessions | 模考会话、草稿恢复、答题卡、考试状态 | 题型和判分规则较简单，没有 FSRS/AI 学习闭环 |
| OpenTutor | `fsrs.py` 有完整卡片状态与 ReviewLog；`flashcards.py` 支持 1=Again、2=Hard、3=Good、4=Easy；review 后回写资产 | FSRS 状态、评级、到期复习、复习日志 | OpenTutor 的课程/卡片体系较重，不应整体移植 |
| Anki | scheduler 有 new/learning/review/relearning 状态和四级评级 | 复习状态机、重学与遗忘处理 | Anki 的完整调度器对本项目过重，需裁剪 |
| MiaowTest | `AgentMessageModel.js` 持久化对话和消息；控制器支持流式保存、历史、分页、重命名、收藏 | AI 会话持久化、历史恢复、题目上下文会话 | 不必照搬 Mongo/Node 技术栈 |
| Gongkao | Prisma 中有 `WrongQuestion`、`AgentTutorMessage`、`QuestionMistakeReview`、`AgentNote`，并通过 ID 建立关联 | 题目级学习档案、AI 讲解、错因复盘、笔记沉淀 | 其业务系统和会员/服务结构不适合直接移植 |
| Moodle | 多选题按答案 fraction 评分；保存每次 attempt 的选项顺序；支持反馈与重判 | 题目版本、作答尝试、部分得分与“正确”分离 | Moodle 的题库/权限体系远超本项目范围 |
| Open edX | `capa_block.py` 保存 `student_answers_history`、`score_history`、attempts、max_attempts，并控制何时显示答案 | 尝试历史、反馈时机、考试规则 | XBlock/CAPA 架构太重，不适合 NAS 轻量底座 |
| Frappe LMS | `Quiz.vue` 有计时、待复查、自动交卷、负分、考试安排、监考入口；提交模型保存成绩和逐题结果 | 完整考试生命周期、待复查、提交结果 | 监考、课程和权限能力不一定属于本项目需求 |
| pdf-exam-bank | `pdf_parser_v2.py` 以行和正则拆分题干、A-D 选项、答案、解析并输出 JSON | 作为 PDF 导入的基础兜底 | 对复杂排版、表格、图片、跨页题目支持有限 |

## 3. 初步主线假设（尚未确认）

系统不应以“集成了多少开源项目”为主线，而应以“每道题的个人学习档案”为主线：

```text
题目
 ├─ 作答尝试与判分
 ├─ 错因与用户自我解释
 ├─ 官方解析
 ├─ AI 助教会话与可保存结论
 ├─ 复习评级与 FSRS 状态
 └─ 掌握度/下一次复习计划
```

考试模式、错题模式、AI 助教、FSRS、笔记和统计都应围绕这个对象服务。

## 4. 必须逐项向用户确认的决策

1. AI 回答是否默认永久保存，还是只有用户点击“保存为本题笔记”才保存？
2. AI 回答保存粒度是保存完整对话，还是保存“最终结论/记忆口诀/避坑规则”等结构化卡片？
3. 多选题漏选是否算“部分得分但未掌握”，还是直接算错？
4. “错题出库”依据是连续答对、FSRS 评级、用户手动确认，还是三者组合？
5. FSRS 作用于所有题目，还是只作用于错题和用户标记的薄弱题？
6. 是否需要完整模考生命周期（倒计时、答题卡、待复查、自动交卷），还是只做练习流？
7. 是否需要题目版本和历史重判，还是导入后题目内容不可变？
8. PDF 导入是否属于首期能力，是否接受“复杂 PDF 需要人工校正”？
9. 是否需要用户、多个设备、跨设备同步，还是单用户单 NAS 本地使用？
10. 考试宝的研究范围是交互体验和功能观察，不复制品牌、内容和闭源实现。

## 5. 当前调查边界

- 源码已下载到本目录，未放入当前项目，也未安装外部依赖。
- 当前项目 `SPEC.md`、`README.md` 未修改。
- 本文档不代表最终架构或承诺。
- 只有用户逐项确认后的需求，才允许写入当前项目的规范文件。
