# cordis_sub_agent V2 需求文档

> 注意：本文保留的是旧版 worktree、Reader 和独立 Coding Agent 设计，已不再是当前实现契约。当前流程以 README 和 `skills/dsh-plugin-development/SKILL.md` 为准：插件位于 `packages/generated/<plugin-name>/`，由 Main Agent 直接开发和修复，仅保留 Documentation 子代理。

> 目标：将现有 `cordis_sub_agent` 从“多 Agent 生成插件的实验性工作流”重构为一个可恢复、可隔离、可验证、可持续迭代的 DSH Plugin Development Harness。
>
> 本文档以当前讨论确定的架构为准，允许对现有实现进行大范围重构；不要求兼容当前内部代码结构，但应尽量复用已经验证可用的 DSH 官方 API 与现有能力。

---

# 1. 背景

当前 `cordis_sub_agent` 已经具备一部分基础能力：

- 用户需求经过多阶段确认后形成 `PluginSpec`
- 可以调用 subagent 参与插件开发
- 已有工程验证服务
- 已有真实 DSH acceptance 相关服务
- 已验证插件自身可以被真实 DSH 加载
- 已验证 DSH 官方提供：
  - `ctx.subagents.start(...)`
  - `ctx.subagents.startContinuable(...)`
  - `ctx.subagents.followup(...)`
  - spawn/fork provider
  - session persistence
  - `ctx.fs`
  - `ctx.shell`
  - `ctx.tools`
  - `ctx.skills`
  - DSH SDK client / HarnessSession

但是当前设计在真实 E2E 中暴露出明显问题：

1. 将 Architecture / Dependency / Implementation / Documentation 拆成多个独立 Agent，会破坏模型天然的 `read → write → test → fix` 编码闭环。
2. Implementation Agent 会在没有全局测试地图的情况下陷入局部 patch 循环。
3. 文档生成容易脑补不存在的命令、能力和行为。
4. 生成代码直接落在现有工作区中，失败后留下脏代码。
5. 失败任务缺少可靠的恢复、重试、清理能力。
6. 主 Agent 在真实 DSH acceptance 中发现问题后，需要将问题送回原 Coding Agent 继续修复，而不是重新创建一个全新的 Agent。
7. 当前 `createBaseProject` / artifact contract / build output / verification contract 之间存在不一致。
8. 当前开发流程对“一个插件应该如何被测试”缺乏稳定边界。
9. 当前文档流程没有完全遵守 DSH 官方 README 双语、i18n pairing、Model Experience、Known Limitations、doc-sync 等要求。

因此 V2 的目标不是继续增加更多 Agent，而是重新划分职责边界。

---

# 2. 总体目标

`cordis_sub_agent` V2 应实现如下闭环：

```text
用户
↓
Main Agent
├─ Phase 1：需求确认
├─ Phase 2：I/O 与交互确认
├─ Phase 3：PluginSpec 确认
│
├─ Workspace Manager
│   └─ 创建隔离 git worktree
│
├─ Reader / Scout Agent（one-shot）
│   └─ 输出 Read Plan
│
├─ Coding Agent（continuable）
│   ├─ read
│   ├─ search
│   ├─ write / edit
│   ├─ build
│   ├─ typecheck
│   ├─ local functional tests
│   ├─ debug / fix
│   ├─ final regression
│   └─ 调 Documentation Agent
│       ├─ README.md
│       ├─ README.zh.md
│       ├─ README.i18n.yaml
│       └─ doc-sync
│
├─ Deterministic Engineering Gate
│
├─ Main Agent：Real-host Acceptance
│   ├─ 启动 fresh DSH
│   ├─ 自动测试
│   ├─ 用户真实输入原样转发
│   └─ 如果失败：followup 原 Coding Agent
│
└─ 成功 / 恢复 / 删除 / 放弃
```

---

# 3. 核心设计原则

## 3.1 不拆模型天然编码闭环

禁止将 Coding Agent 拆成：

- Reader-only
- Writer-only
- Tester-only
- Fixer-only

Coding Agent 应完整拥有：

```text
read → write → test → fix → read again
```

Reader Agent 只负责导航，不替代 Coding Agent 阅读代码。

Documentation Agent 只负责文档，不参与核心源码实现。

---

## 3.2 按系统职责拆分，而不是按思考步骤拆分

V2 只保留三个核心智能体角色：

### Main Agent

负责：

- 与用户确认需求
- 调度开发流程
- 保存 task identity
- 调 Reader Agent
- 调 Coding Agent
- 真实 DSH acceptance
- 将真实运行问题反馈给原 Coding Agent
- 与用户进行最终验收交互

Main Agent 原则上不直接写插件实现代码。

### Reader / Scout Agent

负责：

- 阅读 PluginSpec
- 阅读 Skill
- 探索目标仓库 / package
- 生成 Read Plan
- 指出关键文件、全局约束、风险

Reader Agent 不负责实现。

### Coding Agent

负责：

- 实际开发
- 测试
- 修复
- 回归
- 调用 Documentation 子代理
- 返回可验收状态

Coding Agent 是整个任务中唯一长期存在的开发 Agent。

---

# 4. 生命周期模型

每个开发任务必须有一个稳定的 `DevelopmentTask`。

一个任务至少绑定：

```text
Task
├─ PluginSpec
├─ Worktree
├─ Coding Session
├─ Read Plan
├─ Read Trace
├─ Test Evidence
├─ Documentation Evidence
├─ Engineering Verification
├─ Acceptance Evidence
└─ Status
```

任务中的两个核心状态必须长期绑定：

```text
代码状态 = worktree
模型上下文状态 = continuable Coding Agent session
```

二者不可分离。

---

# 5. DevelopmentTask 状态机

建议状态：

```text
draft
requirements_confirmed
workspace_ready
reading
developing
engineering_verifying
ready_for_acceptance
accepting
repairing
completed
failed
discarded
```

建议转移：

```text
draft
→ requirements_confirmed
→ workspace_ready
→ reading
→ developing
→ engineering_verifying
→ ready_for_acceptance
→ accepting
→ completed
```

真实 acceptance 失败：

```text
accepting
→ repairing
→ developing
→ engineering_verifying
→ ready_for_acceptance
→ accepting
```

用户主动放弃：

```text
* → discarded
```

不可恢复的系统错误：

```text
* → failed
```

`failed` 不应自动删除 worktree。

---

# 6. Worktree / Workspace Manager

这是 V2 的基础设施核心之一。

## 6.1 目标

任何生成代码都不得直接污染主工作区。

每个任务必须创建独立 git worktree。

示意：

```text
main repo
├─ packages/cordis_sub_agent/...
└─ .cordis/worktrees/
   ├─ task-001/
   ├─ task-002/
   └─ ...
```

实际路径可配置，不要求固定为上述目录。

---

## 6.2 创建

创建任务时：

1. 记录当前 base commit
2. 创建独立临时 branch
3. 创建 worktree
4. Coding Agent cwd 指向该 worktree
5. Reader Agent 可以读取主仓库或 worktree，但推荐统一指向 worktree
6. 所有写操作只允许发生在 worktree

建议结构：

```ts
interface DevelopmentWorkspace {
  repoRoot: string
  worktreePath: string
  branchName: string
  baseCommit: string
  createdAt: number
  status: 'active' | 'completed' | 'failed' | 'discarded'
}
```

---

## 6.3 恢复

任务被中断后，应可恢复：

```text
task_id
→ 找回 task metadata
→ 检查 worktree 是否仍存在
→ 检查 branch 是否仍存在
→ 找回 codingAgentId
→ 恢复任务状态
```

恢复时不得重新创建新的 workspace，除非原 workspace 已损坏且用户明确同意。

---

## 6.4 删除 / 放弃

需要提供显式 discard 操作。

流程：

```text
停止/打断 Coding Agent
↓
停止正在运行的 acceptance
↓
停止运行中的 shell/test
↓
git worktree remove --force
↓
删除 Harness 自己创建的 branch
↓
更新 task.status = discarded
```

必须保证：

- 只能删除 TaskStore 中登记为本任务所有的 worktree
- 不允许根据模型输出的任意路径执行删除
- 不允许删除主 worktree
- 不允许删除用户未授权的 branch

---

## 6.5 Checkpoint

建议支持 checkpoint，但可作为 V2.1。

checkpoint 用于：

```text
Coding Agent 完成一轮
↓
工程测试通过
↓
保存 checkpoint commit
↓
real-host acceptance
↓
如果后续修复改坏
↓
允许恢复到最近 checkpoint
```

建议：

```ts
interface WorkspaceCheckpoint {
  commit: string
  createdAt: number
  reason: string
}
```

---

# 7. Reader / Scout Agent

## 7.1 定位

Reader 不负责：

> “把所有代码读完并告诉 Coding Agent 答案”

而负责：

> “把开放式搜索压缩成一份高价值阅读计划”

---

## 7.2 输入

Reader 至少获得：

- PluginSpec
- 当前开发 Skill
- worktree root
- repo/package context
- 用户已确认约束

---

## 7.3 输出

建议结构：

```ts
interface ReadPlan {
  mustRead: ReadPlanItem[]
  recommendedRead: ReadPlanItem[]
  confirmedFacts: ConfirmedFact[]
  risks: string[]
  irrelevantOrAvoid?: string[]
}

interface ReadPlanItem {
  path: string
  reason: string
}
```

`mustRead`：

- Coding Agent 在修改前原则上应亲自读取
- 用于 load-bearing contract

`recommendedRead`：

- 高概率有价值
- 允许 Coding Agent 根据实际任务决定

---

## 7.4 不限制 Coding Agent 额外阅读

Coding Agent 可以自由 grep/glob/read。

不得因为 Coding Agent 阅读了 Reader 未推荐文件而判定违规。

Harness 只记录。

---

# 8. Read Trace

为了评估 Reader 是否真的有用，必须记录实际阅读行为。

至少记录：

```ts
interface ReadTrace {
  recommended: string[]
  actuallyRead: string[]
  recommendedAndRead: string[]
  recommendedButNotRead: string[]
  extraReads: string[]
}
```

可选增强：

```ts
interface ReadEvent {
  path: string
  timestamp: number
  reason?:
    | 'initial_exploration'
    | 'implementation'
    | 'debug_after_failure'
    | 'documentation'
    | 'other'
}
```

建议统计：

- must-read coverage
- recommended-read coverage
- extra-read ratio
- acceptance success rate
- engineering success rate

此数据用于后续实验，不作为当前任务成败 gate。

---

# 9. Coding Agent

## 9.1 生命周期

Coding Agent 必须使用 DSH continuable subagent。

不能使用默认 one-shot `SubagentRun` 作为长期 Coding Agent。

官方目标调用模型：

```text
startContinuable(...)
↓
保存 childId
↓
后续 followup(...)
```

TaskStore 必须保存：

```ts
codingAgentId: string
```

---

## 9.2 Provider

优先使用：

```text
spawn + continuable
```

原因：

- fresh coding context
- 官方有生产可用的 continuable 路径
- 可以在 settled 后 cold resume
- 可以多轮 followup

不要求使用 fork continuable。

---

## 9.3 Coding Agent 工具能力

Coding Agent 必须拥有任务级完整开发能力：

- read
- grep
- glob
- write
- edit
- shell
- build
- test

禁止为了“避免模型乱跑测试”而删除 shell。

模型测试失控应通过：

- Test Plan
- prompt constraint
- timeout
- shell gate
- overall iteration limit

控制，而不是破坏其正常 coding loop。

---

## 9.4 Coding Agent cwd

Coding Agent 的 cwd 必须是本任务 worktree。

不得默认使用：

- 主 repo root
- `packages/cordis_sub_agent` 自身目录
- 任意用户目录

---

## 9.5 Coding Agent 输入

初始 prompt 应包含：

- PluginSpec
- Read Plan
- workspace path / cwd 说明
- DSH plugin engineering contract
- 测试边界
- documentation delegation 规则
- 完成条件

---

# 10. Coding Agent 的测试职责

测试不再拆给单独 Test Agent。

Coding Agent 自己负责全部“真实进程前”的工程测试。

## 10.1 测试层次

### A. 结构契约

检查：

- `package.json`
- `tsconfig.json`
- `src`
- exports
- build script
- main/types
- build output path

### B. 依赖与静态检查

检查：

- direct imports 是否声明依赖
- Config schema/type
- inject
- TypeScript
- lint（若项目要求）

### C. 构建

必须真实运行 build。

例如：

```bash
pnpm build
```

并检查：

- exit code = 0
- 预期 artifact 存在
- package.json 声明与 artifact 一致

### D. 局部功能测试

只测试：

> PluginSpec 明确要求，且不依赖真实 DSH host 的行为。

范围固定为：

```text
输入
输出
错误
局部副作用
```

包括：

- 正常输入
- 正常输出
- required 参数
- 参数类型
- PluginSpec edgeCases
- PluginSpec 明确要求的错误行为
- PluginSpec 明确要求的本地状态变化
- PluginSpec 明确要求的文件副作用

禁止无限扩张到：

- 没有明确要求的性能测试
- 并发测试
- 模糊 UI 行为
- 未声明 lifecycle
- mock 一个假的 DSH host 然后声称“真实 host 已验证”

### E. 最终回归

任何 fix 都可能使之前测试失效。

所以 Coding Agent 宣布完成之前必须重新跑完整测试清单。

不得仅依赖历史成功结果。

---

# 11. Test Plan

不需要额外 Agent。

Test Plan 可由 Harness 规则 + Coding Agent 自己生成。

要求：

每个 local functional test 必须可以追溯到：

- `PluginSpec.tools`
- `PluginSpec.edgeCases`
- `PluginSpec.acceptanceCriteria`

可增加字段：

```ts
interface TestCasePlan {
  id: string
  source:
    | { type: 'tool'; name: string }
    | { type: 'edgeCase'; index: number }
    | { type: 'acceptanceCriterion'; index: number }
  type:
    | 'structure'
    | 'static'
    | 'build'
    | 'local-functional'
    | 'regression'
  description: string
}
```

---

# 12. Documentation Agent

Documentation 必须从 Coding Agent 中拆出去，作为 Coding Agent 的子代理。

## 12.1 生命周期

Documentation Agent 可以是 one-shot。

不需要 continuable。

---

## 12.2 触发时机

只有当：

- 核心代码基本冻结
- build/typecheck/local tests 已通过

之后才调用 Documentation Agent。

避免文档代理针对未完成代码写 README。

---

## 12.3 权限

Documentation Agent：

允许读：

- package.json
- tsconfig
- src/**
- tests/**
- 当前 README*
- 相关 repo documentation rules
- build/test results

允许写：

- README.md
- README.zh.md
- README.i18n.yaml
- 必要 JSDoc（是否允许可配置；默认建议只允许 README 系列）

默认不允许：

- 修改业务源码
- 修改核心逻辑
- 修改 package scripts
- 修改测试来“配合文档”

如果发现实现与文档要求冲突，应返回问题给 Coding Agent，而不是偷偷改代码。

---

# 13. DSH 文档硬约束

Documentation Agent 必须遵守官方 DSH 文档规范。

至少包括：

## 13.1 README 三件套

必须存在：

```text
README.md
README.zh.md
README.i18n.yaml
```

---

## 13.2 Translation Pairing

必须保证：

- 英文 / 中文配对
- H1 后语言切换器
- heading 深度序列对称
- code block 对称
- table 结构对称
- list 结构对称
- link target 对称
- i18n hash 正确

---

## 13.3 Model Experience

README 需要符合官方 Model Experience 规则。

包括：

- 固定位置
- `What the model sees`
- `Token effect`
- `KV Cache effect`
- tool schema 需要引用 canonical tool catalog
- system prompt 必要时提供 verbatim block

具体以当前 DSH repo gate 为准。

---

## 13.4 Known Limitations

必须存在：

```markdown
## Known Limitations and Deferred Work
```

并至少有一个顶层 bullet，除非进入官方 allowlist。

---

## 13.5 文档事实必须来自实现

Documentation Agent 写文档前必须读取：

- package.json
- Config
- Tool schema
- exports
- build/test scripts
- 当前源码

禁止脑补：

- 不存在的安装命令
- 不存在的 test script
- 未发布 package 的安装方式
- 不存在的 config
- 不存在的 tool
- 未验证成功却写“works successfully”
- 未实现功能

---

# 14. Documentation 验证

Documentation Agent 从“写”到“验证”整体负责。

至少应运行：

```bash
pnpm run doc-sync
```

如需单对更新：

```bash
pnpm run verify-translation-pairing --write <pair>
```

最终文档任务只有在相关文档 gate 通过后才算完成。

Coding Agent 最终 regression 中仍需把文档 gate 纳入整体结果。

---

# 15. Engineering Gate

Coding Agent 自己测试通过后，Harness 再进行一次独立、确定性的工程验证。

这里不需要另一个 Agent。

目标：

> 不相信模型口头声称“完成”，而是重新验证关键事实。

至少检查：

1. worktree 存在
2. package.json 存在
3. build script 存在
4. build command 真实执行成功
5. artifact 存在
6. main/types/exports 与 artifact 一致
7. TypeScript 检查成功
8. 必需 test command 成功
9. doc-sync 成功
10. README 三件套存在

失败则：

```text
ready
→ repairing
→ followup Coding Agent
```

而不是直接将 task 置为不可恢复 failed。

---

# 16. Real-host Acceptance

真实 DSH acceptance 由 Main Agent 负责，不再创建独立 Acceptance Agent。

## 16.1 原因

Main Agent 已经拥有：

- 用户需求上下文
- PluginSpec
- task_id
- acceptance history
- 用户真实输入
- 修复决策权

因此它最适合充当最终验收 owner。

---

## 16.2 Fresh DSH

Acceptance 必须：

- 启动新的 DSH child runtime / process
- 从构建产物加载 plugin
- 不复用开发进程中已经加载过的 plugin
- 不以 mock-host 作为最终证明

---

## 16.3 自动验收

Main Agent 首先根据 PluginSpec 做自动真实调用。

检查：

- 插件能否加载
- tool 是否真实注册
- schema 是否真实可见
- 实际调用结果
- session/lifecycle
- PluginSpec acceptanceCriteria

---

## 16.4 用户真实输入

自动验收通过后：

Main Agent 请求用户提供真实输入。

用户输入必须：

> 原样转发，不改写、不润色、不补全。

记录：

```ts
interface AcceptanceMessage {
  actor: 'agent' | 'user'
  input: string
  output?: string
  error?: string
  completed: boolean
}
```

允许同一 acceptance session 多轮交互。

---

# 17. Acceptance 失败后的修复循环

这是 V2 的核心能力。

流程：

```text
Main Agent real-host acceptance
↓
发现 bug
↓
整理 Evidence
↓
followup(codingAgentId, evidence)
↓
同一个 Coding Agent 冷恢复/继续
↓
read → fix → test → regression
↓
Documentation Agent（如文档受影响）
↓
Engineering Gate
↓
Main Agent 再次 real-host acceptance
```

---

## 17.1 Failure Evidence

建议结构：

```ts
interface AcceptanceFailureEvidence {
  round: number
  input: string
  observedOutput?: string
  error?: string
  runtimeLogs?: string
  expectedBehavior: string
  relatedAcceptanceCriteria?: string[]
}
```

必须传给 Coding Agent。

因为 spawn continuable child 不会自动看到 Main Agent 的后续上下文。

---

# 18. Coding Agent Resume

必须基于官方 continuable API：

```text
ctx.subagents.startContinuable(...)
ctx.subagents.followup(...)
```

长期保存：

```text
codingAgentId
```

如果 Coding Agent 当前只是磁盘上的 settled session：

- followup 应触发 cold resume
- 保留完整 conversation history

如果任务丢失了 `codingAgentId`：

- 不得假装恢复原 Agent
- 应显式标记 session unavailable
- 可在用户允许下新建 Coding Agent，并注入已有 evidence / task history

---

# 19. Documentation 更新触发

如果 acceptance 修复修改了：

- Config
- tool schema
- defaults
- error behavior
- wire fields
- model-visible behavior
- Known Limitations

则 Coding Agent 必须再次调用 Documentation Agent。

Documentation Agent 重新：

- 读取最新源码
- 更新双语 README
- 更新 i18n pairing
- doc-sync

---

# 20. PluginSpec

现有 PluginSpec 可以继续使用，但建议作为 V2 的核心稳定契约。

建议结构：

```ts
interface PluginToolParameterSpec {
  name: string
  description: string
  type: string
  required: boolean
}

interface PluginToolSpec {
  name: string
  description: string
  parameters: PluginToolParameterSpec[]
  output: string
}

interface PluginDependencySpec {
  name: string
  reason: string
  required: boolean
}

interface PluginSpec {
  name: string
  description: string
  overview: string
  goals: string[]
  nonGoals: string[]
  userScenarios: string[]
  tools: PluginToolSpec[]
  dependencies: PluginDependencySpec[]
  constraints: string[]
  edgeCases: string[]
  acceptanceCriteria: string[]
}
```

PluginSpec 必须在开始编码前经用户显式确认。

---

# 21. Deterministic Artifact Contract

不能让 LLM 自己猜生成 package 应该如何 build。

Harness 必须提供固定 contract。

建议生成 package 至少：

```json
{
  "name": "<plugin-name>",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "build": "tsc -b"
  },
  "main": "lib/index.js",
  "types": "lib/index.d.ts",
  "exports": {
    ".": {
      "types": "./lib/index.d.ts",
      "default": "./lib/index.js"
    }
  }
}
```

tsconfig：

```json
{
  "compilerOptions": {
    "rootDir": "src",
    "outDir": "lib"
  },
  "include": ["src"]
}
```

实际 extends / references 应根据目标 repo 当前规范生成。

核心要求：

```text
builder contract
=
verification contract
=
package contract
```

三者必须唯一。

---

# 22. Base Project Creation

当前存在 `createBaseProject` 但未被可靠接入流程的问题。

V2 必须明确：

```text
create worktree
↓
createBaseProject
↓
Reader
↓
Coding Agent
```

`createBaseProject` 负责创建确定性基础骨架：

- package.json
- tsconfig
- src/index.ts 最小入口
- README skeleton（可选，若 Documentation Agent 后续生成则只建 placeholder）
- package naming
- build script
- exports contract

Coding Agent 在这个确定性骨架上开发业务功能。

不要让 Coding Agent 从空目录自行猜 package contract。

---

# 23. 依赖策略

Coding Agent 可以调查和增加业务依赖。

但是以下 Harness / host integration 依赖应由模板或规则管理：

- cordis
- dsh-tools
- dsh-fs
- dsh-shell
- dsh-skill
- dsh-subagent
- schemastery

原则：

- direct import → 必须显式声明
- host service 能作为 peer/dev dependency 时遵循官方 package 惯例
- 不因“官方 monorepo root 能 build”而生成一个独立不可 build 的 plugin package

---

# 24. 失败恢复

V2 必须把失败分为：

### recoverable

例如：

- build 失败
- typecheck 失败
- local test 失败
- doc-sync 失败
- acceptance 失败
- runtime integration 失败

行为：

```text
→ task.status = repairing
→ followup same Coding Agent
```

### unrecoverable

例如：

- worktree 丢失
- git repo 损坏
- coding session persistence 丢失且无法恢复
- Harness 自身基础服务失效

行为：

```text
→ task.status = failed
```

但保留 workspace，等待人工处理或 discard。

---

# 25. 禁止“失败即死”

当前：

```text
verification failed
→ task failed
→ workspace exists
→ recreate 又报 exists
```

这种 dead-end 必须消失。

至少支持：

```text
resume task
retry engineering verification
resume coding agent
restart acceptance
discard task
```

---

# 26. 对外 Tool / Command 需求

具体名字可以调整，但能力至少需要：

## create / start development

输入：

- confirmed PluginSpec

输出：

- task_id
- workspace info
- coding agent info
- current status

## get task status

查看：

- state
- worktree
- coding agent id
- last verification
- last acceptance
- error

## resume development

用于中断后继续。

## discard development

显式清理：

- coding session
- acceptance
- worktree
- branch

## start / continue acceptance

Main Agent 使用。

如果已有工具可以复用，不要求增加新名字。

---

# 27. 可观测性

必须保留尽可能完整的 evidence。

至少：

```text
task lifecycle
workspace lifecycle
Reader output
actual file reads
Coding Agent turns
shell commands
test commands
build results
doc-sync results
engineering verification
acceptance input/output/error
repair rounds
```

---

# 28. Trace 设计

建议每个 task 写结构化事件：

```ts
interface DevelopmentTraceEvent {
  timestamp: number
  taskId: string
  type: string
  payload: unknown
}
```

关键 event：

```text
workspace.created
reader.started
reader.completed
coding.started
coding.read
coding.shell
coding.completed
documentation.started
documentation.completed
verification.started
verification.failed
verification.passed
acceptance.started
acceptance.message
acceptance.failed
acceptance.passed
coding.followup
workspace.checkpoint
workspace.discarded
task.completed
```

---

# 29. Completion Definition

任务不能因为 Coding Agent 说“完成”就 completed。

最终 Done 条件：

```text
用户确认 PluginSpec
AND
隔离 worktree
AND
Coding Agent 开发完成
AND
本地工程测试通过
AND
Documentation Agent 文档 gate 通过
AND
Harness Engineering Gate 通过
AND
fresh DSH 成功加载插件
AND
Main Agent 自动 real-host acceptance 通过
AND
至少一次用户真实输入原样转发并通过
```

然后：

```text
task.status = completed
```

---

# 30. Non-goals

V2 暂时不要求：

- 将一个插件的源码拆给多个 Coding Agent 并行开发
- 通用 multi-agent code merge
- 自动解决多 Agent 文件冲突
- vector memory
- 自动 PR
- 自动发布 npm
- 自动 merge 到主分支
- 大规模 benchmark
- 自动代码审查 Agent
- 独立 Test Agent
- 独立 Acceptance Agent

普通插件默认：

```text
1 Reader
1 long-lived Coding Agent
1 Documentation child
1 Main Agent
```

---

# 31. 推荐代码结构

允许大改，建议最终往职责化结构靠：

```text
src/
├── config.ts
├── index.ts
│
├── models/
│   ├── plugin-spec.ts
│   ├── development-task.ts
│   ├── workspace.ts
│   ├── read-plan.ts
│   ├── test-evidence.ts
│   └── acceptance.ts
│
├── services/
│   ├── task-store.ts
│   ├── workspace-manager.ts
│   ├── reader-service.ts
│   ├── coding-session-service.ts
│   ├── engineering-verification-service.ts
│   ├── acceptance-service.ts
│   └── plugin-builder.ts
│
├── workflow/
│   └── development-orchestrator.ts
│
├── tools/
│   ├── create-plugin.ts
│   ├── resume-development.ts
│   ├── discard-development.ts
│   ├── start-acceptance.ts
│   ├── send-acceptance-message.ts
│   └── stop-acceptance.ts
│
└── utils/
    ├── paths.ts
    └── git.ts
```

Documentation Agent 不一定需要独立 service；可以由 Coding Agent 通过 subagent 工具自行调用。

---

# 32. 旧架构迁移建议

当前：

```text
Architecture Agent
Dependency Agent
Implementation Agent
Documentation Agent
```

应废弃为：

```text
Reader Agent
Coding Agent (continuable)
└─ Documentation Agent
```

具体：

### 删除 / 合并

- Architecture Agent → Reader Agent 的 global facts / risks
- Dependency Agent → Coding Agent 自己处理
- Implementation Agent → 升级成 Coding Agent
- Documentation Agent → 保留，但改成 Coding Agent 的 child

### DevelopmentWorkflow

当前固定串并行 orchestration 应大改。

新 orchestrator 重点不再是：

```text
Promise.all(Architecture, Dependency)
→ Implementation
→ Documentation
```

而是：

```text
Workspace
→ Reader
→ startContinuable Coding Agent
→ wait for coding-ready
→ Engineering Gate
→ Main acceptance
→ followup loop
```

---

# 33. 实施优先级

建议 Codex 按以下顺序做，不要一次重写全部。

## P0：先修生命周期骨架

1. DevelopmentTask model
2. WorkspaceManager
3. git worktree create/resume/discard
4. TaskStore persistence/runtime state
5. createBaseProject 接入
6. deterministic artifact contract

## P1：重构 Agent workflow

7. Reader Agent
8. Coding Agent 使用 startContinuable
9. 保存 codingAgentId
10. followup 修复能力
11. 删除 Architecture / Dependency Agent 路径

## P2：测试与验证

12. Coding Agent test contract
13. EngineeringVerificationService
14. 失败 → repairing，而不是 dead-end failed
15. regression evidence

## P3：Documentation

16. Coding Agent 调 Documentation child
17. README 双语
18. i18n pairing
19. Model Experience
20. Known Limitations
21. doc-sync

## P4：Real-host loop

22. Main Agent fresh DSH acceptance
23. 自动 acceptance
24. 用户输入 exact relay
25. acceptance failure evidence
26. followup Coding Agent
27. re-acceptance

## P5：恢复与清理

28. resume task
29. discard task
30. checkpoint（可选）

---

# 34. Codex 开发要求

在实现 V2 时：

1. 先阅读当前 `cordis_sub_agent` 全部代码，不要假设此文档中的文件名与当前代码完全一致。
2. 允许大范围重构。
3. 不要为了兼容旧 workflow 保留明显错误的架构。
4. 优先使用 DSH 官方 API。
5. 不引入社区插件。
6. 不猜 DSH API；遇到不确定行为时直接检索官方仓库源码与测试。
7. 修改后必须真实 build/typecheck/test。
8. 不要只做单元测试；至少完成一次插件自身真实加载 smoke test。
9. 所有 workspace 删除逻辑必须有严格 path ownership 保护。
10. 不要把生成代码写入主工作区。
11. 不要把长期 Coding Agent 做成 one-shot。
12. 不要把 Documentation Agent 写成代码修复 Agent。
13. 不要以 mock DSH 代替最终 real-host acceptance。
14. 不要在失败后把任务做成不可恢复 dead-end。

---

# 35. 最终验收用例

## Case 1：简单 hello plugin

用户：

```text
做一个 hello 插件，提供 say_hello(name)，返回 Hello, <name>
```

预期：

- 创建独立 worktree
- Reader 输出 read plan
- Coding Agent continuable
- build/test/doc-sync 通过
- fresh DSH 加载
- 主 Agent 调用 say_hello
- 用户输入真实名字
- 原样转发
- 通过
- 主 repo 无脏文件

---

## Case 2：acceptance 发现真实 runtime bug

Coding Agent 本地全部通过。

fresh DSH 中真实调用出现：

```text
schema error
```

预期：

- task 不 failed
- Main Agent 记录 evidence
- followup 原 codingAgentId
- 同一个 Coding Agent 修复
- 保留原 worktree
- 重新 engineering verify
- 重新 fresh DSH acceptance
- 成功后 completed

---

## Case 3：用户放弃失败任务

开发过程中代码已大量修改。

用户：

```text
不要这个插件了，删掉
```

预期：

- 停止子 Agent
- 停止 acceptance
- 删除 task worktree
- 删除临时 branch
- 主仓库不受影响
- task = discarded

---

## Case 4：进程重启后恢复

Coding Agent 第一轮已完成，session 已 settled。

Harness 重启。

预期：

- TaskStore 找回 task
- worktree 仍存在
- codingAgentId 仍存在
- followup 触发 continuable child cold resume
- Coding Agent 保留历史继续修

---

## Case 5：Documentation 不得脑补

源码没有：

```text
pnpm test
```

README 不得写：

```text
Run pnpm test
```

源码 package 未发布 npm。

README 不得声称：

```text
pnpm add @deepseek-ai/...
```

除非仓库当前规范明确要求且事实成立。

---

# 36. 架构一句话定义

> `cordis_sub_agent` V2 是一个以 PluginSpec 为契约、以 git worktree 隔离代码状态、以 continuable Coding Agent 保存开发认知状态、以 Documentation 子代理保证 DSH 文档合规、以确定性 Engineering Gate 和 Main Agent fresh-DSH acceptance 保证真实可用性的可恢复插件开发 Harness。
