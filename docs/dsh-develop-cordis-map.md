# DSH Develop Cordis Map

本文按 DeepSeek Harness 根目录组织目录职责。`packages/` 和 `examples/` 按“遇到 README 即停止向下递归”的规则展开；目录作用优先取该目录 `README.zh.md` 的第一段介绍性文字。


```text
DeepSeek Harness/
├── .agents---------Agent 工作流、开发约束和架构决策记录
├── .claude---------Claude Code 的本地配置
├── .cordis---------Cordis 本地运行或配置状态
├── .git---------Git 版本库元数据
├── .github---------CI、Issue 和仓库自动化配置
├── .pnpm-store---------pnpm 依赖缓存
├── .sessions---------本地会话运行数据
├── .tmp---------临时工作目录和生成文件
├── apps---------可独立启动的 CLI、Web 和 ACP 应用入口
├── assets---------仓库或应用使用的静态资源
├── coverage---------测试覆盖率输出
├── docs---------架构、开发、参考目录和其他项目文档
├── packages---------插件源码和 workspace package 目录
│   ├── acp---------ACP（Agent Client Protocol）组通过该协议将 harness 中的 agent（智能体）公开给程序化客户端。它是互操作传输层，不是展示或人机交互层；配对的进程外 subagent *客户端*在 [`subagent/subagent-acp`](../subagent/subagent-acp/README.md)，因为它实现的是 subagent 提供方接口。
│   ├── api---------面向应用的 Remote 技术栈。`remotes` 负责 BFF 策略和选定的业务 API，`gateway` 则实现 Host 与 Client 环境共用的 Typert 一元 RPC endpoint。
│   ├── attachment---------持久二进制附件 seam 及其本地文件系统实现。两者均为产品包。
│   ├── boot---------由 `apps/cli` 和 [`examples/`](../examples/README.md) demo bin 共享、与渠道无关的启动库。
│   ├── bundle---------Profile 组合包：在 manifest（元数据清单）中声明 `"dsh": { "bundle": { "patch": "./cordis.patch.yml" } }` 的 npm 包，因此可作为 patch 层安装进 `dsh --profile` 组合（[profile 约定](../boot/app-boot/README.md#profiles)）。组合包的实体是它的 patch 列表；有些组合包还附带由其 patch 挂载的运行时粘合插件。
│   ├── client---------dsh web GUI 的浏览器侧：shell 启动、浏览器与宿主通信、共享 UI 服务和功能插件。编写规则见 [AGENTS.md](AGENTS.md)；宿主半侧是 [`host/`](../host/README.md)。除 `test-runtime` 外，均为名为 `@deepseek-ai/dsh-client-<name>` 的**产品**包。
│   ├── code-runtime---------代码执行能力 seam（参见[能力 seam](../../.agents/notes/implemented/architecture/2026-06-13-capability-seams.md)）：运行时 Service Definition，用于对宿主提供的异步绑定执行模型编写的程序，并捕获它打印和返回的内容；可替换的提供方；以及工具注册表的 [Code Mode](../core/tools/README.md) Consumer（`tools: { mode: code }`，即 `run_code` 工具和按所加载运行时 `language` 生成的 SDK）。设计见 [Code Mode Agent Note](../../.agents/notes/implemented/feature/2026-06-15-code-mode.md)。这些全是**产品**包。
│   ├── compaction---------一个压缩（compaction）能力家族（参见[能力 seam](../../.agents/notes/implemented/architecture/2026-06-13-capability-seams.md)）：Service Definition、摘要提供方、无模型工具结果修剪配套工具，以及用户命令 Consumer。这些全是**产品**包。
│   ├── context---------在不定义工具的情况下添加模型可见的请求上下文的产品插件。`agent-instructions` 包含在默认 `dsh-agent-spine-demo` 组合包中，可通过组合包配置禁用；`time-context`、`tmux-context` 和 `session-reference` 需主动启用。
│   ├── cordis_sub_agent---------
│   │   └── cordis_sub_agent---------dsh-cordis-sub-agent 负责在 DeepSeek Harness monorepo 内开发插件。每个任务 独占一个生成 workspace package：packages/generated/<plugin-name>/。
│   ├── core---------构成 harness 默认控制主干的会话日志、系统提示词组装、工具注册表、agent（智能体）词汇、部署默认模型选择和具体循环。这些是**产品**包，即插件和消费方构建所依赖的稳定接口。
│   ├── credentials---------凭据能力家族将引用解析与提供方分离：
│   ├── e2b---------这是一个实验性提供方组合 POC，把一个文件系统／进程执行环境放进 E2B Linux 沙箱。E2B 只提供沙箱生命周期与两个基础 OS 适配器；提供方无关的消费方在其上构建更高层能力。
│   ├── examples---------本目录包含 **演示／参考** package：一类是供轻量叶节点 `cordis.yml` 加载的预先组合包，另一类是作为生成插件模板的小型普通插件 `plugin-reference`。组合包的 npm 名称使用 `-demo` 后缀，表示不属于产品对外接口。仓库根目录 [`examples/`](../../examples/AGENTS.md) 下的可运行叶节点与 [Python SDK 运行时](../../python/sdk-runtime/README.md) 是组合包的消费方。
│   ├── extensions---------agent 修改自身运行时：检查已加载的插件与服务接口、定义并运行模型编写的动态包（dynamic package）并再次撤下，外加受限 repository Plugin 运行时。两个浏览器半的包住在这里而不是 `packages/client/`，因为它们是本子系统双半包的其中一半；host 聚合把它们排除在外，让两个契约面各自保有独立的编译 program。设计居所：[工具集 Agent Note](../../.agents/notes/implemented/feature/2026-07-08-self-referential-cordis-toolset.md)。
│   ├── feedback---------反馈家族公开两份刻意分离的契约：写入权威 Session 日志的不可变评价，以及挂在单条 assistant 消息上的可编辑本地伴随记录（sidecar）反馈。两者都不会进入模型对话。
│   ├── fs---------文件系统栈包括：提供方约定（执行世界路径、有界文本 I/O 与带可选版本防护的原子变更）、本地实现、政策门禁插件（已观察状态、编辑前读取、版本防护的写入/编辑）、面向模型的文件工具与执行器，以及基于 ripgrep 的发现工具。全部都是**产品**包。
│   ├── goal---------agent 会话的持久目标状态，独立于消费它的面向模型工具与续行策略。goal 状态是所属会话日志的一部分；消费方依赖 `dsh-goal`，绝不依赖具体的 agent loop（智能体循环）。
│   ├── guard---------行为 guard 插件监视 agent loop（智能体循环）中的无效模式，并强制执行单次调用预算。guard 是核心服务和扩展点的自包含消费方，而非可替换能力。
│   ├── hooks---------hooks 子系统让用户像使用 Claude Code 和 Codex 一样，在生命周期节点扩展 agent（智能体）：把桥接插件指向现有 `hooks.json`（或设置），即可忠实运行这些外部 shell 钩子。规范扩展接口本身是 harness 的类型化拦截点（参见[拦截扩展点 Agent Note](../../.agents/notes/implemented/feature/2026-06-30-interception-extension-points.md)）；「原生钩子」只是这些扩展点上的普通 Cordis 插件。这些包是把外部 shell 钩子协议转换到同一接口的**桥接**，也包括它们共同依赖的共享协议库。
│   ├── host---------dsh Web GUI 的宿主侧：所有客户端形态共享的 API 网关，以及承载它的普通 HTTP 服务器。浏览器侧位于 [`client/`](../client/README.md)；组合应用是 [`apps/cli`](../../apps/cli/README.md)，它启动 [`dsh-base` 组合包](../bundle/base/cordis.patch.yml) 来提供 [`apps/web`](../../apps/web/)。这些全是**产品**包。
│   ├── identity---------跨产品领域共享的身份值。这些值不表示经过身份验证的账户。
│   ├── interaction---------人与运行中的 agent（智能体）协作所经由的服务与插件——提问、审批、权限预设、命令。这些是**产品**包：由用户直接操作的真实接口。
│   ├── jobs---------本家族为长时间运行的工具提供一套按所有者隔离的后台任务协议，用于观察、取消、等待和完成通知。
│   ├── llm---------LLM（大语言模型）seam 及其提供方适配器。`llm` 包同时承担 Service Definition 和 Consumer 角色：抽象服务、内容块词汇和流式分片组装器。提供方适配器注册到 `ctx.llm`。这些全是**产品**包。
│   ├── lsp---------语言服务器能力 seam：LSP Service Definition、通用 stdio 提供方，以及面向模型的 `lsp` 工具。这些全是**产品**包。
│   ├── mcp---------将 harness 与 MCP 生态系统桥接的包。
│   ├── memory---------
│   │   └── memory---------**Session 保存发生过什么；Experience Memory 保存值得复用什么。**
│   ├── plan---------Plan mode 是按 agent（智能体）记录的协作状态，而不是通用模式注册表或能力 seam。
│   ├── preset---------**agent preset** 是一个目录，其中放置一份 `agent.cordis.yml`。把它挂载到某个 agent（智能体）的 scope 上下文之下，该会话就获得自己的工具与提示词段落，而其他在运行的会话各自保持不变，因此一个进程可以同时运行多个组装方式不同的 agent。
│   ├── runtime-diagnostics---------
│   │   └── invariants---------用于包自有运行时不变量检查的可配置注册表服务。根插件注册 `ctx.invariants`；它不包含产品检查或产品包导入。每个工作区包都发布一个 `./invariant` 配套入口，用于注册其精确 npm 包名。
│   ├── sandbox---------本家族将逐会话限制策略应用于进程执行。它覆盖与宿主共享文件系统和内核的子进程；隔离环境会替换完整的能力实现，而不是在此注册。
│   ├── schedule---------Schedule 家族负责管理提醒，其持久状态保存在原 Session 日志中。进程内 owner 只会在该 Session 拥有 live 根 Agent 时等待；cold Session 再次 live 后会恢复逾期工作，但这不意味着存在外部通知渠道。
│   ├── sdk---------本组包含用于从另一进程驱动 Harness 运行时的协议栈。调用方提供运行时可执行文件及其 `cordis.yml`；本组不创建、配置、构建或启动开发者项目。[TypeScript SDK 决策](../../.agents/notes/implemented/feature/2026-07-27-typescript-sdk-and-sdk-subagent-backend.md)负责客户端约定，[工具链移除](../../.agents/notes/implemented/simplification/2026-08-11-remove-sdk-project-toolchain.md)负责产品边界。
│   ├── session---------这是围绕 `core/session` 内存中运行的服务构建的持久功能族：包括持久化 seam 及其存储后端和检查点策略、提供日志派生全量值的投影 seam、日志支持的标题，以及外发会话遥测。它们全部都是**产品**包（package）。`session-query/` 仍是同级独立组：读取／工具接口的消费不依赖持久化内部实现。
│   ├── session-query---------本家族提供经过授权的实时与持久会话日志检索，且独立于压缩（compaction）。
│   ├── settings---------该包族通过注册的命名空间与可替换存储提供方解析用户可编辑配置。
│   ├── shell---------该能力家族涵盖规范执行器 seam、其实现、共享 shell 环境和面向模型的工具。这些全是**产品**包。
│   ├── skill---------本家族发现可复用的 agent（智能体）指令，并通过与提供方无关的目录和 loader 将其公开给模型。
│   ├── spill---------本家族持久化过大的工具输出，并以有界预览和取回定位信息替换内联结果。
│   ├── storage---------本家族通过具名后端和类型化数据形式，持久化会话事件日志以外的应用数据。
│   ├── subagent---------本家族允许一个 agent（智能体）将工作委派给子 agent。多个具名提供方可在同一上下文中共存。
│   ├── subprocess---------这里集中提供一个执行世界的共享进程基底：可执行文件查找、具有原始或收集式 stdio 的完全明确指定的受管子进程树，以及一项底层终端进程原语，负责 PTY 分配、前台进程组和提供方仍可观察到的会话成员清理。命令默认值补全、shell 语义、时限、协议分帧、就绪状态与呈现留在消费方：[bash 执行器](../shell/README.md)、[LSP 主机](../lsp/README.md)、[PTY shell 后端](../terminal/README.md)与 [ACP（Agent Client Protocol）subagent 后端](../subagent/README.md)。参见 [subprocess seam Agent Note](../../.agents/notes/implemented/architecture/2026-07-26-subprocess-seam.md)。
│   ├── terminal---------`PTY` 的全称是 **Pseudo-Terminal（伪终端）**。这项能力提供持久且限定所有者范围的终端会话，适用于需要跨工具调用保留状态或使用交互式 stdin 的工作流。PTY 是单次 bash 与文件系统工具的补充，不会取代后两者更严格的逐操作约定。
│   ├── test-support---------这些包为仓库开发、测试和示例提供支持，而不是产品 API。其兼容性取决于所服务的开发需求。
│   ├── todo---------面向模型的 todo 能力。它是单一**产品**包，因为一个 agent（智能体）会话拥有该列表；不存在可替换的提供方约定。
│   ├── typert---------Typert 将源代码分析、运行时存储和 Loader 发现机制分离。
│   ├── util---------这些零依赖包提供由多个能力家族共享的小型原语。业务语义仍归各个消费这些原语的能力所有。
│   ├── web---------本家族提供与提供方无关的 web 搜索和抓取操作，以及消费这些操作的面向模型工具。
│   ├── workflow---------本家族通过 subagent 运行由模型编写的编排工作流，并将通用工具与固定策略工具公开给模型。
│   └── workspace---------本家族拥有持久 workspace：带标题和有序会话成员关系的用户目录。
├── examples---------可运行的 Cordis 组合和插件示例
│   ├── acp-agent---------通过 JSON-RPC stdio 提供的面向自动化的 [ACP（Agent Client Protocol）](https://agentclientprotocol.com) 服务器。它面向 parent agent（父智能体）、subagent 提供方和其他程序化客户端，而非产品 UI。
│   ├── headless-agent---------本目录负责 headless coding agent（智能体）的回放和真实模型测试组装：DeepSeek V4 + 本地 bash 与文件系统工具 + subagent 委托 + 工作流与全新 agent Ralph 迭代 + `todo_write` + JSONL 持久化。本目录显式挂载共享 agent 主干、一个根 agent、持久化和检查点策略；它不是第二个产品入口。
│   ├── jsonrpc-agent---------面向 Python SDK 内置 JSON-RPC 运行时的无人值守编码 agent（智能体）组合。它有意不加载终端 UI、控制台日志记录器、批准界面或用户交互工具，因为 stdout 属于 SDK 协议，轮次由 SDK 驱动。
│   ├── mcp-memory---------这三份**默认关闭的参考配置**通过 [`@deepseek-ai/dsh-mcp-client`](../../packages/mcp/mcp-client/README.md) 将一个记忆系统连接到 DSH。请选择其中一份，或复制相同的通用 MCP 配置项来连接其他服务器。
│   ├── web-cordis---------[`@deepseek-ai/dsh-tool-cordis`](../../packages/extensions/tool-cordis/README.md) 的自指示例。agent（智能体）可以检查当前 Cordis 进程，并在内存中挂载或卸载模型编写的插件。临时插件会在卸载或进程退出时消失，并可能影响同一进程中的其他会话。
│   └── web-schedule---------此 overlay 让一个 `dsh web` 进程显式启用 Schedule 提醒，同时不改变交付的默认 Web 组合：
├── native---------原生模块和平台相关实现
├── node_modules---------已安装的 Node.js 依赖
├── patches---------第三方依赖的本地补丁
├── python---------Python SDK 和随附运行时
├── scripts---------构建、代码生成、检查和发布脚本
├── vendor---------固定版本的第三方源码副本
└── website---------VitePress 文档网站及其构建入口
```

## 开发插件需查看的文档教程

按需阅读以下文档即可完成从理解 Cordis 插件、开发 Harness 能力到验证和发布的工作。

### 开始编写最小插件

- [`docs/user/develop/basic/index.zh.md`](user/develop/basic/index.zh.md) — 创建一个最小 Harness 插件，并通过 `cordis.yml` 和 `--patch` 加载到 Web UI。
- [`docs/cordis-tutorial/01-first-plugin.zh.md`](cordis-tutorial/01-first-plugin.zh.md) — 从最基础的 `apply(ctx)`、插件加载和运行方式开始学习 Cordis。
- [`docs/cordis-primer.zh.md`](cordis-primer.zh.md) — 解释插件、Context、Service、`inject`、事件和配置等核心概念。

### 添加插件能力

- [`docs/user/develop/basic/config.zh.md`](user/develop/basic/config.zh.md) — 为插件增加可由 `cordis.yml` 配置的参数。
- [`docs/user/develop/basic/tool.zh.md`](user/develop/basic/tool.zh.md) — 使用 Harness 工具定义接口、参数校验、执行逻辑和结果呈现。
- [`docs/cordis-tutorial/07-into-the-harness.zh.md`](cordis-tutorial/07-into-the-harness.zh.md) — 将工具注册到 Harness 的 `tools` 服务，并接入真实工具执行流水线。
- [`docs/cookbook/extension-cookbook.zh.md`](cookbook/extension-cookbook.zh.md) — 按功能查找 Harness 的扩展点、服务、事件和插件组合方式。

### 开发正式 workspace package

- [`docs/cookbook/adding-a-package.zh.md`](cookbook/adding-a-package.zh.md) — 新增正式 `packages/<group>/<pkg>/` package 的目录、manifest、TypeScript 配置、聚合引用、README 和验证要求。
- [`docs/architecture.zh.md`](architecture.zh.md) — 了解插件树、profile、bundle、核心能力、事件和可扩展机制，确定插件应接入哪个扩展点。
- [`docs/development.zh.md`](development.zh.md) — 了解仓库安装、TypeScript Host/Client 项目布局、构建顺序和日常开发命令。
- [`docs/testing.zh.md`](testing.zh.md) — 根据插件类型选择单元测试、真实组合测试、覆盖率和构建验证范围。

### 开发特定类型的插件

- [`docs/cookbook/adding-a-tool.zh.md`](cookbook/adding-a-tool.zh.md) — 专门介绍模型可调用工具的定义和注册。
- [`docs/cookbook/adding-an-llm-adapter.zh.md`](cookbook/adding-an-llm-adapter.zh.md) — 专门介绍新的 LLM provider 和适配器接入方式。
- [`docs/cookbook/adding-a-conversation-node.zh.md`](cookbook/adding-a-conversation-node.zh.md) — 专门介绍 Web Client Chat 节点和对应渲染器。
- [`docs/cordis-tutorial/03-services.zh.md`](cordis-tutorial/03-services.zh.md) — 学习如何声明 Service、提供服务并通过 `inject` 建立依赖。
- [`docs/cordis-tutorial/04-events.zh.md`](cordis-tutorial/04-events.zh.md) — 学习如何声明、监听和使用 Cordis 事件扩展行为。
- [`docs/cordis-tutorial/05-config.zh.md`](cordis-tutorial/05-config.zh.md) — 学习 Cordis 配置对象、校验和运行时配置注入。

### 验证、打包和发布插件

- [`docs/user/develop/basic/publish.zh.md`](user/develop/basic/publish.zh.md) — 将本地插件制作成 bundle，安装到 profile，并通过 `dsh plugin` 管理和发布。
- [`docs/cookbook/maintaining-dsh-code-review.zh.md`](cookbook/maintaining-dsh-code-review.zh.md) — 了解维护者检查、代码审查和提交前需要关注的仓库约束。
- [`docs/cordis-tutorial/06-composition-and-hmr.zh.md`](cordis-tutorial/06-composition-and-hmr.zh.md) — 学习插件组合、加载依赖和热模块替换行为。

### 查询底层 API 和运行链路

- [`docs/cordis-api/`](cordis-api/) — Cordis Context、Service、事件、Registry 和 Fiber 的 API 参考。
- [`docs/subsystems/`](subsystems/) — Harness 各子系统的服务、事件、类型和可注入扩展点参考。
- [`docs/tool-execution-pipeline.zh.md`](tool-execution-pipeline.zh.md) — 查询工具从调用、校验、执行到结果事件的完整流水线。
- [`docs/event-producer-consumer.zh.md`](event-producer-consumer.zh.md) — 查询事件的生产者、消费者和跨插件连接关系。
- [`docs/dsh-develop-cordis-map.md`](dsh-develop-cordis-map.md) — 当前仓库目录和插件开发相关文档的导航地图。
