# CodeHarness 当前现状（2026-08-05）

> 分支：`feature/release-incident-harness`  
> 最近提交：`188d21c refactor: remove output schema completion flow`  
> 本文记录的是当前工作区代码的真实状态，用于下一次继续开发时快速恢复上下文。

## 1. 当前目标与架构判断

CodeHarness 目前是一个“通用 Agent Harness 模板”的早期实现。它已经具备单 Agent 的完整模型—工具循环，并刚开始具备多 Agent 协作所需的基础通信设施。

长期方向是可演化的多 Agent Coding 框架或更通用的 Agent 协作框架；但当前不预建该方向的全部能力。当前的最小边界是：

```text
开发者定义 Agent / Prompt / Tools
                │
                ▼
       Orchestrator 显式调度一轮 Agent.run()
                │
                ├── 单 Agent：Trace session + LLM/工具循环
                │
                └── ROOM：成员注册、消息投递、持久化收件箱
```

`Orchestrator` 是调度器，不承担模型调用与工具执行；`Agent.run()` 才是一个 Agent 的执行入口。工具执行仍由 Agent 自己管理的 `ToolRegistry` 完成。

## 2. 已经实现的单 Agent 基础能力

### 2.1 Agent 定义

文件：`src/codeharness/agents/base.py`

`Agent` 是不可变 dataclass，维护：

- `name`、`model`、`llm`
- `prompt_builder`
- 此 Agent 允许使用的 `tools`
- 候选 `skills`
- `tool_registry`

新增业务 Agent 的基本形式是新增一个 Agent 类，在类中声明自己的 Prompt Builder、工具名单和 Skill 候选。当前已有：

- `CustomerServiceAgent`
- `ReleaseIncidentAgent`

### 2.2 Prompt

目录：`src/codeharness/prompts/`

`BasePromptBuilder` 只保留一个职责：接收已经由子类构造好的系统提示词与用户提示词，返回 `Prompt`。子类自行决定构造参数、模板结构和领域特有字段，不调用任何固定的“任务 Prompt 拼装”流程。

这意味着 Prompt 的扩展点在具体 Builder，而不是基类。

### 2.3 LLM 与工具循环

文件：`src/codeharness/agents/base.py`、`src/codeharness/llm.py`

调用流程：

1. `Agent.run()` 以显式传入的 `messages/tools/model/llm_kwargs` 为优先；未传时使用 Agent 自己的属性。
2. 模型回复普通文本时，返回最终 `assistant` Message。
3. 模型请求工具时，Agent 校验工具是否在本 Agent 的允许名单中，执行工具，将 assistant tool-call Message 与 tool-result Message 追加到历史后继续调用模型。
4. 超出 `max_turns` 仍未产生普通 assistant 回复时失败。

`OpenAICompatibleClient` 使用 OpenAI 兼容 Chat Completions 格式，并在请求体中关闭 DeepSeek 思考过程：`"thinking": {"type": "disabled"}`。

### 2.4 Tool 规范

文件：`src/codeharness/tools.py`

工具以 `@tool` 注册，schema 从函数签名与 `Annotated[..., Field(description=...)]` 自动推导。模块开头已经写有工具设计规范：参数需要清晰描述，工具必须可校验且可 JSON 序列化，工具不能携带 Prompt、路由或最终回答逻辑。

当前示例工具包括：

- `inspect_task`：本地确定性示例。
- `search_customer_knowledge`：客服 Markdown 知识库检索。
- `search_release_runbooks`：发布事故 Runbook 检索。

### 2.5 Trace 与会话恢复

文件：`src/codeharness/trace.py`

每个 Agent 运行会在 `traces/session_.../` 下留下：

- `session.json`：任务、状态、参与 Agent、总 token、时长、恢复次数。
- `{agent}.jsonl`：按增量追加的事实消息流。
- `{agent}.md`：同一事实流的可读投影。

Trace 记录 developer/system、user、assistant、tool、error；assistant 事件包含模型、token、延迟、停止原因。最终工具调用与工具结果会分别落入 trace，不再依赖一次次写完整历史，因此消息存储是线性增长。

`TraceRecorder.resume_session()` 能恢复指定单 Agent 的完整 Message 历史并重新累计 token/时长。CLI 的 `/resume` 复用该能力。

## 3. 交互式 CLI

文件：`src/codeharness/cli.py`；入口：`CodeHarness`

当前 CLI 是单 Agent 的终端交互入口：

```powershell
CodeHarness
CodeHarness /resume session_YYYYMMDD_HHMMSS_xxxxxx
```

它会自动发现 `codeharness.agents` 下的 Agent 类；有多个 Agent 时由用户在启动时选择一个。每轮用户输入被追加到同一 Agent 的消息历史，最终 Trace 写入 `traces/`。

CLI 目前不支持创建/恢复 ROOM，也不支持多 Agent 会话。这是尚未接入的上层交互能力，不是 ROOM 基础设施缺失。

## 4. ROOM：已实现的多 Agent 协作基础设施

目录：`src/codeharness/room/`

ROOM 是多 Agent 可共享信息的平台模型。当前只允许 Agent 成员；人类成员入口明确尚未实现。

### 4.1 数据模型与协议

文件：`room/models.py`

`AgentProfile` 的注册字段：

- `name`
- `introduction`
- `skill`
- `role`
- `kwargs`：开发者自定义扩展字段

`RoomMessage` 的协议字段：

- `name`：发送者
- `at`：接收 Agent 名称，或 `all`
- `txt`、`image`、`audio`：至少一个必须有内容
- `message_id`、`created_at`

### 4.2 成员与消息投递

文件：`room/base.py`

`Room` 已支持：

- `register(profile)`：持久化 Profile，但不自动邀请。
- `invite(name)` / `leave(name)`：维护当前参与者和收件箱。
- `send(message)`：校验发送者是成员；`at="all"` 投递给所有当前成员，定向消息只投递给目标成员。
- `receive(name)`：返回并清空该 Agent 的未读消息。
- `history()`：读取完整消息历史。
- `close()`：关闭后拒绝注册、邀请和发消息，但仍可读取历史与恢复。

注意：目前广播包含发送者自身。这是当前明确的投递语义；若之后希望广播不回送自己，需要单独变更协议。

### 4.3 ROOM 持久化与事件

ROOM 数据默认位于 `room/data/`：

- `{session}_{agent_name}.json`：Agent 注册信息。
- `room_{session}.json`：ROOM 当前状态快照，包括成员、状态、全量消息与每个成员的未读收件箱。
- `room_{session}.events.jsonl`：ROOM 生命周期与消息事件。

已记录的事件包含：`room_created`、`room_resumed`、`agent_registered`、`agent_invited`、`agent_left`、`message_sent`、`messages_received`、`room_closed`。

`Room.resume(room_id, session_id=...)` 能恢复成员、全量历史和尚未领取的收件箱。

### 4.4 Orchestrator 对 ROOM 的支持

文件：`src/codeharness/orchestrator.py`

已提供：

- `register_agent(agent, profile)`：将运行时 Agent 与其 Profile 注册到调度器。
- `create_room(...)` / `resume_room(...)`：创建或恢复 ROOM。
- `invite_agents(room, names)`：将已注册 Agent 的 Profile 写入 ROOM 并邀请成员。
- `register_agent_factory(name, factory)`：注册由开发者掌控的 Agent 重建函数。
- `restore_room_agents(room)`：从 ROOM Profile 的 `kwargs["factory"]` 取得工厂名，调用开发者已注册的 factory 重建运行时 Agent。
- `run_room_turn(room, agent_name, task)`：显式安排一个 ROOM 成员运行一轮。

`run_room_turn` 会先领取该 Agent 的未读收件箱，并构造：

```python
Task(
    description,
    inputs={
        ...原始输入,
        "room": {
            "room_id": ...,
            "session_id": ...,
            "inbox": [...RoomMessage JSON...],
        },
    },
)
```

随后它正常调用 `Agent.run()`，并在该 Agent 的 Trace 中写入 `room_inbox` 事件。Prompt Builder 是否把 `Task.inputs["room"]` 呈现给模型，由该领域开发者决定。

## 5. 当前明确不做的边界

以下能力现在没有实现，且不应被误认为已隐式存在：

1. **会话级工具绑定**：没有按 ROOM/Session 自动把 `send_room_message`、`receive_room_message` 一类工具注入 Agent。
2. **Agent 自动发言**：`run_room_turn` 的最终回复只作为 `AgentResult` 返回，不会被框架自动包装并群发到 ROOM。
3. **自动唤醒与工作流策略**：收到消息不会自动运行目标 Agent；没有轮询、优先级、并发、终止判定或 DAG 调度。
4. **人类入口**：ROOM 协议预留了未来人类参与的方向，但没有 CLI/UI/API 人类成员。
5. **共享状态模型**：没有通用 State/Blackboard。ROOM 目前只负责协议化消息、Profile 与收件箱；文件、代码、状态等共享信息应由具体 Harness 通过显式工具和约定接入。
6. **Output Schema / submit 工具**：已从运行路径移除。Agent 以普通 assistant Message 结束，调度层不依赖强制提交工具或结构化最终输出。

这些边界是刻意保留给具体 Harness 的开发者决策，不应为“未来可能需要”提前耦合进基础模板。

## 6. 下一步建议的最小实现顺序

若明天继续做多 Agent Harness，建议先选择一个真实且有限的协作需求，再只实现其所需的上层能力：

1. **定义一个协作场景**：例如 Planner 向 Reviewer 发送“方案 + 待检查点”，Reviewer 反馈问题。
2. **为该场景设计显式 ROOM 工具或发布步骤**：决定 Agent 怎样发送消息、发给谁、何时结束。不要做全局自动注入。
3. **为两个 Agent 的 Prompt Builder 消费 `Task.inputs["room"]`**：明确告诉 Agent 收件箱数据的语义与处理规则。
4. **在一个场景专用 Orchestrator 工作流中显式调用两次 `run_room_turn`**：先 Planner，再 Reviewer；再决定是否需要第三轮。
5. **用真实模型跑完整 Trace**：观察模型是否正确理解 ROOM 输入与工具调用，而不是先抽象出通用调度算法。

当至少一个真实场景验证了“消息发布—接收—再次决策”的闭环后，再判断是否需要抽象出多 Agent 队列、调度策略、共享文件工具或更强的恢复能力。

## 7. 当前已知不一致与清理项

以下不是本次基础设施必须修复的内容，但明天开始前应注意：

- `README.md` 仍把项目描述为“刻意只实现单 Agent”，并把调度器称为 Runtime；该描述已经落后于 ROOM 基础设施，应在下一次整理文档时更新。
- `tests/test_demo.py` 引用了已不存在的 `runtime.AgentRuntime` 与 `models.AgentSpec`，是旧架构残留，当前 pytest 全量执行不会通过。
- 当前环境没有安装 `pytest`；本次 ROOM 新增的 `tests/test_room_infrastructure.py` 已通过直接断言脚本验证，并已通过 `py_compile`，但尚未通过正式 pytest runner。
- `tests/tool_context_benchmark_results/` 是历史实验输出，里面仍会出现旧的 submit/output-schema 痕迹；它不是当前源码行为，不应据此判断当前运行路径。
- 工作区还有未跟踪的历史文档、日志和测试产物；提交时只应选择本次目标文件，避免把这些内容混入提交。

## 8. 关键文件索引

| 目的 | 文件 |
| --- | --- |
| Agent 定义与 LLM/工具循环 | `src/codeharness/agents/base.py` |
| 领域 Agent | `src/codeharness/agents/customer_service.py`、`release_incident.py` |
| Prompt 基类与领域 Builder | `src/codeharness/prompts/` |
| 工具注册、schema 与规范 | `src/codeharness/tools.py` |
| LLM 协议与真实模型客户端 | `src/codeharness/llm.py` |
| 调度、ROOM 恢复与显式单轮调度 | `src/codeharness/orchestrator.py` |
| Trace 与单 Agent 会话恢复 | `src/codeharness/trace.py` |
| ROOM 协议、路由、持久化 | `src/codeharness/room/` |
| 交互 CLI | `src/codeharness/cli.py` |
| 本次 ROOM 基础设施验证 | `tests/test_room_infrastructure.py` |

