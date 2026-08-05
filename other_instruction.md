# 非生产级 Harness 剩余核心规范

## 1. 当前已经具备的部分

现有 Harness 已经包含四项规范。

### Prompt 规范

负责规定：

```text
提示词存在哪里
提示词如何调用
动态参数如何注入
消息如何分层
提示词内容如何编写
```

每个逻辑提示词对应一个 Prompt Builder 函数，Prompt Builder 只接收当前提示词真正需要的数据。

### Tool 规范

负责规定：

```text
工具如何定义
Schema 如何生成
输入如何校验
工具如何注册
工具如何执行
输出如何校验
```

每个工具只有一个唯一的 `@tool` 函数，Agent Loop 只通过统一 Registry 获取 Schema 和执行工具。

### Skill 规范

负责规定：

```text
某类任务什么时候使用
该类任务应该按照什么流程执行
什么时候读取 references
什么时候运行 scripts
什么时候使用 assets
怎样验证任务完成
```

Skill 只描述任务方法，不负责真正驱动执行；需要新增模型能力时，由扩展包中的 MCP Server 提供工具。

### Trace 规范

负责规定：

```text
实际发送了什么 messages
模型返回了什么原始内容
解析结果是什么
调用了什么工具
工具返回了什么
耗时和 Token 是多少
哪里发生了错误
```

Trace 只如实记录执行过程，不负责发起模型请求、执行工具或控制 Agent。

---

# 2. 仍然缺少的三项核心规范

```text
1. LLM 基础设施规范
2. Context 调度规范
3. Agent Runtime 规范
```

这三项补齐以后，单 Agent Harness 的核心规范就是完整的。

---

# 3. LLM 基础设施规范

## 3.1 负责什么

LLM 基础设施负责把不同模型的调用差异统一成一个稳定接口。

它至少需要统一：

```text
模型请求
普通文本输出
Tool Call 输出
结构化输出
流式输出
模型错误
Token 用量
调用耗时
原始响应
```

否则 OpenAI、Anthropic、DeepSeek、本地模型等不同协议会直接渗透到 Runtime、Agent 和业务代码中。

## 3.2 最小接口

```python
class LLMClient:
    async def generate(
        self,
        request: ModelRequest,
    ) -> ModelResult:
        ...

    async def stream(
        self,
        request: ModelRequest,
    ) -> AsyncIterator[StreamEvent]:
        ...
```

## 3.3 ModelRequest

至少包含：

```python
class ModelRequest:
    model: str
    messages: list[Message]
    tools: list[dict]
    output_type: type | None
```

其中：

* `model`：逻辑模型名或真实模型名；
* `messages`：Context 调度后实际发送的消息；
* `tools`：本轮允许模型看到的 Tool Schema；
* `output_type`：需要结构化输出时使用的目标类型。

## 3.4 ModelResult

应直接复用 Trace 规范中的统一结果概念：

```python
class ModelResult:
    raw_content: object

    parsed_content: object | None
    parse_error: str | None

    model: str | None

    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None

    duration_ms: float | None
    finish_reason: str | None
```

职责关系：

```text
LLM 基础设施
负责产生 ModelResult。

Trace
负责保存 ModelResult。

Runtime
负责根据 ModelResult 决定下一步。
```

禁止分别为 LLM、Trace 和 Runtime 定义三套不同的模型结果结构。

## 3.5 输出方式

LLM 基础设施至少支持三种输出：

```text
1. 直接文本输出
2. Pydantic 结构化输出
3. Tool Calls
```

结构化输出失败时必须保留：

```text
raw_content
parse_error
```

不能只返回解析错误而丢弃模型原始输出。

## 3.6 错误处理

非生产级 Harness 只需要简单处理：

```text
Timeout
网络错误
模型接口错误
结构化解析错误
上下文超长
```

允许进行少量固定重试，但不需要：

```text
复杂负载均衡
多租户
预算控制
分布式限流
智能模型路由
```

---

# 4. Context 调度规范

## 4.1 负责什么

Context 调度负责决定：

> 本轮模型调用实际看到什么。

Prompt Builder 只负责生成基础 Prompt，不负责自动加入所有历史消息、Skill、工具结果和长期记忆。

Trace 记录的则是 Context 调度完成后，真正发送给模型的最终 `messages`。

职责关系：

```text
Prompt Builder
生成基础 Developer / User Messages。

Context 调度
组合基础 Prompt、Skill、历史消息和工具结果。

LLMClient
发送最终 messages。

Trace
记录最终 messages。
```

## 4.2 Context 来源

Context 可以来自：

```text
当前 Prompt
当前激活的 Skill
最近的 Assistant 消息
最近的 Tool Call 和 Tool Result
当前任务状态
必要的项目事实
按需检索的 Memory
```

并不是每次都必须包含全部来源。

## 4.3 默认顺序

推荐顺序：

```text
Developer Message
    ↓
激活 Skill 的必要内容
    ↓
任务和动态上下文
    ↓
保留的历史消息
    ↓
最近的工具调用和结果
```

Skill 内容可以被组装进 Developer Context，但不能覆盖 Prompt 中更高层的固定规则。

## 4.4 最小调度规则

Context 调度至少需要满足：

```text
始终保留当前任务
始终保留当前有效规则
保留最近且仍然相关的交互
Tool Call 和对应 Tool Result 必须成对保留
优先删除过时、重复和无关信息
超长 Tool Result 可以截断或摘要
不得把整个 Runtime State 无脑序列化进 Prompt
```

## 4.5 最小接口

```python
class ContextBuilder:
    def build(
        self,
        prompt: Prompt,
        state: AgentState,
        skill_content: str | None,
    ) -> list[Message]:
        ...
```

返回值就是本次真正发送给模型的完整 `messages`。

## 4.6 Memory 的位置

Memory 不是完整 Harness 的强制模块。

需要跨任务记忆时，可以由：

```text
Memory Tool
+
Context 调度
```

实现：

```text
Runtime 或 Agent 调用 Memory Tool 检索
    ↓
Context 调度选择相关结果
    ↓
注入本轮 messages
```

没有跨任务记忆需求时，可以完全不实现 Memory。

---

# 5. Agent Runtime 规范

## 5.1 负责什么

Runtime 负责把现有所有模块串成完整执行闭环：

```text
创建任务状态
    ↓
调用 Prompt Builder
    ↓
选择并加载 Skill
    ↓
构造 Context
    ↓
调用 LLM
    ↓
解析模型结果
    ↓
执行 Tool Call
    ↓
追加 Tool Result
    ↓
再次调用模型
    ↓
判断是否完成
    ↓
返回最终结果
```

Runtime 是 Harness 真正的执行核心。

## 5.2 Runtime State

Runtime 只需要维护最小状态：

```python
class AgentState:
    task: str
    messages: list[Message]

    turn_count: int
    status: Literal[
        "running",
        "completed",
        "failed",
    ]

    final_result: object | None
    error: str | None
```

State 只保存 Runtime 当前运行所需的信息。

State 与 Trace 的区别：

```text
State
表示现在运行到哪里，可以修改。

Trace
表示之前发生过什么，只追加记录。
```

不需要为非生产级 Harness 建设复杂 Session 数据库。

## 5.3 最小循环

```python
async def run_agent(
    task: str,
) -> AgentResult:
    state = AgentState(
        task=task,
        messages=[],
        turn_count=0,
        status="running",
        final_result=None,
        error=None,
    )

    while state.turn_count < MAX_TURNS:
        prompt = build_prompt(...)
        skill = select_skill(...)
        messages = context_builder.build(
            prompt=prompt,
            state=state,
            skill_content=skill,
        )

        result = await llm.generate(
            ModelRequest(
                model=MODEL,
                messages=messages,
                tools=available_tools(),
                output_type=None,
            )
        )

        trace.record_model_result(
            messages=messages,
            result=result,
        )

        state.turn_count += 1

        if result contains tool calls:
            execute tools
            append tool results
            continue

        if result.parse_error:
            append parse error
            continue

        if completion conditions are satisfied:
            state.status = "completed"
            state.final_result = result.parsed_content
            break

    return AgentResult(...)
```

具体代码可以不同，但执行链必须完整。

## 5.4 Tool Call 处理

Runtime 只负责：

```text
读取模型返回的工具名和参数
调用统一 ToolRegistry 或 MCP Client
获得统一 Tool Result
把 Tool Result 加入消息历史
继续下一轮模型调用
```

Runtime 不允许：

```text
自己解析每个工具参数
自己维护工具调用映射
根据工具名写 if/else
直接调用具体工具函数
```

这些都已经由 Tool 规范处理。

## 5.5 Skill 处理

Runtime 负责：

```text
根据任务选择 Skill
加载被选中的 SKILL.md
将 Skill 内容交给 Context 调度
```

Runtime 不负责解释 Skill 中每个自然语言步骤。

Skill 中的步骤主要用于指导模型。

但 Skill 中的 `Validation` 必须由 Runtime 执行闭环保证：

```text
模型声明完成
    ↓
检查 Skill Validation 是否已经获得证据
    ├── 满足：允许完成
    └── 不满足：继续执行或返回失败
```

Runtime 不需要理解所有 Validation 的业务语义。

验证可以通过：

```text
已有 Tool
MCP Tool
Skill Script
结构化输出校验
```

完成。

## 5.6 终止条件

Runtime 必须明确以下终止条件：

```text
模型返回最终结果并满足验证条件
达到最大轮数
模型调用连续失败
发生无法恢复的 Tool 错误
输出结构多次无法校验
```

禁止只依赖模型输出：

```text
“任务已经完成”
```

来结束任务。

## 5.7 错误处理

非生产级 Runtime 只需要固定规则：

```text
Tool 输入错误
    → 将校验错误作为 Tool Result 返回模型。

Tool 执行错误
    → 将原始错误返回模型，由模型决定是否修复。

结构化输出错误
    → 将 parse_error 返回模型重新生成。

模型临时错误
    → 固定重试少量次数。

超过最大轮数
    → 返回 failed，并保留当前 Trace。
```

不需要复杂恢复编排。

## 5.8 最终结果

Runtime 只需要返回：

```python
class AgentResult:
    status: Literal[
        "completed",
        "failed",
    ]

    content: object | None
    error: str | None
    session_id: str
```

生成文件已经由 Tool 写入 Workspace，不需要额外建设 Artifact 系统。

---

# 6. 不需要单独建设的模块

## Environment / Workspace

对于本地 Harness，可以直接由：

```text
read_file
write_file
run_command
```

等 Tool 实现。

只有未来需要在本地、Docker 和远程环境之间切换时，才单独抽象 Environment。

## Validation

验证方法写在 Skill 中，通过 Tool、MCP Tool 或 Script 执行；Runtime 只负责在验证未通过时禁止结束任务。

因此不需要单独建设 Validator 平台。

## Task

单 Agent Harness 中，Task 可以只是一段任务文本和少量参数，不需要复杂 Task 系统。

## Agent 定义

Agent 可以只是一个普通配置对象：

```python
class Agent:
    name: str
    model: str
    prompt_builder: Callable
```

Tool 和 Skill 可以由 Runtime 根据当前任务提供，不需要独立 Agent Registry。

## Artifact

文本结果由 Runtime 返回，文件结果由 Tool 生成，不需要额外 Artifact 层。

## Memory

只有需要跨任务保存信息时才增加，不是最小 Harness 的必需部分。

## Orchestrator

只有多 Agent 才需要。

单 Agent Harness 不应为了未来可能存在的多 Agent，提前建设任务图、消息队列或调度平台。

---

# 7. 多 Agent Harness 的可选补充

当 Harness 确实需要多个 Agent 协作时，再增加一份：

```text
Multi-Agent Orchestrator 规范
```

它只需要解决：

```text
任务如何拆分
子任务交给哪个 Agent
Agent 之间传递什么结果
依赖任务按照什么顺序执行
失败结果如何返回上游
最终结果如何汇总
```

Orchestrator 仍然复用同一套：

```text
Prompt
Tool
Skill
Trace
LLMClient
ContextBuilder
Runtime
```

每个 Agent 不应该重新实现自己的 Runtime、Tool Registry 和 LLM 调用层。

---

# 8. 完整 Harness 结构

```text
Harness
├── Prompt
│   └── 定义模型的固定职责和当前任务表达
│
├── Skill
│   └── 定义某类任务的执行方法和验证条件
│
├── Context
│   └── 决定本轮模型实际看到什么
│
├── LLM
│   └── 统一模型请求与模型结果
│
├── Tool
│   └── 提供模型可调用的真实能力
│
├── Runtime
│   └── 驱动模型调用、工具执行和终止判断
│
└── Trace
    └── 记录整个执行过程
```

完整执行链：

```text
用户任务
    ↓
Runtime 创建 State
    ↓
Prompt Builder 生成基础 Prompt
    ↓
Skill Selector 选择 Skill
    ↓
Context Builder 组装最终 messages
    ↓
LLMClient 调用模型
    ↓
ModelResult
    ├── Tool Call
    │       ↓
    │   ToolRegistry / MCP Client
    │       ↓
    │   Tool Result
    │       ↓
    │   回到 Context Builder
    │
    └── Final Output
            ↓
        检查 Validation
            ├── 未通过：继续运行
            └── 通过：返回结果
```

Trace 贯穿整个执行链，但不参与控制。

---

# 9. 最终需要维护的规范

一个完整的非生产级单 Agent Harness，只需要七份规范：

```text
1. Prompt 规范
2. Tool 规范
3. Skill 规范
4. Trace 规范
5. LLM 基础设施规范
6. Context 调度规范
7. Agent Runtime 规范
```

其中：

```text
Prompt
规定怎么向模型表达任务。

Skill
规定某类任务应该怎么做。

Tool
规定模型能做什么。

Context
规定模型本轮能看到什么。

LLM 基础设施
规定如何稳定调用模型。

Runtime
规定整个任务如何运行和结束。

Trace
规定如何还原实际执行过程。
```

这七项补齐后，已经可以构成完整的非生产级 Harness；Memory、多 Agent、Environment 抽象、任务平台和 Artifact 系统都应在出现真实需求后再增加，而不是作为 Harness 的强制组成部分。
