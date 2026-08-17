# @deepseek-ai/dsh-tool-cross-session-search

[English](README.md) | 中文

经用户批准、面向模型的工具：通过 `ctx.sessionQuery` 搜索**跨所有工作目录**的历史会话。与 `@deepseek-ai/dsh-tool-session-query` 不同——后者仅允许调用者自身工作目录（`cwd` 相等）内的跨会话读取——本 opt-in 包可以触及在其他工作目录中产生的会话。触及这些会话属于敏感操作，因此每次调用都先经过 `ctx.approval` 的一次性用户授权 gate：被组合的应答者必须授予 `'allowed-once'` 之后才会发生任何 session-query 交互，且每一次 gate 都会在调用者的会话日志上写下持久的 `approval/asked` + `approval/decided` 审计对。

本包注册一个只读工具 `cross_session_search`，且默认不被 shipped 的主机组合挂载。

## 配置

| 键 | 默认值 | 含义 |
|---|---:|---|
| `maxSearchResults` | `20` | 单次调用最多返回的跨工作目录命中数，在服务层强制 |

## 授权与审计

`cross_session_search` 是进入跨工作目录搜索的唯一代码路径，且在接触任何 provider 之前就被 gate 拦截。工具以调用本身的 `callId` 和指明查询词的原因调用 `ctx.approval.request()`，随后强制执行返回的结果：

- `allowed-once` —— 本次调用才继续搜索。
- `rejected` —— 工具以模型安全信息 fail closed；不发生任何 session-query 交互。
- `cancelled` —— 工具 fail closed；不取回任何命中。
- `unavailable` —— 无可用应答者；工具 fail closed。

模型无法决定或伪造授权范围：由应答链（而非工具）决定结果，且 `@deepseek-ai/dsh-user-approval` 下 `never` 策略会确定性拒绝每一个 gate。因为授予是一次性的（`allowed-once`），本包不做跨调用的授权缓存，也绝不从模型参数推导任何工作目录范围。

## 搜索语义

调用始终**不**在会话过滤里加入 `cwd` 子句，因此 live-preferred 逻辑语料横跨所有工作目录。本包复用 `ctx.sessionQuery.searchSessions` 与 `ctx.sessionQuery.readTitleSnapshots`；不建立第二存储，也不复制任何数据库。结果是 cursor-free 的：工具在内部翻页 provider 的光标而不暴露它们，并返回每个命中的折叠标题、所属工作目录、可用性与最强匹配摘录，使模型无需二次查询即可理解跨工作目录的上下文。部署的 `maxSearchResults` 上限在服务层强制，与任何 provider 上限无关。

## 模型体验

### 系统提示

#### 模型所见

插件挂载时，模型会收到一个固定的跨工作目录搜索引导小节。

##### 跨工作目录搜索引导

```markdown
Use session_cross_search to find relevant work across prior sessions in ANY workspace. Each call asks the user for approval before searching. Results are cursor-free and bounded. The search reaches sessions created in other working directories only after the user approves this call.
```

#### Token 影响

插件挂载期间，每次请求都会有一个固定的小节。

#### KV Cache 影响

插件与引导文本未变时前缀稳定。

### 工具 schema

#### 模型所见

模型看到生成的 [`cross_session_search` schema](../../../docs/tool-catalog.md#deepseek-aidsh-tool-cross-session-search)。它暴露查询文本与可选的创建时间/父会话过滤，并有意省略光标、页大小、工作目录路径与任何模型可控的结果上限。

#### Token 影响

工具可见时，每次请求会发送一个只读 schema。

#### KV Cache 影响

工具可见性与定义未变时前缀稳定。

### 工具结果

#### 模型所见

每次获批成功的调用输出一个纯文本块，列出带边界的结果（标题、工作目录、可用性与摘录）。每次被拒的调用输出一个指明关闭结果的错误块。

#### Token 影响

结果依赖数据，在压缩前保留在登录的工具历史中；`maxSearchResults` 限定命中数量。

#### KV Cache 影响

追加式结果文本跟在可复用请求前缀之后，不会使早期缓存条目失效。

## 已知限制与后续工作

- 工作目录身份是每个会话头上存储的精确 `cwd` 字符串，因此 symlink 等价路径与未设置 `cwd` 的会话会被视为各自独立的工作目录。
- gate 每次调用独立求值；没有跨调用持久授权，因此长流程的多步工作流需在每次搜索时重新批准。
- 全文后端是部署挂载的 `ctx.sessionQuery` provider；禁用搜索的部署（`openAt: never`）即使在获批后也会让搜索调用失败，而精确读取仍然可用。
