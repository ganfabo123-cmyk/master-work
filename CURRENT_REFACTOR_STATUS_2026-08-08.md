# CodeHarness 重构现状记录

更新时间：2026-08-08

## 1. 本轮重构目标

本轮开始将 CodeHarness 从传统的：

```text
Prompt + Agent + Tool + Orchestrator
```

逐步调整为：

```text
State → Observation → Policy → Action → Environment → State
```

这里的“强化学习模式”只指运行时架构，不包含训练、奖励函数或策略优化。

核心运行语义是：

1. 任务拥有唯一的 `task_id` 和当前 `session_id`；
2. Agent 根据 Observation 产生 Policy 决策；
3. 决策最终形成 Action；
4. Environment 校验并执行 Action；
5. State 被改变；
6. Environment 产生下一次 Observation。

## 2. 当前已建立的核心目录

### `src/codeharness/core/`

当前用于放平台核心实现和基类。

#### `base_state.py`

定义 `BaseState`，目前包含：

- `task_id`
- `session_id`
- 抽象 `initial(task_id, session_id)`
- 抽象 `is_terminal`
- 抽象 `process(action)`

`BaseState` 已调整为 dataclass，便于具体 State 继承并持有任务身份。

#### `base_observation.py`

定义：

- `BaseObservation`
- `SystemSignal`

`BaseObservation` 当前包含：

- `observation_id`
- `task_id`
- `session_id`
- `user_prompt(text)`：基类直接实现，返回单条 user `Message`
- `tool_result(tool_calls)`：暂时为 `pass`
- `system_signal(**kwargs)`：抽象方法，返回 `SystemSignal`

三种输入格式的当前定义：

```text
文本 → User Message
Tool Calls 协议 → Tool Result
动态 kwargs → System Signal
```

#### `base_environment.py`

定义 `BaseEnvironment`，目前包含：

- `agents` 序列
- 具体 `state`
- 具体 `observation`
- 抽象 `orchestrate_agents()`
- 抽象 `execute_action(action)`

当前没有：

- `policy` 字段
- `action` 字段
- `register_tools()`

当前职责约定是：Agent 负责工具注册和 Tool Call 解析，Environment 负责执行 Action 和改变 State。

#### `base_tool.py`

定义 `BaseAgentTools`，目前只负责：

- 保存 `agent_name`
- 提供 `tool_functions()` 接口

它不负责 Registry，也不负责 Action 执行。

#### `tool_registry.py`

由原来的 `tools/registry.py` 迁移而来，包含：

- `ToolError`
- `CompiledTool`
- `ToolRegistry`
- 全局 `registry`
- `tool` 装饰器

当前 `ToolRegistry` 仍然负责函数注册、Schema 生成、参数校验和函数调用。后续 Agent 可以继续使用它完成工具注册和解析，但实际改变 State 的动作执行应交给 Environment。

#### `memory.py` 和 `room.py`

原来的 Memory、Room 具体实现已迁移到 `core`，作为可直接实例化的核心实现。

## 3. Agent 基础层

### `src/codeharness/base_agent/`

当前结构：

```text
base_agent/
  __init__.py
  llm_agent.py
```

### `core/base_agent.py`

定义最小 `BaseAgent`，包含：

- `name`
- `model`
- `policy`
- `action`
- 抽象 `run()`

### `base_agent/llm_agent.py`

定义 `LLMAgent`，直接继承 `core.base_agent.BaseAgent`。

它承载原来 `agents/base.py` 中的通用 LLM Agent 运行逻辑，包括：

- LLM 调用；
- Prompt/Message 历史处理；
- Tool Call 解析；
- Tool Schema 生成；
- Tool Result Message 追加；
- Trace 记录；
- 最大 LLM 回合数控制。

当前这部分仍保留旧的 LLM Tool Loop，尚未完全改成“Agent 产生 Action、Environment 执行 Action”的新链路。

## 4. 具体 Agent

`src/codeharness/agents/` 不再放通用 `base.py`，目前只保留具体 Agent 文件：

- `customer_service.py`
- `release_incident.py`
- `release_incident_collaboration.py`
- `werewolf.py`

这些具体 Agent 已开始继承 `base_agent.LLMAgent`。

本轮最后重点调整的是 `agents/werewolf.py`，它现在使用：

- `base_agent.LLMAgent`
- `core.room.Room`
- `policy.werewolf.prompt.WerewolfPromptBuilder`
- `policy.werewolf.tool.WerewolfPlayerTools`
- `state.werewolf.WerewolfGameState`

## 5. Policy、Action、Observation 当前目录

### Policy

```text
src/codeharness/policy/
  customer_service/
  release_incident/
  release_incident_collaboration/
  werewolf/
```

每个 Agent 目录下已经放置具体 Prompt 和 Tool 文件。

当前理解：

- Policy 属于 Agent；
- Prompt 是 LLM Policy 的输入构造部分；
- Tool 是 Agent 侧产生 Tool Call/Action 的适配入口。

### Action

```text
src/codeharness/action/werewolf/tools.py
```

当前定义 `WerewolfActionTools`，包含 7 个游戏提交动作：

- `wolf_kill`
- `inspect`
- `save`
- `poison`
- `vote`
- `shoot`
- `skip_shot`

这些工具目前会构造 Werewolf Action 消息并发送到 `game-engine` ROOM。后续需要继续把“构造 Action”和“Environment 执行 Action”拆开。

### Observation

```text
src/codeharness/observation/
  werewolf.py
```

`WerewolfObservation` 当前只实现 `system_signal(**kwargs)`，把动态参数包装成 `SystemSignal`。

现有 Werewolf 的阶段公告、死亡、投票和胜负文本，目前仍是 User Message，不是 System Signal。

## 6. Werewolf State 当前迁移结果

新增：

```text
src/codeharness/state/werewolf.py
```

`WerewolfGameState` 已继承 `BaseState`，并包含：

- `task_id`
- `session_id`
- `initial()`
- `is_terminal`
- `process(action)`

`process(action)` 当前只是对既有 `werewolf_rules.resolve_phase()` 的兼容适配，仍保留原来的批量 Action 结算语义。

旧文件 `src/codeharness/util/werewolf_state.py` 已删除，但调用方导入尚未全部迁移。

## 7. 当前已知的中间态问题

本轮明确接受重构中间状态暂时不可运行，以下问题尚未处理：

1. 旧的 `orchestrator`、Werewolf workflow、Action rules 等模块仍有旧 State/Room/Tool 导入；
2. Policy 下的 Prompt/Tool 文件仍有部分旧相对导入；
3. `LLMAgent` 仍然直接注册和执行 Tool，尚未把 Action 执行交给 Environment；
4. `BaseEnvironment.execute_action()` 只有抽象接口，没有具体 Environment 实现；
5. `BaseObservation.tool_result()` 仍为 `pass`；
6. `StateStore` 仍绑定旧的 State 协议，尚未切换到 `BaseState`；
7. `WerewolfGameState.process()` 与当前规则引擎的批量结算语义仍需进一步设计；
8. `tools/` 目录尚未完全删除，当前仅将 Registry 迁移到了 `core/tool_registry.py`，并保留了兼容导出；
9. Policy、Action、Environment 尚未形成完整的运行闭环；
10. 当前未进行完整测试。

## 8. 明天建议的继续顺序

建议按以下顺序继续，避免一次同时改动多个层次：

1. 先确定 `LLMAgent` 是否停止直接执行 Tool；
2. 将 Tool Call 解析结果明确转换为 Action；
3. 设计 Werewolf 具体 Action 数据结构；
4. 在 Werewolf Environment 中实现 `execute_action()`；
5. 让 Environment 根据 State 执行 Action 并返回结果；
6. 完成 `BaseObservation.tool_result()`；
7. 将 Tool Result 重新送回 LLM Policy；
8. 再迁移 Werewolf workflow 的 State/Action/Observation 导入；
9. 最后处理 StateStore、Orchestrator 和其他 Agent；
10. 全部架构迁移结束后统一测试。

## 9. 本次验证和提交边界

本轮没有运行测试，也没有尝试让中间状态恢复可运行。

提交时应只包含本轮架构重构文件，包括：

- `core` 新增基础层；
- `base_agent` 新增 Agent 基础层；
- `policy`、`action`、`observation`、`state` 的迁移文件；
- Werewolf Agent 的路径调整；
- Registry 的核心层迁移；
- 本现状记录文件。

以下内容不应混入本次提交：

- `logs/`；
- `memory/` 数据；
- `room/` 运行数据；
- `tests/tool_context_benchmark_results/`；
- 工作区中原本已经存在的文档、State、Workflow 和测试修改，除非明确属于本轮重构。
