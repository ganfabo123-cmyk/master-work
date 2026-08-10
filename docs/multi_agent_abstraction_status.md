# 多 Agent / RL 抽象状态记录

## 1. 当前标准过程

当前 Core 希望固定的运行过程是：

```text
State
→ select_agents()
→ observe()
→ Agent.act() / Policy
→ ActionManager.resolve_action()
→ ready_to_step()
→ ActionManager.resolve_actions()
→ Environment.step()
→ build_events()
→ New State / New Observation
```

其中：

- `State` 保存环境的完整事实；
- `Observation` 是指定 Agent 能看到的 State 投影；
- `Agent` 根据 Policy 和 Observation 产生响应；
- `ActionManager` 把响应转换、校验并整理为环境动作；
- `Environment` 选择行动者、推进状态并组织反馈事件。

## 2. 当前已经定义的通用接口

### BaseRL

```python
observe(state, agent)
act(agent, observation)
step(state, action)
run_step(state, agent)
```

用于表达最小的：

```text
State → Observation → Policy → Action → New State
```

### Environment

```python
select_agents(state)
observe(state, agent)
act(agent, observation)
ready_to_step(state, actions)
step(state, resolved_actions)
build_events(old_state, actions, new_state)
```

### ActionManager

```python
resolve_action(response)
available_actions(state, agent)
validate_action(action, state)
resolve_actions(state, actions)
```

### Agent

```python
act(observation)
```

默认通过现有 LLM Runtime 和 Policy 产生响应。

### State

```python
initial(task_id, session_id)
is_terminal
```

State 不再负责执行动作，状态转移由 Environment 负责。

## 3. 剧本杀可以直接复用的抽象

### `select_agents(state)`

可以根据剧本阶段选择行动者：

- 所有玩家同时搜证；
- 指定玩家陈述；
- 主持人推进剧情；
- 所有存活参与者投票；
- 等待 Human Participant 操作。

### `observe(state, agent)`

可以根据 Agent 权限组织：

- 角色剧本；
- 私有身份；
- 个人线索；
- 公共剧情；
- 已公开证据；
- 私聊或秘密关系。

### `available_actions(state, agent)`

可以动态限制：

- 搜证阶段允许 `search`；
- 讨论阶段允许 `speak`、`question`；
- 指认阶段允许 `accuse`；
- 投票阶段允许 `vote`；
- 主持人拥有专用剧情推进动作。

### `resolve_action(response)`与`validate_action()`

可以把 Tool Call 或 raw content 转成搜证、发言、质询、公开线索、指认和投票等结构化动作，并校验阶段、权限、次数和目标。

### `step(state, actions)`

可以处理：

- 搜证次数消耗；
- 线索归属与公开；
- 剧情阶段推进；
- 玩家关系变化；
- 投票与结局生成。

### `build_events()`

可以生成：

- 公共剧情事件；
- 私有搜证结果；
- 指定玩家反馈；
- 动作拒绝原因；
- 投票和最终结局。

因此，剧本杀不需要在 Core 或 Infra 中增加角色、线索、凶手、搜证和剧情阶段等领域概念。

## 4. 接口方向通用，但当前定义仍不合适

### `ready_to_step()`目前被定义为抽象方法

剧本杀确实需要它，例如等待所有玩家完成搜证、等待主持人确认或等待 Human 提交。但简单 App 可能只要收到一个动作就推进。

建议后续在 Environment 提供默认实现：

```python
def ready_to_step(self, state, actions) -> bool:
    return bool(actions)
```

需要等待全部参与者或特殊条件的 App 再覆盖。

### `build_events()`目前被定义为抽象方法

剧本杀和狼人杀需要丰富反馈，但并非所有简单 App 都需要事件系统。

建议后续默认返回空事件：

```python
def build_events(self, old_state, actions, new_state):
    return ()
```

### `resolve_actions()`目前被定义为抽象方法

剧本杀可能需要处理线索争抢、座次顺序、主持人优先和统一投票，但简单 App 可以保持动作原顺序。

建议后续提供默认实现：

```python
def resolve_actions(self, state, actions):
    return actions
```

### `Environment.act()`与`Agent.act()`职责重复

当前两层都存在 `act`。更清晰的关系应是：

```text
Environment.act(agent, observation)
→ agent.act(observation)
→ ActionManager.resolve_action(response)
```

Environment 负责连接，Agent 负责执行 Policy，ActionManager 负责生成结构化动作。

## 5. 当前尚未适配好的通用能力

### 多 Agent 标准主循环

`BaseRL.run_step()`目前只表达一个 Agent 的单步过程，不能完整表达：

```text
select_agents
→ 多个 Agent 分别 observe/act
→ collect actions
→ ready_to_step
→ resolve_actions
→ step
```

狼人杀目前在业务 `run()`中自行编排；剧本杀也会重复编写类似循环。

### 不可变状态转移

标准反馈接口是：

```text
old_state + actions + new_state → events
```

但当前狼人杀会原地修改 State，导致 `old_state`和`new_state`可能引用同一个对象，无法可靠比较状态变化。剧本杀生成线索变化、关系变化和剧情反馈时也会遇到同样问题。

### Action 类型约束

当前部分通用接口使用 `Any`或`object`，原因是 `core.base_action.Action`表示动作映射描述，而 `GameAction`才是运行时结构化动作。Core 尚未明确统一的运行时 Action 类型。

### Participant 抽象

当前 `select_agents()`只能返回 `Agent`。剧本杀很可能需要 AI 玩家、Human 玩家和主持人共同参与。当前还没有统一的 `Participant`接口，也没有标准的 Human Action 等待与恢复机制。

### 中断恢复中的部分动作

剧本杀可能在“六人已有三人完成搜证或投票”时中断。当前 State、ROOM 和 Trace 可以分别持久化，但尚未定义通用的“本阶段已提交动作集合”和恢复后的幂等继续规则。

## 6. 当前结论

现有抽象可以承载剧本杀的基本运行过程，并且不需要向 Core 或 Infra 加入剧本杀领域语义。

当前真正需要后续验证和调整的是：

1. `ready_to_step()`、`build_events()`、`resolve_actions()`改为提供安全默认实现；
2. 消除 Environment 与 Agent 的 `act()`职责重叠；
3. 为 BaseRL 增加多 Agent 标准编排；
4. 保证 `step()`产生可区分的 New State；
5. 用第二个 App 验证运行时 Action、Participant 和部分动作恢复是否确实需要进入 Core。

在第二个 App 验证前，不应把剧本杀角色、剧情节点、线索或主持规则加入 Core/Infra。
