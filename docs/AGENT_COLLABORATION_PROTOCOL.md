# EasyExam 双 Agent 协作协议 (Agent Collaboration Protocol)

本文档固化 EasyExam 项目中双 Agent（AntiGravity 与 Work）的协作规则、状态机、轮次上限、停止条件与接口规范。

## 1. 核心原则与角色分工

1. **唯一事实源**：GitHub Issue（含 Frozen Spec）、Pull Request、GitHub Labels 和 GitHub Checks 是双 Agent 协作的唯一事实源。禁止根据聊天上下文、历史记忆或自行推测扩大或变更规范。
2. **AntiGravity（Implementer Agent）职责**：
   - 仅领取带有 `agent-ready` 标签的 Issue 并自动切换为 `agent-working`。
   - 严格在 Frozen Spec 限定的文件与逻辑范围内实现，禁止顺手重构、增加新功能或擅自改变产品行为。
   - 严禁删除、跳过、放宽现有测试断言来制造虚假通过。
   - 负责编写规范的 PR 描述，如实登记实际改动、测试结果与未运行项。
   - 严禁自行重新定义或扩展 Frozen Spec。
3. **Work（Reviewer / Product Agent）职责**：
   - 负责需求梳理并输出冻结的规范，锁定后为 Issue 添加 `agent-ready` 标签。
   - **严格且仅按 Frozen Spec 进行审查**，严禁在审查时临时追加新需求、新特性或抬高验收门槛。
   - 若发现范围外需求或潜在优化，必须创建独立的 follow-up Issue，不得追加进当前 Frozen Spec。
   - 通过 GitHub 原生 Review 功能提交正式的 `CHANGES_REQUESTED` 或 `APPROVED`。
4. **GitHub Actions CI**：
   - 执行机械化、可重复的自动化门禁检查；本地通过或构建成功绝不能替代 CI。
5. **fnOS Staging Physical Gate**：
   - 在后续阶段中引入，作为 Required Check 验证真实软硬件环境可用性；CI 通过不能替代 Physical Gate 实机通过。

## 2. 协调状态与 Label 体系

仓库使用五种**严格互斥**的协调状态标签管理 Issue 生命周期：

| 标签 | 含义与触发条件 | 谁来添加/切换 |
|---|---|---|
| `agent-ready` | Frozen Spec、修改范围、验收标准和停止条件已完全冻结，等待 AntiGravity 接单。 | Work / 人工管理员 |
| `agent-working` | AntiGravity 已接单并正在进行分支检出、编码实现或测试验证。 | AntiGravity / Dispatcher |
| `changes-requested` | Work 针对 Frozen Spec 正式提交了 GitHub CHANGES_REQUESTED Review。 | Dispatcher / Work |
| `infra-blocked` | 遇到环境崩溃、网络不可达、第三方依赖故障或基础设施受阻，自动处理停止。 | AntiGravity / Work |
| `needs-human` | 达到停止条件、出现不可调和的歧义、或修改超过轮次上限，自动处理停止。 | AntiGravity / Work |

### 分类与属性标签

除协调状态标签外，仅允许使用以下正交分类标签：
- `infrastructure`：基础设施、CI/CD 与工程自动化任务。
- `frozen-spec`：标明 Issue 包含已冻结的规范文本。
- `follow-up-required`：标明当前任务识别出了需后续跟踪的衍生需求。

### 禁止重复创建 GitHub 原生状态标签

**严禁**创建或使用 `pr-open`、`work-review`、`review-approved`、`merge-ready`、`merged`、`fnos-pending` 等与 GitHub 原生状态重复的标签：
- PR 的打开与草稿状态由 GitHub 原生 PR Open / Draft 表达；
- 审查状态由 GitHub 原生 Pull Request Review（Comment / Changes Requested / Approved）表达；
- CI 与门禁状态由 GitHub Checks / Actions Runs 表达；
- 合并状态由 GitHub 原生 Merged / Closed 表达。

## 3. 状态迁移规则与完整生命周期

```text
[Frozen Spec 锁定]
       │
       ▼
 [agent-ready]
       │
       ▼ (AntiGravity 接单)
 [agent-working] ──► 创建分支 ──► 编码与测试 ──► 提交 PR (保持 agent-working)
       │                                              │
       ├──────────────────────────────────────────────┘
       ▼
  (CI 运行与验证)
       │
       ▼
 (Work 针对 Frozen Spec 正式审查)
       ├──────────────────────────────────┐
       │ (发现与 Frozen Spec 不符之处)      │ (满足全部 Frozen Spec)
       ▼                                  ▼
[changes-requested]                  [APPROVED] (GitHub 原生)
       │                                  │
       ▼ (AntiGravity 开始第 N 轮修复)      ▼ (满足保护规则)
 [agent-working] ────────────┐        [MERGED] (GitHub 原生)
                             │            │
                             ▼            ▼
                   (若超过 3 轮审查)   [Issue Closed]
                             │
                             ▼
                       [needs-human] ──► 停止自动处理
```

1. **接单**：Issue 必须带有 `agent-ready` 与 `frozen-spec`。AntiGravity 领取任务后，将协调状态切换为 `agent-working`。
2. **分支与实现**：
   - 来源为 `agent-ready`：创建独立 feature 分支 `agent/issue-<number>-<slug>`，严禁直接在 `main` 上开发。
   - 来源为 `changes-requested`：切换到既有关联分支，只修复最新正式 Review 中指出的具体问题。
3. **提交 PR**：完成实现与测试后，推送分支并创建/更新 PR。PR 必须显式关联源 Issue，Issue 保持 `agent-working` 状态。
4. **CI 门禁**：GitHub Actions CI 自动响应 PR 事件（opened / synchronize / reopened）。CI 结果绑定当前 PR head SHA。
5. **正式审查**：
   - Work 仅基于 PR 当前 head SHA 和 Frozen Spec 进行审查。
   - 若不满足 Frozen Spec，Work 提交正式 `CHANGES_REQUESTED` Review，Issue 状态转为 `changes-requested`。
   - 若完全满足 Frozen Spec，Work 提交 `APPROVED` Review。
6. **合并与关闭**：PR 获得批准且通过所有 Required Checks 后，由原生机制合并并关闭关联 Issue。

## 4. 轮次上限与停止条件

### 4.1 三轮审查上限 (Max 3 Iterations)

- **轮次定义**：一次正式的 GitHub `CHANGES_REQUESTED` Review 严格计为 1 轮。普通的 Issue/PR 评论、以及 AntiGravity 在分支内部的 commit/push 动作**不计入**审查轮次。
- **上限约束**：最多允许 3 轮修改。
- **超限停止**：若在第 3 轮修复提交后，Work 仍然正式提出 `CHANGES_REQUESTED`，Issue 必须立即转为 `needs-human` 标签，并彻底停止自动化 Agent 处理。**严禁开启第 4 轮自动修复。**

### 4.2 停止条件与退出协议

出现以下任意情况时，Agent 必须立即停止代码修改，标记对应状态并退出：

1. **基础设施/环境阻塞 (`infra-blocked`)**：
   - GitHub runner 不可用、网络受限、外部服务彻底中断；
   - 缺失执行环境且无法在当前 Frozen Spec 范围内解决。
   - **动作**：记录详细错误日志与阻断证据，将 Issue 标签转为 `infra-blocked` 并停止。
2. **需要人工介入 (`needs-human`)**：
   - Issue 需求存在明显自相矛盾或无法消除的严重歧义；
   - 实现方案存在重大破坏性风险超出 Frozen Spec 授权；
   - 达到第 3 轮审查上限仍未收敛。
   - **动作**：记录具体原因并列出需要人类决策的问题，将 Issue 标签转为 `needs-human` 并停止。
3. **人工解除特权**：
   - `infra-blocked` 与 `needs-human` 是绝对停止状态。
   - **Agent 严禁自行移除 `infra-blocked` 或 `needs-human` 标签。**
   - 只有人类维护者在 Issue 中记录了解除原因、恢复决定或更新了 Frozen Spec 后，方可手动切回 `agent-ready` 重新触发。

## 5. 需求边界与 Follow-up Issue 机制

1. **范围冻结铁律**：Issue 一旦进入 `agent-ready`，其需求边界严格冻结。任何一方不得在当前执行周期内追加新需求。
2. **范围外发现处理**：
   - AntiGravity 在实现中若发现架构缺陷、关联优化或潜在需求，不得擅自在当前 PR 中顺带实现，必须在 PR 描述中建议或直接创建 follow-up Issue。
   - Work 在审查中若发现可改进点但该点未包含在原始 Frozen Spec 中，不得以此为由提交 `CHANGES_REQUESTED`，必须通过独立 follow-up Issue 记录。

## 6. 证据绑定与不可伪造性

1. **PR head SHA 单一绑定**：
   - 所有的 CI 门禁检查、生成的测试报告、上传的 artifacts 以及 Work 的 Review 结论必须单一绑定到 PR 当前的 head commit SHA。
   - PR 每次 push 新 commit（`synchronize` 事件），旧 commit SHA 的 CI 检查与 Review 结论立即失效，必须针对新 head SHA 重新运行与审查。
2. **诚实报告铁律**：
   - 严禁通过放宽断言、注释测试、使用 `continue-on-error` 或空任务伪造测试通过。
   - 未运行项必须如实报告为 `NOT RUN`；因环境限制跳过项必须如实报告为 `SKIPPED` 并附环境原因。
   - 凡存在 `SKIPPED > 0` 或 `NOT RUN > 0`，严禁在任何报告中宣称“测试全绿”或“全部通过”。
