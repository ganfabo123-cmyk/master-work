# Agent Note: 跨工作目录会话搜索——逐次用户授权 gate

Status: implemented

[English](2026-08-16-tool-cross-session-search.md) | 中文

## Problem

harness 已经能在调用者自身工作目录内搜索*此前*的会话：`@deepseek-ai/dsh-tool-session-query` 经 `ctx.sessionQuery` 注册 `session_search`，workspace-access 模块仅允许目标会话的 `cwd` 与调用者 `cwd` 精确相等时授权——`cwd` 不同或缺失的会话不可见。维护者或模型常常需要查找同一个 harness home 下*其他*工作目录中完成的工作（后续项目的会话、另一 checkout 下的相关工作），以回答「我是否已在别处解决过这个问题」。当时没有面向模型的能力能触及这些记录。触及它们是敏感操作——另一工作目录的会话可能含有无关或私有历史——因此边界必须是用户的决定，而不是模型自己授予的。既有的 workspace-scoped 工具纯粹从会话头（同 `cwd`）推导授权，而这正是跨工作目录访问的错误凭据。

## Decision

新增一个 opt-in 的面向模型 Consumer：位于 `packages/session-query/tool-cross-session-search` 的 `@deepseek-ai/dsh-tool-cross-session-search`，通过同一个 `ctx.sessionQuery` 服务，在**所有**工作目录的 live-preferred 逻辑语料上搜索。它复用既有 provider 及其 cursor-free 的 `searchSessions`/`readTitleSnapshots`；不建立第二存储，不复制任何数据库。与 workspace-scoped 的姊妹工具不同，它**从不**在会话过滤中加入 `cwd` 子句，因此搜索范围是整个语料。

### 逐次用户授权 gate 是唯一入口

`cross_session_search` 是进入跨工作目录搜索的唯一代码路径，且在接触任何 provider 之前就被 gate 拦截。每次调用都调用 `ctx.approval.request({ agent, toolName, callId, reason, signal })` 并强制执行返回结果：

- `allowed-once` —— 仅本次调用继续搜索。
- `rejected`、`cancelled` 或 `unavailable` —— 工具以模型安全的 `SESSION_CROSS_SEARCH_DENIED` 错误 fail closed，且不发生任何 session-query 交互。

决定结果的是被组合的授权应答者链，而非工具，因此模型无法决定或伪造授权范围：`@deepseek-ai/dsh-user-approval` 下 `never` 策略会确定性拒绝每一个 gate；又因为授予是一次性的，本包**不做**任何跨调用授权缓存，也不从模型参数推导任何工作目录范围。每一个 gate 都会向调用者的会话日志追加持久化的 `approval/asked` + `approval/decided` 审计对，满足 harness「模型所见必须可由日志重建」的规则。工具的执行信号与 workspace-scoped 姊妹工具穿过授权的方式一样，穿过 gate，因此取消竞态会以关闭的 `'cancelled'` 结果收场。

### 结果边界

部署的 `maxSearchResults` 配置（默认 `20`，schemastery `Config`）在服务层 `enforceCap` 处强制，与任何 provider 的页上限无关，因此行为异常的 provider 也不可能返回超过上限的命中。结果是纯文本：每个命中的折叠标题、所属工作目录（`cwd`）、可用性与最强匹配摘录，使模型无需二次查询即可理解跨工作目录上下文。

### 消费姿态

该包是 opt-in 的，且不由 shipped 的 base/web/headless bundle 挂载，与 `tool-session-query` 一致。它只依赖 `ctx.sessionQuery` 接口与授权 seam；不导入 SQLite 实现，也不改动 `agent-loop`、`tools` 或 `session-query` 本身。全文搜索还要求部署启用 provider 的内容索引（`openAt`）；搜索被禁用时，provider 已通过 `SESSION_QUERY_SEARCH_DISABLED` 响亮失败，而授权 gate 仍会先运行。

## Testing

- **单元**——本包测试以假的 `SessionQueryEngine` 与真实的 `ApprovalService` 驱动真实 `ctx.tools.execute`，覆盖：schema 形态（无 `cwd`/`cursor`/`limit`）、纯函数 `presentCall`、HMR 安全销毁、审计对落到调用者会话、每个关闭结果（`rejected`、`cancelled`、`unavailable`）都喂给 `SESSION_CROSS_SEARCH_DENIED` 且零 provider 交互、授权请求本身抛错路径产出 `SESSION_CROSS_SEARCH_APPROVAL_FAILED`、缺 agent 路径产出 `SESSION_CROSS_SEARCH_MISSING_AGENT`、省略任何 `cwd` 过滤、parent/root 过滤处理、以及服务层封顶。
- **真实 SQLite 组合**——真实的 `SessionStore` + JSONL 持久化 + `SqliteSessionQueryEngine` + `ApprovalService` 启动插件，并搜索其他 `cwd` 下的持久化会话：获批搜索返回跨工作目录命中；被拒 gate 不返回任何结果，不泄露任何会话 id 或路径；缺授权服务时响亮失败；配置封顶跨工作目录生效；审计对记录到调用者会话。

## Alternatives considered

### 扩展现有 `tool-session-query` 以支持跨工作目录

复用既有包，通过加入授权分支放宽其 workspace 授权。否决：该包的 README 与 workspace-access 模块把同 `cwd` 授权视为不变量，其批量授权（`authorizeSessionIds`）围绕 `cwd` 相等构建，放宽它将削弱已交付 workspace-scoped 工具的安全姿态，并迫使迁移其测试。独立 Consumer 保持安全的默认不被破坏，并把跨工作目录能力做成显式 opt-in。

### 持久的跨工作目录授权缓存

保存一次授予，让后续调用跳过 gate。否决：这扩大攻击面、与 harness 的 fail-closed 授权姿态相悖，且一旦跨调用就无法作为单一审计事件记录。逐次 `allowed-once` 是任务要求的最小、可审计边界。

### 新能力 seam（新的 Service Definition/provider）

为跨工作目录搜索新建独立服务与 provider。否决：这是既有 `ctx.sessionQuery` seam 的 Consumer，而非新 seam；新增服务会重复查询接口，违反「单一内部调用者」的反气味规则（packages/AGENTS.md）。

## Consequences

在获得显式、可审计、逐次的用户批准后，模型可以读取 harness home 的任意工作目录中的历史会话；该操作是 opt-in、cursor-free、受可配置上限约束的，并复用单一可信查询 provider。代价是每次调用都要向用户弹出一个提示，而这正是敏感跨边界读取的刻意定价。workspace-scoped 姊妹工具保持不变，继续在不提示的情况下提供同 `cwd` 搜索。

## Related

- [面向模型的会话查询工具](2026-07-24-model-facing-session-query-tools.md) —— workspace-scoped 姊妹工具及搜索到 trace/read 的工作流。
- [SQLite session-query provider](2026-07-10-sqlite-session-query-provider.md) —— 底层 `ctx.sessionQuery` 服务。
