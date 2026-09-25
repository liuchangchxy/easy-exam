# 题库导入可靠性与开源实现选择性复用

> **执行规则：** 按 `easyexam-implementation` skill 与 `docs/ANTIGRAVITY_WORKFLOW.md` 执行。范围来自 `SPEC.md` §5、§8：格式预检、重复题策略、坏 PDF 拒绝。计划不改变支持格式、不增加 OCR。

**目标：** 借鉴适配度高且许可允许的成熟代码，补齐表格映射体验并保证单次批量导入失败不会留下部分题目；将源代码采用事实与行为参考明确区分。

## 任务 1：复用/改编 Exameow 导入解析

**固定源：** `exameow@70e0d70`（Apache-2.0），源码副本 `C:\Users\chang\Desktop\code\fn-exam-source-research-20260923\exameow`。

**源文件：** `frontend/src/utils/importParser.ts`、`frontend/src/utils/importParser.test.ts`；另检查 `THIRD_PARTY_LICENSES.csv` 及对应依赖。目标现状：`backend/app/infrastructure/importers/spreadsheet_importer.py`。

- [x] 逐文件阅读源解析和测试，检查 Apache NOTICE/third-party license 义务；在实施前将精确源文件→目标文件/改写说明加入开源审计。若移植落在非 Python 层或导致重复解析器，先说明选择理由。
- [x] 写当前 XLSX/CSV 代表性输入、别名、缺列、歧义标题与手工列映射测试，先运行 RED。
- [x] 只移植可复用映射算法/用例，不复制页面、worker 或无关依赖；让用户能够预览并修正列映射，再确认导入。
- [x] 保持现有题库字段、重复题 `skip/new/merge` 语义与 PDF 拒绝规则；数据字段不明确时停问。
- [x] 更新 `OSS_REUSE_AUDIT.md` 为“已移植”，写源 SHA、许可证、attribution 和目标路径；若最终只参考测试/行为则如实写“未复制”。

## 任务 2：批量导入事务原子性（EXAM-MASTER 行为模式）

**参考源：** `exam-master@b7e59fe`（MIT），`db.py` 的 `import_csv` 和 `tests/test_app.py` 的坏 CSV 回滚用例。目标为借鉴事务边界和测试，不要求原样复制 Flask 代码。

**文件：** `backend/app/application/import_service.py`、`backend/app/infrastructure/db/repositories/question_repository.py`、`backend/app/infrastructure/db/connection.py`（若需事务接口）、`tests/test_v1_import.py`、`tests/test_v1_pdf_import.py`。

- [x] 先构造批次中前一题有效、后一题触发真实数据库写失败的测试；断言无题目/版本/导入伪成功残留，失败 job 可审计，确认 RED。
- [x] 设计最小 repository batch transaction，不要将一个事务嵌套成每题独立提交；同一批的新增题、版本与 bank-item 引用应一致提交或整体回滚。
- [x] 为 `skip/new/merge`、无重复、重复需选择策略、解析预检失败和数据库中途失败分别测落盘数量与 job 状态。
- [x] 对 PDF 与 XLSX/CSV 入口使用同一原子写入机制；不要吞掉异常或在回滚后写 `IMPORTED`。
- [x] 明确在审计中标记“事务实现模式/测试参考”或精确记录直接代码拷贝，不夸大源码复用。

## 任务 3：迁移/解析边界与防退化

- [x] 检查目前 XLSX、CSV、JSON、文本和 PDF 所有导入入口共用的校验与落盘边界；禁止一个入口绕过预检/事务。
- [x] 更新回归测试，覆盖纯图片 PDF、损坏 PDF、文本可提取但结构不明、格式不支持、重复策略未选择。
- [x] 保持 `import_jobs` 对成功、预检失败、写入失败状态的语义准确。

## 阶段验收

- [x] `python -m unittest tests.test_v1_import tests.test_v1_pdf_import -v`
- [x] 后端全量测试、前端单测、前端 build、真实浏览器 E2E、`git diff --check`。
- [x] E2E 至少证明用户预览列映射、确认导入、预检错误提示、整批原子失败且无部分题目。
- [x] 更新需求追踪 §5/§8 和 OSS audit 的 source mapping/license；逐项报告“复制/改编/仅参考/未采用”。
