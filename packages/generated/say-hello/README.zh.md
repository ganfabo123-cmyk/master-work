# say-hello

[English](README.md) | 中文

一个最小的 DeepSeek Harness 插件：通过 `defineTool` 向 [`ToolRuntime`](../../core/tools/README.md) 注册表注册一个模型可调用的工具 `say_hello`。工具接收可选参数 `name` 并返回纯文本问候语；插件行为完全在内存中完成，无持久化、无外部服务。

## 工具：`say_hello`

本包是命名导出形式的函数插件（`name` / `inject` / `apply`，无默认导出）：`inject: ['tools']` 声明对工具服务的依赖，`apply` 在 `ctx.effect` 内注册工具，因此注册会随插件 fiber 的 dispose 一并注销。

- 参数 `name`（可选 `string`）：要问候的名字。`execute` 会先 trim 该值；未提供、为空或全空白时返回 `Hello!`，其余情况返回 `Hello, <name>!`（例如 `' Ada '` 问候 `Ada`）。
- 输出：规范值为纯文本问候字符串（`output.schema` 为 `{ type: 'string' }`），以单个 `text` 块呈现给模型。
- 生命周期：插件 fiber 被 dispose 时工具自动注销；单元测试覆盖该注销行为以及两种问候行为。

## 组合方式

`@deepseek-ai/cordis` 与 `@deepseek-ai/dsh-tools` 是 peer 依赖，`lib/index.js` 是插件入口（`main`）。用 `pnpm run build` 构建后，将本包与这些运行时一起挂载到 harness 的 profile 组合中——例如通过挂载本包的 [profile bundle](../../bundle/README.md) 补丁。在会话中要求模型调用该工具：

- "Use the say_hello tool." → 模型收到 `Hello!`
- "Use the say_hello tool with name Ada." → 模型收到 `Hello, Ada!`

## 模型体验

### say_hello 工具

#### 模型看到的内容

模型看到 `say_hello` 函数定义——描述为 `Greet someone by name and return the greeting text.`——带一个可选的 `string` 参数 `name`。定义经 `ctx.tools` 进入提示词组装，每次调用返回纯文本问候字符串。

#### Token 影响

工具可见时，每次请求有固定的一条函数定义开销；问候结果属于数据相关的文本。

#### KV Cache 影响

在工具定义及其可见性不变时前缀稳定；插件生命周期或作用域限制可能使该定义起的缓存复用失效。

### 工具结果

#### 模型看到的内容

每次调用恰好返回一个纯文本字符串：`name` 未提供、为空或全空白时为 `Hello!`，否则为 `Hello, <name>!`；`name` 在使用前会 trim，因此首尾空白不会进入问候语。

#### Token 影响

结果文本随数据变化，且在被压缩（compaction）前会持续重发。

#### KV Cache 影响

仅追加；新出现的可见结果内容跟在可复用的请求前缀之后，不会使现有 KV 缓存条目失效。

## 已知限制与暂缓事项

- **无配置面** — 插件不导出 `Config`，工具名与问候语措辞固定于源码；需要不同措辞的部署必须修改本插件而非配置它。
- **仅纯文本输出** — `say_hello` 只返回单个字符串；需要结构化数据（例如将问候的名字与问候语分开）的调用方必须自行解析文本。