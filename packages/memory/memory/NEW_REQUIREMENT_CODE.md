# DeepSeek Harness Keyword Experience Memory 设计文档

> 当前阶段决策（2026-08-16）：暂时取消 `memory_record` 的用户确认步骤。模型 Tool Call 提交的字段经过既有校验与规范化后直接持久化。本文后续提到的 human confirmation 保留为未来可选扩展，不代表当前实现行为。

## 1. 目标

本插件为 DeepSeek Harness 提供一个独立于 Session 的长期经验记忆层。

它不保存完整 Session，也不尝试重新构建过去的完整执行过程，而是把任务执行过程中具有复用价值的信息提炼为独立的 **Experience Memory**。

例如：

```text
任务：
开发 DeepSeek Harness 插件

问题：
修改包含中文的 TypeScript / Markdown 文件后出现乱码

尝试：
A 方法失败
B 方法成功

最终经验：
在当前 Windows 环境下处理包含中文的源码时，需要显式使用 UTF-8 编码。
```

未来模型再次遇到：

```text
DeepSeek Harness
JavaScript
Windows
encoding
```

相关问题时，可以检索到该经验，将其作为过去的成功或失败 few-shot 使用。

系统核心流程为：

```text
Current Task
    │
    │ 产生可复用经验
    ▼
memory_record
    │
    ▼
Experience Memory Store
    │
    │ keywords
    ▼
Retrieval Layer
    │
    ▼
memory_search
    │
    ▼
candidate memories
    │
    ▼
memory_get
    │
    ▼
Past Experience as Few-shot
```

---

# 2. 核心设计原则

## 2.1 Memory 保存经验，而不是 Session

DeepSeek Harness 的 Session 用于记录任务执行过程中发生的事件。

Memory 解决的是另一个问题：

```text
Session:
发生了什么？

Memory:
这次经历中有什么值得未来复用？
```

因此 Memory 不保存整段历史消息，而是保存经过模型提炼后的经验单元。

每个经验单元应该能够独立回答：

1. 当时在做什么？
2. 遇到了什么问题？
3. 尝试过什么？
4. 哪些方法成功或失败？
5. 最终如何处理？
6. 从中得到什么可迁移经验？

---

## 2.2 Memory Store 与 Retrieval 分离

Memory Store 只负责：

```text
保存 Memory
读取 Memory
分配稳定 ID
保证持久化
```

Retrieval Layer 只负责：

```text
根据当前查询找到可能相关的 Memory
```

整体结构：

```text
                   memory_search
                         │
                         ▼
                ┌─────────────────┐
                │ Retrieval Layer │
                └────────┬────────┘
                         │
                  memory-N candidates
                         │
                         ▼
                ┌─────────────────┐
                │  Memory Store   │
                └─────────────────┘
```

检索算法不得与 Memory 存储格式强绑定。

因此未来：

```text
Keyword Match
      ↓
BM25
      ↓
Vector Search
      ↓
Hybrid Retrieval
```

都不应该改变 Memory 数据模型和 model-facing tool 的基本调用方式。

---

## 2.3 Append-only Memory

Memory 默认采用追加式存储。

```text
memory-1
memory-2
memory-3
...
memory-N
```

新增经验只追加新的 Memory，不因为分类变化移动旧 Memory。

V1 不提供复杂的：

```text
tree rebuild
move
merge
topic management
memory graph
```

当前版本的正式记忆使用 Markdown 标题树，同时通过 `memory_children` 逐层导航，并通过稳定 `memory-N` 获取经验正文。

新设计取消“树结构作为正式记忆必要组成部分”，将 Memory 本身作为 Source of Truth。

---

# 3. Experience Memory 数据模型

每条 Memory 表示一次独立、可复用的经验。

推荐逻辑结构：

```ts
interface ExperienceMemory {
    id: string
    title: string
    keywords: string[]
    recordedAt: string
    outcome?: "success" | "failure" | "mixed" | "unknown"
    body: string
}
```

其中只有以下字段参与基础检索：

```text
title
keywords
```

正文默认不参与 V1 Keyword Match。

---

# 4. Memory 内容规范

推荐 Memory Body 使用统一 Experience Template：

```markdown
## Context

当时正在进行什么任务，以及相关环境。

## Problem

遇到了什么问题、错误或异常现象。

## Attempts

尝试过哪些方案，以及各自的结果。

## Resolution

如果问题得到解决，最终采用了什么方法。

## Lesson

从这次经历中得到的、未来可以复用的经验。
```

例如：

```markdown
### DeepSeek Harness 修改中文文件后出现乱码

Keywords:
deepseek-harness, typescript, javascript, encoding, windows, filesystem

Recorded At:
2026-08-16 10:00

Outcome:
success

## Context

在 Windows 环境开发 DeepSeek Harness 插件，修改包含中文内容的
TypeScript 和 Markdown 文件。

## Problem

工具重新写入文件后，部分中文内容出现乱码。

## Attempts

尝试使用方案 A 重写文件，但编码问题仍然存在。

之后尝试方案 B，并显式指定 UTF-8 编码。

## Resolution

通过显式 UTF-8 读取和写入解决问题。

## Lesson

在 Windows 环境修改可能包含非 ASCII 字符的 Harness 源文件时，
应优先确认文件读写编码，避免依赖默认编码。
```

`body` 可以作为一个完整 Markdown 字符串保存。

系统不解析：

```text
Context
Problem
Attempts
Resolution
Lesson
```

这些章节的具体内容。

它们主要用于帮助模型产生稳定、具有 few-shot 价值的经验。

---

# 5. Keywords

## 5.1 Keywords 的职责

Keywords 表示：

> 未来模型在什么概念或问题语境下可能需要想起这条 Memory。

例如：

```text
DeepSeek Harness 修改中文文件出现乱码
```

可以包含：

```text
deepseek-harness
typescript
javascript
encoding
windows
filesystem
chinese-text
```

一条 Memory 可以拥有任意多个关键词。

因此不同语义维度可以同时指向同一个 Memory。

逻辑上可以理解成：

```text
                     memory-17
                    /    |    \
                   /     |     \
             encoding  windows  filesystem
                 |
          deepseek-harness
```

这相当于使用非常轻量的：

> Memory ↔ Keyword 多对多关系。

相比单一 Tree Parent，一条经验天然可以属于多个问题语境。

---

# 6. Keyword 生成

V1 中 Keyword 由模型在 `memory_record` 时生成。

要求模型尽可能覆盖以下几类信息：

### Technology

```text
javascript
typescript
python
git
```

### System / Project

```text
deepseek-harness
react
fastapi
```

### Problem

```text
encoding
timeout
tool-call-error
import-error
```

### Environment

```text
windows
linux
wsl
```

### Component

```text
filesystem
session
plugin
tool
```

不要求每条 Memory 必须同时拥有所有类别。

Keyword 应尽量：

```text
短
稳定
具有明确技术语义
```

推荐：

```text
deepseek-harness
typescript
encoding
```

不推荐：

```text
这个问题
很重要
之前失败的方法
编程
```

---

# 7. Storage

V1 可以继续使用单个 Markdown 文件。

例如：

```text
memory.md
```

内部连续存储：

```markdown
# DeepSeek Harness 中文文件编码异常 {memory-1}

Keywords: deepseek-harness, encoding, windows, filesystem
Recorded At: 2026-08-16 10:00
Outcome: success

...

# TypeScript Tool Schema 类型不匹配 {memory-2}

Keywords: typescript, tool-call, schema, validation
Recorded At: 2026-08-16 11:00
Outcome: failure

...
```

这里 Markdown heading 不再表达分类层级。

所有 Experience 都是同级 Memory Record。

因此不存在：

```text
移动节点
重建树
创建分类
修改父节点
```

Memory ID 是唯一稳定身份。

---

# 8. Memory ID

Memory 使用：

```text
memory-N
```

例如：

```text
memory-1
memory-2
memory-17
```

ID 由 Memory Store 分配。

模型不能：

```text
指定 ID
猜测 ID
创建 ID
```

ID 仅承担稳定身份职责，不承担语义。

---

# 9. Model-facing Tools

V1 只提供三个核心工具。

---

## 9.1 `memory_record`

记录一个或多个新的 Experience Memory。

接口：

```text
{
    entries: [
        {
            title: string,
            keywords: string[],
            outcome?: "success" | "failure" | "mixed" | "unknown",
            body: string
        }
    ]
}
```

`recordedAt` 建议由 Harness / Plugin 自动产生，而不是要求模型提供。

调用流程：

```text
Model
  │
  │ 发现值得长期复用的经验
  ▼
memory_record
  │
  │ human confirmation
  ▼
Memory Store
  │
  ▼
memory-N
```

当前版本的 `memory_record` 已经具有“模型产生候选经验 → 用户确认 → 持久化”的基础能力，只是目前确认后的经验进入 `temp_memory.md`。

新设计由于不存在“等待分类”的需求，可以在用户确认后直接写入正式 Memory Store。

因此：

```text
temp_memory.md
```

在新设计中不再是必需组件。

---

## 9.2 `memory_search`

根据关键词搜索过去的 Experience Memory。

接口：

```text
{
    keywords: string[],
    limit?: number
}
```

例如：

```json
{
    "keywords": [
        "deepseek-harness",
        "javascript",
        "encoding"
    ],
    "limit": 10
}
```

返回：

```text
[memory-17]
title: DeepSeek Harness 中文文件编码异常
keywords: deepseek-harness, javascript, encoding, windows
outcome: success
score: 3

[memory-8]
title: PowerShell 修改 TypeScript 文件导致编码变化
keywords: powershell, typescript, encoding, windows
outcome: failure
score: 1
```

`memory_search` 不返回完整正文。

这样避免：

```text
搜索一次
→ 大量完整 Memory 进入上下文
```

模型只根据：

```text
ID
Title
Keywords
Outcome
Score
```

判断哪条经验值得进一步读取。

---

## 9.3 `memory_get`

根据 Memory ID 获取完整经验。

接口：

```text
{
    id: string
}
```

例如：

```text
memory_get(memory-17)
```

返回：

```text
title
keywords
recordedAt
outcome
body
```

只有模型认为某个候选 Memory 可能真正相关时，才读取完整正文。

因此整个 Retrieval 是 progressive disclosure：

```text
memory_search
      │
      ▼
small candidate list
      │
      ▼
model judges relevance
      │
      ▼
memory_get
      │
      ▼
full few-shot experience
```

这延续了当前插件“不一次向模型返回整个 Memory 文件”的基本原则。

---

# 10. Retrieval Layer

Retrieval 必须设计为独立组件。

建议内部接口：

```ts
interface MemoryRetriever {
    search(
        query: MemorySearchQuery,
        memories: MemorySearchDocument[]
    ): Promise<MemorySearchResult[]>
}
```

查询：

```ts
interface MemorySearchQuery {
    keywords: string[]
    limit: number
}
```

内部用于检索的 Memory Document：

```ts
interface MemorySearchDocument {
    id: string
    title: string
    keywords: string[]
}
```

结果：

```ts
interface MemorySearchResult {
    id: string
    score: number
}
```

Model-facing 的：

```text
memory_search
```

永远只依赖：

```text
MemoryRetriever
```

而不关心实际使用哪一种检索算法。

整体：

```text
memory_search tool
        │
        ▼
MemoryRetrievalService
        │
        ▼
MemoryRetriever
        │
   ┌────┴────────────────────────┐
   │                             │
KeywordRetriever          Future Retrievers
                                 │
                        ┌────────┼─────────┐
                        ▼        ▼         ▼
                      BM25    Vector    Hybrid
```

---

# 11. V1：KeywordRetriever

初版只实现最简单的 Keyword Match。

## 11.1 Normalize

搜索前统一做基础 normalize：

```text
trim
lowercase
去除重复 keyword
```

例如：

```text
" TypeScript "
"TYPESCRIPT"
"typescript"
```

统一为：

```text
typescript
```

V1 不需要维护复杂 synonym dictionary。

---

# 12. V1 Keyword Matching

假设用户查询：

```text
deepseek-harness
javascript
encoding
```

Memory：

```text
deepseek-harness
javascript
encoding
windows
filesystem
```

则：

```text
matched keywords = 3
```

最简单评分：

```text
score = matched keyword count
```

例如：

```text
memory-17

query:
deepseek-harness
javascript
encoding

memory keywords:
deepseek-harness
javascript
encoding
windows

score = 3
```

另一个：

```text
memory-8

keywords:
typescript
encoding
windows

score = 1
```

最终：

```text
memory-17 > memory-8
```

---

# 13. V1 搜索规则

KeywordRetriever：

```text
1. normalize query keywords
2. normalize memory keywords
3. 求交集
4. 没有交集则过滤
5. score = intersection size
6. score 从高到低排序
7. 截断到 limit
```

伪代码：

```text
for memory in memories:
    matched = intersection(
        query.keywords,
        memory.keywords
    )

    if matched.length === 0:
        continue

    results.push({
        id: memory.id,
        score: matched.length
    })

sort(results by score descending)

return results.slice(0, limit)
```

初版不需要：

```text
BM25
embedding
reranker
LLM judge
```

---

# 14. 为什么 Model 应该提交多个 Keyword

Keyword Exact Match 最大的问题是：

```text
Memory:
javascript

Query:
js
```

不会产生匹配。

因此 V1 不在 Retrieval Layer 里实现复杂语义理解。

而是利用模型本身做 Query Expansion。

例如当前任务涉及：

```text
JS 文件乱码
```

模型可以搜索：

```json
{
    "keywords": [
        "javascript",
        "js",
        "encoding",
        "charset",
        "filesystem",
        "deepseek-harness"
    ]
}
```

因此：

```text
LLM
负责理解当前问题并产生多个语义候选关键词

Retriever
负责确定性匹配和排序
```

职责保持清晰。

---

# 15. Retrieval Layer 的未来演进

当前：

```text
KeywordRetriever
```

只是 `MemoryRetriever` 的一种实现。

未来所有升级不得改变：

```text
memory_record
memory_search
memory_get
```

三个 model-facing tools 的核心语义。

---

# 16. V2：BM25

当 Memory 数量增大后，可以增加：

```text
BM25Retriever
```

BM25 可以使用：

```text
title
keywords
```

作为搜索 Document。

必要时再加入：

```text
Lesson
Problem
```

等正文内容。

流程：

```text
query keywords / query text
          │
          ▼
        BM25
          │
          ▼
Top-K candidate memories
```

此阶段解决：

```text
exact keyword match recall 较低
```

的问题。

---

# 17. V3：Vector Retrieval

进一步可以增加：

```text
VectorRetriever
```

每条 Memory 生成 embedding：

```text
embedding(
    title
    + keywords
    + selected body
)
```

当前任务转换成 query embedding：

```text
query
   ↓
embedding
   ↓
vector similarity
   ↓
Top-K Memory
```

主要解决：

```text
用户和过去 Memory 使用不同表达方式
但语义上高度相关
```

的问题。

---

# 18. V4：Hybrid Retrieval

最终可以同时运行：

```text
Keyword
BM25
Vector
```

例如：

```text
                     Query
                       │
         ┌─────────────┼──────────────┐
         ▼             ▼              ▼
     Keyword          BM25          Vector
         │             │              │
         └─────────────┼──────────────┘
                       ▼
                Candidate Merge
                       │
                       ▼
                    Rerank
                       │
                       ▼
                Top-K Memories
```

例如使用：

```text
final_score =
    keyword_score
    + bm25_score
    + vector_score
```

或者以后增加专门的：

```text
RRF
reranker
LLM relevance judge
```

这些都属于 Retrieval Layer 内部实现。

Memory Store 不需要因此改变。

---

# 19. Retrieval 配置

未来可以支持：

```ts
type RetrievalMode =
    | "keyword"
    | "bm25"
    | "vector"
    | "hybrid"
```

例如：

```ts
memory: {
    retrieval: {
        provider: "keyword"
    }
}
```

以后：

```ts
memory: {
    retrieval: {
        provider: "hybrid"
    }
}
```

Model-facing tools 完全不变。

---

# 20. Model Retrieval Flow

System Prompt 应指导模型：

当过去经验可能有帮助时：

```text
1. 根据当前问题识别多个具体关键词；
2. 使用 memory_search 搜索候选 Memory；
3. 根据 title / keywords / outcome 判断相关性；
4. 只对真正相关的候选调用 memory_get；
5. 将过去 Memory 作为历史经验，而不是绝对正确事实。
```

推荐检索关键词覆盖：

```text
technology
system
symptom
environment
component
```

例如：

```text
用户：
DeepSeek Harness 这里为什么写完文件中文全乱码了？
```

模型可以搜索：

```text
deepseek-harness
filesystem
encoding
windows
javascript
typescript
chinese-text
```

---

# 21. Model Recording Flow

当任务产生以下内容时，可以考虑调用 `memory_record`：

```text
非显而易见问题的成功诊断

某种方法被证明不可行

环境特定问题及解决方式

某个 Harness / Framework 的隐藏约束

未来很可能再次遇到的问题

具有明确成功或失败结果的技术尝试
```

不应该因为：

```text
普通工具调用失败

一次偶发 typo

简单语法错误

没有形成任何可迁移经验
```

就创建 Memory。

Memory 的目标是：

> 减少未来重复推理和重复犯错。

而不是：

> 保存所有执行历史。

---

# 22. Success 与 Failure 都属于有效 Memory

系统不能只记录成功经验。

失败经验同样具有 few-shot 价值。

例如：

```text
Attempt:
使用 PowerShell 默认文本读写命令重新生成文件。

Outcome:
failure

Lesson:
该方式可能改变原始文件编码，因此不应该用于当前环境中的源码重写。
```

未来模型找到该 Memory 后，可以直接排除已经验证失败的路径。

因此：

```text
success
failure
mixed
```

都属于正常 Experience。

---

# 23. 不自动把 Memory 当成真理

Memory 表示：

> 在某个过去任务上下文中的经验。

而不是：

> 当前世界绝对正确的知识。

因此模型读取 Memory 时应理解：

```text
过去：
方法 A 成功

当前：
环境可能已经变化
```

Memory 是：

```text
few-shot
hint
past evidence
```

而不是：

```text
hard constraint
```

---

# 24. Scope

V1 可以继续保持当前插件的 Global Memory 模式。

当前实现中 Memory 文件位于 Harness-owned persistence，并由进程中的 Session 共享。

未来建议支持：

```text
global
workspace
```

### Global

存放：

```text
通用 Coding Experience
Harness 使用经验
工具行为
跨项目经验
```

### Workspace

存放：

```text
repo-specific architecture
项目特殊约束
项目历史问题
项目特定 workaround
```

Scope 应属于 Memory Store / Retrieval 的过滤条件，而不是新的 Memory 类型。

---

# 25. 不需要 Temporary Memory

旧设计中：

```text
memory_record
→ temp_memory.md
→ 后续分类
→ memory.md
```

临时层的主要作用是等待模型把经验组织进正式 Tree。当前规划也明确将 `temp_memory.md` 中的经验读取后再插入正式记忆树。

新设计取消 Tree 后，不再存在“尚未分类”的必要状态。

因此：

```text
memory_record
→ human confirmation
→ memory-N
```

即可。

如果用户拒绝：

```text
不写入
```

如果用户修改：

```text
按照修改后的 Experience 写入
```

这能够直接删除：

```text
temp_memory_list
temp_memory_get
promotion
temp → formal mapping
两文件 transaction
```

等复杂逻辑。

---

# 26. Internal Architecture

建议内部至少分为四层：

```text
src/
└── memory/
    ├── store/
    │   └── memory_store.ts
    │
    ├── retrieval/
    │   ├── retriever.ts
    │   └── keyword_retriever.ts
    │
    ├── service/
    │   └── memory_service.ts
    │
    └── tools/
        ├── memory_record.ts
        ├── memory_search.ts
        └── memory_get.ts
```

逻辑依赖：

```text
Tools
  │
  ▼
MemoryService
  │
  ├───────────────┐
  ▼               ▼
MemoryStore    MemoryRetriever
                   │
                   ▼
             KeywordRetriever
```

未来增加：

```text
bm25_retriever.ts
vector_retriever.ts
hybrid_retriever.ts
```

不会影响：

```text
MemoryStore
MemoryService public API
Model-facing tools
```

---

# 27. MemoryService

MemoryService 负责统一业务语义：

```text
interface MemoryService {
    record(
        entries: NewExperienceMemory[]
    ): Promise<ExperienceMemory[]>

    search(
        query: MemorySearchQuery
    ): Promise<MemorySearchResult[]>

    get(
        id: string
    ): Promise<ExperienceMemory | null>
}
```

其中：

```text
record → MemoryStore
get    → MemoryStore

search
    → MemoryStore 获取 SearchDocument
    → MemoryRetriever
    → MemoryStore 补充结果展示信息
```

---

# 28. Retriever 不负责读取完整 Memory

Retrieval Layer 最好只操作轻量 Search Document：

```text
{
    id,
    title,
    keywords
}
```

而不是：

```text
每次 memory_search
→ 读取所有完整 body
```

这样以后 Memory Body 很大时不会把检索成本和正文大小绑死。

V1 数据量很小时可以先直接解析整个 Markdown 文件实现。

接口上仍然保持：

```text
SearchDocument
```

抽象。

后续优化时可以增加独立索引，而无需改 Tool。

---

# 29. Future Index

V1：

```text
memory.md
```

本身即可作为 Source of Truth。

以后为了检索性能，可以生成：

```text
memory_index.json
```

例如：

```json
{
    "memory-17": {
        "title": "DeepSeek Harness 中文文件编码异常",
        "keywords": [
            "deepseek-harness",
            "encoding",
            "windows"
        ]
    }
}
```

甚至进一步生成：

```text
bm25.index
vector.index
```

这些全部属于：

> Derived Index

而不是：

> Source of Truth

因此索引损坏时始终可以通过 `memory.md` 重建。

---

# 30. Consistency Principle

必须保持：

```text
Memory Store = Source of Truth

Retrieval Index = Derived Data
```

因此：

```text
删除 index
→ 可以重新生成

删除 memory.md
→ Memory 丢失
```

未来无论加入 BM25 还是 Vector，都必须坚持这个原则。

---

# 31. V1 明确不做

初版不实现：

```text
Tree
Graph

Memory category

Topic management

Memory move

Memory merge

Memory delete

Memory decay

Importance score

Automatic deduplication

Automatic session mining

BM25

Embedding

Vector database

Reranker

Automatic contradiction resolution

Memory versioning
```

这些能力只有在真实使用中出现明确需求后再增加。

---

# 32. V1 完整能力

最终 V1 只有：

```text
Memory Capture
    memory_record

Memory Retrieval
    memory_search

Memory Loading
    memory_get

Persistence
    memory.md

Retrieval Algorithm
    Keyword Exact Match
```

形成最小完整闭环：

```text
               ┌──────────────┐
               │ Current Task │
               └───────┬──────┘
                       │
                derive keywords
                       │
                       ▼
               ┌──────────────┐
               │memory_search │
               └───────┬──────┘
                       │
                 candidate IDs
                       │
                       ▼
               ┌──────────────┐
               │  memory_get  │
               └───────┬──────┘
                       │
                 past few-shot
                       │
                       ▼
                     Task
                       │
                reusable lesson
                       │
                       ▼
               ┌──────────────┐
               │memory_record │
               └───────┬──────┘
                       │
                       ▼
                    memory-N
```

---

# 33. 后续演进路线

整个系统建议按照以下顺序演进。

## V1 — Keyword Experience Memory

```text
append-only Memory
keyword exact match
memory_record
memory_search
memory_get
```

目标：

> 验证 Experience Memory 对真实 Harness Coding Task 是否有帮助。

---

## V2 — BM25 Retrieval

增加：

```text
BM25
title / keyword / selected body indexing
```

目标：

> 提高词法检索 Recall，降低对 Keyword 完全一致的依赖。

---

## V3 — Semantic Retrieval

增加：

```text
embedding
vector index
semantic similarity
```

目标：

> 找到使用不同表述但语义相似的历史经验。

---

## V4 — Hybrid Retrieval

增加：

```text
Keyword
+
BM25
+
Vector
+
Candidate Fusion / Rerank
```

目标：

> 在规模较大的长期 Memory 中兼顾精确匹配和语义召回。

---

# 34. 最终设计定位

本系统不是 Session Search。

Session Search 解决：

```text
过去发生过什么？
```

Experience Memory 解决：

```text
过去发生的事情中，有什么值得我在当前任务中直接复用？
```

本系统也不是通用知识库。

它保存的核心对象是：

> **Experience**

每条 Experience 都是一份过去任务留下的：

```text
Context
Problem
Attempts
Outcome
Resolution
Lesson
```

未来作为模型 few-shot 被重新使用。

因此整个设计可以概括为：

> **An append-only experience memory layer for DeepSeek Harness that distills reusable successes and failures from tasks, retrieves candidate experiences through a pluggable retrieval layer, and progressively loads only the memories relevant to the current task.**

V1 使用最简单的：

> **LLM-generated keywords + deterministic keyword matching**

完成闭环。

未来 BM25、Vector Search 和 Hybrid Retrieval 都只是：

> **Retrieval Layer 的实现升级**

而不改变 Memory 本身以及 Agent 使用 Memory 的基本方式。



# 后续补充（涉及到前面方案修改）：
Q：有一个问题 score重要性要弱化 否则模型可能完全选score高的 这个本身没问题 但score设定本身也是模型设定的 他不是一个很严谨的score生成 因此相信一个不是那么严谨的score本身不靠谱 除此之外没问题了

A：对，这个点我赞同，而且我觉得应该**直接上升成 Retrieval Layer 的设计原则**。

更准确地说，V1 的 `score` 虽然不是模型直接填的，而是：

```text
score = matched keyword count
```

但它依赖的 `keywords` 本身是模型生成的，所以这个分数本质上只是：

> **由启发式特征计算出来的 retrieval signal，而不是相关性的可靠度量。**

所以不能让模型形成这种错误认知：

```text
score = 5
一定比
score = 3
更值得相信
```

## 我建议直接把 `score` 从 model-facing result 里删掉

内部 Retriever 当然可以继续：

```text
score = matched keyword count
```

用于：

```text
排序
Top-K 截断
```

但不要暴露给模型。

`memory_search` 返回：

```text
[memory-17]
title: DeepSeek Harness 中文文件编码异常
keywords: deepseek-harness, javascript, encoding, windows
matched: deepseek-harness, javascript, encoding
outcome: success

[memory-8]
title: PowerShell 修改 TypeScript 文件导致编码变化
keywords: powershell, typescript, encoding, windows
matched: encoding
outcome: failure
```

而不是：

```text
memory-17 score=3
memory-8 score=1
```

这样模型看到的是**为什么它被召回**，而不是一个看起来很精确、实际上并不精确的数字。

这其实更符合 LLM 使用习惯：

```text
retriever
负责：
候选召回 + 粗排序

model
负责：
结合当前上下文判断候选是否真正相关
```

---

而且这个原则对未来 BM25 / Vector 更重要。

因为以后会出现：

```text
BM25 score = 7.83
cosine similarity = 0.81
keyword match = 4
```

这些数字**根本不是同一种语义**。

如果全展示给 Agent，它反而很容易产生虚假的：

> `0.89 > 0.81，所以第一条明显更可靠`

但 vector similarity 根本不代表“经验可靠度”，甚至不严格等于“任务相关度”。

所以整个系统最好明确：

> **Retrieval scores are internal ranking signals, not memory confidence or relevance guarantees.**

Model-facing 层尽量提供：

```text
interface MemorySearchCandidate {
    id: string
    title: string
    keywords: string[]
    matchedKeywords?: string[]
    outcome?: MemoryOutcome
}
```

而内部可以是：

```text
interface InternalRetrievalResult {
    id: string
    rankingScore: number
    signals: ...
}
```

两者分开。

---

### 最终流程就很合理

```text
query
  ↓
Retriever
  ↓
计算内部 ranking score
  ↓
排序 / Top-K
  ↓
隐藏 score
  ↓
返回候选的可解释信息
  ↓
Model 自己判断
  ↓
memory_get
```

System Prompt 再明确一句：

> Search results are retrieval candidates only. Their order does not guarantee relevance or correctness. Judge relevance from the current task, title, keywords, matched keywords, and memory content.

我觉得这个改动甚至让整个设计更漂亮了：

**Retriever 可以越来越复杂，但永远只是“帮模型缩小搜索空间”，而不是替模型做最终相关性判断。**

所以设计文档里原本所有 `score` 的 model-facing 描述都可以改成：

* **内部可以有 ranking score；**
* **外部不承诺 score 的语义；**
* **V1 返回 `matchedKeywords` 作为可解释召回依据；**
* **未来 BM25/Vector 的数值同样默认不暴露给模型。**

这个我认为应该定下来。
