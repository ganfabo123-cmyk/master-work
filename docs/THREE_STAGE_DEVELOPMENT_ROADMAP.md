# CodeHarness 三阶段开发路线

## 1. 文档目的

本文用于约束 CodeHarness 后续三个阶段的开发边界，避免为了未来需求过早引入复杂抽象，也避免当前实现反过来阻碍下一阶段演进。

三阶段分别解决三个不同问题：

```text
第一阶段：多 Agent 如何在明确回合中协作
第二阶段：协作流程如何被事件打断、暂停、嵌套并恢复
第三阶段：不同类型模型如何在实时环境中按时间预算持续决策
```

每一阶段都应先用真实 App 验证抽象，再决定哪些能力进入 Core 或 Infra。业务角色、规则、状态字段和具体动作始终留在 `apps/<app_name>`。

---

# 2. 第一阶段：同步多 Agent RL 循环

## 2.1 阶段目标

建立一个面向 LLM Agent 的、同步推进的多 Agent 应用运行框架。

标准过程为：

```text
State
→ select_agents()
→ observe()
→ Agent / Policy
→ Action
→ ready_to_step()
→ resolve_actions()
→ Environment.step()
→ build_events()
→ New State
→ New Observation
```

本阶段解决的是：多个 Agent 在一个具有明确阶段、有限动作和确定性规则的环境中如何协作。

## 2.2 适用需求

第一阶段适用于以下特征的应用：

- 行动者可以根据 State 明确选出；
- Action 类型有限且可以结构化描述；
- Agent 行动以轮次或阶段为单位；
- 同一阶段可以有一个或多个 Agent 行动；
- 收集完本阶段动作后，Environment 可以一次完成状态转移；
- 状态转移不需要等待外部系统；
- 规则结果原则上是确定性的；
- 可以在阶段或回合边界保存和恢复。

代表场景：

- 简化狼人杀；
- 多专家会诊；
- Planner → Worker → Reviewer；
- 多人投票与评审；
- 简单辩论与裁判；
- 固定流程的内容生产流水线。

## 2.3 核心职责

### State

- 保存环境的完整事实；
- 创建初始状态；
- 判断是否终止；
- 不直接执行 Action。

### Observation

- 从完整 State 中裁剪 Agent 可见信息；
- 隔离公开信息和私有信息；
- 合并当前阶段事件和动作反馈。

### Agent / Policy

- Agent 只根据 Observation 决策；
- Policy 组织 Prompt、策略工具和模型参数；
- Agent 不直接修改 State。

### ActionManager

- 把模型响应转换为结构化 Action；
- 返回动态可用 Action；
- 校验 Action；
- 对多个 Action 进行排序、覆盖、过滤或聚合。

### Environment

- 持有 State；
- 选择当前行动者；
- 生成 Observation；
- 判断是否可以推进；
- 执行状态转移；
- 根据状态变化生成反馈事件。

### Infra

- LLM Client 和 Runtime；
- Tool Registry；
- ROOM 通信；
- 增量 Context；
- Session、StateStore 和 Trace；
- Agent 注册及通用 ROOM 回合运行。

Infra 不包含任何狼人、投票、角色、回合或其他 App 领域语义。

## 2.4 实现方式

第一阶段采用同步主循环：

```python
while not state.is_terminal:
    agents = environment.select_agents(state)
    actions = []

    for agent in agents:
        observation = environment.observe(state, agent)
        action = environment.act(agent, observation)
        if action is not None:
            actions.append(action)

    if environment.ready_to_step(state, actions):
        resolved_actions = action_manager.resolve_actions(state, actions)
        old_state = state
        state = environment.step(state, resolved_actions)
        events = environment.build_events(old_state, resolved_actions, state)
```

业务 App 实现这些接口，主循环不出现业务角色、阶段或动作名称。

## 2.5 第一阶段不解决

- Action 执行中途插入其他 Agent 响应；
- 动作栈、技能栈和嵌套子流程；
- 等待 Human、CI 或其他外部系统；
- 长时间暂停后从动作中间恢复；
- 无限开放的自然语言 Action；
- 实时帧循环和毫秒级决策；
- 非 LLM 模型协议。

## 2.6 验收标准

至少实现两个差异明显的 App：

```text
狼人杀 + 多专家会诊
```

要求：

1. 两个 App 使用相同 Core 和 Infra；
2. 第二个 App 只新增 `apps/<app_name>`及自身配置；
3. Core 和 Infra 修改 0 行；
4. 两个 App 都使用同一个标准多 Agent 循环；
5. Agent 只能读取自己的 Observation；
6. Action 必须经过解析、校验和 Environment 状态转移；
7. State、ROOM 和 Trace 能在阶段边界恢复；
8. Core 和 Infra 中不存在任一 App 的业务名词。

---

# 3. 第二阶段：事件驱动、暂停、嵌套与恢复

## 3.1 阶段目标

在第一阶段的同步循环基础上，支持不能在一次 `step()`中立即完成的协作过程。

标准过程扩展为：

```text
State / Event
→ 选择参与者
→ Action
→ 创建 Pending Operation
→ 触发新 Event 或 Response Window
→ 暂停原流程
→ 执行子流程或等待外部结果
→ 恢复原流程
→ 完成状态转移
```

本阶段解决的是：流程如何被打断、等待、嵌套、恢复，并且仍然保持可追踪和可重放。

## 3.2 适用需求

- 三国杀式出牌响应、技能插入和连锁结算；
- Human 审批或 Human Participant；
- 外部服务调用后等待结果；
- CI、测试或任务执行完成后继续；
- 动态加入新的行动者；
- 超时、取消和重试；
- 一个 Action 触发多个后续 Event；
- 在流程执行中间 kill process 并恢复。

代表场景：

- 三国杀；
- 人机混合审批；
- 带异步执行的多 Agent 软件开发；
- 应急响应；
- 复杂谈判；
- 需要暂停和恢复的任务工作流。

## 3.3 第一阶段为什么不足

第一阶段假设：

```text
收集 Action → step() → New State
```

第二阶段实际可能是：

```text
Action A
→ 暂停 A
→ 等待 Action B
→ B 触发 Action C
→ 完成 C
→ 恢复 B
→ 恢复 A
→ New State
```

如果把这段逻辑隐藏在业务 `step()`内部，Core 无法观察其中的暂停点、等待对象、重试、Trace 和恢复状态，应用只能自行实现另一套运行时。

## 3.4 需要新增的通用概念

以下是第二阶段的候选通用能力，只有经过真实 App 验证后才能进入 Core：

### Event

不可变的运行事实，用于驱动下一步调度。

```text
event_id
event_type
source
payload
visibility
created_at
```

### Pending Operation

表示尚未完成的 Action、外部调用或 Human 请求。

```text
operation_id
parent_operation_id
status
waiting_for
resume_point
```

### Response Window

描述哪些 Participant 可以在什么条件和期限内响应当前事件。

### Operation Stack / Workflow Stack

保存父流程与子流程的嵌套关系，使子流程结束后能够恢复原动作。

### Participant

统一表示 LLM Agent、非 LLM Agent、Human 或外部执行器。第二阶段可以先验证 Human，完整模型无关能力留到第三阶段。

### Idempotent Resume

恢复时必须知道：

- 哪些事件已经产生；
- 哪些动作已经执行；
- 哪些副作用已经提交；
- 哪些参与者仍需响应。

重复恢复不得重复产生业务副作用。

## 3.5 实现方式

运行方式从单纯同步循环演进为事件调度：

```python
while not runtime.is_finished:
    event = runtime.next_event()
    participants = workflow.select_participants(state, event)
    operation = workflow.handle_event(state, event, participants)

    if operation.is_waiting:
        runtime.persist(operation)
        continue

    state, events = workflow.commit(operation)
    runtime.publish(events)
```

第一阶段的 `observe()`、`act()`、`resolve_actions()`和`step()`仍可作为一种最简单的 Operation 使用，不应被推翻。

## 3.6 第二阶段不解决

- 高频实时游戏帧循环；
- 毫秒级 Action deadline；
- GPU 推理批处理；
- 非 LLM Tensor Observation；
- 连续动作空间；
- 实时物理环境同步；
- 大规模 Actor 并行采样。

## 3.7 验收标准

至少选择一个会打断第一阶段原子 `step()`假设的 App：

```text
三国杀响应链
或
Human + CI 审批工作流
```

要求：

1. Action 可以进入等待状态；
2. 等待期间可以持久化并退出进程；
3. 恢复后继续原 Operation；
4. 子流程完成后能返回父流程；
5. 重试不会重复产生副作用；
6. Trace 能还原 Event、Operation 和状态变化；
7. 第一阶段 App 不需要重写即可继续运行。

---

# 4. 第三阶段：模型无关的实时多 Agent 环境

## 4.1 阶段目标

将 CodeHarness 从以 LLM 为默认决策模型的协作运行框架，扩展为兼容非 LLM 模型、可驱动需要实时反应的电子游戏的运行系统。

第三阶段解决两个紧密相关的问题：

1. Agent 不再假设使用 Prompt、Message、Tool Call 和文本 Observation；
2. Environment 不再只在逻辑回合中推进，而需要按照固定 Tick 或实时事件持续更新。

标准过程变为：

```text
Real-time Environment Tick
→ State Snapshot
→ Per-Agent Observation
→ Model Adapter Inference
→ Action with Deadline
→ Validate / Arbitrate
→ Simulation Step
→ Next Tick
```

## 4.2 适用需求

- 电子游戏 NPC 协作与对抗；
- RTS、MOBA、FPS 或动作游戏中的实时决策；
- 多机器人或仿真环境；
- 强化学习 Policy 网络；
- 规则模型、行为树和有限状态机；
- LLM 与非 LLM Agent 混合；
- 高频 Observation、低延迟 Action；
- 连续动作或高维离散动作；
- 模型批处理和独立推理服务。

## 4.3 第三阶段与前两阶段的根本差异

### 模型输入输出不同

LLM 使用：

```text
Message / Prompt / Tool Call / Raw Content
```

非 LLM 模型可能使用：

```text
Tensor / Feature Vector / Image / Audio / Game Snapshot
→ Discrete Action / Continuous Action / Action Distribution
```

因此 `Agent.act()`不能继续假设 Observation 是消息，也不能假设 Action 来自工具名。

### 时间语义不同

前两阶段通常是：

```text
Agent 完成后 Environment 再继续
```

实时游戏必须是：

```text
Environment 按 Tick 持续运行
Agent 必须在 Deadline 前返回 Action
超时则使用默认动作、上一动作或降级策略
```

### 状态更新频率不同

实时 State 可能每秒更新几十次或几百次，不能每 Tick 都执行完整 JSON 持久化、ROOM 投递和 LLM Trace。

### 并发模型不同

多个 Agent 可能同时推理；Environment、推理服务、渲染和网络输入可能位于不同线程、进程或机器。

## 4.4 需要形成的模型无关接口

第三阶段需要把当前 LLM Agent 能力放到适配器后面，而不是删除 LLM 支持。

候选接口：

```python
class ModelAdapter:
    def infer(self, observation, *, deadline) -> ModelOutput:
        ...

class ObservationEncoder:
    def encode(self, state_snapshot, participant) -> ModelInput:
        ...

class ActionDecoder:
    def decode(self, model_output) -> Action:
        ...
```

适配器示例：

```text
LLMModelAdapter
PolicyNetworkAdapter
BehaviorTreeAdapter
HumanInputAdapter
RemoteInferenceAdapter
```

当前 Prompt、Tool Registry 和 LLMRuntime 应成为 `LLMModelAdapter`内部能力，而不是所有 Agent 的强制依赖。

## 4.5 实时运行方式

实时主循环应由稳定时钟驱动：

```python
while game.is_running:
    tick = clock.next_tick()
    snapshot = environment.snapshot(tick)
    participants = environment.active_participants(snapshot)

    observations = observation_encoder.encode_batch(snapshot, participants)
    actions = inference_scheduler.infer_batch(observations, deadline=tick.deadline)
    accepted_actions = action_arbiter.resolve(snapshot, actions)

    environment.step(tick.delta_time, accepted_actions)
```

关键要求：

- Environment Tick 不等待单个慢 Agent；
- 每个 Action 带 Tick、时间戳或序列号；
- 过期 Action 不得作用于新 State；
- 多 Agent Action 需要确定性仲裁；
- 推理超时必须有明确降级策略；
- Observation 应基于一致的 State Snapshot；
- Trace 分为高频指标和低频可重放关键事件。

## 4.6 第三阶段需要新增的基础能力

### Clock / Tick

- 固定或可变时间步；
- Tick ID；
- Deadline；
- Delta time；
- 暂停、加速和回放。

### Snapshot

- 在一个 Tick 内为所有 Agent 提供一致 State；
- 支持局部 Observation；
- 避免 Agent 读取正在变化的可变 State。

### Inference Scheduler

- 并行推理；
- 批处理；
- 优先级；
- 超时和取消；
- 本地与远程模型统一调度。

### Action Arbiter

- Action deadline 校验；
- 顺序和冲突处理；
- 过期动作丢弃；
- 缺失动作降级；
- 连续动作裁剪；
- 保证同一输入可确定性重放。

### Backpressure

当模型处理速度低于游戏 Tick 时：

- 不无限堆积 Observation；
- 可以覆盖过期 Observation；
- 限制在途推理；
- 记录丢帧和超时指标。

### 分层 Trace

```text
高频：延迟、超时、Tick、Action 接收情况
关键事件：状态变化、模型版本、随机种子、仲裁结果
低频：可读诊断和会话摘要
```

## 4.7 第三阶段实现顺序

建议按以下顺序推进：

1. 定义模型无关的 Observation、ModelOutput 和 Runtime Action；
2. 将现有 LLMRuntime 包装为 `LLMModelAdapter`；
3. 实现一个简单非 LLM Adapter，例如规则策略或小型 Policy Network；
4. 增加 Clock、Tick 和 State Snapshot；
5. 增加 Deadline、超时和默认 Action；
6. 增加并行 Inference Scheduler；
7. 增加 Action Arbiter 和过期动作处理；
8. 使用一个低复杂度实时电子游戏验证；
9. 最后再扩大 Agent 数量、Tick 频率和模型复杂度。

首个实时验证 App 不应直接选择完整 FPS 或 MOBA。建议选择：

```text
实时二维躲避/追逐
或
简化多人资源争夺游戏
```

它们足以验证 Snapshot、Deadline、并发推理、动作仲裁和回放。

## 4.8 验收标准

1. 同一 Environment 可以混合 LLM Agent、规则 Agent 和非 LLM Policy Agent；
2. Core 不依赖 Prompt、Message 或 Tool Call 才能完成基本决策循环；
3. Environment 按固定 Tick 推进，不等待慢 Agent；
4. 超时、缺失和过期 Action 有确定行为；
5. 所有 Agent 在同一 Tick 读取一致 Snapshot；
6. 实时指标可以量化推理延迟、Action 延迟和丢弃情况；
7. 给定相同初始 State、随机种子和 Action 记录可以重放；
8. 第一、第二阶段 App 通过兼容适配器继续运行；
9. 实时 App 不要求 Core 出现具体游戏角色、地图或战斗规则。

---

# 5. 三阶段对比

| 维度 | 第一阶段 | 第二阶段 | 第三阶段 |
|---|---|---|---|
| 核心问题 | 明确回合中的多 Agent 协作 | 中断、等待、嵌套与恢复 | 模型无关的实时决策 |
| 驱动方式 | 同步阶段循环 | Event / Operation | Clock / Tick |
| Action | 有限、结构化 | 可暂停、可嵌套 | 带时间约束、可连续 |
| State 转移 | 一次 `step()`完成 | Pending 后提交 | 每 Tick 持续更新 |
| Agent | 默认 LLM | LLM + Human/外部执行器 | LLM + Policy Network + 规则模型 |
| Observation | Message 为主 | Message + Event | Tensor/Image/Feature/Snapshot |
| 等待 | 同步等待 Agent | 持久化等待并恢复 | 不阻塞 Tick，超时降级 |
| 恢复粒度 | 阶段/回合边界 | Operation 中间 | Tick、关键帧和 Action Replay |
| 代表场景 | 狼人杀、会诊 | 三国杀、审批、CI | 实时电子游戏、机器人仿真 |

---

# 6. 演进原则

## 6.1 后一阶段扩展前一阶段，不推翻前一阶段

- 第一阶段循环是第二阶段的一种无等待 Operation；
- 第二阶段 Event 可以成为第三阶段低频控制事件；
- 第三阶段 ModelAdapter 包装现有 LLMRuntime，而不是删除 LLM 能力。

## 6.2 不提前实现下一阶段

第一阶段不要提前加入动作栈、异步调度和实时 Tick。第二阶段不要提前把所有 Observation 改成 Tensor，也不要为未知模型设计庞大的通用协议。

只有当前阶段验收 App 证明现有接口不足时，才把新能力加入 Core。

## 6.3 Core、Infra 与 App 边界

```text
Core：稳定协议、运行语义和必要类型
Infra：存储、通信、模型适配、调度、Trace 等实现能力
Apps：角色、规则、状态字段、动作含义、流程和终止条件
```

无论发展到哪个阶段，Core 和 Infra 都不能出现具体游戏或业务场景的名词与条件分支。

## 6.4 每阶段都必须有异构 App 验证

只用一个 App 无法证明抽象通用。每阶段至少使用两个差异明显的场景，并要求第二个场景在不修改 Core/Infra 的情况下接入。

## 6.5 可观察、可恢复、可重放

三个阶段对性能和恢复粒度的要求不同，但必须始终能够回答：

- Agent 实际看到了什么 Observation；
- 使用了哪个 Policy 或模型版本；
- 产生了什么 Action；
- Action 是否被接受、拒绝、超时或覆盖；
- State 为什么发生变化；
- 系统从哪里恢复并继续。

这组证据是 CodeHarness 从演示程序发展为可靠运行系统的共同基础。
