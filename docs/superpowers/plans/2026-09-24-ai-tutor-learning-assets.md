# AI 助教对话与学习资料闭环

> **执行规则：** 按 `easyexam-implementation` skill 与 `docs/ANTIGRAVITY_WORKFLOW.md` 执行。只落实 `SPEC.md` §2.2–2.4、§6 已确认的行为；不得把 AI 候选提升为官方答案。外部 provider 或密钥缺失时保留离线刷题，不得伪造成功。

**目标：** 从“保存单次回答版本”补成“用户可恢复、可继续追问的题目上下文对话”，并提供可追溯个人资料检索与真实联网适配器；每项单独验收，不将单一 AI 回复/资产 CRUD 宣称为完整 AI 系统。

## 任务 1：持久化 AI 对话及消息

**参考：** `docs/research/OSS_REUSE_AUDIT.md` 中 MiaowTest `803dadc` 的 `Express-node/models/AgentMessageModel.js`（MIT）。只取实体/消息生命周期中有用的字段，不复制 Mongo/Express 实现。

**文件：** 新 migration、`backend/app/infrastructure/db/repositories/ai_answer_repository.py`、`backend/app/application/ai_tutor_service.py`、AI routes、`frontend/src/api/ai.js`、AI store/PracticeView、`tests/test_v1_architecture.py`、`frontend/tests/browser_e2e.test.js`。

- [ ] 写失败测试：不同 user / question_version 的 conversation 不能串读；消息顺序稳定；重新生成形成独立版本；追问读取既有历史；生成失败状态/离线状态可见。
- [ ] RED 后新增 conversation/message schema。最少关联 owner、question version、message sequence/role、生成结果状态与时间；对 user/version 做服务端授权，禁止信任客户端 user_id。
- [ ] 让回答版本仍独立于官方答案，采纳后是个人答案；对话历史和解释版本分别建模，不用一段 JSON 同时承担两种语义。
- [ ] 前端进入题目后恢复最近对话、能追问并查看历史回答；刷新和关闭后通过真实数据库恢复。
- [ ] 后端单测覆盖版本/隔离；浏览器 E2E 做登录→答题→AI 生成→追问→刷新→历史恢复→另一用户不可见。

## 任务 2：个人资料上传、预检和题目检索

**文件：** `backend/app/infrastructure/importers/`、`asset_repository.py`、AI retrieval boundary、assets/import routes、frontend 上传界面、相关 migration/tests。

- [ ] 先为 PDF、TXT、Markdown 可读文本、纯图片 PDF、损坏文件、超出限制文件和用户隔离写失败测试。SPEC 明确纯图片 PDF 不做 OCR，必须上传前拒绝并给原因。
- [ ] 设计资产元数据和实际文件持久化的安全边界：文件名不可作路径，用户私有，上传/解析/检索状态可查，失败不留下“可检索成功”的假资产。
- [ ] 文本可提取且预检通过的内容才可进入索引/检索；AI 回答必须附来源资产与片段引用；无资料命中时明确无依据。
- [ ] 先复用仓内现有解析器/依赖；本批次不引入重型向量数据库，不新增 SPEC 未确认的 OCR/文档格式。
- [ ] 浏览器 E2E 覆盖上传→拒绝不可读 PDF、接受可读文档→对题提问→答案显示资料来源→另一用户无法检索。

## 任务 3：联网核查 provider 与证据版本

**文件：** `backend/app/infrastructure/ai/web_search.py`、`backend/app/main.py`、config/dependencies、AI service/repository/routes、前端、相应 tests。

- [ ] 先检查当前部署说明/环境中 `open-webSearch` 的可执行服务协议、地址、认证方式与输出格式。若事实不存在或需用户提供端点/密钥，先停下报告，不得编造协议，也不得把 `OfflineWebSearch` 改名冒充在线服务。
- [ ] 有可验证服务契约时，写 provider contract 测试：成功映射标题/URL/摘要/检索时间；超时、断网、无结果如实 `UNAVAILABLE`；永不伪造 evidence。
- [ ] 联网核查必须新增 WEB explanation version 与 evidence rows，不覆写 AI/官方/个人答案；前端能展开核对来源。
- [ ] 无在线服务时以现有 `UNAVAILABLE` 降级，普通刷题、AI历史查看及回答存档不受影响。

## 阶段验收

- [ ] 后端全量 unittest、前端 unit、build、真实 browser E2E、`git diff --check`。
- [ ] 分别汇报持久对话、资料检索、真实联网三个能力的实际状态；某一能力未提供不得宣称 AI 全功能完成。
- [ ] 更新追踪矩阵 SPEC §2.2–2.4/§6 与开源审计；若适配 MiaowTest 仅参考 schema，明确标“行为/模型参考，未复制代码”。
