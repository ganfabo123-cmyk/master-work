# 狼人杀强化学习链路问题记录

## 标准过程

```text
State → Observation → Policy → Action → Environment → New State
      → New Observation → Policy → Next Action → Environment → ...
```

标准职责如下：

- `Environment` 持有 `State`，并根据 `State` 生成 `Observation`。
- `Policy` 根据 `Observation` 产生 `Action`。
- `Environment` 接收并执行 `Action`，产生 `New State`。
- `New State` 再生成 `New Observation`，循环直到环境终止。
- Agent 不直接读取完整 `State`，只读取属于自己的 `Observation`。

## 当前实现过程

```text
State
→ Environment 手工构造状态 Message
→ Agent 根据 Policy 调用 Tool
→ Action Tool 将动作 JSON 写入 ROOM
→ Environment 从 ROOM 读取消息
→ ActionManager 解析并校验 GameAction
→ resolve_phase() 直接修改 State
→ Environment 再次手工构造状态 Message
→ 下一轮 Agent
```

当前循环主要由 `WerewolfEnvironment.run()` 手工组织，而不是由统一的 `Observation → Action → Environment → New State` 接口连接。

## 与标准过程的差异

### 1. `State → Observation`

标准过程由 `Environment` 根据当前 `State` 生成完整的 Agent 专属 `Observation`。

当前实现只是调用 `WerewolfObservation.game_state_message()` 构造一条状态 Message，再由 `run_room_turn()` 额外拼入 Task、ROOM 消息和历史上下文。系统没有一个统一入口负责从 `State` 生成并投递完整 `Observation`。

### 2. `Observation → Policy → Action`

标准过程要求 `Policy` 接收 `Observation` 并产生可交给 `Environment` 的 `Action`。

当前 Agent 接收到的是状态 Message、Task、ROOM 消息和增量历史的混合结果。模型调用动作工具后，工具不直接返回结构化 `Action`，而是把动作编码为 JSON 并写入 ROOM。

### 3. `Action → Environment`

标准过程要求 Agent 产生的 `Action` 直接交给 `Environment`。

当前过程多了一层 ROOM 中转：`Action Tool → JSON → ROOM → Environment → ActionManager`。Agent 的普通模型输出也没有统一进入 `ActionManager.resolve_action()`，因此不存在完整的统一响应转动作入口。

### 4. `Environment → New State`

标准过程由 `Environment` 执行动作并产生 `New State`。

当前主循环没有调用 `WerewolfEnvironment.execute_action()`，而是直接调用 `resolve_phase()` 修改 `WerewolfGameState`。`WerewolfGameState.process()` 同样没有正确接入当前 `ActionManager` 和 `resolve_phase()` 接口。

### 5. `New State → New Observation`

标准过程在每次状态转移后，根据 `New State` 生成下一轮 `Observation`。

当前实现依靠 `run()` 进入下一次阶段循环后再次手工构造状态 Message。状态变化和 Observation 生成之间没有明确、统一的接口连接。

### 6. State 所有权和同步

标准过程中 `Environment` 是 `State` 的唯一持有者和更新者，其他对象通过当前 Observation 工作。

当前 Agent、Policy Tools 和 Action Tools 都保存了创建 Agent 时传入的 State 引用，同时 `WerewolfEnvironment` 和 `WerewolfSession` 也分别持有 State。虽然部分修改发生在同一个可变对象上，但系统没有定义统一的 State 所有权和更新同步机制。

## 后续重构目标

让 `WerewolfEnvironment` 成为循环和 State 的唯一管理者，并形成统一过程：

```text
State → Observation → Policy → Action → Environment → New State
      → New Observation → Policy → Next Action → Environment → ...
```
