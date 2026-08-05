# 本地 Agent 应用 Trace 记录规范

## 1. 目标

Trace 用于完整记录一次 Agent 任务的实际执行过程，使开发者能够查看：

* 每个 Agent 收到了什么输入
* 每次模型调用发送了哪些 messages
* 模型返回了什么原始内容
* 模型输出被解析成了什么
* 调用了哪些工具
* 工具参数和结果是什么
* 每一步耗时多少
* 每次模型调用消耗多少 Token
* 哪一步发生了解析错误或执行错误

Trace 不记录程序中的所有局部变量，只记录 Agent 执行过程中有意义的输入、输出和状态。

---

## 2. 核心结构

一次完整任务对应一个 `session_id`。

一次任务中，每个 Agent 使用唯一的 `agent_name`。

```text
session
├── agent_1
│   ├── system_prompt
│   ├── user_prompt
│   ├── model_response
│   ├── tool_call
│   └── tool_result
│
└── agent_2
    ├── system_prompt
    ├── user_prompt
    └── model_response
```

文件目录：

```text
traces/
└── {session_id}/
    ├── session.json
    ├── {agent_name}.jsonl
    └── {agent_name}.md
```

例如：

```text
traces/
└── session_20260804_001/
    ├── session.json
    ├── planner.jsonl
    ├── planner.md
    ├── coder.jsonl
    └── coder.md
```

其中：

* `session.json`：记录任务级信息
* `{agent_name}.jsonl`：原始结构化 Trace，作为事实源
* `{agent_name}.md`：根据 JSONL 渲染的可读文件

Markdown 不是事实源。需要重新渲染时，必须从 JSONL 生成。

---

## 3. Session 规范

```python
class TraceSession:
    session_id: str
    task: str

    start_time: str
    end_time: str | None
    duration_ms: float | None

    status: Literal[
        "running",
        "completed",
        "failed",
    ]

    agents: list[str]
    error: str | None
```

示例：

```json
{
  "session_id": "session_20260804_001",
  "task": "修复登录接口",
  "start_time": "2026-08-04T17:00:00.000+08:00",
  "end_time": "2026-08-04T17:00:08.420+08:00",
  "duration_ms": 8420,
  "status": "completed",
  "agents": [
    "planner",
    "coder"
  ],
  "error": null
}
```

---

## 4. Agent Event 规范

Agent 每发生一个有意义的动作，就生成一个 `AgentEvent`。

```python
class AgentEvent:
    session_id: str
    agent_name: str

    event_id: str
    sequence: int

    event_type: Literal[
        "system_prompt",
        "user_prompt",
        "assistant",
        "model_response",
        "tool_call",
        "tool_result",
        "parse_error",
        "error",
    ]

    timestamp: str
    duration_ms: float | None

    raw_content: object | None
    parsed_content: object | None

    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None

    error_type: str | None
    error_message: str | None
```

字段含义：

```text
session_id
当前事件属于哪次任务

agent_name
当前事件属于哪个 Agent

event_id
当前事件唯一标识

sequence
当前 Agent 内的事件顺序，从 1 开始

event_type
当前事件类型

timestamp
事件发生时间

duration_ms
当前操作耗时

raw_content
未经修改的原始输入或输出

parsed_content
对 raw_content 解析后的结构化结果

model
本次模型调用使用的模型

input_tokens
模型输入 Token 数

output_tokens
模型输出 Token 数

total_tokens
总 Token 数

error_type
错误类型

error_message
完整错误信息
```

---
## 5. 模型调用结果规范

每次模型调用完成后，调用方必须向 Trace 系统提交一个统一的 `ModelResult`。

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

字段说明：

```text
raw_content
模型返回的原始内容，必须完整保留

parsed_content
调用方对原始内容解析后得到的结构化结果

parse_error
原始内容解析失败时产生的错误信息

model
本次调用实际使用的模型名称

input_tokens
本次调用的输入 Token 数

output_tokens
本次调用的输出 Token 数

total_tokens
本次调用的总 Token 数

duration_ms
本次模型调用耗时

finish_reason
模型结束生成的原因
```

Trace 系统只负责接收、保存和渲染这些数据。

以下内容均由调用方自行实现：

```text
模型请求
耗时计算
Token 获取
原始响应提取
内容解析
错误捕获
模型字段适配
```

Trace 规范不限制调用方使用的模型 SDK、Agent 框架、响应格式或数据获取方式。

核心要求：

```text
调用方向 Trace 系统提交什么，Trace 系统就如实记录什么。
```

---

## 6. 模型响应记录规则

每次模型响应至少应提交：

```text
raw_content
parsed_content
parse_error
model
input_tokens
output_tokens
total_tokens
duration_ms
finish_reason
实际发送给模型的 messages
```

其中：

```text
raw_content 是事实源
parsed_content 是调用方的解析结果
parse_error 是解析失败信息
```

程序不得只提交 `parsed_content` 而丢弃 `raw_content`。

当解析失败时，仍然必须记录：

```text
raw_content
parse_error
model
Token 数据
duration_ms
finish_reason
messages
```

---

## 7. Content 类型规范

模型返回内容统一解析成 `ContentBlock`。

```python
ContentBlock = (
    TextContent
    | ToolCallContent
)
```

### 7.1 普通文本

```python
class TextContent:
    type: Literal["text"]
    text: str
```

### 7.2 工具调用

```python
class ToolCallContent:
    type: Literal["tool_call"]

    tool_call_id: str
    tool_name: str
    arguments: dict
```

一个模型回复可以包含多个 Content Block：

```python
class ParsedModelContent:
    blocks: list[ContentBlock]
```

例如：

```json
{
  "blocks": [
    {
      "type": "text",
      "text": "我需要先读取配置文件。"
    },
    {
      "type": "tool_call",
      "tool_call_id": "call_001",
      "tool_name": "read_file",
      "arguments": {
        "path": "config.py"
      }
    }
  ]
}
```

---

## 8. Event 类型说明

### 8.1 system_prompt

记录 Agent 实际使用的系统提示词。

```json
{
  "event_type": "system_prompt",
  "raw_content": "你是一个代码开发 Agent。",
  "parsed_content": null
}
```

### 8.2 user_prompt

记录当前 Agent 收到的用户输入或上游任务。

```json
{
  "event_type": "user_prompt",
  "raw_content": "修复登录接口。",
  "parsed_content": null
}
```

### 8.3 model_response

记录一次完整模型响应。

```json
{
  "event_type": "model_response",
  "raw_content": "{\"name\":\"read_file\",\"arguments\":{\"path\":\"auth.py\"}}",
  "parsed_content": {
    "blocks": [
      {
        "type": "tool_call",
        "tool_call_id": "call_001",
        "tool_name": "read_file",
        "arguments": {
          "path": "auth.py"
        }
      }
    ]
  },
  "model": "qwen3-32b",
  "input_tokens": 1240,
  "output_tokens": 42,
  "total_tokens": 1282,
  "duration_ms": 823
}
```

### 8.4 assistant

模型返回普通文本时生成。

```json
{
  "event_type": "assistant",
  "raw_content": "登录失败来自 Token 判断条件错误。",
  "parsed_content": {
    "text": "登录失败来自 Token 判断条件错误。"
  }
}
```

### 8.5 tool_call

模型请求调用工具时生成。

```json
{
  "event_type": "tool_call",
  "raw_content": {
    "id": "call_001",
    "name": "read_file",
    "arguments": {
      "path": "auth.py"
    }
  },
  "parsed_content": {
    "tool_call_id": "call_001",
    "tool_name": "read_file",
    "arguments": {
      "path": "auth.py"
    }
  }
}
```

### 8.6 tool_result

工具执行完成后生成。

```json
{
  "event_type": "tool_result",
  "raw_content": {
    "tool_call_id": "call_001",
    "result": "def login(...): ..."
  },
  "parsed_content": {
    "tool_call_id": "call_001",
    "tool_name": "read_file",
    "success": true,
    "result": "def login(...): ..."
  },
  "duration_ms": 3
}
```

### 8.7 parse_error

模型输出无法解析时生成。

```json
{
  "event_type": "parse_error",
  "raw_content": "{\"name\":\"read_file\",\"arguments\":{\"path\":\"auth.py\"}",
  "parsed_content": null,
  "error_type": "JSONDecodeError",
  "error_message": "Expecting ',' delimiter"
}
```

### 8.8 error

模型调用、工具执行或 Agent 执行发生异常时生成。

```json
{
  "event_type": "error",
  "raw_content": null,
  "parsed_content": null,
  "error_type": "FileNotFoundError",
  "error_message": "auth.py does not exist"
}
```

---

## 9. Messages 记录规范

每次模型调用都必须记录实际发送给模型的完整 `messages`。

```python
class ModelCallInput:
    messages: list[dict]
```

例如：

```json
{
  "messages": [
    {
      "role": "system",
      "content": "你是代码开发 Agent。"
    },
    {
      "role": "user",
      "content": "修复登录接口。"
    },
    {
      "role": "assistant",
      "content": "我需要读取 auth.py。"
    },
    {
      "role": "tool",
      "tool_call_id": "call_001",
      "content": "def login(...): ..."
    }
  ]
}
```

必须记录的是：

```text
实际发送给模型的 messages
```

而不是根据历史事件重新推测 messages。

---

## 10. JSONL 写入规范

每个 `AgentEvent` 单独占一行。

```jsonl
{"sequence":1,"event_type":"system_prompt","raw_content":"你是代码 Agent"}
{"sequence":2,"event_type":"user_prompt","raw_content":"修复登录接口"}
{"sequence":3,"event_type":"model_response","raw_content":"...","duration_ms":823}
{"sequence":4,"event_type":"tool_call","raw_content":{"name":"read_file"}}
{"sequence":5,"event_type":"tool_result","raw_content":"...","duration_ms":3}
```

事件产生后立即追加：

```python
def append_event(event: AgentEvent) -> None:
    path = (
        TRACE_ROOT
        / event.session_id
        / f"{event.agent_name}.jsonl"
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            event.model_dump_json()
            + "\n"
        )
```

不得等任务结束后统一写入，否则程序异常退出时会丢失 Trace。

---

## 11. Markdown 渲染规范

Markdown 按事件顺序追加。

文件头：

```markdown
# Session: session_20260804_001

# Agent: coder
```

### System Prompt

```markdown
## 1. System Prompt

你是一个代码开发 Agent。
```

### User Prompt

```markdown
## 2. User Prompt

修复登录接口。
```

### 模型普通回复

```markdown
## 3. Assistant

登录失败来自 Token 判断条件错误。

- Model: `qwen3-32b`
- Time: `641 ms`
- Input tokens: `2380`
- Output tokens: `76`
- Total tokens: `2456`
```

### Tool Call

````markdown
## 4. Tool Call

- ID: `call_001`
- Tool: `read_file`

```json
{
  "path": "src/auth.py"
}
````

* Model: `qwen3-32b`
* Time: `823 ms`
* Input tokens: `1240`
* Output tokens: `42`
* Total tokens: `1282`

````

### Tool Result

```markdown
## 5. Tool Result

- ID: `call_001`
- Tool: `read_file`
- Success: `true`

```text
def login(...):
    ...
````

* Time: `3 ms`

````

### Parse Error

```markdown
## 6. Parse Error

### Raw Content

```text
{"name":"read_file","arguments":{"path":"src/auth.py"}
````

### Error

```text
JSONDecodeError: Expecting ',' delimiter
```

* Model: `qwen3-32b`
* Time: `823 ms`
* Input tokens: `1240`
* Output tokens: `42`
* Total tokens: `1282`

````

---

## 12. 渲染规则

根据 `event_type` 选择对应渲染器。

```python
RENDERERS = {
    "system_prompt": render_system_prompt,
    "user_prompt": render_user_prompt,
    "assistant": render_assistant,
    "model_response": render_model_response,
    "tool_call": render_tool_call,
    "tool_result": render_tool_result,
    "parse_error": render_parse_error,
    "error": render_error,
}
````

统一入口：

```python
def render_event(event: AgentEvent) -> str:
    renderer = RENDERERS[event.event_type]
    return renderer(event)
```

写入流程：

```text
生成 AgentEvent
→ 追加到 JSONL
→ 根据 event_type 渲染 Markdown
→ 追加到对应 Agent 的 Markdown 文件
```

---

## 13. 必须遵守的规则

### 规则一：Raw Content 优先

任何模型返回必须先记录 `raw_content`，再进行解析。

### 规则二：解析失败不能覆盖原始数据

解析失败时必须同时保存：

```text
raw_content
parse_error
model
tokens
duration_ms
```

### 规则三：JSONL 是事实源

Markdown 仅用于阅读，不得作为后续统计和分析的数据源。

### 规则四：每次调用记录实际 Messages

必须保存真正发送给模型的完整 Messages。

### 规则五：事件立即写入

每个事件生成后立即追加到文件，避免任务异常退出导致记录丢失。

### 规则六：工具调用和工具结果分开记录

模型请求调用工具时记录 `tool_call`。

工具真正执行完成后记录 `tool_result`。

### 规则七：模型耗时和工具耗时分开

模型耗时记录在模型调用事件中。

工具耗时记录在工具结果事件中。

### 规则八：Token 只记录模型调用

工具调用本身没有 Token，不得把工具执行耗时或结果长度伪装成 Token。

---

## 14. 最终执行流程

```text
创建 session_id
→ 创建 Agent
→ 写入 system_prompt
→ 写入 user_prompt
→ 调用模型
→ 保存完整 messages
→ 保存 raw_content、tokens、耗时
→ 尝试解析模型输出
    ├── 普通文本 → assistant
    ├── 工具调用 → tool_call
    └── 解析失败 → parse_error
→ 执行工具
→ 写入 tool_result
→ 将工具结果加入下一次 messages
→ 再次调用模型
→ 任务结束
→ 更新 session.json
```

---

## 15. 最小实现模型

```python
class TraceRecorder:
    def create_session(
        self,
        task: str,
    ) -> str:
        ...

    def record(
        self,
        event: AgentEvent,
    ) -> None:
        ...

    def record_model_result(
        self,
        session_id: str,
        agent_name: str,
        messages: list[dict],
        result: ModelResult,
    ) -> None:
        ...

    def finish_session(
        self,
        session_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        ...
```

业务代码只调用：

```python
recorder.record(...)
```

文件写入、事件排序、JSONL 序列化和 Markdown 渲染全部由 `TraceRecorder` 统一处理。
