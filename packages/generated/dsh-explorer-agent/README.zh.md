[English](README.md) | 中文

# @deepseek-ai/dsh-explorer-agent

用于 DeepSeek Harness 的可复用只读目录探索代理（Explorer Agent）。

该插件注册 `explorer` 工具。调用方代理传入一个或多个目录以及一个自然语言问题；插件启动一个只读的 Explorer 子代理，其作用域严格限定在这些目录内，只能使用 `read`/`glob`/`grep` 以及两个结构化提交通道，并返回一个简洁、有证据支撑的答案，涵盖子代理提交的路径与语义发现。

该插件是 `cordis-sub-agent` 过去为其自身插件开发工作流所内嵌的 Explorer 代理的提取与泛化形式：原先固定的单一仓库根目录被替换为调用方提供的目录，因此任意目录或目录集合都可以被探索。

## 使用方法

在 `dsh web` 中加载该插件：

```sh
pnpm dsh web --patch ./packages/generated/explorer-agent/cordis.yml
```

例如，让代理探索某个目录：

> 探索 `packages/fs` 和 `packages/subagent`，并告诉我一个面向模型的文件系统搜索工具是如何注册自身的。

代理使用 `directories` 和 `question` 调用 `explorer`，并总结有证据支撑的答案。

### 工具：explorer

输入：

- `directories`（必填）：要探索的目录路径。支持多个目录；条目会去除首尾空白、基于当前工作目录解析，并去重。Explorer 子代理只能在这些目录内探索；空列表会明确报错（fails loudly）。
- `question`（必填）：探索问题，原样传给 Explorer 子代理，并用作其提交内容的匹配键。

输出：一个包含两个可选部分的字符串——`# Explored paths`（`explore_paths` 提交内容）和 `# Semantic findings`（`explore_semantics` 提交内容），每部分均为子代理提交的原始 JSON。当子代理异常停止、完成时未提交任何结构化结果，或没有带 `toolFilter` 能力的子代理提供方可用时，该工具会明确报错。

Explorer 子代理通过 `explore_paths`（路径发现）和 `explore_semantics`（多文件语义分析）提交发现结果。这两个工具均由本插件注册，并且由于它们位于共享的工具注册表上，对调用方代理同样可见；预期只有 Explorer 子代理会调用它们。

## 模型体验

### 插件交互

#### 模型看到什么

`explorer` 工具的模式（schema，必填的 `directories` 数组和 `question`），以及每次调用返回的包含已提交路径/语义 JSON 的格式化答案字符串。每次调用对应一次子代理运行：子代理使用 `read`/`glob`/`grep` 执行探索，并通过结构化通道提交；每次调用都会在一个全新的子会话中产生一次额外的模型对话。

#### Token 影响

每次 `explorer` 调用都会启动一次子代理运行，该运行从所组合的 LLM 提供方消耗自己的模型预算。返回的答案字符串会加入调用方代理的上下文；`explore_paths`/`explore_semantics` 的响应就是子代理提交的 JSON。

#### KV 缓存影响

该插件自身不添加任何固定的提示词前缀。子代理运行是独立的会话，其缓存行为遵循所组合的提供方与 agent-loop 配置。

## 要求

- 带有至少一个具备 `toolFilter` 能力的提供方的 `subagents` 服务（进程内 `spawn`/`fork` 提供方符合条件）。
- 在同一进程中组合 `read`/`glob`/`grep` 工具，以便 Explorer 子代理能够探索：当你的组合缺少文件系统工具套件时，加载 `@deepseek-ai/dsh-tool-fs`（read）和 `@deepseek-ai/dsh-tool-fs-search`（glob/grep）。
- 为子代理运行配置的 LLM 提供方。

## 已知限制与延后工作

- 探索范围由 persona 与提示词文本约束，而非文件系统策略围栏：`read`/`glob`/`grep` 并不受路径限制于传入的目录。该插件自身从不注册写工具，且子代理的 toolFilter 会隐藏除五个读取/提交工具之外的一切，但组合进来的支持任意路径的 `read` 仍可能被子代理指向任何位置。
- 子代理的结构化提交内容通过完全一致的问题字符串与运行相匹配；同一工作流上两个问题相同的并发运行会相互冲突记录。面向模型的工具会在新调用开始前返回，因此正常工具使用不会出现这种情况。
- 结果记录是进程本地的，会随进程终止而消失；没有之前探索结果的持久缓存。