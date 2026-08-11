# App 通用抽象与投资、扑克场景适用性分析

## 1. 文档目的

本文基于当前 `src/coworker/apps/` 下四个真实 App，回答两个问题：

1. 四个 App 已经重复出现、但 Core 和 Infra 尚未完整承接的通用逻辑有哪些；
2. 新增“多 Agent 投资分析团队”和“多 Agent 德州扑克”时，这些候选抽象哪些仍可使用，哪些不能直接使用或需要调整。

本文只讨论第一阶段同步多 Agent App。三国杀响应链、异步代码执行、Human 等待和实时 Tick 不属于本文的当前实现范围。

## 2. 当前四个 App

- `werewolf`：多阶段、公开与私密 ROOM、按角色选择行动者，部分阶段收集多人 Action 后统一结算；
- `script_murder`：按固定顺序发言、公开与私人材料、讨论阶段和最终提交阶段；
- `incident_consultation`：多个专家读取不同证据、并行提交 Finding、最终形成诊断；
- `werewolf_instruction`：多参与者讨论并分别提交内容，全部提交后合并结果。

四个 App 都遵循：

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
```

但循环控制、Session 组装、Action 消费、Event 投递和持久化仍大量留在各自 Environment 中。

## 3. 四个 App 中可抽象的通用逻辑

### 3.1 同步多 Agent 运行循环

四个 `run_session()` 都在重复：

1. 打开或恢复 App Session；
2. 判断 State 是否终止；
3. 根据 State 选择 Agent；
4. 为每个 Agent 生成 Observation；
5. 调用 Agent，解析并收集 Action；
6. 判断 Action 是否足以推进；
7. 结算 Action 并执行 State 转移；
8. 生成事件、持久化 State；
9. 返回最终 AgentResult。

可抽象为第一阶段专用的 `SynchronousAppRunner`。Runner 只控制执行顺序，不包含角色、阶段、投票、证据或卡牌规则。

### 3.2 App Session 创建与恢复

四个 App 都重复维护：

- `session_id`、当前 State；
- Agent、ROOM 和 IncrementalContext 映射；
- StateStore；
- 新建与恢复分支；
- Trace metadata；
- Agent 注册和 ROOM 邀请。

可抽象为 `AppSession` 和 `AppSessionFactory`。App 只提供初始 State、Agent 创建方式和资源拓扑。

### 3.3 Agent 组装描述

领域 Agent 都在组装名称、角色、LLM、模型、Policy、Prompt Builder、Policy Tool、Action Tool、temperature 和可选 Skill。

可先抽象为可序列化的 `AgentDefinition`，再由 AgentFactory 创建现有 Agent。领域 Agent 类暂时保留，避免配置能力尚未被新场景验证时过早删除扩展点。

### 3.4 Observation 投影与 Agent 回合

四个 Observation 都在组合：

- 当前 Agent 可见的 State Message；
- 当前可用 Action/Tool；
- Agent 有权读取的 ROOM；
- task_id 和 session_id。

四个 `act()` 又重复调用 RoomRuntime，传入 ROOM、Task、Session、IncrementalContext、状态消息和可用工具。

可抽象 `AgentTurnRequest` 和通用 Turn Runner。App 的 `observe()` 仍负责领域可见性和状态裁剪。

### 3.5 Action 公共信封与幂等

四个 ActionValue 都重复保存 Action ID、actor、Action 名称、原始 ToolCall、Observation 和领域 payload。四个 State 也都保存 `consumed_action_ids`。

可抽象泛型 `ActionEnvelope[Payload]`。通用层负责 ID、Actor、ToolCall、Observation、Trace 和幂等协议；App 负责 payload、合法性和领域效果。

### 3.6 Action 消费管线

四个 `step()` 都重复：

```text
校验 Action
→ 无效则生成 reject Tool Result
→ 有效则执行 Action Tool 并生成 Tool Result
→ 修改领域 State/ROOM
→ 标记 Action 已消费
→ 保存 State
```

可抽象公共 `ActionConsumer`，统一 ToolCall/ToolResult 配对、Trace 和幂等。领域校验和 State transition 继续由 App 提供。

### 3.7 Event 与投递

四个 App 都需要在 State 改变后通知 Agent，但当前有的返回领域 Event、有的返回 Message、有的直接在 `step()` 中调用 `room.send()`。

可统一为：

- `AppEvent`：不可变领域事实；
- `EventDelivery`：投递目标和可见范围；
- `EventDispatcher`：负责 ROOM 投递、Trace 和恢复幂等。

### 3.8 State 持久化生命周期

四个 App 都使用 StateStore 完成初始保存、每步更新和恢复，但调用时机及 State kind 由各 App 重复维护。

可由 Runner 或 AppSession 统一初始保存、成功 step 后提交、按注册类型恢复，以及失败时不提交新 State。State 的领域字段、`initial()`、`is_terminal()` 和序列化内容仍属于 App。

### 3.9 Action 收集与完成条件

当前已经出现：

- 多 Agent 收集：会诊专家、狼人讨论、教程参与者；
- 单 Agent 顺序行动：剧本杀轮流发言。

可抽象 `ActionCollectionPolicy`：

- `parallel_all`：激活一组 Agent，等待全部完成；
- `ordered`：一次激活一个 Agent；
- 完成条件仍由 App 的 `ready_to_step()` 或独立 CompletionPolicy 判断。

### 3.10 不应抽象进 Core/Infra

以下仍是领域逻辑：

- 具体 Phase 名称和转换顺序；
- 狼人、专家、人物等角色；
- 投票、多数决、报告评分、牌型比较；
- Action 业务参数和合法性；
- 胜负、诊断、真相和最终报告；
- Prompt、私密资料和领域事件正文。

它们必须留在 App 或未来 AppSpec 中。

## 4. 两个新需求的适用性总表

| 四 App 候选抽象 | 投资分析 | 德州扑克 | 结论 |
|---|---|---|---|
| 同步多 Agent Runner | 直接可用 | 直接可用 | 两者都能以一次 State 转移结算当前 Action |
| AppSession / SessionFactory | 调整后可用 | 调整后可用 | Session 不能只管理 ROOM |
| AgentDefinition / AgentFactory | 直接可用 | 调整后可用 | Dealer 应是 Environment，不是 LLM Agent |
| Observation 投影 | 直接可用 | 直接可用 | 都需要公开与私密信息隔离 |
| AgentTurnRequest | 直接可用 | 直接可用 | 投资以并行为主，扑克按顺序行动 |
| ActionEnvelope | 直接可用 | 直接可用 | 仅领域 payload 不同 |
| ActionConsumer | 直接可用 | 直接可用 | 校验和 State 效果仍由 App 提供 |
| AppEvent / EventDelivery | 直接可用 | 直接可用 | 报告提交、下注和发牌都可表达为 Event |
| StateStore 生命周期 | 直接可用 | 调整后可用 | 扑克还需记录确定性随机过程 |
| `parallel_all` | 直接可用 | 不适用 | 扑克不等待所有玩家同时行动 |
| `ordered` | 部分使用 | 直接可用 | 投资的汇总、审查阶段可以顺序执行 |
| ROOM 中心资源模型 | 不够 | 不够 | 投资需要 Artifact，扑克需要 Deck 和 RandomSource |
| 当前 App 专属 Session dataclass | 不直接使用 | 不直接使用 | 应改为通用 Session 加领域资源 |
| 当前 Message/直接 `room.send()` | 不应沿用 | 不应沿用 | 应统一 Event 与 Delivery |
| 现有领域 ActionManager 实现 | 不可用 | 不可用 | 只能复用接口，新 App 必须实现规则 |
| 现有 Phase、角色和终止逻辑 | 不可用 | 不可用 | 属于原 App 领域逻辑 |

## 5. 多 Agent 投资分析团队

### 5.1 仍可使用

- 同步 Runner：分析师并行提交，全部完成后推进；
- `parallel_all` Action 收集；
- AgentDefinition：宏观、行业、公司、估值、风险等角色；
- Observation：为不同分析师提供不同数据和任务；
- ActionEnvelope：提交分析、请求补充、批准或驳回；
- Event：分析提交、证据补充、汇总完成；
- StateStore、Trace、Context 和 Session 恢复。

### 5.2 不可直接使用或需要调整

ROOM 不能作为分析成果的唯一载体。投资分析会产生可引用、可版本化的正式产物：

- 数据集；
- 单项分析报告；
- 估值结果；
- 引用来源；
- 风险意见；
- 最终投资报告。

需要补充通用 `ArtifactStore`、`ArtifactReference` 和 `SourceCitation`。State 保存产物状态和引用，不把大段报告复制进每条 ROOM 消息。

还需要 Barrier/CompletionPolicy：只有规定的分析任务全部完成，才激活汇总或审查 Agent。

## 6. 多 Agent 德州扑克

### 6.1 仍可使用

- 同步 Runner：玩家 Action 依次结算并产生 New State；
- `ordered` 调度：按座位和下注状态选择下一名玩家；
- Observation：公共牌公开，手牌只对本人可见；
- ActionEnvelope：fold、check、call、raise、all-in；
- ActionConsumer：统一验证、Tool Result、幂等和 Trace；
- Event：发牌、下注、弃牌、进入下一街、摊牌；
- StateStore、Session 恢复和终止判断。

### 6.2 不可直接使用或需要调整

发牌不是 Agent Action，不能让 LLM Dealer 决定牌面。需要由 Environment 使用确定性 `RandomSource` 管理：

- 随机 seed；
- 洗牌序列；
- 发牌结果；
- 随机操作序号。

这些信息必须能够持久化和 replay。

Session 还要管理牌堆等非 ROOM 资源，因此通用 Session 应使用 ResourceRegistry，ROOM、Artifact、Deck 和 RandomSource 都是 Resource。

下注轮结束不能使用 `parallel_all`。扑克 App 必须提供自己的 CompletionPolicy，例如所有仍在局玩家下注相等、只剩一名未弃牌玩家或全部已 all-in。牌型、底池、边池和下注合法性仍属于扑克 App。

## 7. 面向两个需求的最小补足能力

1. `SynchronousAppRunner`：统一现有四 App 和两个新 App 的同步主循环；
2. `AppSession + AppSessionFactory`：统一创建、恢复、Agent、Context、State 和资源；
3. `ActionEnvelope + ActionConsumer`：统一动作协议、反馈配对和幂等；
4. `AppEvent + EventDelivery + EventDispatcher`：统一事件事实和可靠投递；
5. `ActionCollectionPolicy`：支持 `parallel_all` 与 `ordered`；
6. `ResourceRegistry`：使 Session 不再只围绕 ROOM；
7. `ArtifactStore`：服务投资报告、数据和引用；
8. `DeterministicRandomSource`：服务洗牌、发牌、恢复和重放。

暂不增加：

- Pending Operation；
- Response Window；
- Operation Stack；
- Human Participant；
- 异步外部任务；
- 实时 Tick；
- 多 Agent 代码 Workspace。

## 8. 验证方式

先以投资分析验证 `parallel_all + Artifact`，再以德州扑克验证 `ordered + private Observation + deterministic random`。

如果德州扑克只新增自己的 `apps/<app_name>`、规则和配置，而不修改通用 Runner、Session、Action、Event 和 Resource 接口，才能说明这批抽象成立。

如果接入时仍必须在通用 Runner 中加入 `poker`、`dealer`、`betting` 或 `deck` 条件分支，说明抽象混入了领域语义，应停止扩张并重新划分边界。
