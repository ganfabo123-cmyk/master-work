# dsh-memory

[English](README.md) | 中文

**Session 保存发生过什么；Experience Memory 保存值得复用什么。**

`@deepseek-ai/dsh-memory` 是 DeepSeek Harness 的仅追加经验记忆插件。它把可复用的成功与失败隔离到具名块文件中，每个文件包含独立 Markdown 记录，而不是保存对话或重建完整 Session。它还提供按 cwd 隔离的事实记忆：关于用户或工作空间的稳定事实会在每一轮自动注入模型上下文。

![Experience Memory 核心流程](assets/memory-flow.svg)

模型先搜索轻量候选元数据，只显式加载值得使用的经验；仅当当前任务产生了可复用结论时，才记录一条新经验。

## 查看真实运行

下面的终端记录来自仓库内通过[真实 Cordis Loader 运行的 Demo](examples/encoding-experience/demo.ts)，使用的插件、工具、Prompt 注册、Parser 和 Retriever 均与正式实现相同。

![真实 Loader Demo：先调用 memory_search，再调用 memory_get](assets/demo-terminal.svg)

在仓库根目录运行：

```powershell
pnpm exec tsx packages/memory/memory/examples/encoding-experience/demo.ts
```

完整示例包含真实的 [`cordis.yml`](examples/encoding-experience/cordis.yml) 和预置 [`global_memory.md`](examples/encoding-experience/global_memory.md)。

## 为什么需要 Experience Memory？

| 系统 | 保存内容 | 最适合 | 主要代价 |
|---|---|---|---|
| Session 历史/搜索 | 完整交互与事件 | 审计、回放、恢复 | 作为可复用 Prompt 时体积大、噪声多 |
| 通用 RAG Memory | 从广泛语料检索出的 Chunk | 查找可能相关的信息 | Chunk 不一定是经过验证的经验 |
| Experience Memory | 提炼后的成功/失败记录 | 复用已验证的调试和任务经验 | 需要有意识地提炼经验 |

Experience Memory 是 Session 存储的补充。Session 数据保留完整历史证据；每个块文件只保存被选中供未来复用的紧凑经验。

## 一个真实的 UTF-8 调试案例

本插件源于反复出现的 Windows 编码故障：通过隐式默认编码写入包含中文的 TypeScript 或 Markdown 文件，会破坏源码。失败方案及最终成功的 UTF-8 解决方法被整理成了一条可复用经验。

![真实 UTF-8 调试经验被后续任务复用](assets/encoding-case.svg)

持久记录就是普通 Markdown：

```markdown
# Windows 中文源码写入必须显式使用 UTF-8 {memory-17}

Keywords: deepseek-harness, windows, encoding, filesystem, typescript
Recorded At: 2026-08-16T02:34:23.123Z
Outcome: success

## Problem

依赖 PowerShell 默认编码写回文件后，中文内容发生乱码。

## Resolution

读写包含非 ASCII 内容的文件时显式使用 UTF-8，并通过磁盘重新加载验证内容。

## Lesson

跨平台文本修改必须控制源文件编码，并用真实多语言内容做 round-trip 回归。
```

后续任务搜索时不加载所有正文：

```text
[memory-17]
title: Windows 中文源码写入必须显式使用 UTF-8
keywords: deepseek-harness, windows, encoding, filesystem, typescript
matched keywords: deepseek-harness, encoding, typescript
outcome: success
```

只有 `memory_get({ block_name: "global", id: "memory-17" })` 才会把完整经验加入模型上下文。

## 安装与配置

在 DeepSeek Harness Workspace 中添加该包：

```powershell
pnpm add @deepseek-ai/dsh-memory
```

在 System Prompt 和 Tool 服务之后加载插件：

```yaml
- name: '@deepseek-ai/dsh-system-prompt'
- name: '@deepseek-ai/dsh-tools'
- name: '@deepseek-ai/dsh-memory'
  config:
    memoryDir: 'C:/Users/you/.dsh/memory'
```

`memoryDir` 默认为 `$DSH_HOME/memory`。该目录由 Host 所有；模型只能选择经过校验的块名，不能选择工作空间路径。每个块映射为 `<block_name>_memory.md`，因此 `global`、`python` 和 `dsh` 分别使用 `global_memory.md`、`python_memory.md` 和 `dsh_memory.md`。块名会转为小写，并且只能包含 1–64 个 ASCII 字母、数字、下划线或连字符。

使用默认配置时，首次访问 `global` 会把旧 `$DSH_HOME/memory.md` 移动到 `$DSH_HOME/memory/global_memory.md`，不解析或重写文件字节。如果两个文件同时存在，迁移会失败而不是覆盖。

事实记忆按绝对 cwd 存储在 `factsDir` 下（默认为 `$DSH_HOME/memory-facts`），每个 cwd 一个 Markdown 文件，文件名是该绝对路径的短 SHA-256 摘要。`maxFacts` 限制每个 cwd 注入到系统提示中的事实数量（默认 `100`）。

## 事实记忆（按 cwd 隔离的长期记忆）

与经验记忆不同，事实从不被搜索：`fact_remember` 和 `fact_forget` 维护一个以绝对会话工作目录为作用域的标题/正文存储，当前 cwd 的每条事实都会在每次装配时自动注入系统提示。

```text
user says "我叫 gan" or asks to remember the name
  → fact_remember({ title: 'user name', body: 'gan' })
  → persisted to <factsDir>/<sha256(cwd)>.md
  → injected every turn as "## 1. user name" plus body content for this cwd only
```

- 隔离按绝对 cwd：在 `D:/project-a` 保存的事实永远不会出现在 `D:/project-b`，也不会出现在大小写或分隔符不同但语义相同的路径上。
- 标题会被去空格并转小写；`fact_remember` 是 upsert，同一标题的后续正文会替换旧值。
- 注入区块指导模型把这些事实视为已知、当前的事实（除非用户反驳），并主动记住稳定的个人或项目事实，在用户更正或撤销时删除对应事实。
- 注入是 `system-prompt/assemble` 的动态贡献，因此事实每轮都会出现，并且 `fact_remember` 或 `fact_forget` 调用后会立即更新，无需重启。

## 模型工具

### `memory_search`

要求提供 `block_name`，接收具体关键词与可选 limit，只从该块返回 `id`、标题、规范化关键词、匹配关键词和 outcome，绝不返回正文或内部 Ranking Score。

### `memory_list_blocks`

无参数，按字典序返回所有当前拥有持久块文件的块名。清单来自磁盘目录，因此由其他进程或会话写出的块即使本进程未加载也会出现。内存目录不存在时返回空清单而不是报错。

### `memory_get`

要求提供 `block_name`，通过块内稳定的 `memory-N` ID 加载一条完整记录。该块内不存在对应 ID 时返回明确、模型可读的提示。

### `memory_record`

要求提供 `block_name`，校验模型工具调用提交的字段，并把整个批次直接持久化到该块。Harness 生成块内 ID 和 ISO 8601 `recordedAt`；缺省 outcome 变为 `unknown`。当前没有用户确认步骤。

```text
model Tool Call
  → validate block_name and select <block_name>_memory.md
  → validate title, keywords, body, outcome
  → normalize keywords
  → serialize the write
  → reload the selected block file and allocate max(memory-N) + 1
  → atomic replace
```

空标题、正文或关键词列表会被拒绝。正文允许 `##` 到 `######` Heading，但禁止一级 Heading，因为只有 `# <title> {memory-N}` 才能定义 Record Boundary。

### `fact_remember`

为当前会话 cwd 保存一条标题/正文事实。空标题或空正文会被拒绝；标题在持久化前去空格并转小写。

### `fact_forget`

按标题删除当前会话 cwd 的一条已保存事实。标题不存在时返回明确、模型可读的提示，而不是报错。

## 架构

![Experience Memory 架构](assets/architecture.svg)

每个具名块拥有一个 `MemoryStore` 和格式不变的 Markdown 真源，`MemoryRetriever` 负责在所选块内筛选候选。V1 的 `KeywordRetriever` 使用规范化关键词精确交集与线性扫描。

内部匹配关键词数量只用于选出 Top-K。入选候选随后按 `memory-N` 升序展示，因此展示顺序不表达相关性。面向模型的输出永不暴露 `score`、`rankingScore` 或 `similarity`。

`MemoryRetriever` 接收已经按块选定的 `MemorySearchSource`。未来 BM25、Vector 或 Hybrid Provider 可以维护派生 Index，而不用改变块文件、Service 或模型工具。这些是扩展点，不是 V1 功能。

`FactStore` 拥有按 cwd 的事实文件；`FactSource` 是它面向系统提示注入的只读投影。`MemoryService` 同时暴露两个 Store，是所有工具的唯一入口。

## 持久化与并发

- 每次读取和每次 Append 内都会重新加载所选块文件，因此可以看到外部编辑。
- 写入采用原子替换，并设置仅 Owner 可访问的文件与目录权限。
- 每个块拥有独立的进程内串行队列，覆盖重新加载、块内 ID 分配和写入。同一进程内的并发 Session 不会在同一块产生重复 ID 或丢失 Append。
- 不支持多个进程并发写入同一个块文件。
- 每个 cwd 的事实文件有自己的串行写队列，因此同一 cwd 上并发的 `fact_remember` 不会丢失事实；`fact_forget` 清空存储时会删除该文件。

## 验证

面向发布的测试覆盖：

- 空、单条、多条、损坏及嵌套 Heading 的 Markdown 记录；
- 块内最大 ID 分配、缺失文件创建、外部修改重载和 Batch 原子拒绝；
- 块间隔离、安全块名校验、旧全局文件迁移，以及三条并发 Append 不重复 ID、不丢失内容；
- 关键词精确匹配、规范化、零匹配、limit 以及 Top-K 选择与展示分离；
- Tool 输出契约，包括 Search 不泄露正文或 Score；
- 事实 round-trip、并发 remember、按 cwd 隔离以及注入 Section 渲染；
- 真实 Cordis Loader 装配及完整的块内 `record → search → get` 工具执行；
- 插件卸载后清理 Tool、Service 和 System Prompt Section；
- 多语言 UTF-8 round-trip，包含中文、English、日本語、Emoji、Markdown、代码片段和中文 Windows 路径。

运行命令：

```powershell
pnpm exec vitest run packages/memory/memory/tests
pnpm exec tsc -p packages/memory/memory/tsconfig.json --noEmit
```

覆盖率百分比是诊断指标而不是发布定义；产品契约和可复现的集成行为才是验收标准。

## Model Experience

### Experience and fact interaction

#### What the model sees

模型能看到 `memory_list_blocks`、`memory_search`、`memory_get`、`memory_record`、`fact_remember` 和 `fact_forget` 工具 schema。除 `memory_list_blocks` 外每个经验工具都要求 `block_name`；指导内容要求模型先用 `memory_list_blocks` 发现当前块集合，再选择一个块，生成多个具体搜索关键词，把搜索结果视为候选而不是真相，只从同一块加载值得读取的记录，并且只记录可复用经验，而不是普通错误或完整 Session 历史。按 cwd 注入的事实会作为已知上下文出现，`fact_remember` 和 `fact_forget` 会更新该 cwd 范围内的上下文。

#### Token effect

插件可见性不变时，工具 schema 和固定指导保持 Prefix Stable。搜索成本随所选块内的轻量元数据增长；只有显式调用块内 `memory_get` 才会把完整正文 Token 加入上下文。注入的事实每个 cwd 每轮最多增加 `maxFacts` 条简短的 `标题 + 正文` 记录。

#### KV Cache effect

工具视图和事实集合不变时，请求前缀保持稳定。调用 `memory_get` 或修改 cwd 事实会在稳定前缀之后追加依赖数据的上下文；这不承诺固定的 Token 节省。

## Known Limitations and Deferred Work

- 经验块是显式文件命名空间，不是访问控制规则：任何拥有这些工具的模型都能指定任意块。检索只支持精确关键词，没有项目根作用域、BM25、Embedding、Vector、Reranking、Hybrid Retrieval、跨块搜索或整块读取工具。事实记忆仅按 cwd 隔离——不会随项目进入其子目录。
- 没有自动 Session 挖掘、迁移、删除、合并、语义去重、矛盾处理或衰减。
- 写队列只保护单个进程。
- 事实标题按设计不区分大小写（去空格并转小写），所以 `User Name` 与 `user name` 是同一条事实。
- 性能 Benchmark 和大语料检索评估推迟到真实使用证明当前线性扫描假设失效之后。
